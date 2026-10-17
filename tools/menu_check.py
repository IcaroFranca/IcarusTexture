"""Renders IcarusRPG menus the way the Minecraft client composes them and checks them.

Input: a menus.jsonl dumped by the MenuDump test plugin (exact title string, size and items of
each menu), this resource pack, and the vanilla client textures (extracted from the 26.2 client
jar - never committed). For each menu it draws the vanilla chest window, the title (bitmap font
glyphs from this pack, vanilla ascii for text), then the items, and runs the checks below.

    python tools/menu_check.py menus.jsonl <vanilla-assets-dir> <out-dir>

Exit code 1 if any check fails.
"""
import json
import sys
from pathlib import Path

from PIL import Image

PACK = Path(__file__).resolve().parent.parent
MARGIN_X, MARGIN_Y = 48, 30
COLORS = {"f": (255, 255, 255), "8": (85, 85, 85), "0": (0, 0, 0), "7": (170, 170, 170)}
DEFAULT_TITLE = (64, 64, 64)
VANILLA_GRAYS = {(198, 198, 198), (139, 139, 139)}


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


class Font:
    def __init__(self, vanilla: Path):
        self.bitmaps = {}  # char -> (glyph image, ascent, scale)
        self.space = {" ": 4}
        d = json.loads((PACK / "assets/minecraft/font/default.json").read_text(encoding="utf-8"))
        for p in d["providers"]:
            if p["type"] == "space":
                self.space.update(p["advances"])
            elif p["type"] == "bitmap":
                ns, path = p["file"].split(":")
                img = Image.open(PACK / "assets" / ns / "textures" / path).convert("RGBA")
                rows = p["chars"]
                cw, ch = img.width // len(rows[0]), img.height // len(rows)
                for r, row in enumerate(rows):
                    for c, char in enumerate(row):
                        cell = img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))
                        self.bitmaps[char] = (cell, p.get("ascent", 7), p.get("height", 8) / ch)
        ascii_img = Image.open(vanilla / "textures/font/ascii.png").convert("RGBA")
        for code in range(32, 127):
            if code == 32:
                continue
            cell = ascii_img.crop(((code % 16) * 8, (code // 16) * 8, (code % 16) * 8 + 8, (code // 16) * 8 + 8))
            self.bitmaps.setdefault(chr(code), (cell, 7, 1.0))

    @staticmethod
    def width(cell):
        for x in range(cell.width - 1, -1, -1):
            if any(cell.getpixel((x, y))[3] for y in range(cell.height)):
                return x + 1
        return 0

    def draw(self, canvas, text, x, y, issues):
        """Draws a legacy-formatted string; returns the pixel boxes covered by plain text."""
        color = DEFAULT_TITLE
        pen = x
        text_boxes = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch == "§" and i + 1 < len(text):
                color = COLORS.get(text[i + 1], color)
                i += 2
                continue
            if ch in self.space:
                pen += self.space[ch]
            elif ch in self.bitmaps:
                cell, ascent, scale = self.bitmaps[ch]
                if scale != 1:
                    cell = cell.resize((round(cell.width * scale), round(cell.height * scale)), Image.NEAREST)
                top = y + 7 - ascent
                tinted = Image.new("RGBA", cell.size)
                for py in range(cell.height):
                    for px in range(cell.width):
                        r, g, b, a = cell.getpixel((px, py))
                        if a:
                            tinted.putpixel((px, py), (r * color[0] // 255, g * color[1] // 255, b * color[2] // 255, a))
                canvas.alpha_composite(tinted, (pen, top))
                w = self.width(cell)
                if ord(ch) < 128:
                    text_boxes.append((pen, top, pen + w, top + cell.height, color))
                pen += w + 1
            elif 0xE000 <= ord(ch) <= 0xF8FF:
                issues.append(f"title has a private-use character the pack doesn't define: U+{ord(ch):04X} (shows as a box)")
                pen += 6
            else:
                pen += 6  # an ordinary character from Minecraft's own fallback fonts (not drawn here)
            i += 1
        return text_boxes


class Items:
    def __init__(self, vanilla: Path):
        self.vanilla = vanilla
        self.cache = {}

    def texture(self, material, model):
        """(image, offset) to draw at the slot's item position."""
        key = (material, model)
        if key in self.cache:
            return self.cache[key]
        img = None
        if model:
            ns, path = model.split(":")
            item_def = PACK / "assets" / ns / "items" / f"{path}.json"
            if item_def.exists():
                model_ref = json.loads(item_def.read_text())["model"].get("model", "")
                mns, mpath = model_ref.split(":") if ":" in model_ref else ("minecraft", model_ref)
                model_json = json.loads((PACK / "assets" / mns / "models" / f"{mpath}.json").read_text())
                textures = model_json.get("textures", {})
                tex = textures.get("layer0") or (next(iter(textures.values())) if model_json.get("elements") else None)
                scale = model_json.get("display", {}).get("gui", {}).get("scale", [1, 1, 1])[0] if model_json.get("elements") else 1
                if tex:
                    tns, tpath = tex.split(":") if ":" in tex else ("minecraft", tex)
                    root = PACK if tns != "minecraft" else self.vanilla.parent.parent
                    f = root / "assets" / tns / "textures" / f"{tpath}.png"
                    if f.exists():
                        img = Image.open(f).convert("RGBA").resize((round(16 * scale), round(16 * scale)), Image.NEAREST)
                        off = (16 - img.width) // 2
                        self.cache[key] = (img, off)
                        return self.cache[key]
        if img is None:
            for cand in (f"item/{material}", f"block/{material}", f"block/{material}_front", f"block/{material}_side", f"block/{material}_top"):
                f = self.vanilla / "textures" / f"{cand}.png"
                if f.exists():
                    img = Image.open(f).convert("RGBA").crop((0, 0, 16, 16))
                    break
        if img is None and material.endswith("_head"):
            skin = Image.open(self.vanilla / "textures/entity/player/wide/steve.png").convert("RGBA")
            img = skin.crop((8, 8, 16, 16)).resize((16, 16), Image.NEAREST)
        if img is None:
            img = Image.new("RGBA", (16, 16), (255, 0, 255, 255))
        img = img.resize((16, 16), Image.NEAREST) if img.size != (16, 16) else img
        self.cache[key] = (img, 0)
        return self.cache[key]


def render(menu, font, items, vanilla):
    rows = menu["size"] // 9
    h = 114 + rows * 18
    canvas = Image.new("RGBA", (176 + 2 * MARGIN_X, h + 2 * MARGIN_Y), (24, 24, 28, 255))
    bg = Image.open(vanilla / "textures/gui/container/generic_54.png").convert("RGBA")
    ox, oy = MARGIN_X, MARGIN_Y
    canvas.alpha_composite(bg.crop((0, 0, 176, rows * 18 + 17)), (ox, oy))
    canvas.alpha_composite(bg.crop((0, 126, 176, 222)), (ox, oy + rows * 18 + 17))
    issues = []
    text_boxes = font.draw(canvas, menu["title"], ox + 8, oy + 6, issues)
    # The client's own "Inventory" label.
    label_y = h - 94
    font.draw(canvas, "Inventory", ox + 8, oy + label_y, [])
    background = canvas.copy()
    for it in menu["items"]:
        s = it["slot"]
        x, y = ox + 8 + (s % 9) * 18, oy + 18 + (s // 9) * 18
        img, off = items.texture(it["material"], it["model"])
        canvas.alpha_composite(img, (x + off, y + off))
    return canvas, background, issues, text_boxes, h


def checks(menu, canvas, background, issues, text_boxes, h):
    ox, oy = MARGIN_X, MARGIN_Y
    rows = menu["size"] // 9

    def region(img, x, y, w, hh):
        return [img.getpixel((x + i, y + j))[:3] for j in range(hh) for i in range(w)]

    for it in menu["items"]:
        s = it["slot"]
        x, y = ox + 8 + (s % 9) * 18, oy + 18 + (s // 9) * 18
        if it["filler"]:
            if region(canvas, x, y, 16, 16) != region(background, x, y, 16, 16):
                issues.append(f"slot {s}: filler item ({it['model']}) is visible - should be invisible")
        else:
            inside = region(background, x, y, 16, 16)
            if sum(map(lum, inside)) / len(inside) > 90:
                issues.append(f"slot {s} ({it['name'] or it['material']}): button isn't on a drawn slot")
    window = region(background, ox, oy, 176, h)
    vanilla = sum(1 for c in window if c in VANILLA_GRAYS) / len(window)
    if vanilla > 0.005:
        issues.append(f"vanilla chest background still showing ({vanilla:.0%} of the window)")
    if text_boxes and text_boxes[0][0] != ox + 8:
        issues.append(f"title text starts at x={text_boxes[0][0] - ox} instead of 8 (glyph reset is off)")
    for (x0, y0, x1, y1, color) in text_boxes:
        under = [background.getpixel((x, y))[:3] for y in range(y0, y1) for x in range(x0, x1)
                 if background.getpixel((x, y))[:3] != tuple(c * 1 for c in color)]
        if under and abs(sum(map(lum, under)) / len(under) - lum(color)) < 60:
            issues.append("title text has too little contrast with its background")
            break
    for k in range(36):
        col, row = k % 9, k // 9
        y = oy + (rows * 18 + 31 + row * 18 if row < 3 else rows * 18 + 89)
        inside = region(background, ox + 8 + col * 18, y, 16, 16)
        if sum(map(lum, inside)) / len(inside) > 90 and vanilla <= 0.005:
            issues.append(f"player inventory slot {k} isn't drawn where its item goes")
            break
        # The 1-px rim right above where the item goes must be the frame, not the slot interior.
    label = region(background, ox + 8, oy + h - 94 - 1, 54, 10)
    if vanilla <= 0.005 and sum(map(lum, label)) / len(label) < 120:
        issues.append("'Inventory' label sits on a dark background")
    return issues


def main():
    menus = [json.loads(l) for l in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines() if l.strip()]
    vanilla = Path(sys.argv[2])
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    font, items = Font(vanilla), Items(vanilla)
    failed = 0
    sheet = []
    for n, menu in enumerate(menus):
        canvas, background, issues, boxes, h = render(menu, font, items, vanilla)
        issues = checks(menu, canvas, background, issues, boxes, h)
        name = f"{n:02d}_{menu['path'].replace('>', '_').replace(' ', '').replace('[', '').replace(']', '').replace(',', '-')}"
        canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST).save(out / f"{name}.png")
        sheet.append(canvas)
        status = "OK  " if not issues else "FAIL"
        failed += bool(issues)
        print(f"{status} {menu['path']}  ({menu['size']} slots)")
        for i in dict.fromkeys(issues):
            print(f"       - {i}")
    cols = 5
    cw, ch = max(c.width for c in sheet), max(c.height for c in sheet)
    contact = Image.new("RGBA", (cw * cols, ch * ((len(sheet) + cols - 1) // cols)), (24, 24, 28, 255))
    for i, c in enumerate(sheet):
        contact.alpha_composite(c, ((i % cols) * cw, (i // cols) * ch))
    contact.save(out / "_all.png")
    print(f"\n{len(menus) - failed}/{len(menus)} menus pass")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
