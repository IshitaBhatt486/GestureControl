import json

import pytest

from handwave.config.template_manager import TemplateManager


def test_corrupt_primary_template_file_recovers_from_backup(tmp_path):
    path = tmp_path / "templates.json"
    manager = TemplateManager(path)
    manager.create_template("Browser")
    manager.create_template("Presentation")
    path.write_text("not json", encoding="utf-8")

    recovered = TemplateManager(path)

    assert [template.name for template in recovered.list_templates()] == ["General", "Browser"]


def test_create_duplicate_modify_switch_delete_and_persist(tmp_path):
    path = tmp_path / "templates.json"
    manager = TemplateManager(path)
    general = manager.get_active_template()
    presentation = manager.create_template("Presentation", gesture_bindings={"Peace Sign": "next_track"})
    copy = manager.duplicate_template(presentation.template_id, "Presentation copy")
    manager.update_template(copy.template_id, gesture_bindings={"Peace Sign": "previous_track"})
    manager.set_active_template(copy.template_id)
    assert manager.get_active_template().name == "Presentation copy"
    assert manager.get_template(presentation.template_id).gesture_bindings["Peace Sign"].value == "next_track"
    manager.delete_template(presentation.template_id)
    restored = TemplateManager(path)
    assert restored.get_active_template().name == "Presentation copy"
    assert restored.get_template(general.template_id) is not None


def test_import_export_and_old_configuration_migration(tmp_path):
    path = tmp_path / "templates.json"; manager = TemplateManager(path)
    created = manager.create_template("Browser", application_mappings={"browser.exe": "Browser"}, custom_gesture_ids=("custom-1",))
    exported = tmp_path / "browser.json"; manager.export_template(created.template_id, exported)
    imported = manager.import_template(exported)
    assert imported.template_id != created.template_id
    assert imported.application_mappings == {"browser.exe": "Browser"}
    legacy = tmp_path / "legacy.json"; legacy.write_text(json.dumps({"templates": [{"name": "Legacy"}]}), encoding="utf-8")
    assert TemplateManager(legacy).get_active_template().name == "Legacy"


def test_invalid_import_and_last_template_deletion_are_rejected(tmp_path):
    manager = TemplateManager(tmp_path / "templates.json")
    invalid = tmp_path / "invalid.json"; invalid.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError): manager.import_template(invalid)
    with pytest.raises(ValueError): manager.delete_template(manager.get_active_template().template_id)
