from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt


def _labelList(names, checked):
    lst = QtWidgets.QListWidget()
    lst.setMinimumHeight(110)
    for name in names:
        item = QtWidgets.QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if name in checked else Qt.Unchecked)
        lst.addItem(item)
    return lst


def _checked(lst):
    return [lst.item(i).text() for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]


class ShrinkPolygonsDialog(QtWidgets.QDialog):
    """Parameters for Shrink Polygons (same options as shrink_polygons.py)."""

    def __init__(self, labels, last=None, parent=None, n_selected=0):
        super().__init__(parent)
        last = last or {}
        self.setWindowTitle(self.tr("Shrink Polygons"))
        self.setMinimumWidth(480)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(self.tr(
            "Moves each polygon vertex toward its polygon's centre.\n"
            "Runs on the files open in labelme. Changed JSONs go to a fixed/ folder for review."
        )))

        # scope: open files (reviewed via fixed/) or the selected polygons of this image
        scopeBox = QtWidgets.QGroupBox(self.tr("Apply to"))
        scopeLay = QtWidgets.QVBoxLayout(scopeBox)
        self.filesRadio = QtWidgets.QRadioButton(self.tr("All open files (review in fixed/ folder)"))
        self.selectedRadio = QtWidgets.QRadioButton(
            self.tr("Selected polygon(s) in the current image: %d  (applied directly, Ctrl+Z to undo)") % n_selected)
        self.selectedRadio.setEnabled(n_selected > 0)
        (self.selectedRadio if n_selected > 0 else self.filesRadio).setChecked(True)
        scopeLay.addWidget(self.selectedRadio)
        scopeLay.addWidget(self.filesRadio)
        layout.addWidget(scopeBox)

        names = sorted(labels, key=str.lower)
        form = QtWidgets.QFormLayout()
        self.pixelsSpin = QtWidgets.QDoubleSpinBox()
        self.pixelsSpin.setRange(-500.0, 500.0)
        self.pixelsSpin.setSingleStep(0.5)
        self.pixelsSpin.setDecimals(2)
        self.pixelsSpin.setSuffix(" px")
        self.pixelsSpin.setValue(last.get("pixels", 1.0))
        self.pixelsSpin.setToolTip(self.tr("Positive shrinks (inward), negative grows (outward)"))
        form.addRow(self.tr("Distance (+ shrink, - grow):"), self.pixelsSpin)
        layout.addLayout(form)

        row = QtWidgets.QHBoxLayout()
        self.box1 = box1 = QtWidgets.QGroupBox(self.tr("Labels to shrink (none checked = all)"))
        l1 = QtWidgets.QVBoxLayout(box1)
        self.labelsList = _labelList(names, set(last.get("labels", ())))
        l1.addWidget(self.labelsList)
        box2 = QtWidgets.QGroupBox(self.tr("Ignore labels (overlap check)"))
        l2 = QtWidgets.QVBoxLayout(box2)
        self.ignoreList = _labelList(names, set(last.get("ignore", ())))
        l2.addWidget(self.ignoreList)
        row.addWidget(box1)
        row.addWidget(box2)
        layout.addLayout(row)

        self.overlapCheck = QtWidgets.QCheckBox(self.tr(
            "Overlap: leave vertices untouched that sit in, or next to, a vertex of a different polygon"))
        self.overlapCheck.setChecked(last.get("overlap", False))
        layout.addWidget(self.overlapCheck)
        box2.setEnabled(self.overlapCheck.isChecked())
        self.overlapCheck.toggled.connect(box2.setEnabled)

        sliceRow = QtWidgets.QHBoxLayout()
        self.startSpin = self._sliceSpin(last.get("slice_start"))
        self.endSpin = self._sliceSpin(last.get("slice_end"))
        sliceRow.addWidget(QtWidgets.QLabel(self.tr("Slice range (from file name):")))
        sliceRow.addWidget(self.startSpin)
        sliceRow.addWidget(QtWidgets.QLabel(self.tr("to")))
        sliceRow.addWidget(self.endSpin)
        sliceRow.addStretch(1)
        self.sliceWidgets = [self.startSpin, self.endSpin]
        layout.addLayout(sliceRow)
        self.selectedRadio.toggled.connect(self._scopeChanged)
        self._scopeChanged()

        self.hint = QtWidgets.QLabel()
        layout.addWidget(self.hint)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.okBtn = buttons.button(QtWidgets.QDialogButtonBox.Ok)
        self.okBtn.setText(self.tr("Run"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.pixelsSpin.valueChanged.connect(self._validate)
        self.startSpin.valueChanged.connect(self._validate)
        self.endSpin.valueChanged.connect(self._validate)
        self._validate()

    def _scopeChanged(self, *_):
        files = not self.selectedRadio.isChecked()
        self.box1.setEnabled(files)
        for w in self.sliceWidgets:
            w.setEnabled(files)

    def selectedOnly(self):
        return self.selectedRadio.isChecked()

    def _sliceSpin(self, value):
        spin = QtWidgets.QSpinBox()
        spin.setRange(-1, 99999)
        spin.setSpecialValueText(self.tr("any"))
        spin.setValue(-1 if value is None else int(value))
        return spin

    def _validate(self, *_):
        lo, hi = self.sliceStart(), self.sliceEnd()
        if self.pixels() == 0:
            msg, ok = self.tr("Distance must not be 0."), False
        elif lo is not None and hi is not None and lo > hi:
            msg, ok = self.tr("Slice start is after slice end."), False
        else:
            msg, ok = "", True
        self.hint.setText(msg)
        self.okBtn.setEnabled(ok)

    def pixels(self):
        return self.pixelsSpin.value()

    def labels(self):
        return _checked(self.labelsList)

    def ignoreLabels(self):
        return _checked(self.ignoreList) if self.overlapCheck.isChecked() else []

    def overlap(self):
        return self.overlapCheck.isChecked()

    def sliceStart(self):
        return None if self.startSpin.value() < 0 else self.startSpin.value()

    def sliceEnd(self):
        return None if self.endSpin.value() < 0 else self.endSpin.value()

    def values(self):
        return dict(pixels=self.pixels(), labels=self.labels(), ignore=_checked(self.ignoreList),
                    overlap=self.overlap(), slice_start=self.sliceStart(), slice_end=self.sliceEnd())
