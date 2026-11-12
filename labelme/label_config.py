# Unified label configuration shared by mask_gen.py and create_segmentation_4_labels.py.
#
# Each entry maps a canonical label name to:
#   mask_gray    – the grayscale value (R=G=B) burned into the mask PNG
#   segment_name – the human-readable name shown in the 3D segmentation viewer
#   segment_rgb  – the display colour used in the 3D segmentation viewer
#
# To add or change a label, edit only this file — both scripts will pick it up.

LABEL_MAP = {
    #  canonical key    mask gray   segment display name    segment RGB
    "flow":          {"mask_gray": 245, "segment_name": "artery",        "segment_rgb": [255,   0,   0]},
    "plaque":        {"mask_gray": 128, "segment_name": "plaque",        "segment_rgb": [255, 206,   0]},
    "calcification": {"mask_gray": 255, "segment_name": "calcification", "segment_rgb": [255, 238, 170]},
    "thrombus":      {"mask_gray": 102, "segment_name": "thrombus",      "segment_rgb": [ 85,   0,   0]},
    "reconstructed": {"mask_gray":  51, "segment_name": "reconstructed", "segment_rgb": [  0, 255,   0]},
}

# ---------------------------------------------------------------------------
# Pattern-based label resolution
#
# When a JSON annotation label does not exactly match a LABEL_MAP key, these
# rules are tried in order (case-insensitive substring match). First hit wins.
#
# Examples that resolve automatically without adding entries here:
#   "artery"                 -> None            (bare "artery" label is ignored)
#   "right popliteal artery" -> "flow"          (contains "artery" with other words)
#   "artery calcified"       -> "calcification" (artery + calcif → kept)
#   "flow1" / "flow2"        -> "flow"   (contains "flow")
#   "soft plaque"            -> "plaque" (contains "plaque")
#   "calcified plaque"       -> "plaque" (contains "plaque")  ← checked before "calcif"
#   "aneurysm"               -> "thrombus" (merged into the thrombus class)
#   "abdominal aorta"        -> "flow"     (merged into the flow/artery class)
#
# To add a new class:
#   1. Add the canonical key + mask_gray + colours to LABEL_MAP above.
#   2. Add one or more (keyword, canonical_key) rows here.
# ---------------------------------------------------------------------------

LABEL_PATTERNS = [
    # keyword (substring)   canonical key
    ("artery",              "flow"),
    ("flow",                "flow"),
    ("trunk",               "flow"),
    ("aorta",               "flow"),
    ("plaque",              "plaque"),
    ("calcif",              "calcification"),
    ("thrombus",            "thrombus"),
    ("aneurysm",            "thrombus"),
    ("reconstruct",         "reconstructed"),
]


_FLOW_KEYWORDS = {"flow", "artery", "trunk"}


def resolve_label(raw_label):
    """
    Resolve a raw JSON annotation label to a canonical LABEL_MAP key.

    Resolution order:
      1. Exact match (case-insensitive) against LABEL_MAP keys.
      2. Compound-label priority (handles mixed labels like flow_plaque, artery_calcified):
           - "plaque" present                          → plaque
           - "calcif" present + flow synonym present   → calcification
           - flow synonym only                         → fall through to pattern scan
      3. Substring keyword match via LABEL_PATTERNS (first match wins).

    Returns the canonical key string, or None if nothing matches.
    """
    key = raw_label.strip().lower()

    # 1. Exact match
    if key in LABEL_MAP:
        return key

    # 2. Compound-label priority
    has_plaque = "plaque" in key
    has_calcif = "calcif" in key
    has_flow   = any(kw in key for kw in _FLOW_KEYWORDS)

    if has_plaque:
        return "plaque"
    if has_calcif and has_flow:
        return "calcification"

    # Ignore labels where "artery" is the only meaningful content (e.g. "artery",
    # "right artery", "left femoral artery") — no other non-flow keyword present.
    if key == "artery":
        return None

    # 3. General pattern scan
    for keyword, canonical in LABEL_PATTERNS:
        if keyword in key:
            return canonical

    return None


# ---------------------------------------------------------------------------
# Derived lookups (consumed by mask_gen.py and create_segmentation_4_labels.py)
# ---------------------------------------------------------------------------

# mask_gen.py COLOR_MAP: canonical label -> (R, G, B) equal channels = grayscale pixel
COLOR_MAP = {label: (v["mask_gray"],) * 3 for label, v in LABEL_MAP.items()}

# create_segmentation_4_labels.py reverse lookup:
#   grayscale pixel value -> {name, rgb} for the segmentation viewer
GRAY_TO_SEGMENT = {
    v["mask_gray"]: {"name": v["segment_name"], "rgb": v["segment_rgb"]}
    for v in LABEL_MAP.values()
}
