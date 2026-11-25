from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import Qt

DEFAULT_LOW = -500
DEFAULT_HIGH = 1300


class HuWindowDialog(QtWidgets.QDialog):
    """Set the HU window (low / high), pick or save presets, choose the DICOM folder.

    Non-modal: the HU pane updates while this window is open.
    presets: list of {"name": str, "low": int, "high": int}
    """

    windowChanged = QtCore.pyqtSignal(int, int)
    offsetChanged = QtCore.pyqtSignal(int)
    presetsChanged = QtCore.pyqtSignal(list)
    dicomRootRequested = QtCore.pyqtSignal()

    def __init__(self, low, high, presets, dicom_root, parent=None, offset=0):
        super().__init__(parent)
        self.setWindowTitle(self.tr("HU window"))
        self.setMinimumWidth(380)
        self._presets = [dict(p) for p in presets]

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QGridLayout()
        self.lowSpin = self._spin(low)
        self.highSpin = self._spin(high)
        self.widthSpin = QtWidgets.QSpinBox()
        self.widthSpin.setRange(1, 40000)
        self.widthSpin.setSingleStep(10)
        self.levelSpin = QtWidgets.QDoubleSpinBox()
        self.levelSpin.setRange(-5000.0, 30000.0)
        self.levelSpin.setDecimals(1)
        self.levelSpin.setSingleStep(10.0)
        self.widthSpin.setToolTip(self.tr("Window width W = High - Low"))
        self.levelSpin.setToolTip(self.tr("Window level (centre) L = (Low + High) / 2"))
        form.addWidget(QtWidgets.QLabel(self.tr("Low (black):")), 0, 0)
        form.addWidget(self.lowSpin, 0, 1)
        form.addWidget(QtWidgets.QLabel(self.tr("High (white):")), 0, 2)
        form.addWidget(self.highSpin, 0, 3)
        form.addWidget(QtWidgets.QLabel(self.tr("Window (W):")), 1, 0)
        form.addWidget(self.widthSpin, 1, 1)
        form.addWidget(QtWidgets.QLabel(self.tr("Level (L):")), 1, 2)
        form.addWidget(self.levelSpin, 1, 3)
        layout.addLayout(form)
        self._showWL()

        row = QtWidgets.QHBoxLayout()
        self.saveBtn = QtWidgets.QPushButton(self.tr("Save as new preset..."))
        self.resetBtn = QtWidgets.QPushButton(self.tr("Default (%d / %d)") % (DEFAULT_LOW, DEFAULT_HIGH))
        row.addWidget(self.saveBtn)
        row.addWidget(self.resetBtn)
        layout.addLayout(row)

        layout.addWidget(QtWidgets.QLabel(self.tr("Presets (click to apply):")))
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumHeight(130)
        layout.addWidget(self.list)
        self.overwriteHint = QtWidgets.QLabel()
        self.overwriteHint.setStyleSheet("color: #d9822b; font-weight: bold;")
        self.overwriteHint.setWordWrap(True)
        self.overwriteHint.hide()
        layout.addWidget(self.overwriteHint)
        row2 = QtWidgets.QHBoxLayout()
        self.renameBtn = QtWidgets.QPushButton(self.tr("Rename..."))
        self.updateBtn = QtWidgets.QPushButton(self.tr("Overwrite with current"))
        self.updateBtn.setCheckable(True)  # armed = the next preset you click is overwritten
        self.updateBtn.setToolTip(self.tr(
            "Set the values you want, click this, then click the preset to overwrite.\n"
            "Click again or press Esc to cancel."))
        self._overwriteArmed = False
        self.deleteBtn = QtWidgets.QPushButton(self.tr("Delete"))
        for b in (self.renameBtn, self.updateBtn, self.deleteBtn):
            row2.addWidget(b)
        layout.addLayout(row2)

        layout.addWidget(QtWidgets.QLabel(self.tr("DICOM folder:")))
        rootRow = QtWidgets.QHBoxLayout()
        self.rootEdit = QtWidgets.QLineEdit(dicom_root)
        self.rootEdit.setReadOnly(True)
        self.rootEdit.setPlaceholderText(self.tr("(not set)"))
        browse = QtWidgets.QPushButton(self.tr("Browse..."))
        browse.clicked.connect(self.dicomRootRequested.emit)
        rootRow.addWidget(self.rootEdit, 1)
        rootRow.addWidget(browse)
        layout.addLayout(rootRow)
        offRow = QtWidgets.QHBoxLayout()
        self.offsetSpin = QtWidgets.QSpinBox()
        self.offsetSpin.setRange(-100000, 100000)
        self.offsetSpin.setValue(offset)
        self.offsetSpin.setToolTip(self.tr(
            "The DICOM used is the one whose InstanceNumber = (number at the end of the image name) + offset.\n"
            "Leave 0 unless the image numbering is shifted compared to the DICOMs."))
        offRow.addWidget(QtWidgets.QLabel(self.tr("Slice offset:")))
        offRow.addWidget(self.offsetSpin)
        offRow.addWidget(QtWidgets.QLabel(self.tr("(DICOM InstanceNumber = image number + offset)")), 1)
        layout.addLayout(offRow)
        self.offsetSpin.valueChanged.connect(self.offsetChanged.emit)

        self.lowSpin.valueChanged.connect(lambda _v: self._edited(self.lowSpin))
        self.highSpin.valueChanged.connect(lambda _v: self._edited(self.highSpin))
        self.widthSpin.valueChanged.connect(lambda _v: self._editedWL(self.widthSpin))
        self.levelSpin.valueChanged.connect(lambda _v: self._editedWL(self.levelSpin))
        self.saveBtn.clicked.connect(self.saveNew)
        self.resetBtn.clicked.connect(lambda: self.setValues(DEFAULT_LOW, DEFAULT_HIGH, emit=True))
        self.list.itemClicked.connect(self._applyItem)
        self.list.currentRowChanged.connect(self._updateButtons)
        self.renameBtn.clicked.connect(self.renameSelected)
        self.updateBtn.toggled.connect(self._armOverwrite)
        self.deleteBtn.clicked.connect(self.deleteSelected)
        self._fillList()

    # -- helpers -----------------------------------------------------------------

    def _spin(self, value):
        sp = QtWidgets.QSpinBox()
        sp.setRange(-5000, 30000)
        sp.setSingleStep(10)
        sp.setValue(value)
        return sp

    def low(self):
        return self.lowSpin.value()

    def high(self):
        return self.highSpin.value()

    def setDicomRoot(self, root):
        self.rootEdit.setText(root)

    def setValues(self, low, high, emit=False):
        """Set both boxes. emit=True also notifies the app (used by presets / default)."""
        for sp, v in ((self.lowSpin, low), (self.highSpin, high)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
        self._showWL()
        self._highlightMatch()
        if emit:
            self.windowChanged.emit(self.low(), self.high())

    def _showWL(self):
        """Show W = high - low and L = (low + high) / 2 without triggering their handlers."""
        for sp, v in ((self.widthSpin, self.high() - self.low()), (self.levelSpin, (self.low() + self.high()) / 2.0)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)

    def _editedWL(self, sender):
        """W or L typed: low = L - W/2, high = low + W (so W stays exactly what was typed
        when it is odd, only the centre moves by half a unit)."""
        width = self.widthSpin.value()
        level = self.levelSpin.value()
        low = int(round(level - width / 2.0))
        for sp, v in ((self.lowSpin, low), (self.highSpin, low + width)):
            sp.blockSignals(True)
            sp.setValue(v)
            sp.blockSignals(False)
        if self.high() - self.low() != width:  # a box hit its limit: show what was applied
            self._showWL()
        elif sender is self.widthSpin:
            self._showWL()
        else:
            self.widthSpin.blockSignals(True)
            self.widthSpin.setValue(self.high() - self.low())
            self.widthSpin.blockSignals(False)
        self._highlightMatch()
        self.windowChanged.emit(self.low(), self.high())

    def _edited(self, sender):
        # keep low < high by pushing the other box
        lo, hi = self.low(), self.high()
        if lo >= hi:
            other = self.highSpin if sender is self.lowSpin else self.lowSpin
            other.blockSignals(True)
            other.setValue(lo + 1 if sender is self.lowSpin else hi - 1)
            other.blockSignals(False)
        self._showWL()
        self._highlightMatch()
        self.windowChanged.emit(self.low(), self.high())

    def _label(self, p):
        return "%s   (%d / %d)" % (p["name"], p["low"], p["high"])

    def _fillList(self, select=None):
        self.list.blockSignals(True)
        self.list.clear()
        for p in self._presets:
            self.list.addItem(self._label(p))
        if select is not None and 0 <= select < len(self._presets):
            self.list.setCurrentRow(select)
        self.list.blockSignals(False)
        self._updateButtons()
        self._highlightMatch()

    def _highlightMatch(self):
        """Select the preset equal to the current values (if any)."""
        self.list.blockSignals(True)
        match = next((i for i, p in enumerate(self._presets)
                      if p["low"] == self.low() and p["high"] == self.high()), None)
        if match is not None:
            self.list.setCurrentRow(match)
        elif self.list.currentRow() >= 0 and (
                self._presets[self.list.currentRow()]["low"], self._presets[self.list.currentRow()]["high"]
        ) != (self.low(), self.high()):
            self.list.setCurrentRow(-1)
        self.list.blockSignals(False)
        self._updateButtons()

    def _updateButtons(self, *_):
        has = self.list.currentRow() >= 0
        for b in (self.renameBtn, self.deleteBtn):
            b.setEnabled(has)
        self.updateBtn.setEnabled(bool(self._presets))  # needs no selection: you pick after arming
        if not self._presets:
            self._disarmOverwrite()

    def _changed(self, select=None):
        self._fillList(select)
        self.presetsChanged.emit([dict(p) for p in self._presets])

    def _nameTaken(self, name, ignore=None):
        return any(p["name"].lower() == name.lower() for i, p in enumerate(self._presets) if i != ignore)

    def _askName(self, title, default, ignore=None):
        while True:
            name, ok = QtWidgets.QInputDialog.getText(self, title, self.tr("Preset name:"), text=default)
            name = name.strip()
            if not ok or not name:
                return None
            if self._nameTaken(name, ignore):
                QtWidgets.QMessageBox.information(self, title, self.tr("A preset called '%s' already exists.") % name)
                default = name
                continue
            return name

    # -- actions -----------------------------------------------------------------

    def _applyItem(self, item):
        row = self.list.row(item)
        if not 0 <= row < len(self._presets):
            return
        if self._overwriteArmed:
            self._overwritePreset(row)  # keep the window as it is, store its values in this preset
            return
        p = self._presets[row]
        self.setValues(p["low"], p["high"], emit=True)

    # -- overwrite: arm the button, then click the preset ----------------------------

    def _armOverwrite(self, checked):
        self._overwriteArmed = checked
        if checked:
            self.updateBtn.setStyleSheet(
                "QPushButton { background-color: #d9822b; color: white; font-weight: bold; }")
            self.overwriteHint.setText(self.tr(
                "Click the preset to overwrite with the current values (%d / %d). Esc cancels.")
                % (self.low(), self.high()))
            self.overwriteHint.show()
            self.list.setStyleSheet("QListWidget { border: 2px solid #d9822b; }")
        else:
            self.updateBtn.setStyleSheet("")
            self.list.setStyleSheet("")
            self.overwriteHint.hide()

    def _disarmOverwrite(self):
        if self.updateBtn.isChecked():
            self.updateBtn.setChecked(False)  # triggers _armOverwrite(False)

    def _overwritePreset(self, row):
        p = self._presets[row]
        p["low"], p["high"] = self.low(), self.high()
        self._disarmOverwrite()
        self._changed(select=row)
        self.overwriteHint.setText(self.tr("'%s' now stores %d / %d") % (p["name"], p["low"], p["high"]))
        self.overwriteHint.show()
        QtCore.QTimer.singleShot(3000, lambda: self.overwriteHint.hide() if not self._overwriteArmed else None)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key_Escape and self._overwriteArmed:
            self._disarmOverwrite()  # cancel overwrite instead of closing the window
            return
        super().keyPressEvent(ev)

    def hideEvent(self, ev):
        self._disarmOverwrite()
        super().hideEvent(ev)

    def saveNew(self):
        self._disarmOverwrite()
        n = len(self._presets) + 1
        default = "Preset %d" % n
        while self._nameTaken(default):
            n += 1
            default = "Preset %d" % n
        name = self._askName(self.tr("Save preset"), default)
        if name is None:
            return
        self._presets.append({"name": name, "low": self.low(), "high": self.high()})
        self._changed(select=len(self._presets) - 1)

    def renameSelected(self):
        self._disarmOverwrite()
        row = self.list.currentRow()
        if row < 0:
            return
        name = self._askName(self.tr("Rename preset"), self._presets[row]["name"], ignore=row)
        if name is None:
            return
        self._presets[row]["name"] = name
        self._changed(select=row)

    def deleteSelected(self):
        self._disarmOverwrite()
        row = self.list.currentRow()
        if row < 0:
            return
        del self._presets[row]
        self._changed(select=min(row, len(self._presets) - 1))
