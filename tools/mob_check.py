"""Checks a converted custom mob against its source glTF by drawing both.

    python tools/mob_check.py <model.gltf> <texture.png> <mob_id> <rig.json> <out-dir>

A: the glTF's own triangles and uvs (bind pose). B: only what the game gets - the item models in
this pack and the rig's "bind" matrices, composed the way the 26.2 client draws an item display
(matrix, 180 degree turn around Y, -0.5 offset, model / 16). Both are rasterized orthographically
from the front, side, top and a diagonal; they must match. Also writes frame strips of every
animation (from B) for a visual check. Exit code 1 on mismatch.
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_mob as cm  # noqa: E402

PACK = Path(__file__).resolve().parent.parent
PX = 34  # pixels per block


def tex_sample(tex, u, v):
    x = min(tex.width - 1, max(0, int(u * tex.width)))
    y = min(tex.height - 1, max(0, int(v * tex.height)))
    return tex.getpixel((x, y))


def view_matrix(name):
    """World (block units, mob facing +Z) -> screen-ish (x right, y down, depth toward viewer)."""
    if name == "front":   # camera on +Z looking at the mob's face
        return lambda p: (p[0], -p[1], p[2])
    if name == "side":    # camera on +X
        return lambda p: (-p[2], -p[1], p[0])
    if name == "top":     # camera above
        return lambda p: (p[0], p[2], p[1])
    yaw, pitch = math.radians(35), math.radians(25)  # diagonal from front-right, a bit above

    def diag(p):
        x = p[0] * math.cos(yaw) + p[2] * math.sin(yaw)
        z = -p[0] * math.sin(yaw) + p[2] * math.cos(yaw)
        y = p[1] * math.cos(pitch) - z * math.sin(pitch)
        d = p[1] * math.sin(pitch) + z * math.cos(pitch)
        return (x, -y, d)
    return diag


def raster(tris, view, size=(420, 330)):
    """tris: [(p0, p1, p2), (uv0, uv1, uv2), texture]. Nearest sampling, alpha cutout like MASK 0.05."""
    img = Image.new("RGBA", size, (30, 30, 36, 255))
    zbuf = [[-1e9] * size[0] for _ in range(size[1])]
    proj = view_matrix(view)
    cx, cy = size[0] / 2, size[1] * 0.86
    for pts, uvs, tex in tris:
        s = [proj(p) for p in pts]
        sx = [cx + q[0] * PX for q in s]
        sy = [cy + q[1] * PX for q in s]
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9:
            continue
        # Flat shading by the face's normal in view space (same light for both renders).
        e1 = [s[1][k] - s[0][k] for k in range(3)]
        e2 = [s[2][k] - s[0][k] for k in range(3)]
        nx, ny, nz = e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0]
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
        shade = 0.55 + 0.45 * abs((-0.3 * nx - 0.6 * ny + 0.74 * nz) / ln)
        x0, x1 = max(0, int(min(sx))), min(size[0] - 1, int(max(sx)) + 1)
        y0, y1 = max(0, int(min(sy))), min(size[1] - 1, int(max(sy)) + 1)
        for py in range(y0, y1 + 1):
            for px in range(x0, x1 + 1):
                fx, fy = px + 0.5, py + 0.5
                w0 = ((sx[1] - fx) * (sy[2] - fy) - (sx[2] - fx) * (sy[1] - fy)) / area
                w1 = ((sx[2] - fx) * (sy[0] - fy) - (sx[0] - fx) * (sy[2] - fy)) / area
                w2 = 1 - w0 - w1
                if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                    continue
                d = w0 * s[0][2] + w1 * s[1][2] + w2 * s[2][2]
                if d <= zbuf[py][px]:
                    continue
                u = w0 * uvs[0][0] + w1 * uvs[1][0] + w2 * uvs[2][0]
                v = w0 * uvs[0][1] + w1 * uvs[1][1] + w2 * uvs[2][1]
                c = tex_sample(tex, u, v)
                if c[3] < 13:
                    continue
                zbuf[py][px] = d
                img.putpixel((px, py), (int(c[0] * shade), int(c[1] * shade), int(c[2] * shade), 255))
    return img


def source_tris(gl, tex, flip):
    tris = []
    hitbox = {i for i, n in enumerate(gl.g["nodes"]) if n.get("name") == "hitbox"}
    for i, n in enumerate(gl.g["nodes"]):
        if "mesh" not in n or hitbox & set(gl.ancestors(i)):
            continue
        m = cm.mat_mul(flip, gl.world(i))
        for prim in gl.g["meshes"][n["mesh"]]["primitives"]:
            pos = [cm.apply(m, p) for p in gl.accessor(prim["attributes"]["POSITION"])]
            uv = gl.accessor(prim["attributes"]["TEXCOORD_0"])
            idx = [x[0] for x in gl.accessor(prim["indices"])] if "indices" in prim else list(range(len(pos)))
            for k in range(0, len(idx), 3):
                a, b, c = idx[k:k + 3]
                tris.append(((pos[a], pos[b], pos[c]), (uv[a], uv[b], uv[c]), tex))
    return tris


def game_tris(rig, frame, mob_id, tex):
    """What the client draws for one animation frame, from the pack's models and the rig only."""
    flip = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
    tris = []
    for part, flat in zip(rig["parts"], frame):
        model = json.loads((PACK / "assets/icarus/models/mob" / mob_id / f"{part['name']}.json").read_text())
        M = [[flat[c * 4 + r] for c in range(4)] for r in range(4)]  # column-major -> rows
        full = cm.mat_mul(M, flip)  # the client's own 180 degree turn
        for el in model["elements"]:
            lo = [v / 16 - 0.5 for v in el["from"]]
            hi = [v / 16 - 0.5 for v in el["to"]]
            for face, f in el["faces"].items():
                corners = [cm.apply(full, c) for c in cm.face_corners(face, lo, hi)]
                x1, y1, x2, y2 = [v / 16 for v in f["uv"]]
                cuv = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
                rot = f.get("rotation", 0) // 90
                cuv = [cuv[(j + rot) % 4] for j in range(4)]
                tris.append(((corners[0], corners[1], corners[2]), (cuv[0], cuv[1], cuv[2]), tex))
                tris.append(((corners[0], corners[2], corners[3]), (cuv[0], cuv[2], cuv[3]), tex))
    return tris


