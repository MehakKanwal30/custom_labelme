"""Mask generation and outline overlays for the folder open in labelme.

Ported from Scipts/mask_gen.py and Scipts/outline_overlay.py. Both functions
work on one flat folder (images + jsons side by side) and report progress via
a callback so the GUI can drive a QProgressDialog.
"""
import json
import os
import os.path as osp

import cv2
import numpy as np

from labelme.label_colors import color_for_value
from labelme.label_config import COLOR_MAP, resolve_label

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
MASKS_DIRNAME = "masks"
OVERLAYS_DIRNAME = "overlays"


def output_dir_for(image_path, kind, out_root=None, base_dir=None):
    """Folder that holds this image's masks (kind='masks') or overlays ('overlays').

    Default (no out_root): next to the image. With out_root: <out_root>/<kind>, flat
    (no per-image subfolders). base_dir is kept for call compatibility."""
    if not out_root:
        return osp.join(osp.dirname(osp.abspath(image_path)), kind)
    return osp.normpath(osp.join(out_root, kind))


def list_images(folder):
    return sorted(
        f for f in os.listdir(folder)
        if osp.splitext(f)[1].lower() in IMAGE_EXTS
        and osp.isfile(osp.join(folder, f))
    )


def _read_image(path):
    # imdecode handles non-ASCII paths that cv2.imread can fail on
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _write_image(path, img):
    ok, buf = cv2.imencode(osp.splitext(path)[1], img)
    if ok:
        buf.tofile(path)
    return ok


def collect_labels(image_paths, json_dir=None):
    """Return {label: shape count} over the JSONs belonging to these images."""
    counts = {}
    for path in image_paths:
        folder, fname = osp.split(path)
        json_path = osp.join(json_dir or folder, osp.splitext(fname)[0] + ".json")
        if not osp.exists(json_path):
            continue
        try:
            with open(json_path, encoding="utf-8") as fh:
                shapes = json.load(fh).get("shapes", [])
        except (OSError, ValueError):
            continue
        for shape in shapes:
            label = shape.get("label", "")
            counts[label] = counts.get(label, 0) + 1
    return counts


def default_label_values(labels):
    """Default gray value per label from label_config, or None when unmapped."""
    out = {}
    for label in labels:
        canonical = resolve_label(label)
        out[label] = COLOR_MAP[canonical][0] if canonical is not None else None
    return out


def _multiclass_mask(shapes, w, h, label_values=None):
    """Same logic as mask_gen.create_multiclass_mask. Returns (mask, skipped).

    label_values ({label: gray}) overrides label_config when given."""
    mask = np.zeros((h, w, 3), dtype=np.uint8)
    skipped = set()

    def area(s):
        return cv2.contourArea(np.array(s["points"], dtype=np.float32))

    for shape in sorted(shapes, key=area, reverse=True):
        label = shape["label"]
        if label_values is not None:
            gray = label_values.get(label)
            if not gray:
                skipped.add(label)
                continue
            color = (int(gray),) * 3
        else:
            canonical = resolve_label(label)
            if canonical is None:
                skipped.add(label)
                continue
            color = COLOR_MAP[canonical]
        points = np.array(shape["points"], dtype=np.int32)
        cv2.fillPoly(mask, [points], color=color)
        if cv2.contourArea(points.astype(np.float32)) < 1.0:
            cx = max(0, min(int(round(np.mean(points[:, 0]))), w - 1))
            cy = max(0, min(int(round(np.mean(points[:, 1]))), h - 1))
            cv2.circle(mask, (cx, cy), 0, color, -1)
    return mask, skipped


def generate_masks(image_paths, json_dir=None, progress=None, label_values=None,
                   out_root=None, base_dir=None):
    """Write <image dir>/masks/<stem>_mask.png for every image path given.

    json_dir overrides where JSONs are read from (labelme output dir).
    progress(i, total, name) -> False to cancel.
    """
    image_paths = list(image_paths)
    result = dict(written=0, black=0, skipped_labels=set(), out_dirs=set(),
                  cancelled=False, failed=0, total=len(image_paths), collisions=[])
    seen = set()
    for i, path in enumerate(image_paths):
        if progress and progress(i, len(image_paths), osp.basename(path)) is False:
            result["cancelled"] = True
            break
        folder, fname = osp.split(path)
        stem = osp.splitext(fname)[0]
        out_dir = output_dir_for(path, MASKS_DIRNAME, out_root, base_dir)
        target = osp.join(out_dir, f"{stem}_mask.png")
        if target in seen:  # same file name from another subfolder, flat output
            result["collisions"].append(path)
            continue
        seen.add(target)
        os.makedirs(out_dir, exist_ok=True)
        img = _read_image(path)
        if img is None:
            result["failed"] += 1
            continue
        h, w = img.shape[:2]
        json_path = osp.join(json_dir or folder, stem + ".json")
        if osp.exists(json_path):
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            mask, skipped = _multiclass_mask(data.get("shapes", []), w, h, label_values)
            result["skipped_labels"] |= skipped
        else:
            mask = np.zeros((h, w, 3), dtype=np.uint8)
            result["black"] += 1
        _write_image(osp.join(out_dir, f"{stem}_mask.png"), cv2.cvtColor(mask, cv2.COLOR_RGB2BGR))
        result["written"] += 1
        result["out_dirs"].add(out_dir)
    if progress and not result["cancelled"]:
        progress(len(image_paths), len(image_paths), "")
    return result


