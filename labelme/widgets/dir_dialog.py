"""Light-weight folder / file pickers (Linux only).

On Windows (and anything that is not Linux) every function here falls back to the
stock Qt / native dialogs, exactly as upstream labelme calls them, with no pinning.

Qt's stock file dialog can freeze the window for seconds on a real desktop: it asks the
system icon theme for an icon (and a mime type) for every entry, lists every mounted
drive and network share in its side bar (a stale mount blocks), and replays the
history. These helpers keep Qt's own dialog (no native / portal dialog) but remove those
costs: one cached icon per kind, a short fixed side bar, no history, list view.
"""
import json
import os
import os.path as osp
import sys

from PyQt5 import QtCore, QtWidgets


class _FastIconProvider(QtWidgets.QFileIconProvider):
    """Two cached icons, no per-file theme or mime-type lookups."""

    def __init__(self):
        super().__init__()
        style = QtWidgets.QApplication.style()
        self._dir = style.standardIcon(QtWidgets.QStyle.SP_DirIcon)
        self._file = style.standardIcon(QtWidgets.QStyle.SP_FileIcon)

    def icon(self, arg):
        if isinstance(arg, QtCore.QFileInfo):
            return self._dir if arg.isDir() else self._file
        return self._dir

    def type(self, info):
        return "Folder" if info.isDir() else "File"


def _use_lean_dialogs():
    """The lean dialog + pinned folders are for Linux. Other platforms keep the default."""
    return sys.platform.startswith("linux")


_PINS_KEY = "dialogs/pinned_folders"


def _settings():
    return QtCore.QSettings("labelme", "labelme")


def load_pins():
    """Pinned folders, in the order they were pinned."""
    try:
        pins = json.loads(_settings().value(_PINS_KEY, "[]") or "[]")
    except (ValueError, TypeError):
        return []
    return [p for p in pins if isinstance(p, str) and p]


def save_pins(pins):
    _settings().setValue(_PINS_KEY, json.dumps(pins))


def _norm(path):
    return osp.normpath(path)


def _sidebar_pins(dlg):
    """Pins as currently shown in the dialog's side bar (so dragging a folder in, or
    right-click > Remove, is remembered too). The home entry is not a pin."""
    home = _norm(osp.expanduser("~"))
    out = []
    for url in dlg.sidebarUrls():
        if url.isLocalFile():
            path = _norm(url.toLocalFile())
            if path != home and path not in out:
                out.append(path)
    return out


def _existing_start(path):
    """Nearest existing folder at or above path, else the home folder."""
    path = path or ""
    try:
        path = osp.abspath(path) if path else ""
        while path and not osp.isdir(path):
            parent = osp.dirname(path)
            if parent == path:
                break
            path = parent
        if path and osp.isdir(path):
            return path
    except OSError:
        pass
    return osp.expanduser("~")


def slim_file_dialog(dlg, start):
    """Apply the light-weight settings to any QFileDialog (Linux only, no-op elsewhere)."""
    if not _use_lean_dialogs():
        return
    start = _existing_start(start)
    dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
    dlg.setOption(QtWidgets.QFileDialog.DontResolveSymlinks, True)
    dlg.setOption(QtWidgets.QFileDialog.DontUseCustomDirectoryIcons, True)
    dlg.setIconProvider(_FastIconProvider())
    dlg.setViewMode(QtWidgets.QFileDialog.List)
    dlg.setHistory([])
    home = osp.expanduser("~")
    urls = [QtCore.QUrl.fromLocalFile(home)]
    urls += [QtCore.QUrl.fromLocalFile(p) for p in load_pins() if _norm(p) != _norm(home)]
    dlg.setSidebarUrls(urls)
    _install_pin_menu(dlg)
    dlg.finished.connect(lambda _r: save_pins(_sidebar_pins(dlg)))


def _toggle_pin(dlg, folder):
    pins = _sidebar_pins(dlg)
    folder = _norm(folder)
    if folder in pins:
        pins.remove(folder)
    else:
        pins.append(folder)
    home = QtCore.QUrl.fromLocalFile(osp.expanduser("~"))
    dlg.setSidebarUrls([home] + [QtCore.QUrl.fromLocalFile(p) for p in pins])
    save_pins(pins)


class _PinMenuFilter(QtCore.QObject):
    """Right-click on a folder in the dialog's list: offer Pin / Unpin for that folder.

    Right-clicks on anything else (files, empty space) keep Qt's own menu."""

    def __init__(self, dlg, view):
        super().__init__(view)
        self.dlg = dlg
        self.view = view

    def eventFilter(self, obj, event):
        if event.type() != QtCore.QEvent.ContextMenu:
            return False
        index = self.view.indexAt(event.pos())
        if not index.isValid():
            return False
        path = index.data(QtWidgets.QFileSystemModel.FilePathRole)
        if not path or not osp.isdir(path):
            return False
        path = _norm(path)
        pinned = path in _sidebar_pins(self.dlg)
        menu = QtWidgets.QMenu(self.view)
        act = menu.addAction(self.dlg.tr("Unpin from side bar") if pinned else self.dlg.tr("Pin to side bar"))
        act.setToolTip(path)
        if menu.exec_(event.globalPos()) is act:
            _toggle_pin(self.dlg, path)
        return True


def _install_pin_menu(dlg):
    for name in ("listView", "treeView"):
        view = dlg.findChild(QtWidgets.QAbstractItemView, name)
        if view is not None:
            view.viewport().installEventFilter(_PinMenuFilter(dlg, view))


def get_existing_directory(parent, caption, start=""):
    """Pick a folder. Returns the path, or "" if cancelled."""
    if not _use_lean_dialogs():
        # stock dialog, same call and options labelme always used
        return QtWidgets.QFileDialog.getExistingDirectory(
            parent, caption, start,
            QtWidgets.QFileDialog.ShowDirsOnly | QtWidgets.QFileDialog.DontResolveSymlinks,
        )
    start = _existing_start(start)
    dlg = QtWidgets.QFileDialog(parent, caption, start)
    dlg.setFileMode(QtWidgets.QFileDialog.Directory)
    dlg.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
    slim_file_dialog(dlg, start)
    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        return ""
    files = dlg.selectedFiles()
    return files[0] if files else ""
