"""Turns a Blockbench glTF export back into a Blockbench project (.bbmodel) for BetterModel.

    python tools/gltf_to_bbmodel.py <model.gltf> <texture.png> <name> <out.bbmodel>

BetterModel reads .bbmodel files, but models bought/downloaded are often only shipped as glTF.
A Blockbench glTF export keeps everything a project needs: one node per group (its pivot is the
sum of the translations up the tree), one mesh per cube (axis-aligned - checked), and the
animations as dense linear keyframes. This rebuilds the "free" format project from that:

- groups keep their names (duplicates get _2, _3...), pivots in pixels, no rest rotation;
- cubes get from/to in pixels and the face uvs read off the mesh (in texture pixels);
- each animation channel becomes Blockbench keyframes. Blockbench shows a bone rotation keyframe
  (x, y, z) as three.js euler (-x, -y, z) in ZYX order and a position keyframe as (-x, y, z)
  pixels on top of the rest pose, so the glTF values are converted back through that;
- "attack" plays once, everything else loops; a "walk" is added when the model has none (legs
  swinging opposite each other, arms countering, a light body bob), since BetterModel plays
  "idle" and "walk" on its own;
- the "hitbox" group is left out - the plugin sizes the base mob to the model itself.
"""
import base64
import importlib.util
import json
import math
import sys
import uuid
from pathlib import Path

_spec = importlib.util.spec_from_file_location("convert_mob", Path(__file__).with_name("convert_mob.py"))
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

NS = uuid.UUID("6b7f6f7e-2f3c-4f59-9a51-1c6c0d1e2a33")


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def euler_zyx(q):
    """three.js Euler.setFromQuaternion(q, 'ZYX') in degrees (x, y, z)."""
    m = cm.quat(q)
    m31 = max(-1.0, min(1.0, m[2][0]))
    y = math.asin(-m31)
    if abs(m31) < 0.9999999:
        x = math.atan2(m[2][1], m[2][2])
        z = math.atan2(m[1][0], m[0][0])
    else:
        x = 0.0
        z = math.atan2(-m[0][1], m[1][1])
    return [math.degrees(x), math.degrees(y), math.degrees(z)]


def unwrap(prev, cur):
    """Keeps consecutive euler angles from jumping by 360."""
    if prev is None:
        return cur
    return [c + 360 * round((p - c) / 360) for p, c in zip(prev, cur)]


def fmt(v):
    v = round(v, 4)
    return "0" if v == 0 else repr(v)


