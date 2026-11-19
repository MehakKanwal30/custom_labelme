"""Shrink Polygons: move every polygon vertex toward that polygon's own centre by a
fixed number of pixels (negative = grow).

Ported from Scipts/shrink_polygons.py (geometry unchanged). The GUI runs it on the
files currently open and writes changed JSONs to a fixed/ folder for review, reusing
mirror_snap.confirm_fixed / reject_fixed.
"""
import json
import math
import os
import os.path as osp
import re
from collections import defaultdict

from labelme.mirror_snap import FIXED_DIRNAME, json_path_for


def slice_number(path):
    m = re.search(r"(\d+)$", osp.splitext(osp.basename(path))[0])
    return int(m.group(1)) if m else None


def centroid(points):
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return cx, cy


def pixel_of(x, y):
    return math.floor(x), math.floor(y)


NEIGHBOR_OFFSETS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]


def find_overlapping_points(shapes, ignore_labels=None):
    """Return {shape_index: {point_index, ...}} for every polygon vertex that
    sits in the same pixel as, or one pixel away from (8-connected), a vertex
    belonging to a DIFFERENT polygon shape — across ALL polygon shapes in the
    file, regardless of label. E.g. a 'flow' vertex touching or neighboring a
    'calcification' vertex is flagged even if only 'flow' is being processed.
    Two vertices of the SAME polygon never protect each other (consecutive
    vertices are often only a pixel or two apart, which would otherwise freeze
    most of a normal polygon). Shapes whose label is in `ignore_labels` are left
    out of the overlap check entirely, both as protector and protected — a point
    that only overlaps an ignored-label shape is free to move."""
    ignore_labels = set(ignore_labels or ())
    pixel_map = defaultdict(list)
    for shape_idx, shape in enumerate(shapes):
        if shape.get("shape_type") != "polygon":
            continue
        if shape.get("label") in ignore_labels:
            continue
        for point_idx, (x, y) in enumerate(shape.get("points", [])):
            pixel_map[pixel_of(x, y)].append((shape_idx, point_idx))

    protected = defaultdict(set)
    for pixel, entries in pixel_map.items():
        px, py = pixel
        neighbor_entries = []
        for dx, dy in NEIGHBOR_OFFSETS:
            neighbor_entries.extend(pixel_map.get((px + dx, py + dy), []))
        for shape_idx, point_idx in entries:
            if any(other_shape_idx != shape_idx for other_shape_idx, _ in neighbor_entries):
                protected[shape_idx].add(point_idx)
    return protected


def shrink_points(points, amount, skip_indices=None):
    """Move each vertex `amount` px toward the polygon center (negative = away).

    A vertex nearer the center than `amount` is snapped to the center rather than
    overshooting past it. Vertices whose index is in `skip_indices` are left
    untouched (still counted toward the centroid, just not moved)."""
    skip_indices = skip_indices or set()
    cx, cy = centroid(points)
    out = []
    for i, (x, y) in enumerate(points):
        if i in skip_indices:
            out.append([x, y])
            continue
        vx, vy = cx - x, cy - y
        dist = math.hypot(vx, vy)
        if dist == 0:
            out.append([x, y])
            continue
        step = amount if amount < dist else dist
        out.append([x + vx / dist * step, y + vy / dist * step])
    return out


def in_range(n, lo, hi):
    if lo is not None and (n is None or n < lo):
        return False
    if hi is not None and (n is None or n > hi):
        return False
    return True


def shrink_shapes(shapes, pixels, labels=None, overlap=False, ignore_labels=None):
    """Shrink matching polygons in place. Returns (polygons_moved, vertices_exempted)."""
    labels = set(labels or ())
    protected = find_overlapping_points(shapes, ignore_labels) if overlap else {}
    moved = exempted = 0
    for shape_idx, shape in enumerate(shapes):
        if shape.get("shape_type") != "polygon":
            continue
        if labels and shape.get("label") not in labels:
            continue
        pts = shape.get("points", [])
        if len(pts) < 3:
            continue
        skip = protected.get(shape_idx, set())
        new = shrink_points(pts, pixels, skip)
        if new == [list(p) for p in pts]:
            continue
        exempted += len(skip)
        shape["points"] = new
        moved += 1
    return moved, exempted


def make_fixed_folder(image_paths, pixels, labels=None, overlap=False, ignore_labels=None,
                      slice_start=None, slice_end=None, json_dir=None, progress=None):
    """Write <json folder>/fixed/<name>.json for every JSON that changes. Originals untouched."""
    result = dict(pending={}, fixed_dirs=set(), scanned=0, no_json=0, failed=0,
                  cancelled=False, runs=0, exempted=0, skipped_range=0, errors=[])
    jsons, seen = [], set()
    for p in image_paths:
        j = json_path_for(p, json_dir)
        if j in seen:
            continue
        seen.add(j)
        jsons.append(j)
    for i, jpath in enumerate(jsons):
        if progress and progress(i, len(jsons), osp.basename(jpath)) is False:
            result["cancelled"] = True
            break
        if not in_range(slice_number(jpath), slice_start, slice_end):
            result["skipped_range"] += 1
            continue
        if not osp.exists(jpath):
            result["no_json"] += 1
            continue
        try:
            with open(jpath, encoding="utf-8") as fh:
                data = json.load(fh)
            moved, exempted = shrink_shapes(data.get("shapes", []), pixels, labels, overlap, ignore_labels)
        except Exception as e:
            result["failed"] += 1
            result["errors"].append("%s: %s" % (osp.basename(jpath), e))
            continue
        result["scanned"] += 1
        if not moved:
            continue
        fdir = osp.join(osp.dirname(jpath), FIXED_DIRNAME)
        os.makedirs(fdir, exist_ok=True)
        fpath = osp.join(fdir, osp.basename(jpath))
        with open(fpath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        result["pending"][jpath] = fpath
        result["fixed_dirs"].add(fdir)
        result["runs"] += moved
        result["exempted"] += exempted
    if progress and not result["cancelled"]:
        progress(len(jsons), len(jsons), "")
    return result
