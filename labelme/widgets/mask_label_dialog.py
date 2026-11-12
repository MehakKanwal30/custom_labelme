import random

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt


class MaskLabelDialog(QtWidgets.QDialog):
    """Review / assign the mask value (1-255) for every polygon label.

    labels:   {label: shape count}
    defaults: {label: value or None}  (value from config or previously saved)
    A value of 0 (shown as "unassigned") means no value yet; Generate stays
    disabled until every label has one.
    """

    COL_LABEL, COL_COUNT, COL_VALUE, COL_SOURCE = range(4)

    def __init__(self, labels, defaults, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Mask values"))
        self.setMinimumSize(520, 360)
        self._defaults = defaults
        self._spins = {}
        self._sources = {}

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(self.tr(
            "Pixel value written into the mask for each polygon label.\n"
            "Labels without a value must be assigned before generating."
        )))

        names = sorted(labels, key=lambda l: (defaults.get(l) is not None, l.lower()))
        self.table = QtWidgets.QTableWidget(len(names), 4)
        self.table.setHorizontalHeaderLabels(
            [self.tr("Label"), self.tr("Shapes"), self.tr("Mask value"), self.tr("Status")])
        self.table.verticalHeader().hide()
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_LABEL, QtWidgets.QHeaderView.Stretch)
        for c in (self.COL_COUNT, self.COL_VALUE, self.COL_SOURCE):
            hdr.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
        for row, label in enumerate(names):
            item = QtWidgets.QTableWidgetItem(label)
            self.table.setItem(row, self.COL_LABEL, item)
            cnt = QtWidgets.QTableWidgetItem(str(labels[label]))
            cnt.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, self.COL_COUNT, cnt)
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 255)
            spin.setSpecialValueText(self.tr("unassigned"))
            default = defaults.get(label)
            spin.setValue(int(default) if default else 0)
            spin.valueChanged.connect(lambda _v, l=label: self._refresh(l))
            self.table.setCellWidget(row, self.COL_VALUE, spin)
            self.table.setItem(row, self.COL_SOURCE, QtWidgets.QTableWidgetItem())
            self._spins[label] = spin
            self._sources[label] = row
            self._refresh(label)
        layout.addWidget(self.table)

        self.summary = QtWidgets.QLabel()
        layout.addWidget(self.summary)

        btnRow = QtWidgets.QHBoxLayout()
        self.randomBtn = QtWidgets.QPushButton(self.tr("Random Assign"))
        self.randomBtn.setToolTip(self.tr("Give every unassigned label a random unused value"))
        self.randomBtn.clicked.connect(self.randomAssign)
        btnRow.addWidget(self.randomBtn)
        btnRow.addStretch(1)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.okBtn = self.buttons.button(QtWidgets.QDialogButtonBox.Ok)
        self.okBtn.setText(self.tr("Generate"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        btnRow.addWidget(self.buttons)
        layout.addLayout(btnRow)
        self._updateState()

    def _refresh(self, label):
        spin = self._spins[label]
        item = self.table.item(self._sources[label], self.COL_SOURCE)
        default = self._defaults.get(label)
        value = spin.value()
        if value == 0:
            text, color = self.tr("needs a value"), QtGui.QColor(200, 60, 60)
        elif default and value == int(default):
            text, color = self.tr("default"), None
        else:
            text, color = self.tr("custom"), QtGui.QColor(60, 140, 200)
        item.setText(text)
        item.setForeground(QtGui.QBrush(color) if color else QtGui.QBrush())
        self._updateState()

    def _updateState(self):
        if not hasattr(self, "okBtn"):
            return  # still building the table
        missing = [l for l, s in self._spins.items() if s.value() == 0]
        self.okBtn.setEnabled(not missing)
        self.randomBtn.setEnabled(bool(missing))
        self.summary.setText(
            self.tr("%d label(s) still need a value.") % len(missing) if missing
            else self.tr("All labels have a value."))

    def randomAssign(self):
        used = {s.value() for s in self._spins.values() if s.value()}
        free = [v for v in range(1, 256) if v not in used]
        random.shuffle(free)
        for label, spin in self._spins.items():
            if spin.value() == 0 and free:
                spin.setValue(free.pop())

    def values(self):
        return {label: spin.value() for label, spin in self._spins.items()}
