from PyQt5 import QtWidgets


class MirrorSnapDialog(QtWidgets.QDialog):
    """Pick the smaller / bigger polygon labels and the snap tolerance."""

    def __init__(self, labels, small="", big="", tol=2.5, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Mirror Snap"))
        self.setMinimumWidth(420)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(self.tr(
            "Points of the bigger polygon that hug the smaller polygon's edge are\n"
            "moved to its far side. Changed JSONs go to a fixed/ folder for review."
        )))

        names = sorted(labels, key=str.lower)
        form = QtWidgets.QFormLayout()
        self.smallBox = self._labelCombo(names, small)
        self.bigBox = self._labelCombo(names, big)
        self.tolSpin = QtWidgets.QDoubleSpinBox()
        self.tolSpin.setRange(0.1, 100.0)
        self.tolSpin.setSingleStep(0.5)
        self.tolSpin.setDecimals(2)
        self.tolSpin.setSuffix(" px")
        self.tolSpin.setValue(tol)
        self.tolSpin.setToolTip(self.tr(
            "Max distance from the smaller polygon's edge for a big-polygon point to be moved"))
        form.addRow(self.tr("Smaller label:"), self.smallBox)
        form.addRow(self.tr("Bigger label:"), self.bigBox)
        form.addRow(self.tr("Tolerance:"), self.tolSpin)
        layout.addLayout(form)

        self.hint = QtWidgets.QLabel()
        layout.addWidget(self.hint)
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.okBtn = self.buttons.button(QtWidgets.QDialogButtonBox.Ok)
        self.okBtn.setText(self.tr("Run"))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for box in (self.smallBox, self.bigBox):
            box.currentTextChanged.connect(self._validate)
        self._validate()

    def _labelCombo(self, names, current):
        box = QtWidgets.QComboBox()
        box.setEditable(True)
        box.addItems(names)
        box.setCurrentIndex(-1)
        box.setEditText(current)
        box.lineEdit().setPlaceholderText(self.tr("choose or type a label"))
        return box

    def _validate(self, *_):
        small, big = self.smallLabel(), self.bigLabel()
        if not small or not big:
            msg, ok = self.tr("Enter both labels."), False
        elif small == big:
            msg, ok = self.tr("Smaller and bigger labels must differ."), False
        else:
            msg, ok = "", True
        self.hint.setText(msg)
        self.okBtn.setEnabled(ok)

    def smallLabel(self):
        return self.smallBox.currentText().strip()

    def bigLabel(self):
        return self.bigBox.currentText().strip()

    def tolerance(self):
        return self.tolSpin.value()