def main():
    gltf_path, texture, name, out = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
    gl = cm.Gltf(gltf_path)
    nodes = gl.g["nodes"]
    from PIL import Image
    tw, th = Image.open(texture).size

    hitbox = {i for i, n in enumerate(nodes) if n.get("name") == "hitbox"}
    skip = set(hitbox)
    for i in range(len(nodes)):
        if hitbox & set(gl.ancestors(i)):
            skip.add(i)
    is_group = {i for i, n in enumerate(nodes) if "mesh" not in n and i not in skip}

    names, used = {}, {}
    for i in sorted(is_group):
        base = "".join(c if c.isalnum() or c == "_" else "_" for c in nodes[i].get("name", f"group{i}").lower())
        used[base] = used.get(base, 0) + 1
        names[i] = base if used[base] == 1 else f"{base}_{used[base]}"

    def pivot(i):
        w = gl.world(i)
        return [w[0][3] * 16, w[1][3] * 16, w[2][3] * 16]

    elements = []

    def cubes(group):
        out_ids = []
        for c in nodes[group].get("children", []):
            if c in skip or "mesh" not in nodes[c]:
                continue
            ident = cm.translate(0, 0, 0)
            for k, (lo, hi, faces) in enumerate(cm.cubes_of(gl, c, ident)):
                eid = uid(name, "cube", c, k)
                bb_faces = {}
                for face in ("north", "east", "south", "west", "up", "down"):
                    f = faces.get(face)
                    if f is None:
                        bb_faces[face] = {"uv": [0, 0, 0, 0], "texture": None}
                        continue
                    u1, v1, u2, v2 = f["uv"]
                    entry = {"uv": [round(u1 * tw / 16, 4), round(v1 * th / 16, 4), round(u2 * tw / 16, 4), round(v2 * th / 16, 4)], "texture": 0}
                    if f.get("rotation"):
                        entry["rotation"] = f["rotation"]
                    bb_faces[face] = entry
                elements.append({
                    "name": "cube", "type": "cube", "uuid": eid, "box_uv": False, "rescale": False, "locked": False,
                    "light_emission": 0, "render_order": "default", "allow_mirror_modeling": True, "autouv": 0, "color": 0,
                    "from": [round(v * 16, 4) for v in lo], "to": [round(v * 16, 4) for v in hi],
                    "origin": [round(v, 4) for v in pivot(group)], "faces": bb_faces,
                })
                out_ids.append(eid)
        return out_ids

    def outline(i):
        children = cubes(i)
        for c in nodes[i].get("children", []):
            if c in is_group:
                children.append(outline(c))
        return {"name": names[i], "origin": [round(v, 4) for v in pivot(i)], "rotation": [0, 0, 0], "color": 0,
                "uuid": uid(name, "group", i), "export": True, "mirror_uv": False, "isOpen": False, "locked": False,
                "visibility": True, "autouv": 0, "children": children}

    roots = [i for i in sorted(is_group) if gl.parent.get(i) is None]
    outliner = [outline(i) for i in roots]

    animations = []
    for anim in gl.g.get("animations", []):
        length = cm.anim_length(gl, anim)
        animators = {}
        for ch in anim["channels"]:
            node = ch["target"]["node"]
            path = ch["target"]["path"]
            if node not in is_group or path not in ("rotation", "translation"):
                continue
            s = anim["samplers"][ch["sampler"]]
            times = [x[0] for x in gl.accessor(s["input"])]
            vals = gl.accessor(s["output"])
            rest = nodes[node].get("translation", [0, 0, 0])
            a = animators.setdefault(uid(name, "group", node), {"name": names[node], "type": "bone", "keyframes": []})
            prev = None
            for k, (t, v) in enumerate(zip(times, vals)):
                if path == "rotation":
                    e = unwrap(prev, euler_zyx(v))
                    prev = e
                    point = [-e[0], -e[1], e[2]]
                    channel = "rotation"
                else:
                    d = [(v[j] - rest[j]) * 16 for j in range(3)]
                    point = [-d[0], d[1], d[2]]
                    channel = "position"
                a["keyframes"].append({"channel": channel, "data_points": [{"x": fmt(point[0]), "y": fmt(point[1]), "z": fmt(point[2])}],
                                       "uuid": uid(name, anim["name"], node, channel, k), "time": round(t, 4), "color": -1, "interpolation": "linear"})
        animations.append({"uuid": uid(name, "anim", anim["name"]), "name": anim["name"], "loop": "once" if anim["name"] == "attack" else "loop",
                           "override": False, "length": round(length, 4), "snapping": 24, "selected": False, "anim_time_update": "",
                           "blend_weight": "", "start_delay": "", "loop_delay": "", "animators": animators})

    if not any(a["name"] == "walk" for a in animations):
        by_name = {nodes[i].get("name"): i for i in sorted(is_group, reverse=True)}
        period = 1.5
        animators = {}

        def swing(bone, amp):
            i = by_name.get(bone)
            if i is None:
                return
            kf = []
            for k in range(5):
                t = period * k / 4
                deg = amp * math.sin(2 * math.pi * t / period)
                kf.append({"channel": "rotation", "data_points": [{"x": fmt(-deg), "y": "0", "z": "0"}], "uuid": uid(name, "walk", bone, k),
                           "time": round(t, 4), "color": -1, "interpolation": "catmullrom"})
            animators[uid(name, "group", i)] = {"name": names[i], "type": "bone", "keyframes": kf}

        swing("leg1", 22)
        swing("leg2", -22)
        swing("arm1", -10)
        swing("arm2", 10)
        body = by_name.get("body")
        if body is not None:
            kf = []
            for k in range(9):
                t = period * k / 8
                kf.append({"channel": "position", "data_points": [{"x": "0", "y": fmt(0.96 * abs(math.sin(2 * math.pi * t / period))), "z": "0"}],
                           "uuid": uid(name, "walk", "body", k), "time": round(t, 4), "color": -1, "interpolation": "catmullrom"})
            animators[uid(name, "group", body)] = {"name": names[body], "type": "bone", "keyframes": kf}
        animations.append({"uuid": uid(name, "anim", "walk"), "name": "walk", "loop": "loop", "override": False, "length": period,
                           "snapping": 24, "selected": False, "anim_time_update": "", "blend_weight": "", "start_delay": "",
                           "loop_delay": "", "animators": animators})

    png = base64.b64encode(texture.read_bytes()).decode()
    project = {
        "meta": {"format_version": "4.10", "model_format": "free", "box_uv": False},
        "name": name, "model_identifier": "", "visible_box": [1, 1, 0],
        "variable_placeholders": "", "variable_placeholder_buttons": [], "timeline_setups": [], "unhandled_root_fields": {},
        "resolution": {"width": tw, "height": th},
        "elements": elements, "outliner": outliner,
        "textures": [{"path": "", "name": f"{name}.png", "folder": "", "namespace": "", "id": "0", "group": "", "width": tw, "height": th,
                      "uv_width": tw, "uv_height": th, "particle": False, "use_as_default": False, "layers_enabled": False,
                      "sync_to_project": "", "render_mode": "default", "render_sides": "auto", "pbr_channel": "color",
                      "frame_time": 1, "frame_order_type": "loop", "frame_order": "", "frame_interpolate": False, "visible": True,
                      "internal": True, "saved": False, "uuid": uid(name, "texture"), "source": "data:image/png;base64," + png}],
        "animations": animations,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(project, indent=1), encoding="utf-8")
    print(f"{len(elements)} cubes in {len(names)} groups, animations: " + ", ".join(f"{a['name']} ({a['length']}s, {a['loop']})" for a in animations))


if __name__ == "__main__":
    main()