def main():
    gltf, texture, mob_id, rig_path, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]), Path(sys.argv[5])
    out.mkdir(parents=True, exist_ok=True)
    gl = cm.Gltf(gltf)
    tex = Image.open(texture).convert("RGBA")
    pack_tex = Image.open(PACK / "assets/icarus/textures/item/mob" / f"{mob_id}.png").convert("RGBA")
    rig = json.loads(rig_path.read_text())
    flip = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]
    a_tris = source_tris(gl, tex, flip)
    b_tris = game_tris(rig, rig["animations"]["bind"]["frames"][0], mob_id, pack_tex)
    worst = 0.0
    sheet = []
    for view in ("front", "side", "top", "diagonal"):
        a, b = raster(a_tris, view), raster(b_tris, view)
        diff = sum(1 for pa, pb in zip(a.getdata(), b.getdata()) if sum(abs(x - y) for x, y in zip(pa, pb)) > 30)
        frac = diff / (a.width * a.height)
        worst = max(worst, frac)
        print(f"{view:<9} source vs game: {frac:.2%} of pixels differ")
        pair = Image.new("RGBA", (a.width * 2 + 8, a.height), (0, 0, 0, 255))
        pair.paste(a, (0, 0))
        pair.paste(b, (a.width + 8, 0))
        sheet.append(pair)
    full = Image.new("RGBA", (sheet[0].width, sum(s.height for s in sheet)))
    y = 0
    for s in sheet:
        full.paste(s, (0, y))
        y += s.height
    full.save(out / f"{mob_id}_source_vs_game.png")
    for name, anim in rig["animations"].items():
        frames = anim["frames"][::max(1, len(anim["frames"]) // 8)][:8]
        strip = Image.new("RGBA", (420 * len(frames), 330))
        for k, fr in enumerate(frames):
            strip.paste(raster(game_tris(rig, fr, mob_id, pack_tex), "diagonal"), (420 * k, 0))
        strip.save(out / f"{mob_id}_anim_{name}.png")
    ok = worst < 0.01
    print("PASS" if ok else "FAIL", f"(worst view differs on {worst:.2%} of pixels, limit 1%)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
