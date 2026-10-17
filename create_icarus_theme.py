"""Draws the "Icarus" menu theme: bronze frame, marble, gold trim, feathered wings.

Outputs (all in assets/icarus/textures/font, plus the filler item texture):

* menu_base_1..6.png - the background every IcarusRPG chest menu gets (MenuBackground#apply),
  one per row count: frame, title band, the player's inventory and a winged emblem above the
  window. Chest slots are NOT drawn here - MenuBackground adds one menu_slot_row_N glyph per
  button, so a slot only appears where there's something to click.
* menu_slot_row_0..5.png - that per-button slot frame, one per row.
* menu_theme_skills.png - the main Skills menu's own full background (MenuBackground#applyThemed):
  title plaque with wings, colored panels and every slot baked in.
* textures/item/menu_background.png - the filler item's texture: fully transparent, so the
  panes filling empty slots never show.

Placement (see assets/minecraft/font/default.json): base/theme glyphs are drawn after a -48
space from the title origin (window x=8) with ascent 33, so image (x, y) = window (x + 40, y + 20).
Slot glyphs keep ascent 13 and their own column shifts, so their image y = window y.
Every base image has an alpha-1 pixel in column 255 so they share one glyph width (advance 257)
and the single -209 reset (\\uE002) puts the pen back on the title origin.
"""
from pathlib import Path
import random

from PIL import Image

ROOT = Path(__file__).resolve().parent
FONT = ROOT / "assets" / "icarus" / "textures" / "font"
ITEM = ROOT / "assets" / "icarus" / "textures" / "item"

OX, OY = 40, 20  # image offset of the window's top-left corner
W = 176

C = {
    "outline": (42, 26, 12, 255),
    "bronze": (122, 74, 36, 255),
    "bronze_dark": (78, 47, 22, 255),
    "gold": (226, 177, 74, 255),
    "gold_light": (246, 214, 120, 255),
    "gold_dark": (176, 128, 44, 255),
    "marble": (233, 225, 207, 255),
    "marble_light": (246, 241, 230, 255),
    "marble_dark": (214, 204, 182, 255),
    "marble_vein": (200, 188, 164, 255),
    "parchment": (247, 238, 214, 255),
    "slot_rim": (42, 26, 12, 255),
    "slot": (29, 36, 51, 255),
    "slot_shadow": (15, 20, 30, 255),
    "slot_light": (58, 71, 102, 255),
    "white": (250, 250, 250, 255),
    "feather": (236, 236, 236, 255),
    "feather_shade": (196, 196, 196, 255),
    "feather_tip": (124, 124, 124, 255),
}
SKY, SKY_DARK = (63, 143, 214, 255), (31, 90, 150, 255)

LETTERS = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}


def window_height(rows: int) -> int:
    return 114 + rows * 18


def player_slot_y(rows: int, row: int) -> int:
    """Window y of the slot FRAME (item y - 1) of player inventory row 0-2, or 3 for the hotbar - vanilla ChestMenu's own layout."""
    return (rows * 18 + 88) if row == 3 else (rows * 18 + 30 + row * 18)


