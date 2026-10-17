"""Turns a Blockbench glTF export into an IcarusRPG custom mob: item models + a pre-baked rig.

    python tools/convert_mob.py <model.gltf> <texture.png> <mob_id> <rig_out.json>

Writes, inside this pack:
  assets/icarus/textures/item/mob/<mob_id>.png                 the model's texture
  assets/icarus/models/mob/<mob_id>/<part>.json                one item model per bone
  assets/icarus/items/mob/<mob_id>/<part>.json                 its item definition
and <rig_out.json> for the plugin (IcarusRPG's src/main/resources/mobs/): every part's item model
plus, for each animation, one 4x4 matrix per part per game tick (20/s). The plugin only has to
put those matrices on one ItemDisplay per part - all the bone hierarchy math happens here.

Geometry: every Blockbench cube is an axis-aligned box (checked), so it maps 1:1 to a Minecraft
model element. A part's cubes are placed with the bone's pivot at the model's (8, 8, 8) and,
when the bone reaches further than 1.5 blocks from it (Minecraft caps elements to -16..32),
shrunk by a factor the part's matrix scales back up.

Orientation: Blockbench models face north (-Z); Minecraft mobs face +Z at yaw 0, so every
matrix includes a 180 degree turn around Y. Units are blocks, origin at the mob's feet.

Animations: the glTF's own (sampled at 20 fps, linear) plus a generated "walk" - legs swinging
opposite each other, arms countering, a slight body bob - since the model ships without one.
"""
import base64
import json
import math
import shutil
import struct
import sys
from pathlib import Path

PACK = Path(__file__).resolve().parent.parent
FIT = 1.5  # max distance (blocks) from the pivot a part may reach before it's shrunk


# ---- small matrix helpers (4x4, row-major lists) ----

def mat_mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def translate(x, y, z):
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z], [0, 0, 0, 1]]


def scale(s):
    return [[s, 0, 0, 0], [0, s, 0, 0], [0, 0, s, 0], [0, 0, 0, 1]]


def quat(q):
    x, y, z, w = q
    return [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1]]


def axis_angle(axis, deg):
    h = math.radians(deg) / 2
    s = math.sin(h)
    return (axis[0] * s, axis[1] * s, axis[2] * s, math.cos(h))


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz)


def slerp(a, b, t):
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0:
        b, dot = tuple(-x for x in b), -dot
    if dot > 0.9995:
        r = tuple(x + (y - x) * t for x, y in zip(a, b))
    else:
        th = math.acos(dot)
        sa, sb = math.sin((1 - t) * th) / math.sin(th), math.sin(t * th) / math.sin(th)
        r = tuple(sa * x + sb * y for x, y in zip(a, b))
    n = math.sqrt(sum(x * x for x in r))
    return tuple(x / n for x in r)


def apply(m, p):
    return [sum(m[i][k] * (p[k] if k < 3 else 1) for k in range(4)) for i in range(3)]


def column_major(m):
    return [round(m[r][c], 5) for c in range(4) for r in range(4)]


# ---- glTF reading ----

class Gltf:
    def __init__(self, path: Path):
        self.g = json.loads(path.read_text(encoding="utf-8"))
        uri = self.g["buffers"][0]["uri"]
        self.buf = base64.b64decode(uri.split(",", 1)[1]) if uri.startswith("data:") else (path.parent / uri).read_bytes()
        self.parent = {}
        for i, n in enumerate(self.g["nodes"]):
            for c in n.get("children", []):
                self.parent[c] = i

    def accessor(self, i):
        a = self.g["accessors"][i]
        bv = self.g["bufferViews"][a["bufferView"]]
        n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
        fmt = {5126: "f", 5123: "H", 5125: "I", 5121: "B"}[a["componentType"]]
        size = struct.calcsize(fmt)
        off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", n * size)
        return [struct.unpack_from("<" + fmt * n, self.buf, off + k * stride) for k in range(a["count"])]

    def node(self, i):
        return self.g["nodes"][i]

    def local(self, i, override=None):
        n = self.node(i)
        o = (override or {}).get(i, {})
        t = o.get("translation", n.get("translation", [0, 0, 0]))
        r = o.get("rotation", n.get("rotation", [0, 0, 0, 1]))
        s = n.get("scale", [1, 1, 1])
        return mat_mul(mat_mul(translate(*t), quat(r)), [[s[0], 0, 0, 0], [0, s[1], 0, 0], [0, 0, s[2], 0], [0, 0, 0, 1]])

    def world(self, i, override=None):
        m = self.local(i, override)
        p = self.parent.get(i)
        while p is not None:
            m = mat_mul(self.local(p, override), m)
            p = self.parent.get(p)
        return m

    def ancestors(self, i):
        out = []
        p = self.parent.get(i)
        while p is not None:
            out.append(p)
            p = self.parent.get(p)
        return out


