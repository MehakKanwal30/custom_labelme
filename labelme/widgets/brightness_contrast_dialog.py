import PIL.Image
import PIL.ImageEnhance
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QImage


class BrightnessContrastDialog(QtWidgets.QDialog):
    _base_value = 50

    def __init__(self, img, callback, parent=None, keep_setter=None):
        super(BrightnessContrastDialog, self).__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Brightness/Contrast")

        sliders = {}
        layouts = {}
        for title in ["Brightness:", "Contrast:"]:
            layout = QtWidgets.QHBoxLayout()
            title_label = QtWidgets.QLabel(self.tr(title))
            title_label.setFixedWidth(75)
            layout.addWidget(title_label)
            #
            slider = QtWidgets.QSlider(Qt.Horizontal)  # type: ignore[attr-defined]
            slider.setRange(0, 3 * self._base_value)
            slider.setValue(self._base_value)
            layout.addWidget(slider)
            #
            value_label = QtWidgets.QLabel(f"{slider.value() / self._base_value:.2f}")
            value_label.setAlignment(Qt.AlignRight)  # type: ignore[attr-defined]
            layout.addWidget(value_label)
            #

            slider.valueChanged.connect(self.onNewValue)
            slider.valueChanged.connect(
                lambda _,
                value_label_=value_label,
                slider_=slider: value_label_.setText(
                    f"{slider_.value() / self._base_value:.2f}"
                )
            )

            #EDITED BRIGHTNESS
            # slider.valueChanged.connect(
            #     lambda value, s=slider, l=value_label: l.setText(f"{s.value() / self._base_value:.2f}")
            # )
            # slider.sliderReleased.connect(self.onNewValue)
    
            #END

            # slider.valueChanged.connect(self.onNewValue)
            # slider.valueChanged.connect(
            #     lambda: value_label.setText(f"{slider.value() / self._base_value:.2f}")
            # )

            layouts[title] = layout
            sliders[title] = slider

        self.slider_brightness = sliders["Brightness:"]
        self.slider_contrast = sliders["Contrast:"]
        del sliders

        layout = QtWidgets.QVBoxLayout()  # type: ignore[assignment]
        layout.addLayout(layouts["Brightness:"])
        layout.addLayout(layouts["Contrast:"])
        del layouts

        #EDITED BRIGHTNESS
        button_layout = QtWidgets.QHBoxLayout()
        self.keep_brightness_btn = QtWidgets.QCheckBox("Keep Brightness")
        if keep_setter is not None:
            self.keep_brightness_btn.toggled.connect(keep_setter)
        button_layout.addWidget(self.keep_brightness_btn)
        button_layout.addStretch()
        reset_button = QtWidgets.QPushButton("Reset")
        reset_button.clicked.connect(self.resetValues)
        button_layout.addWidget(reset_button)
        layout.addLayout(button_layout)

        # Preset slots: [brightness_value, contrast_value] or None if unset
        self._settings = QSettings("labelme", "BrightnessContrastDialog")
        self._presets = [None, None]
        self._preset_btns = []
        for i in range(2):
            b = self._settings.value(f"preset_{i}_brightness")
            c = self._settings.value(f"preset_{i}_contrast")
            if b is not None and c is not None:
                self._presets[i] = (int(b), int(c))

            preset_layout = QtWidgets.QHBoxLayout()
            apply_btn = QtWidgets.QPushButton(f"Preset {i + 1}")
            apply_btn.setEnabled(self._presets[i] is not None)
            apply_btn.clicked.connect(lambda checked, idx=i: self._applyPreset(idx))
            save_btn = QtWidgets.QPushButton(f"Save to Preset {i + 1}")
            save_btn.clicked.connect(lambda checked, idx=i: self._savePreset(idx))
            preset_layout.addWidget(apply_btn)
            preset_layout.addWidget(save_btn)
            layout.addLayout(preset_layout)
            self._preset_btns.append(apply_btn)
        #END

        self.setLayout(layout)

        assert isinstance(img, PIL.Image.Image)
        self.img = img
        self.callback = callback

    def onNewValue(self, _=None):
        brightness = self.slider_brightness.value() / self._base_value
        contrast = self.slider_contrast.value() / self._base_value

        #EDITED BRIGHTNESS
        img = self.img.copy()
        #END

        # img = self.img
        if brightness != 1:
            img = PIL.ImageEnhance.Brightness(img).enhance(brightness)
        if contrast != 1:
            img = PIL.ImageEnhance.Contrast(img).enhance(contrast)

        #EDITED BRIGHTNESS
        img = img.convert("RGB")
        #END

        qimage = QImage(
            img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888
        )
        self.callback(qimage)

    #EDITED BRIGHTNESS
    def resetValues(self):
        self.slider_brightness.setValue(self._base_value)
        self.slider_contrast.setValue(self._base_value)

        # Reset image to original
        img = self.img.copy().convert("RGB")
        qimage = QImage(
            img.tobytes(), img.width, img.height, img.width * 3, QImage.Format_RGB888
        )
        if not qimage.isNull():
            self.callback(qimage)

    def setImage(self, img):
        """Called when a new image is loaded — updates the dialog's base image."""
        self.img = img
        # Re-apply current brightness/contrast to the new image
        self.onNewValue()

    def _savePreset(self, idx):
        b = self.slider_brightness.value()
        c = self.slider_contrast.value()
        self._presets[idx] = (b, c)
        self._settings.setValue(f"preset_{idx}_brightness", b)
        self._settings.setValue(f"preset_{idx}_contrast", c)
        self._preset_btns[idx].setEnabled(True)

    def _applyPreset(self, idx):
        if self._presets[idx] is None:
            return
        brightness_val, contrast_val = self._presets[idx]
        self.slider_brightness.setValue(brightness_val)
        self.slider_contrast.setValue(contrast_val)

    #END