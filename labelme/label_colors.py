"""One colour scheme for every label drawing outside the main canvas (mask overlays,
Fixed JSON pane for Mirror Snap / Shrink Polygons).

Fixed colours:
    flow          red
    calcification yellow
    plaque        light green
    aneurysm      blue
Every other label gets a colour from OTHER_PALETTE, picked by a stable hash of the
label name (same label -> same colour in every session and on every PC).
"""
import zlib

from labelme.label_config import LABEL_MAP, resolve_label

RED = (255, 0, 0)
YELLOW = (255, 255, 0)
LIGHT_GREEN = (144, 238, 144)
BLUE = (0, 90, 255)

FIXED = {
    "flow": RED,
    "calcification": YELLOW,
    "plaque": LIGHT_GREEN,
    "aneurysm": BLUE,
}

# RGB. No reds / yellows / greens / pure blue, so none can be mistaken for a fixed colour.
OTHER_PALETTE = [
    (120, 120, 255),  # periwinkle
    (255, 0, 255),    # magenta
    (0, 230, 230),    # cyan
    (255, 140, 0),    # orange
    (160, 32, 240),   # purple
    (255, 105, 180),  # pink
    (255, 255, 255),  # white
    (0, 150, 150),    # teal
    (165, 100, 60),   # brown
]


def _palette_color(key):
    return OTHER_PALETTE[zlib.crc32(key.encode("utf-8")) % len(OTHER_PALETTE)]


def kind_of(label):
    """'flow' / 'calcification' / 'plaque' / 'aneurysm' for labels that map to a fixed
    colour (including variants like left_flow1 or 'artery calcified'), else None."""
    key = label.strip().lower()
    if "aneurysm" in key:
        return "aneurysm"
    canonical = resolve_label(label)
    return canonical if canonical in FIXED else None


def label_rgb(label):
    kind = kind_of(label)
    return FIXED[kind] if kind else _palette_color(label.strip().lower())


def label_bgr(label):
    r, g, b = label_rgb(label)
    return (b, g, r)


def value_colors(label_values):
    """{mask gray value: BGR colour} from {label: gray}. Labels with a fixed colour win
    when several labels share a value."""
    out = {}
    ordered = sorted((l for l, v in label_values.items() if v),
                     key=lambda l: (kind_of(l) is None, l.lower()))
    for label in ordered:
        out.setdefault(int(label_values[label]), label_bgr(label))
    return out


def color_for_value(gray, value_map=None):
    """BGR colour for a mask pixel value: this run's label values first, then the
    default label config, then the stable palette."""
    gray = int(gray)
    if value_map and gray in value_map:
        return value_map[gray]
    for name, info in LABEL_MAP.items():
        if info["mask_gray"] == gray:
            r, g, b = FIXED.get(name) or _palette_color(name)
            return (b, g, r)
    r, g, b = _palette_color("value-%d" % gray)
    return (b, g, r)
