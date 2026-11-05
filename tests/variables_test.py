import asyncio
from pathlib import Path

import pytest
from textual.app import App
from textual.widgets import DataTable, Input, Select, TextArea

from krest import krest_tui
from krest.krest_backend import KrestBackend


def test_save_variables_copies_data_and_marks_dirty():
    backend = KrestBackend()
    source = {"payload": {"items": []}}
    backend.save_variables(source)
    source["payload"]["items"].append(1)
    assert backend.file_data["variables"] == {"payload": {"items": []}}
    assert backend.dirty_bit is True
    backend.save_variables({})
    assert backend.file_data["variables"] == {}


def test_save_variables_rejects_invalid_input():
    backend = KrestBackend()
    backend.dirty_bit = False
    with pytest.raises(TypeError):
        backend.save_variables([])
    assert backend.file_data["variables"] == {}
    assert backend.dirty_bit is False


def test_legacy_file_defaults_and_variable_persistence(tmp_path):
    backend = KrestBackend()
    path = str(tmp_path / "legacy.krest")
    backend.create_file(path, "secret")
    backend.file_data.pop("variables")
    backend.save_file()
    backend.load_file()
    assert backend.file_data["variables"] == {}
    assert backend.dirty_bit is False
    backend.save_variables({"count": "3", "enabled": False})
    backend.save_file()
    backend.unload_file()
    backend.select_file(path, "secret")
    backend.load_file()
    assert backend.file_data["variables"] == {"count": "3", "enabled": False}
    backend.unload_file()


@pytest.mark.parametrize("loaded", [False, True])
def test_variables_binding_requires_open_file(tmp_path, loaded):
    path = str(tmp_path / "project.krest")
    KrestBackend().create_file(path, "secret")

    async def check():
        app = krest_tui.KrestTui(file_path=path if loaded else None,
                                 file_password="secret" if loaded else None)
        async with app.run_test(size=(120, 50)) as pilot:
            await pilot.pause()
            assert app.check_action("edit_variables", ()) is loaded
            await pilot.press("v")
            await pilot.pause()
            assert isinstance(app.screen, krest_tui.Variables) is loaded

    asyncio.run(check())


def test_variables_add_rename_delete_and_cancel():
    async def check():
        backend = KrestBackend()
        backend.file_data.pop("variables")
        backend.dirty_bit = False
        app = App(css_path=Path(krest_tui.__file__).with_suffix(".tcss"))
        async with app.run_test(size=(120, 50)) as pilot:
            dialog = krest_tui.Variables(backend)
            app.push_screen(dialog)
            await pilot.pause()
            table = dialog.query_one(DataTable)
            assert table.row_count == 0
            dialog.action_edit_variable()
            dialog.action_delete_variable()
            assert app.screen is dialog
            await pilot.press("a")
            await pilot.pause()
            editor = app.screen
            editor.query_one("#variable-name", Input).value = "count"
            editor.query_one(TextArea).load_text("3")
            await pilot.click("#variable-save-btn")
            await pilot.pause()
            assert backend.file_data["variables"] == {"count": "3"}
            assert backend.dirty_bit is True
            assert table.row_count == 1

            await pilot.press("m")
            await pilot.pause()
            editor = app.screen
            assert editor.query_one(TextArea).text == "3"
            editor.query_one(Input).value = "total"
            editor.query_one(TextArea).load_text("4")
            await pilot.click("#variable-save-btn")
            await pilot.pause()
            assert backend.file_data["variables"] == {"total": "4"}

            await pilot.press("m")
            await pilot.pause()
            app.screen.query_one(TextArea).load_text("discarded")
            await pilot.click("#variable-cancel-btn")
            await pilot.pause()
            assert backend.file_data["variables"] == {"total": "4"}

            await pilot.press("d")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()
            assert backend.file_data["variables"] == {"total": "4"}
            await pilot.press("d")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()
            assert backend.file_data["variables"] == {}
            assert table.row_count == 0
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is not dialog

    asyncio.run(check())


def test_variable_dialogs_fit_standard_terminal():
    async def check():
        app = App(css_path=Path(krest_tui.__file__).with_suffix(".tcss"))
        async with app.run_test(size=(80, 24)) as pilot:
            app.push_screen(krest_tui.Variables(KrestBackend()))
            await pilot.pause()
            for selector in ("#variables_data_table", "#variables-close-btn", "#variables-add-btn"):
                widget = app.screen.query_one(selector)
                assert widget.region.y >= 0 and widget.region.bottom <= 24
            await pilot.press("a")
            await pilot.pause()
            for selector in ("#variable-name", "#variable-value", "#variable-save-btn"):
                widget = app.screen.query_one(selector)
                assert widget.region.y >= 0 and widget.region.bottom <= 24
            # Character bindings from the parent must not intercept input.
            await pilot.click("#variable-name")
            await pilot.press("v", "a", "r")
            assert app.screen.query_one(Input).value == "var"

    asyncio.run(check())


@pytest.mark.parametrize("value", ["[bold]literal[/bold]", "", False, 3, None, {"items": [1]}])
def test_variable_editor_preserves_value_types(value):
    async def check():
        app = App(css_path=Path(krest_tui.__file__).with_suffix(".tcss"))
        saved = []
        async with app.run_test(size=(120, 50)) as pilot:
            app.push_screen(krest_tui.VariableEditor("value", value, ["value"]), saved.append)
            await pilot.pause()
            await pilot.click("#variable-save-btn")
            await pilot.pause()
            assert saved == [("value", value)]
            assert type(saved[0][1]) is type(value)

    asyncio.run(check())


@pytest.mark.parametrize("name,value,value_type", [
    ("", "text", "text"),
    ("1invalid", "text", "text"),
    ("has-dash", "text", "text"),
    ("duplicate", "text", "text"),
    ("valid", "{invalid json}", "json"),
])
def test_variable_editor_rejects_invalid_fields(name, value, value_type):
    async def check():
        app = App(css_path=Path(krest_tui.__file__).with_suffix(".tcss"))
        saved = []
        async with app.run_test(size=(120, 50)) as pilot:
            editor = krest_tui.VariableEditor(existing_names=["duplicate"])
            app.push_screen(editor, saved.append)
            await pilot.pause()
            editor.query_one(Input).value = name
            editor.query_one(TextArea).load_text(value)
            editor.query_one(Select).value = value_type
            await pilot.click("#variable-save-btn")
            await pilot.pause()
            assert app.screen is editor
            assert saved == []

    asyncio.run(check())
