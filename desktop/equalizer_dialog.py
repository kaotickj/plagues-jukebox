"""Equalizer editor for K-Tunes.

The UI deliberately disables processing until a compatible DSP playback engine
is installed and selected. It never pretends that Qt Multimedia applies EQ.
"""
from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSlider, QVBoxLayout,
)

from audio_equalizer import BANDS, PRESETS, EqualizerSettings
from vlc_equalizer_engine import availability as vlc_availability


class EqualizerDialog(QDialog):
    def __init__(self, settings_store, parent=None, apply_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Equalizer")
        self.setMinimumWidth(690)
        self.store = settings_store
        self.apply_callback = apply_callback
        self.custom = self._read_custom()
        self.state = self._read_state()
        self.sliders = []
        self.values = []
        layout = QVBoxLayout(self)
        vlc_status = vlc_availability()
        self.notice = QLabel(
            ("VLC playback is active. Enable the equalizer below to hear changes."
             if apply_callback is not None else
             ("VLC is installed, but Qt playback is active. Select Tools → Use VLC audio engine, "
              "then restart K-Tunes to enable EQ." if vlc_status.available else
              "VLC DSP unavailable: " + vlc_status.reason + ". Install VLC and restart K-Tunes."))
        )
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        header = QHBoxLayout()
        self.enabled = QCheckBox("Enable equalizer")
        self.enabled.setObjectName("EqualizerEnableCheckbox")
        self.enabled.setStyleSheet("QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #8e9ba7; border-radius: 4px; background: #20262d; } QCheckBox::indicator:checked { background: #39d98a; border-color: #39d98a; image: none; } QCheckBox { spacing: 10px; padding: 6px; }")
        self.enabled.setChecked(self.state.enabled)
        self.enabled.setEnabled(apply_callback is not None)
        self.enabled.setToolTip("Available only when VLC audio engine is active. Restart after switching engines.")
        self.enabled.toggled.connect(self.changed)
        header.addWidget(self.enabled)
        header.addWidget(QLabel("Preset"))
        self.preset = QComboBox()
        self.preset.addItems(list(PRESETS) + sorted(self.custom))
        self.preset.currentTextChanged.connect(self.load_preset)
        header.addWidget(self.preset, 1)
        layout.addLayout(header)
        grid = QGridLayout()
        for col, name in enumerate(["Preamp"] + [self._label(hz) for hz in BANDS]):
            grid.addWidget(QLabel(name), 0, col, alignment=Qt.AlignmentFlag.AlignCenter)
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-12, 12)
            slider.setTickInterval(3)
            slider.setTickPosition(QSlider.TickPosition.TicksBothSides)
            slider.setValue(round(self.state.preamp_db if col == 0 else self.state.gains_db[col-1]))
            slider.valueChanged.connect(self.changed)
            grid.addWidget(slider, 1, col, alignment=Qt.AlignmentFlag.AlignCenter)
            value = QLabel(f"{slider.value():+d} dB")
            grid.addWidget(value, 2, col, alignment=Qt.AlignmentFlag.AlignCenter)
            self.sliders.append(slider)
            self.values.append(value)
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        for name, callback in [
            ("Save custom preset", self.save_custom),
            ("Delete custom preset", self.delete_custom),
            ("Reset to flat", self.reset),
            ("Close", self.accept),
        ]:
            button = QPushButton(name)
            button.clicked.connect(callback)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._refresh_labels()

    @staticmethod
    def _label(hz):
        return f"{hz // 1000}k" if hz >= 1000 else str(hz)

    def _read_state(self):
        try:
            return EqualizerSettings.from_dict(json.loads(str(self.store.value("audio/equalizer", "{}"))))
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return EqualizerSettings()

    def _read_custom(self):
        try:
            data = json.loads(str(self.store.value("audio/custom_presets", "{}")))
            if not isinstance(data, dict):
                return {}
            return {str(name): list(map(float, gains)) for name, gains in data.items()
                    if isinstance(gains, list) and len(gains) == len(BANDS)
                    and all(isinstance(g, (int, float)) and -12 <= g <= 12 for g in gains)}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _refresh_labels(self):
        for slider, value in zip(self.sliders, self.values):
            value.setText(f"{slider.value():+d} dB")

    def changed(self, *_):
        self._refresh_labels()
        self.state = EqualizerSettings(
            self.enabled.isChecked(), self.sliders[0].value(),
            [slider.value() for slider in self.sliders[1:]],
        )
        self.store.setValue("audio/equalizer", json.dumps(self.state.to_dict()))
        if self.apply_callback is not None:
            self.apply_callback(self.state)

    def load_preset(self, name):
        gains = PRESETS.get(name, self.custom.get(name))
        if gains is None:
            return
        for slider, gain in zip(self.sliders[1:], gains):
            slider.setValue(round(gain))
        self.changed()

    def reset(self):
        self.preset.setCurrentText("Flat")
        self.load_preset("Flat")
        self.sliders[0].setValue(0)

    def save_custom(self):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Save EQ preset", "Preset name:")
        name = name.strip()
        if not ok or not name:
            return
        if name in PRESETS:
            QMessageBox.warning(self, "Reserved name", "Choose a different name.")
            return
        self.custom[name] = [slider.value() for slider in self.sliders[1:]]
        self.store.setValue("audio/custom_presets", json.dumps(self.custom))
        if self.preset.findText(name) < 0:
            self.preset.addItem(name)
        self.preset.setCurrentText(name)

    def delete_custom(self):
        name = self.preset.currentText()
        if name not in self.custom:
            return
        del self.custom[name]
        self.store.setValue("audio/custom_presets", json.dumps(self.custom))
        self.preset.removeItem(self.preset.currentIndex())
