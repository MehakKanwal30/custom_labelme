"""HU windowing from DICOM files, for any study.

The user picks any DICOM folder. For the open image we work out which DICOM it is:

 1. Find the *series folders* under the chosen folder (folders that directly hold DICOM
    files). The folder itself counts, so a single-series folder works as is.
 2. If there are several, pick the one that matches the image: a folder named like the
    image's prefix (CE061_10.png -> CE061/) or sharing a name with a folder on the
    image's path (.../S1/PNG_IMAGES/5.png -> S1/DICOMS/).
 3. Inside that folder pick the file whose DICOM file name equals the image name, else
    whose InstanceNumber equals the number at the end of the image name (+ the slice
    offset the user can set for studies numbered differently).
"""
import os
import os.path as osp
import re
from functools import lru_cache

import numpy as np

DEFAULT_LOW = -500
DEFAULT_HIGH = 1300

# files that are never DICOM slices
_SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".json", ".txt", ".csv",
    ".xml", ".md", ".yaml", ".yml", ".zip", ".gz", ".npy", ".npz", ".py", ".pdf", ".log",
    ".nii", ".mha", ".nrrd", ".ini", ".db",
}
_MAX_DEPTH = 6  # how deep below the chosen folder series folders are searched

_NAME_RE = re.compile(r"^(.*?)(\d+)$")
_roots = {}  # root path -> _RootIndex


def parse_name(image_path):
    """'/x/CE061_10.png' -> ('CE061_', 10); 'I01342' -> ('I', 1342); None if no number."""
    m = _NAME_RE.match(osp.splitext(osp.basename(image_path))[0])
    return (m.group(1), int(m.group(2))) if m else None


def _candidate_files(folder):
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return []
    out = []
    for n in names:
        p = osp.join(folder, n)
        if osp.isfile(p) and osp.splitext(n)[1].lower() not in _SKIP_EXT and n.upper() != "DICOMDIR":
            out.append(p)
    return out


def _is_dicom(path):
    import pydicom

    try:
        ds = pydicom.dcmread(path, force=True, stop_before_pixels=True, specific_tags=["InstanceNumber", "Rows"])
        return "InstanceNumber" in ds or "Rows" in ds
    except Exception:
        return False


class _RootIndex:
    def __init__(self, root):
        self.root = root
        self._series = None
        self._dir_index = {}

    def series_dirs(self):
        """Folders under root that directly hold DICOM files (root itself included)."""
        if self._series is None:
            found = []
            base_depth = self.root.rstrip(os.sep).count(os.sep)
            for dirpath, dirnames, _ in os.walk(self.root):
                if dirpath.count(os.sep) - base_depth >= _MAX_DEPTH:
                    dirnames[:] = []
                files = _candidate_files(dirpath)
                if files and any(_is_dicom(f) for f in files[:3]):
                    found.append(dirpath)
            self._series = found
        return self._series

    def index(self, folder):
        """({InstanceNumber: path}, {file stem: path}) for a series folder."""
        if folder not in self._dir_index:
            import pydicom

            by_inst, by_stem = {}, {}
            for path in _candidate_files(folder):
                by_stem[osp.splitext(osp.basename(path))[0]] = path
                try:
                    ds = pydicom.dcmread(path, force=True, stop_before_pixels=True,
                                         specific_tags=["InstanceNumber"])
                    by_inst[int(ds.InstanceNumber)] = path
                except Exception:
                    continue
            self._dir_index[folder] = (by_inst, by_stem)
        return self._dir_index[folder]


def _root(root):
    root = osp.abspath(root)
    if root not in _roots:
        _roots[root] = _RootIndex(root)
    return _roots[root]


def _split_tokens(text):
    return {t for t in re.split(r"[_\-\s]+", text) if t}


def _choose_series(ri, image_path, prefix):
    """Pick the series folder for this image. Returns (folder, message)."""
    cands = ri.series_dirs()
    if not cands:
        return None, "No DICOM files found in the chosen folder"
    if len(cands) == 1:
        return cands[0], ""
    image_dir_parts = set(osp.abspath(image_path).split(os.sep))
    stem_tokens = _split_tokens(prefix) | _split_tokens(osp.splitext(osp.basename(image_path))[0])
    scored = []
    for d in cands:
        rel_parts = [p for p in osp.relpath(d, ri.root).split(os.sep) if p and p != "."]
        score = 0
        if rel_parts and rel_parts[-1] in stem_tokens:        # folder named like the image prefix
            score += 100
        score += 10 * len(set(rel_parts) & (image_dir_parts | stem_tokens))  # shared names
        scored.append((score, d))
    scored.sort(key=lambda t: -t[0])
    if scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1], ""
    names = ", ".join(osp.relpath(d, ri.root) for _, d in scored[:4])
    return None, "Cannot tell which of %d DICOM folders matches this image (%s ...)" % (len(cands), names)


def find_dicom(root, image_path, offset=0):
    """Return (dicom path or None, message, description). message explains a miss."""
    if not root or not osp.isdir(root):
        return None, "Set the DICOM folder first", ""
    parsed = parse_name(image_path)
    prefix, number = parsed if parsed else (osp.splitext(osp.basename(image_path))[0], None)
    ri = _root(root)
    folder, why = _choose_series(ri, image_path, prefix)
    if folder is None:
        return None, why, ""
    by_inst, by_stem = ri.index(folder)
    stem = osp.splitext(osp.basename(image_path))[0]
    rel = osp.relpath(folder, ri.root)
    if offset == 0 and stem in by_stem:  # image and DICOM share their file name
        path = by_stem[stem]
        return path, "", "%s (same file name)" % osp.join(rel, osp.basename(path))
    if number is None:
        return None, "Image name has no slice number and no DICOM has the same name", ""
    target = number + offset
    path = by_inst.get(target)
    if path is None:
        return None, "No DICOM with InstanceNumber %d in %s" % (target, rel if rel != "." else "the folder"), ""
    return path, "", "%s (InstanceNumber %d)" % (osp.join(rel, osp.basename(path)), target)


@lru_cache(maxsize=8)
def load_hu(path):
    """Slice as float32 HU (rescale slope / intercept applied). Cached; do not modify."""
    import pydicom

    ds = pydicom.dcmread(path, force=True)
    arr = ds.pixel_array.astype(np.float32)
    arr = arr * float(getattr(ds, "RescaleSlope", 1)) + float(getattr(ds, "RescaleIntercept", 0))
    arr.setflags(write=False)
    return arr


def window_to_uint8(hu, low, high):
    """Same mapping as dicom_to_png.py, with a custom window."""
    high = max(high, low + 1)
    return ((np.clip(hu, low, high) - low) / (high - low) * 255).astype(np.uint8)


def is_default_window(low, high):
    return (int(low), int(high)) == (DEFAULT_LOW, DEFAULT_HIGH)


def make_image_loader(root, low, high, offset=0):
    """Return loader(image_path) -> BGR uint8 image windowed to [low, high] from the DICOM,
    or None when that image has no matching DICOM / cannot be read (caller falls back to
    the PNG). Used by Generate Overlay."""

    def loader(image_path):
        try:
            path, _why, _desc = find_dicom(root, image_path, offset)
            if path is None:
                return None
            gray = window_to_uint8(load_hu(path), low, high)
        except Exception:
            return None
        return np.dstack([gray, gray, gray])  # equal channels, so BGR == RGB

    return loader


def clear_cache():
    _roots.clear()
    load_hu.cache_clear()
