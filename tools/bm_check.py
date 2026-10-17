"""Checks a BetterModel mob in game against its source glTF, from what the server really sends.

    python tools/bm_check.py <model.gltf> <texture.png> <bettermodel build dir> <capture.jsonl> <out-dir>

<capture.jsonl> comes from a test server (IcarusRPG's BetterModel test plugin): one line per
snapshot with every display entity BetterModel sent a player - item model, display
transformation (translation, left rotation, scale, right rotation). This rebuilds what the
26.2 client draws from those and the generated pack (models + texture in <build dir>, same math
as mob_check.py: transformation, 180 degree turn, -0.5, model / 16), then finds the source pose
it matches: the glTF animation named by the snapshot label (idle_*, attack_*, walk_* - walk is
convert_mob.py's generated one) at the best time, the mob's facing and position fitted.

Per snapshot: mean distance between the two vertex clouds (blocks) and the share of differing
pixels from a diagonal view; both side by side in <out-dir>. Exit code 1 if any snapshot is off.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import convert_mob as cm  # noqa: E402
import mob_check as mc  # noqa: E402

FLIP = [[-1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0], [0, 0, 0, 1]]


def quat_m(q):
    return cm.quat(q)


def display_tris(build, disp, tex, cache):
    """The client's triangles for one item display (its transformation + the pack's model)."""
    ns, path = disp["model"].split(":", 1)
    if path not in cache:
        item = json.loads((build / "assets" / ns / "items" / f"{path}.json").read_text())
        mns, mpath = item["model"]["model"].split(":", 1)
        cache[path] = json.loads((build / "assets" / mns / "models" / f"{mpath}.json").read_text())
    model = cache[path]
    t, s = disp["t"], disp["s"]
    m = cm.mat_mul(cm.mat_mul(cm.mat_mul(cm.translate(*t), quat_m(disp["l"])), [[s[0], 0, 0, 0], [0, s[1], 0, 0], [0, 0, s[2], 0], [0, 0, 0, 1]]), quat_m(disp["r"]))
    # The display entity's own facing (DisplayRenderer: rotationYXZ(-yaw, pitch, 0)) goes first.
    yaw = math.radians(disp.get("yaw", 0))
    c, sn = math.cos(-yaw), math.sin(-yaw)
    full = cm.mat_mul(cm.mat_mul([[c, 0, sn, 0], [0, 1, 0, 0], [-sn, 0, c, 0], [0, 0, 0, 1]], m), FLIP)
    tris = []
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


def source_tris(gl, tex, override):
    tris = []
    hitbox = {i for i, n in enumerate(gl.g["nodes"]) if n.get("name") == "hitbox"}
    for i, n in enumerate(gl.g["nodes"]):
        if "mesh" not in n or i in hitbox or hitbox & set(gl.ancestors(i)):
            continue
        m = cm.mat_mul(FLIP, gl.world(i, override))
        for prim in gl.g["meshes"][n["mesh"]]["primitives"]:
            pos = [cm.apply(m, p) for p in gl.accessor(prim["attributes"]["POSITION"])]
            uv = gl.accessor(prim["attributes"]["TEXCOORD_0"])
            idx = [x[0] for x in gl.accessor(prim["indices"])] if "indices" in prim else list(range(len(pos)))
            for k in range(0, len(idx), 3):
                a, b, c = idx[k:k + 3]
                tris.append(((pos[a], pos[b], pos[c]), (uv[a], uv[b], uv[c]), tex))
    return tris


def verts(tris):
    return np.unique(np.round(np.array([p for t in tris for p in t[0]]), 4), axis=0)


def rot_y(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def fit(src, bm, yaws):
    """Best yaw + translation putting bm onto src; returns (error, yaw, offset)."""
    best = (1e9, 0, np.zeros(3))
    for yaw in yaws:
        r = bm @ rot_y(yaw).T
        off = src.mean(0) - r.mean(0)
        for _ in range(4 if len(yaws) < 20 else 2):
            moved = r + off
            d = ((moved[:, None, :] - src[None, :, :]) ** 2).sum(-1)
            off = off + (src[d.argmin(1)] - moved).mean(0)
        moved = r + off
        d = np.sqrt(((moved[:, None, :] - src[None, :, :]) ** 2).sum(-1))
        err = (d.min(1).mean() + d.min(0).mean()) / 2
        if err < best[0]:
            best = (err, yaw, off)
    return best


def move(tris, yaw, off):
    r = rot_y(yaw)
    return [(tuple(tuple(r @ np.array(p) + off) for p in pts), uvs, tex) for pts, uvs, tex in tris]


def main():
    gltf, texture, build, capture, out = (Path(a) for a in sys.argv[1:6])
    out.mkdir(parents=True, exist_ok=True)
    gl = cm.Gltf(gltf)
    tex = Image.open(texture).convert("RGBA")
    pack_tex = None
    cache = {}
    anims = {a["name"]: a for a in gl.g.get("animations", [])}
    worst_err, worst_px, bad = 0.0, 0.0, []
    for line in capture.read_text().splitlines():
        snap = json.loads(line)
        parts = [d for d in snap["displays"] if "redstone_monstrosity" in d["model"]]
        if not parts:
            bad.append(snap["label"] + " (no displays)")
            continue
        if pack_tex is None:
            tex_file = next((build / "assets/bettermodel/textures/item").glob("*redstone_monstrosity*.png"))
            pack_tex = Image.open(tex_file).convert("RGBA")
        bm_tris = [t for d in parts for t in display_tris(build, d, pack_tex, cache)]
        bm_v = verts(bm_tris)
        kind = snap["label"].split("_")[0]
        if kind == "walk":
            length, pose = 1.5, (lambda t: cm.walk_override(gl, t))
        else:
            anim = anims[kind]
            length, pose = cm.anim_length(gl, anim), (lambda t, a=anim: cm.sample(gl, a, t))
        by = snap["mob"]["bodyYaw"]
        # A turning mob's model lags its body yaw (BetterModel lerps it), so search the facing freely.
        yaws = list(range(0, 360, 4))
        best = None
        for step in range(int(length * 20) + 1):
            t = step / 20
            src_v = verts(source_tris(gl, tex, pose(t)))
            e = fit(src_v, bm_v, yaws)
            if best is None or e[0] < best[0][0]:
                best = (e, t)
        # refine time and facing around the best one
        (err, yaw, off), t0 = best
        for dt in np.linspace(-0.05, 0.05, 11):
            t = min(max(0.0, t0 + dt), length)
            e = fit(verts(source_tris(gl, tex, pose(t))), bm_v, [yaw + dy for dy in np.linspace(-2, 2, 9)])
            if e[0] < err:
                err, yaw, off, best = e[0], e[1], e[2], (e, t)
        t_best = best[1]
        a_img = mc.raster(source_tris(gl, tex, pose(t_best)), "diagonal")
        b_img = mc.raster(move(bm_tris, yaw, off), "diagonal")
        diff = sum(1 for pa, pb in zip(a_img.getdata(), b_img.getdata()) if sum(abs(x - y) for x, y in zip(pa, pb)) > 30)
        px = diff / (a_img.width * a_img.height)
        pair = Image.new("RGBA", (a_img.width * 2 + 8, a_img.height), (0, 0, 0, 255))
        pair.paste(a_img, (0, 0))
        pair.paste(b_img, (a_img.width + 8, 0))
        pair.save(out / f"bm_{snap['label']}.png")
        # rot_y(yaw) brings the model back to facing +Z, so it was facing Minecraft yaw `yaw`.
        turn = (yaw - by + 180) % 360 - 180
        print(f"{snap['label']:<10} {len(parts)} parts  matches {kind} at {t_best:.3f}s  faces yaw {yaw % 360:.0f} (mob {by % 360:.0f})  vertex error {err * 16:.2f} px  pixels differ {px:.2%}")
        worst_err, worst_px = max(worst_err, err), max(worst_px, px)
        if err * 16 > 0.75 or px > 0.03 or abs(turn) > 20:
            bad.append(snap["label"])
    ok = not bad
    print(("PASS" if ok else "FAIL " + ", ".join(bad)) + f" (worst vertex error {worst_err * 16:.2f} px, worst pixels {worst_px:.2%}; limits 0.75 px / 3%)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
