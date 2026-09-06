"""Shared test configuration and suite classification."""

from __future__ import annotations

import pytest


UI_MODULES = {"test_main_window.py", "test_settings_dialog.py"}
INTEGRATION_MODULES = {
    "test_camera_manager.py",
    "test_integration_configuration.py",
    "test_release_config.py",
    "test_startup_manager.py",
}
BENCHMARK_MODULES = {"test_pipeline_benchmark.py", "test_performance_pipeline.py"}


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Assign every test to one explicit framework layer by module purpose."""
    for item in items:
        filename = item.path.name
        if filename in BENCHMARK_MODULES:
            marker = pytest.mark.benchmark
        elif filename in UI_MODULES:
            marker = pytest.mark.ui
        elif filename in INTEGRATION_MODULES:
            marker = pytest.mark.integration
        else:
            marker = pytest.mark.unit
        item.add_marker(marker)