# ---- geometry ----

FACE_BY_NORMAL = {(1, 0, 0): "east", (-1, 0, 0): "west", (0, 1, 0): "up", (0, -1, 0): "down", (0, 0, 1): "south", (0, 0, -1): "north"}


def face_corners(face, lo, hi):
    """The face's corners as Minecraft maps a face's uv onto them: top-left, top-right, bottom-right, bottom-left (seen from outside)."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    return {
        "north": [(x1, y1, z0), (x0, y1, z0), (x0, y0, z0), (x1, y0, z0)],
        "south": [(x0, y1, z1), (x1, y1, z1), (x1, y0, z1), (x0, y0, z1)],
        "east": [(x1, y1, z1), (x1, y1, z0), (x1, y0, z0), (x1, y0, z1)],
        "west": [(x0, y1, z0), (x0, y1, z1), (x0, y0, z1), (x0, y0, z0)],
        "up": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
        "down": [(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)],
    }[face]


def uv_for(corner_uvs):
    """Minecraft uv [x1, y1, x2, y2] + rotation reproducing the given per-corner uvs (TL, TR, BR, BL)."""
    for k in range(4):
        c = [corner_uvs[(j + k) % 4] for j in range(4)]  # texture corners C0..C3 seen at face corners rotated by k
        if (abs(c[0][1] - c[1][1]) < 1e-4 and abs(c[1][0] - c[2][0]) < 1e-4
                and abs(c[2][1] - c[3][1]) < 1e-4 and abs(c[3][0] - c[0][0]) < 1e-4):
            return [c[0][0], c[0][1], c[2][0], c[2][1]], (k * 90) % 360
    raise ValueError(f"uvs {corner_uvs} aren't a rectangle")


def cubes_of(gl: Gltf, mesh_node: int, group_inv):
    """The axis-aligned boxes of a mesh node, in its group's frame, with Minecraft faces/uvs."""
    m = mat_mul(group_inv, gl.world(mesh_node))
    out = []
    for prim in gl.g["meshes"][gl.node(mesh_node)["mesh"]]["primitives"]:
        pos = [apply(m, p) for p in gl.accessor(prim["attributes"]["POSITION"])]
        nrm = gl.accessor(prim["attributes"]["NORMAL"])
        uvs = gl.accessor(prim["attributes"]["TEXCOORD_0"])
        lo = [round(min(p[k] for p in pos), 5) for k in range(3)]
        hi = [round(max(p[k] for p in pos), 5) for k in range(3)]
        for k in range(3):
            if len({round(p[k], 4) for p in pos}) > 2:
                raise ValueError(f"mesh {mesh_node} isn't an axis-aligned box")
        faces = {}
        for i in range(len(pos)):
            n = tuple(int(round(v)) for v in nrm[i])
            faces.setdefault(FACE_BY_NORMAL[n], []).append((tuple(round(v, 4) for v in pos[i]), uvs[i]))
        elem_faces = {}
        for face, verts in faces.items():
            lookup = {v: uv for v, uv in verts}
            corners = face_corners(face, lo, hi)
            corner_uvs = []
            for c in corners:
                key = tuple(round(v, 4) for v in c)
                best = min(lookup, key=lambda v: sum((a - b) ** 2 for a, b in zip(v, key)))
                u, v = lookup[best]
                corner_uvs.append((u * 16, v * 16))
            uv, rot = uv_for(corner_uvs)
            elem_faces[face] = {"uv": [round(x, 4) for x in uv], "texture": "#0", **({"rotation": rot} if rot else {})}
        out.append((lo, hi, elem_faces))
    return out