def _component_outlines(mask):
    """[(area, label value, contour)] for every connected shape in the mask, largest first.

    RETR_CCOMP returns the outer boundary of every component, including components that
    sit inside a hole of another component with the same value (a small aneurysm inside
    a flow polygon inside a big aneurysm). RETR_EXTERNAL would silently drop those.
    Hole boundaries (hierarchy parent != -1) are skipped, so the inner edge of a ring is
    not drawn twice: the shape inside it draws its own outline."""
    items = []
    for lbl in np.unique(mask):
        lbl = int(lbl)
        if lbl == 0:
            continue
        contours, hierarchy = cv2.findContours(
            (mask == lbl).astype(np.uint8) * 255, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if hierarchy is None:
            continue
        for contour, info in zip(contours, hierarchy[0]):
            if info[3] == -1:
                items.append((abs(cv2.contourArea(contour)), lbl, contour))
    items.sort(key=lambda t: -t[0])  # big shapes first, so small inner shapes are drawn on top
    return items


def _draw_outlines(image, mask, thickness, value_map=None):
    """Draw per-label outlines. thickness may be fractional (0.5, 1.5, ...).

    Whole-number thickness draws directly. Fractional thickness draws the lines on a
    supersampled layer (k x resolution) and averages them back down, so the image
    itself is untouched except under the lines."""
    thickness = max(float(thickness), 0.25)
    whole = abs(thickness - round(thickness)) < 1e-6
    h, w = mask.shape[:2]
    if whole:
        k = 1
    else:
        px = h * w
        k = 4 if px <= 1_000_000 else 2 if px <= 4_000_000 else 1
    t = max(1, int(round(thickness if whole else thickness * k)))

    layer = np.zeros((h * k, w * k, 3), np.uint8) if k > 1 else image
    alpha = np.zeros((h * k, w * k), np.uint8) if k > 1 else None
    for _area, lbl, contour in _component_outlines(mask):
        color = color_for_value(lbl, value_map)
        contours = [contour]
        if k > 1:
            contours = [contour.astype(np.int32) * k + (k - 1) // 2]
            cv2.drawContours(alpha, contours, -1, 255, thickness=t, lineType=cv2.LINE_AA)
        cv2.drawContours(layer, contours, -1, color, thickness=t, lineType=cv2.LINE_AA)
    if k == 1:
        return image
    layer_d = cv2.resize(layer, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)
    a = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255.0
    # layer_d is already weighted by coverage (black elsewhere), so it is premultiplied
    out = image.astype(np.float32) * (1.0 - a) + layer_d
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)


def generate_overlays(image_paths, thickness=1, progress=None, out_root=None, base_dir=None,
                      value_map=None, image_loader=None):
    """Draw outlines from <image dir>/masks onto each image -> <image dir>/overlays.

    image_loader(path) may return a replacement background (e.g. the HU-windowed DICOM)
    of the same size as the image; None means "use the PNG itself"."""
    image_paths = list(image_paths)
    result = dict(written=0, missing_masks=0, failed=0, out_dirs=set(),
                  cancelled=False, total=len(image_paths), collisions=[], hu_used=0, hu_fallback=0)
    seen = set()
    for i, path in enumerate(image_paths):
        if progress and progress(i, len(image_paths), osp.basename(path)) is False:
            result["cancelled"] = True
            break
        folder, fname = osp.split(path)
        stem = osp.splitext(fname)[0]
        mask_path = osp.join(output_dir_for(path, MASKS_DIRNAME, out_root, base_dir), f"{stem}_mask.png")
        if not osp.exists(mask_path):
            result["missing_masks"] += 1
            continue
        image = _read_image(path)
        mask = cv2.imdecode(np.fromfile(mask_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if image is None or mask is None:
            result["failed"] += 1
            continue
        if image_loader is not None:
            alt = image_loader(path)
            if alt is not None and alt.shape[:2] == image.shape[:2]:
                image = np.ascontiguousarray(alt)
                result["hu_used"] += 1
            else:
                result["hu_fallback"] += 1  # no DICOM / size mismatch: keep the PNG
        if mask.shape[:2] != image.shape[:2]:
            mask = cv2.resize(mask, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
        out_dir = output_dir_for(path, OVERLAYS_DIRNAME, out_root, base_dir)
        target = osp.join(out_dir, f"{stem}.png")
        if target in seen:
            result["collisions"].append(path)
            continue
        seen.add(target)
        os.makedirs(out_dir, exist_ok=True)
        _write_image(osp.join(out_dir, f"{stem}.png"), _draw_outlines(image, mask, thickness, value_map))
        result["written"] += 1
        result["out_dirs"].add(out_dir)
    if progress and not result["cancelled"]:
        progress(len(image_paths), len(image_paths), "")
    return result
