"""Draws the "Icarus" themed menu backgrounds (bronze frame, marble, winged title plaque).

Each theme is one 256x256 font glyph covering the whole 6-row chest screen - the chest part,
the player's inventory below it and a plaque that rises above the window - with slot frames
baked in only where that menu has buttons. The plugin writes it into the menu title (see
IcarusRPG's MenuBackground#applyThemed).

Glyph placement: drawn after a -48 space (\\uE101) from the title origin (window x=8), so image
x = window x + 40; ascent 33 (13 + 20) puts image y = window y + 20.
"""
from pathlib import Path
import random

from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets" / "icarus" / "textures" / "font"

OX, OY = 40, 20  # image offset of the window's top-left corner
W, H = 176, 222  # 6-row chest window

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
    "slot_rim": (42, 26, 12, 255),
    "slot": (29, 36, 51, 255),
    "slot_shadow": (15, 20, 30, 255),
    "slot_light": (58, 71, 102, 255),
    "white": (250, 250, 250, 255),
    "feather": (236, 236, 236, 255),
    "feather_shade": (196, 196, 196, 255),
    "feather_tip": (124, 124, 124, 255),
}

# 5x7 pixel letters for plaque titles.
FONT = {
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


class Canvas:
    def __init__(self) -> None:
        self.img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))

    def px(self, x: int, y: int, color) -> None:
        x += OX
        y += OY
        if 0 <= x < 256 and 0 <= y < 256:
            self.img.putpixel((x, y), color)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color) -> None:
        """Fills window-space [x0, x1) x [y0, y1)."""
        for y in range(y0, y1):
            for x in range(x0, x1):
                self.px(x, y, color)

    def text(self, s: str, x: int, y: int, color, shadow=None) -> None:
        for ch in s:
            glyph = FONT[ch]
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        if shadow:
                            self.px(x + gx + 1, y + gy + 1, shadow)
                        self.px(x + gx, y + gy, color)
            x += len(glyph[0]) + 1

    @staticmethod
    def text_width(s: str) -> int:
        return sum(len(FONT[ch][0]) + 1 for ch in s) - 1


