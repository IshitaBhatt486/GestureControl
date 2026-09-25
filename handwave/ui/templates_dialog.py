"""User-facing manager for reusable HandWave templates."""

from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QMessageBox, QPushButton, QVBoxLayout

from handwave.config.settings_manager import AppSettings
from handwave.config.template_manager import TemplateManager
from handwave.ui.settings_dialog import SettingsDialog


class TemplatesDialog(QDialog):
    def __init__(self, manager: TemplateManager, global_settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.manager, self.global_settings = manager, global_settings
        self.setWindowTitle("HandWave Templates")
        self.setMinimumWidth(480)
        self.current = QLabel()
        self.selector = QComboBox()
        self.selector.currentIndexChanged.connect(self._select)
        buttons = {name: QPushButton(label) for name, label in {
            "create": "Create Template", "duplicate": "Duplicate Template", "edit": "Edit Template", "delete": "Delete Template", "import": "Import", "export": "Export",
        }.items()}
        buttons["create"].clicked.connect(self._create); buttons["duplicate"].clicked.connect(self._duplicate)
        buttons["edit"].clicked.connect(self._edit); buttons["delete"].clicked.connect(self._delete)
        buttons["import"].clicked.connect(self._import); buttons["export"].clicked.connect(self._export)
        layout = QVBoxLayout(self); layout.addWidget(self.current); layout.addWidget(self.selector)
        for pair in (("create", "duplicate"), ("edit", "delete"), ("import", "export")):
            row = QHBoxLayout(); [row.addWidget(buttons[key]) for key in pair]; layout.addLayout(row)
        self._refresh()

    def _active_id(self) -> str: return str(self.selector.currentData())
    def _refresh(self) -> None:
        self.selector.blockSignals(True); self.selector.clear()
        for template in self.manager.list_templates(): self.selector.addItem(template.name, template.template_id)
        active = self.manager.get_active_template(); self.selector.setCurrentIndex(self.selector.findData(active.template_id)); self.selector.blockSignals(False)
        self.current.setText(f"Current Template: {active.name}")
    def _select(self) -> None:
        if self.selector.currentIndex() >= 0: self.manager.set_active_template(self._active_id()); self._refresh()
    def _named(self, title: str, default: str = "") -> str | None:
        value, ok = QInputDialog.getText(self, title, "Name", text=default); return value.strip() if ok and value.strip() else None
    def _create(self) -> None:
        if name := self._named("Create Template"): self.manager.create_template(name); self._refresh()
    def _duplicate(self) -> None:
        source = self.manager.get_template(self._active_id())
        if name := self._named("Duplicate Template", f"{source.name} (copy)"): self.manager.duplicate_template(source.template_id, name); self._refresh()
    def _edit(self) -> None:
        template = self.manager.get_template(self._active_id()); resolved = template.resolve(self.global_settings)
        dialog = SettingsDialog(resolved, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            self.manager.update_template(template.template_id, gesture_sensitivity=values["gesture_sensitivity"], gesture_cooldown=values["gesture_cooldown"], gesture_bindings=values["gesture_bindings"], enabled_gestures=values["enabled_gestures"])
            self._refresh()
    def _delete(self) -> None:
        try: self.manager.delete_template(self._active_id())
        except ValueError as exc: QMessageBox.warning(self, "Templates", str(exc))
        self._refresh()
    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import Template", filter="HandWave template (*.json)")
        if path: self.manager.import_template(path); self._refresh()
    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Template", "template.json", "HandWave template (*.json)")
        if path: self.manager.export_template(self._active_id(), path)
