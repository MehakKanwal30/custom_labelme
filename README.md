# Custom LabelMe

A modified fork of **LabelMe 5.8.3** built for faster, more ergonomic image annotation.  
Adds dark mode, viewport-aware keep-previous, pixel painting, batch annotation ops, and more on top of the upstream tool.

---

## Requirements

- Python 3.10
- PyQt5, Pillow, numpy (installed automatically via `pip install -e .`)

---

## Installation

```bash
git clone https://github.com/MehakKanwal30/custom_labelme.git
cd custom_labelme
pip install -e .
```

> Optional: create a virtual environment first (`python -m venv env && source env/bin/activate`).

## Running

```bash
labelme
```

## Updating

```bash
git pull
pip install -e .   # only needed if dependencies changed
```

---

## Custom Features

### Dark Mode
Default theme. Applied via Qt Fusion palette on startup — no configuration needed.

---

### Lasso / Freehand Tool
Hold **Left Shift + drag** to stream points continuously.  
End with **Ctrl + Left Click**.  
Adjust point spacing with the **Lasso Step** spinbox in the toolbar.

---

### Ghost Flip
Flips the canvas display for easier point placement. Saved coordinates always use original image space.

| Action | Shortcut |
|---|---|
| Flip image horizontally | `H` |
| Flip image vertically | `V` |
| Show original (no flip/adjustments) | `B` |

---

### Annotation Flip
Flips the **selected polygon** in place.

| Action | Shortcut |
|---|---|
| Flip polygon horizontally | `Ctrl+Shift+H` |
| Flip polygon vertically | `Ctrl+Shift+V` |

---

### Redo
`Ctrl+Y` — restores deleted shapes or re-applies undone point edits.  
Works for both whole-shape undo/redo and individual point undo/redo during drawing.

---

### Pixel Paint
`Ctrl+R` — paint pixels directly onto the image; finalises as a polygon.

| Action | Input |
|---|---|
| Paint | LMB drag |
| Erase | RMB drag |
| Finalise | `Ctrl+LMB` or `Enter` |
| Undo stroke | `Ctrl+Z` |

---

### Pixel Grid
`X` — draws a per-pixel boundary grid overlay. Most useful when zoomed in.

---

### Hide Annotations
`G` — toggles annotation visibility. State persists across image switches.

---

### Keep Scale
Toolbar toggle — carries the current zoom level to every subsequent image.

---

### Keep Annotation
Toolbar toggle — copies annotations from the previous image to the next.

**Rules:**
- New image is **empty** → all annotations visible in the previous viewport are copied.
- New image has shapes + previous viewport had **exactly 1** annotation → copies that annotation only if no shape overlaps the same region.
- New image already has shapes in that region, or previous viewport had multiple shapes → nothing is copied.

---

### Keep Brightness
Toolbar toggle (also available as a checkbox inside the Brightness/Contrast dialog) — carries brightness and contrast settings across image switches.  
The button lives in the main toolbar next to **Keep Annotation**.

---

### Follow Mouse
`C` — when exactly **one annotation is geometrically inside the current viewport**, its centroid follows the mouse cursor on hover.  
Works correctly even when the image has multiple annotations — only the count visible in the current zoom view matters.  
Undo is committed when the toggle is turned off.

---

### Auto Advance
`T` — starts a timer that automatically moves to the next image.

- Set the interval (in seconds) with the spin box below the button (0.1 – 999, default 3 s).
- Changing the value while the timer is running restarts it at the new interval immediately.
- Press `T` again (or click the button) to stop.

---

### Annotation Operations
Five toolbar buttons for batch editing. All operate on the **current image only** and work on annotations **visible in the zoomed viewport**.

#### Auto Delete
Toggle. On each image switch, deletes the annotation in the current view.  
**Delete All** checkbox: when ticked, deletes *all* annotations in view instead of requiring exactly one.

#### Replace Label
Toggle + text box. On each image switch, renames the label of the single annotation in view to the text typed in the box. Ignored if more than one annotation is in view.

#### Replace Polygon
Toggle. Two-step workflow:
1. Zoom in to the annotation you want to use as a template → click to store it (label shown below button).
2. Navigate to target images — the single annotation in view is replaced with the stored template, centroid-aligned.

Click again to clear the template and turn off.

#### Separate L/R
Toggle. On each image switch, prefixes every annotation with `left_` or `right_` based on its mean x-position vs the image midline. Annotations already prefixed are skipped.  
**Apply Folder** button: one-shot — applies the same operation to every JSON file in the current folder.

> All annotation operations (except Separate L/R and Apply Folder) skip automatically if 0 or 2+ annotations are in the viewport.

---

## Keyboard Shortcut Reference

| Feature | Shortcut |
|---|---|
| Next image | `D` |
| Previous image | `A` |
| Lasso start/continue | `Shift + LMB drag` |
| Lasso end | `Ctrl + LMB` |
| Pixel paint mode | `Ctrl+R` |
| Undo shape / point | `Ctrl+Z` |
| Redo shape / point | `Ctrl+Y` |
| Flip image H | `H` |
| Flip image V | `V` |
| Show original | `B` |
| Flip polygon H | `Ctrl+Shift+H` |
| Flip polygon V | `Ctrl+Shift+V` |
| Pixel grid | `X` |
| Hide annotations | `G` |
| Follow Mouse toggle | `C` |
| Auto Advance toggle | `T` |
| Toggle all polygons | `Shift+T` |

---

