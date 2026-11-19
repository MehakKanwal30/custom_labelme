"""Mirror Snap: move big-polygon points that hug a small polygon's edge to the
opposite side of the small polygon, snapping them to the small polygon's vertices.

Ported from Scipts/mirror_snap.py (geometry unchanged). The GUI calls
make_fixed_folder() / confirm_fixed() / reject_fixed().
"""
import json
import os
import os.path as osp
import shutil

import numpy as np

TOL = 2.5
MIN_RUN = 1
FIXED_DIRNAME = "fixed"


def dist_to_boundary(pts, poly):
    """Distance from each point in pts (N,2) to the closed polygon boundary."""
    a = poly
    b = np.roll(poly, -1, axis=0)
    ab = b - a
    denom = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.empty(len(pts))
    for i, p in enumerate(pts):
        t = np.clip(((p - a) * ab).sum(1) / denom, 0, 1)
        proj = a + ab * t[:, None]
        out[i] = np.sqrt(((proj - p) ** 2).sum(1)).min()
    return out


def centroid(poly):
    """Area centroid; falls back to vertex mean for degenerate polygons."""
    x, y = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    area = cr.sum() / 2
    if abs(area) < 1e-9:
        return poly.mean(0)
    return np.array([((x + x1) * cr).sum() / (6 * area),
                     ((y + y1) * cr).sum() / (6 * area)])


def circular_runs(flags):
    """Runs of True in a circular boolean list -> list of index lists."""
    n = len(flags)
    if n == 0 or not any(flags) or all(flags):
        return []
    start = next(i for i in range(n) if not flags[i])
    runs, cur = [], []
    for k in range(1, n + 1):
        i = (start + k) % n
        if flags[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def process_pair(big, small, tol, min_run):
    """Return (new_big_points, number_of_runs_changed)."""
    n = len(big)
    d = dist_to_boundary(big, small)
    flags = [bool(x <= tol) for x in d]
    runs = [r for r in circular_runs(flags) if len(r) >= min_run]
    if not runs:
        return big, 0

    c = centroid(small)
    # winding of the big polygon: +1 means its interior is on the left of travel
    x, y = big[:, 0], big[:, 1]
    wind = np.sign((x * np.roll(y, -1) - np.roll(x, -1) * y).sum()) or 1.0

    replace = {}  # first index of run -> (set of run indices, new points)
    for run in runs:
        pts = big[run]
        chord = pts[-1] - pts[0]
        if np.hypot(*chord) < 1e-9:  # closed/degenerate run: use principal axis
            chord = np.linalg.svd(pts - pts.mean(0))[2][0]
        u = chord / np.hypot(*chord)          # direction of travel
        nrm = np.array([-u[1], u[0]])         # normal to it
        side = np.sign(((pts - c) @ nrm).mean()) or 1.0
        # The run is already on the inside when the small polygon lies on the
        # outer side of it (big polygon's interior is on the run's `wind` side).
        if side == wind:
            continue
        n_s = (small - c) @ nrm               # small vertices: signed offset
        far = np.where(n_s * side <= 1e-9)[0]  # vertices on the far side
        if len(far) == 0:
            far = np.arange(len(small))

        def mirror_idx(p):
            """Index of the small vertex nearest to p mirrored across the line."""
            m = p - 2 * (((p - c) @ nrm) * nrm)
            return int(far[np.argmin(((small[far] - m) ** 2).sum(1))])

        i0, i1 = mirror_idx(pts[0]), mirror_idx(pts[-1])
        m = len(small)
        fwd = [(i0 + k) % m for k in range((i1 - i0) % m + 1)]
        bwd = [(i0 - k) % m for k in range((i0 - i1) % m + 1)]
        # of the two ways round the ring, take the one on the far side
        sel = np.array(fwd if n_s[fwd].mean() * side <= n_s[bwd].mean() * side
                       else bwd)
        replace[run[0]] = (set(run), small[sel])

    if not replace:
        return big, 0

    # rebuild in order, starting from a point that is not part of any run
    in_run = set().union(*(r for r, _ in replace.values()))
    start = next(i for i in range(n) if i not in in_run)
    new = []
    for k in range(n):
        i = (start + k) % n
        if i in in_run:
            if i in replace:
                new.extend(replace[i][1].tolist())
        else:
            new.append(big[i].tolist())
    # drop consecutive duplicates (incl. wrap-around)
    out = []
    for p in new:
        if not out or p != out[-1]:
            out.append(p)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return np.array(out, dtype=float), len(replace)


def fix_shapes(shapes, big_label, small_label, tol=TOL, min_run=MIN_RUN):
    """Apply the mirror-snap to the shapes list in place. Returns number of runs moved."""
    smalls = [np.array(s["points"], float) for s in shapes
              if s.get("label") == small_label and s.get("shape_type", "polygon") == "polygon"
              and len(s["points"]) >= 3]
    moved = 0
    for s in shapes:
        if s.get("label") != big_label or s.get("shape_type", "polygon") != "polygon":
            continue
        pts = np.array(s["points"], float)
        changed = 0
        for sm in smalls:
            pts, k = process_pair(pts, sm, tol, min_run)
            changed += k
        if changed:
            s["points"] = pts.tolist()
            moved += changed
    return moved


def json_path_for(image_path, json_dir=None):
    return osp.join(json_dir or osp.dirname(image_path),
                    osp.splitext(osp.basename(image_path))[0] + ".json")


def make_fixed_folder(image_paths, big_label, small_label, json_dir=None, progress=None,
                      tol=TOL, min_run=MIN_RUN):
    """Write <json folder>/fixed/<name>.json for every JSON that actually changes.

    Returns dict(pending={orig_json: fixed_json}, fixed_dirs=set, scanned, no_json,
    cancelled, failed). Originals are never modified."""
    result = dict(pending={}, fixed_dirs=set(), scanned=0, no_json=0, failed=0,
                  cancelled=False, runs=0, errors=[])
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
        if not osp.exists(jpath):
            result["no_json"] += 1
            continue
        try:
            with open(jpath, encoding="utf-8") as fh:
                data = json.load(fh)
            moved = fix_shapes(data.get("shapes", []), big_label, small_label, tol, min_run)
        except Exception as e:  # keep going on a bad file
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
    if progress and not result["cancelled"]:
        progress(len(jsons), len(jsons), "")
    return result


def confirm_fixed(pending, fixed_dirs):
    """Replace each original JSON with its fixed version, then delete the fixed folders."""
    replaced = 0
    for orig, fixed in pending.items():
        if osp.exists(fixed):
            os.replace(fixed, orig)
            replaced += 1
    for d in fixed_dirs:
        shutil.rmtree(d, ignore_errors=True)
    return replaced


def reject_fixed(fixed_dirs):
    """Delete the fixed folders; originals stay untouched."""
    for d in fixed_dirs:
        shutil.rmtree(d, ignore_errors=True)