class Canvas:
    def __init__(self, ox: int = OX, oy: int = OY, size=(256, 256)) -> None:
        self.img = Image.new("RGBA", size, (0, 0, 0, 0))
        self.ox, self.oy = ox, oy

    def px(self, x: int, y: int, color) -> None:
        x += self.ox
        y += self.oy
        if 0 <= x < self.img.width and 0 <= y < self.img.height:
            self.img.putpixel((x, y), color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        """Fills window-space [x0, x1) x [y0, y1)."""
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.px(x, y, color)

    def text(self, s: str, x: int, y: int, color, shadow=None) -> None:
        for ch in s:
            glyph = LETTERS[ch]
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        if shadow:
                            self.px(x + gx + 1, y + gy + 1, shadow)
                        self.px(x + gx, y + gy, color)
            x += len(glyph[0]) + 1

    @staticmethod
    def text_width(s: str) -> int:
        return sum(len(LETTERS[ch][0]) + 1 for ch in s) - 1

    def pin_width(self) -> None:
        """Alpha-1 pixel in the last column: every base glyph gets the same width, so one reset fits all."""
        self.img.putpixel((255, 0), (0, 0, 0, 1))


def marble(cv: Canvas, x0: int, y0: int, x1: int, y1: int, seed: int) -> None:
    cv.rect(x0, y0, x1, y1, C["marble"])
    rnd = random.Random(seed)
    for _ in range((x1 - x0) * (y1 - y0) // 60):
        x, y = rnd.randrange(x0, x1), rnd.randrange(y0, y1)
        cv.px(x, y, C["marble_light"] if rnd.random() < 0.55 else C["marble_dark"])
    for _ in range(max(2, (x1 - x0) // 40)):
        x, y = rnd.randrange(x0, x1), rnd.randrange(y0, y1)
        for _ in range(rnd.randrange(8, 22)):
            if x0 <= x < x1 and y0 <= y < y1:
                cv.px(x, y, C["marble_vein"])
            x += 1
            y += rnd.choice((0, 1, 1))


def slot(cv: Canvas, x: int, y: int) -> None:
    """An 18x18 slot frame whose item sits at (x+1, y+1) - same spot as vanilla's."""
    cv.rect(x, y, x + 18, y + 18, C["slot_rim"])
    cv.rect(x + 1, y + 1, x + 17, y + 17, C["slot"])
    cv.rect(x + 1, y + 1, x + 17, y + 2, C["slot_shadow"])
    cv.rect(x + 1, y + 1, x + 2, y + 17, C["slot_shadow"])
    cv.rect(x + 1, y + 16, x + 17, y + 17, C["slot_light"])
    cv.rect(x + 16, y + 1, x + 17, y + 17, C["slot_light"])


def frame(cv: Canvas, rows: int, seed: int) -> None:
    """Window frame, marble, the strip behind the client's "Inventory" label and the player's own slots."""
    h = window_height(rows)
    chest_bottom = 17 + rows * 18 + 3          # marble ends just under the last chest row
    label_y = h - 94                          # where the client draws "Inventory"
    cv.rect(0, 0, W, h, C["outline"])
    cv.rect(1, 1, W - 1, h - 1, C["bronze"])
    cv.rect(1, 1, W - 1, 2, C["gold_light"])
    cv.rect(3, 3, W - 3, h - 3, C["gold"])
    cv.rect(4, 4, W - 4, h - 4, C["bronze_dark"])
    marble(cv, 5, 5, W - 5, chest_bottom, seed)
    cv.rect(5, chest_bottom, W - 5, label_y + 10, C["parchment"])
    cv.rect(5, chest_bottom, W - 5, chest_bottom + 1, C["gold_dark"])
    cv.rect(5, label_y + 10, W - 5, label_y + 11, C["gold_dark"])
    marble(cv, 5, label_y + 11, W - 5, h - 5, seed + 1)
    for (cx, cy) in ((2, 2), (W - 5, 2), (2, h - 5), (W - 5, h - 5)):
        cv.rect(cx, cy, cx + 3, cy + 3, C["gold_light"])
        cv.px(cx + 1, cy + 1, C["gold_dark"])
    for r in range(4):
        for col in range(9):
            slot(cv, 7 + col * 18, player_slot_y(rows, r))


def title_band(cv: Canvas) -> None:
    """Light band behind the menu's own title text (drawn by the client at y=6, dark gray)."""
    cv.rect(5, 4, W - 5, 16, C["outline"])
    cv.rect(5, 5, W - 5, 15, C["gold"])
    cv.rect(6, 6, W - 6, 14, C["parchment"])
    cv.rect(6, 6, W - 6, 7, C["marble_light"])


BIG_WING = [(40, 2), (36, 3), (31, 4), (26, 5), (20, 7), (14, 9)]  # (length, px per 1 rise)
SMALL_WING = [(30, 3), (26, 4), (22, 5), (18, 6), (14, 8)]


def wing(cv: Canvas, x_edge: int, y: int, direction: int, feathers=BIG_WING, spacing: int = 3) -> None:
    """A fan of feathers sweeping up and away from x_edge (direction -1 = left, +1 = right)."""
    for i in reversed(range(len(feathers))):
        length, slope = feathers[i]
        fy = y + i * spacing
        for k in range(length):
            x = x_edge + direction * k
            top = fy - k // slope
            tip = k >= length - 5
            col = C["feather_tip"] if tip else C["feather"]
            cv.px(x, top, C["outline"])
            cv.px(x, top + 1, col)
            cv.px(x, top + 2, col if tip else C["feather_shade"])
            cv.px(x, top + 3, C["outline"])
        cv.px(x_edge + direction * length, fy - (length - 1) // slope + 1, C["outline"])
        cv.px(x_edge + direction * length, fy - (length - 1) // slope + 2, C["outline"])
    for k in range(10):
        cv.px(x_edge + direction * k, y + 2 - k // 3, C["gold_dark"])
        cv.px(x_edge + direction * k, y + 3 - k // 3, C["gold"])


def emblem(cv: Canvas) -> None:
    """Winged sun disc centered above the window - the generic menus' crest (no text). Kept
    entirely above y=3, so nothing reaches the title band and its text."""
    cx = W // 2
    wing(cv, cx - 10, -13, -1, SMALL_WING, 2)
    wing(cv, cx + 9, -13, 1, SMALL_WING, 2)
    cv.rect(cx - 8, -16, cx + 8, 1, C["outline"])
    cv.rect(cx - 7, -15, cx + 7, 0, C["gold"])
    cv.rect(cx - 5, -13, cx + 5, -2, C["gold_light"])
    cv.rect(cx - 3, -11, cx + 3, -4, SKY)
    cv.rect(cx - 2, -10, cx + 2, -8, (150, 205, 245, 255))


def plaque(cv: Canvas, title: str, accent, accent_dark) -> None:
    tw = Canvas.text_width(title)
    w = max(90, tw + 20)
    x0 = W // 2 - w // 2
    y0, y1 = -16, 13
    wing(cv, x0 - 3, y0 + 14, -1)
    wing(cv, x0 + w + 2, y0 + 14, 1)
    cv.rect(x0 - 2, y0, x0 + w + 2, y1, C["outline"])
    cv.rect(x0 - 1, y0 + 1, x0 + w + 1, y1 - 1, C["gold"])
    cv.rect(x0 - 1, y0 + 1, x0 + w + 1, y0 + 2, C["gold_light"])
    cv.rect(x0 + 2, y0 + 4, x0 + w - 2, y1 - 4, accent_dark)
    cv.rect(x0 + 3, y0 + 5, x0 + w - 3, y1 - 5, accent)
    cv.rect(x0 + 3, y0 + 5, x0 + w - 3, y0 + 6, tuple(min(255, c + 50) for c in accent[:3]) + (255,))
    cv.rect(W // 2 - 3, y0 - 4, W // 2 + 3, y0 + 1, C["outline"])
    cv.rect(W // 2 - 2, y0 - 3, W // 2 + 2, y0, C["gold_light"])
    cv.text(title, W // 2 - tw // 2, y0 + 7, C["white"], shadow=accent_dark)


def panel(cv: Canvas, first: int, last: int, fill, edge) -> None:
    row, c0, c1 = first // 9, first % 9, last % 9
    x0, x1 = 7 + c0 * 18 - 3, 7 + (c1 + 1) * 18 + 3
    y0, y1 = 17 + row * 18 - 3, 17 + (row + 1) * 18 + 3
    cv.rect(x0, y0, x1, y1, C["outline"])
    cv.rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, edge)
    cv.rect(x0 + 2, y0 + 2, x1 - 2, y1 - 2, fill)
    cv.rect(x0 + 2, y0 + 2, x1 - 2, y0 + 3, C["gold_light"])


def meander(cv: Canvas, x0: int, x1: int, y: int) -> None:
    """Greek key band, 10 px tall, between x0 and x1."""
    cv.rect(x0, y, x1, y + 10, C["bronze_dark"])
    cv.rect(x0, y, x1, y + 1, C["gold_dark"])
    cv.rect(x0, y + 9, x1, y + 10, C["gold_dark"])
    for x in range(x0 + 1, x1 - 7, 8):
        cv.rect(x, y + 2, x + 6, y + 3, C["gold"])
        cv.rect(x + 5, y + 2, x + 6, y + 7, C["gold"])
        cv.rect(x + 2, y + 6, x + 6, y + 7, C["gold"])
        cv.rect(x + 2, y + 4, x + 3, y + 7, C["gold"])
        cv.rect(x, y + 2, x + 1, y + 8, C["gold"])
        cv.rect(x, y + 7, x + 8, y + 8, C["gold"])


def sun(cv: Canvas, index: int) -> None:
    x, y = 7 + (index % 9) * 18, 17 + (index // 9) * 18
    cx, cy = x + 9, y + 9
    cv.rect(x - 3, y - 3, x + 21, y + 21, C["gold_dark"])
    cv.rect(x - 2, y - 2, x + 20, y + 20, C["gold"])
    cv.rect(x - 1, y - 1, x + 19, y + 19, C["gold_light"])
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
        for r in range(14, 24):
            col = C["gold"] if r % 3 else C["gold_light"]
            for w in (-1, 0, 1):
                if dx and dy:
                    cv.px(cx + dx * r + w, cy + dy * r, col)
                elif dx:
                    cv.px(cx + dx * r, cy + w, col)
                else:
                    cv.px(cx + w, cy + dy * r, col)


def base(rows: int) -> Image.Image:
    cv = Canvas()
    frame(cv, rows, seed=rows * 7)
    title_band(cv)
    emblem(cv)
    cv.pin_width()
    return cv.img


def slot_row(row: int) -> Image.Image:
    cv = Canvas(ox=0, oy=0, size=(18, 256))
    slot(cv, 0, 17 + row * 18)
    return cv.img


SKILLS_BUTTONS = (13, 19, 20, 21, 22, 23, 24, 29, 30, 31, 32, 45, 49, 53)


def skills_main() -> Image.Image:
    cv = Canvas()
    frame(cv, 6, seed=7)
    sun(cv, 13)
    panel(cv, 19, 24, (95, 165, 225, 255), SKY_DARK)
    panel(cv, 29, 32, (196, 150, 96, 255), C["bronze"])
    meander(cv, 26, 79, 111)
    meander(cv, 97, 151, 111)
    for i in SKILLS_BUTTONS:
        slot(cv, 7 + (i % 9) * 18, 17 + (i // 9) * 18)
    plaque(cv, "ICARUS RPG", SKY, SKY_DARK)
    return cv.img


if __name__ == "__main__":
    FONT.mkdir(parents=True, exist_ok=True)
    for rows in range(1, 7):
        base(rows).save(FONT / f"menu_base_{rows}.png", optimize=True)
    for row in range(6):
        slot_row(row).save(FONT / f"menu_slot_row_{row}.png", optimize=True)
    skills_main().save(FONT / "menu_theme_skills.png", optimize=True)
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(ITEM / "menu_background.png", optimize=True)
    print("wrote menu_base_1..6, menu_slot_row_0..5, menu_theme_skills and the transparent filler")