def invert_rigid(m):
    """Inverse of a rotation+translation matrix."""
    r = [[m[j][i] for j in range(3)] for i in range(3)]
    t = [-sum(r[i][k] * m[k][3] for k in range(3)) for i in range(3)]
    return [r[0] + [t[0]], r[1] + [t[1]], r[2] + [t[2]], [0, 0, 0, 1]]


# ---- animations ----

def sample(gl: Gltf, anim, t):
    """Node -> {translation/rotation} at time t (seconds), linear like the source."""
    out = {}
    for ch in anim["channels"]:
        s = anim["samplers"][ch["sampler"]]
        times = [x[0] for x in gl.accessor(s["input"])]
        vals = gl.accessor(s["output"])
        path = ch["target"]["path"]
        if path not in ("translation", "rotation"):
            continue
        if t <= times[0]:
            v = vals[0]
        elif t >= times[-1]:
            v = vals[-1]
        else:
            k = next(i for i in range(len(times) - 1) if times[i] <= t <= times[i + 1])
            f = (t - times[k]) / (times[k + 1] - times[k])
            a, b = vals[k], vals[k + 1]
            v = slerp(a, b, f) if path == "rotation" else tuple(x + (y - x) * f for x, y in zip(a, b))
        out.setdefault(ch["target"]["node"], {})[path] = list(v)
    return out


def anim_length(gl: Gltf, anim):
    return max(gl.accessor(anim["samplers"][c["sampler"]]["input"])[-1][0] for c in anim["channels"])


def walk_override(gl: Gltf, t, period=1.5):
    """Generated walk: legs swing +-22 degrees around X opposite each other, arms counter at +-10, body bobs."""
    phase = math.sin(2 * math.pi * t / period)
    by_name = {}
    for i, n in enumerate(gl.g["nodes"]):
        by_name.setdefault(n.get("name"), i)
    out = {}

    def rot(name, deg):
        i = by_name.get(name)
        if i is not None:
            base = tuple(gl.node(i).get("rotation", [0, 0, 0, 1]))
            out.setdefault(i, {})["rotation"] = list(quat_mul(base, axis_angle((1, 0, 0), deg)))

    rot("leg1", 22 * phase)
    rot("leg2", -22 * phase)
    rot("arm1", -10 * phase)
    rot("arm2", 10 * phase)
    body = by_name.get("body")
    if body is not None:
        t0 = gl.node(body).get("translation", [0, 0, 0])
        out.setdefault(body, {})["translation"] = [t0[0], t0[1] + 0.06 * abs(phase), t0[2]]
    return out