def marble(cv: Canvas, x0: int, y0: int, x1: int, y1: int, seed: int) -> None:
    cv.rect(x0, y0, x1, y1, C["marble"])
    rnd = random.Random(seed)
    for _ in range((x1 - x0) * (y1 - y0) // 60):
        x, y = rnd.randrange(x0, x1), rnd.randrange(y0, y1)
        cv.px(x, y, C["marble_light"] if rnd.random() < 0.55 else C["marble_dark"])
    # A few thin diagonal veins.
    for _ in range(max(2, (x1 - x0) // 40)):
        x, y = rnd.randrange(x0, x1), rnd.randrange(y0, y1)
        for _ in range(rnd.randrange(8, 22)):
            if x0 <= x < x1 and y0 <= y < y1:
                cv.px(x, y, C["marble_vein"])
            x += 1
            y += rnd.choice((0, 1, 1))


def frame(cv: Canvas) -> None:
    cv.rect(0, 0, W, H, C["outline"])
    cv.rect(1, 1, W - 1, H - 1, C["bronze"])
    cv.rect(1, 1, W - 1, 2, C["gold_light"])  # top bevel
    cv.rect(3, 3, W - 3, H - 3, C["gold"])
    cv.rect(4, 4, W - 4, H - 4, C["bronze_dark"])
    marble(cv, 5, 5, W - 5, 126, seed=7)
    marble(cv, 5, 137, W - 5, H - 5, seed=11)
    # Strip behind the client's own "Inventory" label (drawn at y=128 in dark gray).
    cv.rect(5, 126, W - 5, 137, C["marble_light"])
    cv.rect(5, 126, W - 5, 127, C["gold_dark"])
    cv.rect(5, 136, W - 5, 137, C["gold_dark"])
    # Gold corner studs.
    for (cx, cy) in ((2, 2), (W - 5, 2), (2, H - 5), (W - 5, H - 5)):
        cv.rect(cx, cy, cx + 3, cy + 3, C["gold_light"])
        cv.px(cx + 1, cy + 1, C["gold_dark"])


def slot(cv: Canvas, x: int, y: int) -> None:
    """An 18x18 slot frame whose item sits at (x+1, y+1) - same spot as vanilla's."""
    cv.rect(x, y, x + 18, y + 18, C["slot_rim"])
    cv.rect(x + 1, y + 1, x + 17, y + 17, C["slot"])
    cv.rect(x + 1, y + 1, x + 17, y + 2, C["slot_shadow"])
    cv.rect(x + 1, y + 1, x + 2, y + 17, C["slot_shadow"])
    cv.rect(x + 1, y + 16, x + 17, y + 17, C["slot_light"])
    cv.rect(x + 16, y + 1, x + 17, y + 17, C["slot_light"])


def chest_slot(cv: Canvas, index: int) -> None:
    slot(cv, 7 + (index % 9) * 18, 17 + (index // 9) * 18)


def panel(cv: Canvas, first: int, last: int, fill, edge) -> None:
    """A colored band behind the slots first..last of one row."""
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
    """Golden rays around a featured slot (the player's own head)."""
    x, y = 7 + (index % 9) * 18, 17 + (index // 9) * 18
    cx, cy = x + 9, y + 9
    cv.rect(x - 3, y - 3, x + 21, y + 21, C["gold_dark"])
    cv.rect(x - 2, y - 2, x + 20, y + 20, C["gold"])
    cv.rect(x - 1, y - 1, x + 19, y + 19, C["gold_light"])
    rays = [(-1, 0), (1, 0), (0, -1), (-1, -1), (1, -1), (-1, 1), (1, 1)]
    for dx, dy in rays:
        for r in range(14, 24):
            col = C["gold"] if r % 3 else C["gold_light"]
            for w in (-1, 0, 1):
                if dx and dy:
                    cv.px(cx + dx * r + w, cy + dy * r, col)
                elif dx:
                    cv.px(cx + dx * r, cy + w, col)
                else:
                    cv.px(cx + w, cy + dy * r, col)


def wing(cv: Canvas, x_edge: int, y: int, direction: int) -> None:
    """A fan of feathers sweeping up and away from x_edge (direction -1 = left, +1 = right) -
    the top feather longest and steepest, each one below shorter and flatter."""
    feathers = [(40, 2), (36, 3), (31, 4), (26, 5), (20, 7), (14, 9)]  # (length, px per 1 rise)
    for i in reversed(range(len(feathers))):
        length, slope = feathers[i]
        fy = y + i * 3
        for k in range(length):
            x = x_edge + direction * k
            top = fy - k // slope
            tip = k >= length - 5
            col = C["feather_tip"] if tip else C["feather"]
            cv.px(x, top, C["outline"])
            cv.px(x, top + 1, col)
            cv.px(x, top + 2, col if tip else C["feather_shade"])
            cv.px(x, top + 3, C["outline"])
        # Rounded tip.
        cv.px(x_edge + direction * length, fy - (length - 1) // slope + 1, C["outline"])
        cv.px(x_edge + direction * length, fy - (length - 1) // slope + 2, C["outline"])
    # Gold "arm" where the wing meets the plaque.
    for k in range(10):
        cv.px(x_edge + direction * k, y + 2 - k // 3, C["gold_dark"])
        cv.px(x_edge + direction * k, y + 3 - k // 3, C["gold"])


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
    # Small sun gem on top.
    cv.rect(W // 2 - 3, y0 - 4, W // 2 + 3, y0 + 1, C["outline"])
    cv.rect(W // 2 - 2, y0 - 3, W // 2 + 2, y0, C["gold_light"])
    cv.text(title, W // 2 - tw // 2, y0 + 7, C["white"], shadow=accent_dark)


def skills_main() -> Image.Image:
    cv = Canvas()
    frame(cv)
    sky, sky_dark = (63, 143, 214, 255), (31, 90, 150, 255)
    sun(cv, 13)
    panel(cv, 19, 24, (95, 165, 225, 255), sky_dark)
    panel(cv, 29, 32, (196, 150, 96, 255), C["bronze"])
    meander(cv, 26, 79, 111)
    meander(cv, 97, 151, 111)
    for i in (13, 19, 20, 21, 22, 23, 24, 29, 30, 31, 32, 45, 49, 53):
        chest_slot(cv, i)
    for row in range(3):
        for col in range(9):
            slot(cv, 7 + col * 18, 139 + row * 18)
    for col in range(9):
        slot(cv, 7 + col * 18, 197)
    plaque(cv, "ICARUS RPG", sky, sky_dark)
    return cv.img


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    skills_main().save(OUT / "menu_theme_skills.png", optimize=True)
    print("wrote", OUT / "menu_theme_skills.png")
