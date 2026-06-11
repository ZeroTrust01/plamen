from __future__ import annotations

from plamen_langgraph.plamen_lg.config import build_config


def test_default_scratchpad_is_langgraph_specific(tmp_path):
    project = tmp_path / "project"
    project.mkdir()

    config = build_config(project)

    assert config.scratchpad == str(project / ".lg_scratchpad")
    assert config.db_path == str(project / ".lg_scratchpad" / "plamen_lg.sqlite")


def test_explicit_scratchpad_override_is_respected(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    scratchpad = tmp_path / "custom-scratch"

    config = build_config(project, scratchpad=scratchpad)

    assert config.scratchpad == str(scratchpad.resolve())
    assert config.db_path == str(scratchpad.resolve() / "plamen_lg.sqlite")
