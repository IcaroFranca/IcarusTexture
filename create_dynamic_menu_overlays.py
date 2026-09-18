from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets" / "icarus" / "textures" / "font"
SLOT = (
    ROOT.parent
    / "vanilla-gui-26.2"
    / "assets"
    / "minecraft"
    / "textures"
    / "gui"
    / "sprites"
    / "container"
    / "slot.png"
)

CANVAS = (198, 198, 198, 255)


def base(rows: int) -> None:
    image = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    image.paste(CANVAS, (7, 17, 169, 17 + rows * 18))
    # Keeps the same glyph advance as the proven main-menu overlay without a
    # visible pixel outside the inventory window.
    image.putpixel((175, 0), (198, 198, 198, 1))
    image.save(OUT / f"menu_base_{rows}.png", optimize=True)


def slot_rows() -> None:
    slot = Image.open(SLOT).convert("RGBA")
    for row in range(6):
        image = Image.new("RGBA", (18, 256), (0, 0, 0, 0))
        image.alpha_composite(slot, (0, 17 + row * 18))
        image.save(OUT / f"menu_slot_row_{row}.png", optimize=True)


OUT.mkdir(parents=True, exist_ok=True)
base(3)
base(6)
slot_rows()