def main():
    gltf_path, texture, mob_id, rig_out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    gl = Gltf(gltf_path)
    nodes = gl.g["nodes"]
    hitbox = {i for i, n in enumerate(nodes) if n.get("name") == "hitbox"}
    groups = {}
    for i, n in enumerate(nodes):
        if "mesh" in n:
            g = gl.parent[i]
            if g in hitbox or hitbox & set(gl.ancestors(i)):
                continue
            groups.setdefault(g, []).append(i)
    flip = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]  # 180 degrees around Y

    models_dir = PACK / "assets/icarus/models/mob" / mob_id
    items_dir = PACK / "assets/icarus/items/mob" / mob_id
    for d in (models_dir, items_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
    tex_dir = PACK / "assets/icarus/textures/item/mob"
    tex_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(texture, tex_dir / f"{mob_id}.png")

    parts = []
    used = set()
    for g, mesh_nodes in groups.items():
        name = "".join(c if c.isalnum() else "_" for c in nodes[g].get("name", f"part{g}").lower())
        while name in used:
            name += "_"
        used.add(name)
        inv = invert_rigid(gl.world(g))
        cubes = [c for m in mesh_nodes for c in cubes_of(gl, m, inv)]
        # Centered on the part's own cubes (not the bone pivot, which can sit far away) - the
        # part's matrix moves it back by `center`.
        center = [(min(lo[k] for lo, _, _ in cubes) + max(hi[k] for _, hi, _ in cubes)) / 2 for k in range(3)]
        reach = max(abs(v - center[k % 3]) for lo, hi, _ in cubes for k, v in enumerate(lo + hi))
        s = min(1.0, FIT / reach) if reach > 0 else 1.0
        elements = []
        for lo, hi, faces in cubes:
            frm = [round((v - center[k]) * 16 * s + 8, 4) for k, v in enumerate(lo)]
            to = [round((v - center[k]) * 16 * s + 8, 4) for k, v in enumerate(hi)]
            for v in frm + to:
                assert -16 <= v <= 32, f"{name}: element out of range ({v})"
            elements.append({"from": frm, "to": to, "faces": faces})
        model = {"texture_size": [16, 16], "textures": {"0": f"icarus:item/mob/{mob_id}", "particle": f"icarus:item/mob/{mob_id}"}, "elements": elements}
        (models_dir / f"{name}.json").write_text(json.dumps(model, separators=(",", ":")), encoding="utf-8")
        (items_dir / f"{name}.json").write_text(json.dumps({"model": {"type": "minecraft:model", "model": f"icarus:mob/{mob_id}/{name}"}}), encoding="utf-8")
        parts.append({"name": name, "node": g, "scale": s, "center": center, "model": f"icarus:mob/{mob_id}/{name}", "cubes": len(cubes)})

    # What the client does to an item display's model (DisplayRenderer.ItemDisplayRenderer and
    # ItemTransform.apply, read from the 26.2 client): our matrix, then a 180 degree turn around Y,
    # then -0.5 on every axis, then the model in 1/16 units. The trailing `flip` cancels that turn.
    def frame(override):
        return [column_major(mat_mul(mat_mul(mat_mul(mat_mul(flip, gl.world(p["node"], override)), translate(*p["center"])), scale(1 / p["scale"])), flip)) for p in parts]

    animations = {}
    for anim in gl.g.get("animations", []):
        length = anim_length(gl, anim)
        ticks = max(1, round(length * 20))
        animations[anim["name"]] = {"loop": anim["name"] != "attack", "frames": [frame(sample(gl, anim, k / 20)) for k in range(ticks)]}
    animations["walk"] = {"loop": True, "frames": [frame(walk_override(gl, k / 20)) for k in range(30)]}
    animations["bind"] = {"loop": True, "frames": [frame({})]}

    lo = [1e9] * 3
    hi = [-1e9] * 3
    for i in hitbox:
        for c in nodes[i].get("children", []):
            if "mesh" in nodes[c]:
                for prim in gl.g["meshes"][nodes[c]["mesh"]]["primitives"]:
                    for p in gl.accessor(prim["attributes"]["POSITION"]):
                        wp = apply(gl.world(c), p)
                        for k in range(3):
                            lo[k], hi[k] = min(lo[k], wp[k]), max(hi[k], wp[k])
    rig = {"id": mob_id, "hitbox": {"width": round(max(hi[0] - lo[0], hi[2] - lo[2]), 3), "height": round(hi[1], 3)},
           "parts": [{"name": p["name"], "model": p["model"]} for p in parts], "animations": animations}
    rig_out.parent.mkdir(parents=True, exist_ok=True)
    rig_out.write_text(json.dumps(rig, separators=(",", ":")), encoding="utf-8")
    for p in parts:
        print(f"  {p['name']:<14} {p['cubes']:>2} cubes, scale {p['scale']:.3f}")
    print(f"{len(parts)} parts, animations: " + ", ".join(f"{k} ({len(v['frames'])} ticks{', loop' if v['loop'] else ''})" for k, v in animations.items()))
    print(f"hitbox {rig['hitbox']}")


if __name__ == "__main__":
    main()
