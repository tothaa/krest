import asyncio
import logging
from unittest.mock import patch

import pytest
from textual.widgets import Input, Static

from krest import krest_tui
from krest.krest_backend import KrestBackend
from krest.translations import t


@pytest.mark.parametrize("kind", ["body", "multipart", "response"])
@pytest.mark.parametrize("outcome", ["save", "overwrite", "exists", "cancel", "empty"])
def test_history_binary_downloads(tmp_path, kind, outcome):
    import base64
    from copy import deepcopy
    from textual.app import App
    from textual.widgets import Button, Checkbox, TextArea

    async def check():
        content = b"" if outcome == "empty" else b"\x00\xffhistory bytes"
        encoded = base64.b64encode(content).decode("ascii")
        endpoint = {"body_type": "TEXT", "body": "request", "response_type": "TEXT"}
        record = {"endpoint": endpoint, "response_body": "response"}
        if kind == "body":
            endpoint.update(body_type="BINARY", body=encoded)
            selector = "#history-body-download"
        elif kind == "multipart":
            endpoint.update(body_type="MULTIPART", body={
                "description": {"value_type": "TEXT", "value": "[bold]literal text[/bold]"},
                "attachment [1]": {"filename": "data.bin", "value_type": "BINARY",
                                   "mime_type": "application/octet-stream", "value": encoded},
            })
            selector = "#history-part-1-download"
        else:
            endpoint["response_type"] = "BINARY"
            record.update(response_content_base64=encoded, response_body="must not display binary response")
            selector = "#history-response-download"
        original = deepcopy(record)
        viewer = krest_tui.CallHistoryDetailsViewer(record)
        app = App(css_path=krest_tui.Path(krest_tui.__file__).with_suffix(".tcss"))
        destination = tmp_path / "saved.bin"
        if outcome in ("overwrite", "exists"):
            destination.write_bytes(b"existing")
        async with app.run_test(size=(100, 35)) as pilot:
            app.push_screen(viewer)
            await pilot.pause()
            assert not viewer.query(Input)
            assert all(area.read_only for area in viewer.query(TextArea))
            rendered = "\n".join(
                [area.text for area in viewer.query(TextArea)]
                + [str(widget.render()) for widget in viewer.query("Label, Pretty")]
            )
            if encoded:
                assert encoded not in rendered
            assert "must not display binary response" not in rendered
            assert len(viewer.query(krest_tui.HistoryDownloadButton)) == 1
            if kind == "multipart":
                assert "data.bin" in rendered
                assert "application/octet-stream" in rendered
                assert "[bold]literal text[/bold]" in rendered
            viewer.query_one(selector, Button).press()
            await pilot.pause()
            dialog = app.screen
            assert isinstance(dialog, krest_tui.BodyFileDialog)
            assert dialog.download
            if outcome == "cancel":
                dialog.action_cancel_dialog()
                await pilot.pause()
                assert not destination.exists()
            else:
                dialog.query_one("#body-directory-name", Input).value = str(tmp_path)
                dialog.query_one("#body-file-name", Input).value = destination.name
                dialog.query_one("#body-overwrite", Checkbox).value = outcome == "overwrite"
                with patch.object(viewer, "notify") as notify:
                    dialog.confirm_file()
                    await pilot.pause()
                    assert notify.call_args.kwargs["severity"] == ("error" if outcome == "exists" else "information")
                assert destination.read_bytes() == (b"existing" if outcome == "exists" else content)
            assert app.screen is viewer
            assert record == original
            assert viewer.history_record == original

    asyncio.run(check())


@pytest.mark.parametrize("record", [
    {},
    {"endpoint": None, "credential": None},
    {"response_body": "[bold]response[/bold]", "response_content_base64": "ignored",
     "response_headers": {"X-Test": "header"}, "cookies": [{"name": "cookie"}],
     "endpoint": {"body": "[bold]request[/bold]"}},
    {"endpoint": {"body_type": "JSON", "body": {"test": [1, 2]}}},
])
def test_history_details_read_only_and_legacy_records(record):
    from copy import deepcopy
    from textual.app import App
    from textual.widgets import TextArea

    async def check():
        original = deepcopy(record)
        viewer = krest_tui.CallHistoryDetailsViewer(record)
        app = App(css_path=krest_tui.Path(krest_tui.__file__).with_suffix(".tcss"))
        async with app.run_test(size=(100, 35)) as pilot:
            app.push_screen(viewer)
            await pilot.pause()
            assert not viewer.query(Input)
            assert not viewer.query(krest_tui.HistoryDownloadButton)
            assert viewer.query_one("#history-response-body", TextArea).text == (record.get("response_body") or "")
            for area in viewer.query(TextArea):
                assert area.read_only
                before = area.text
                area.focus()
                await pilot.press("ctrl+a", "x", "backspace", "enter")
                assert area.text == before
            assert record == original
            viewer.query_one("#history-detail-cancel-btn").press()
            await pilot.pause()
            assert app.screen is not viewer

    asyncio.run(check())


@pytest.mark.parametrize("old, new, again, accepted", [
    ("secret", "changed", "changed", True),
    ("secret", "", "", True),
    ("wrong", "changed", "changed", False),
    ("secret", "changed", "different", False),
])
def test_password_dialog_validation(encrypted_file, old, new, again, accepted):
    async def check():
        app = krest_tui.KrestTui(file_path=encrypted_file, file_password="secret")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            dialog = app.screen
            assert isinstance(dialog, krest_tui.ChangePassword)
            for selector, value in [("#old-password", old), ("#new-password", new), ("#new-password-again", again)]:
                field = dialog.query_one(selector, Input)
                assert field.password
                field.value = value
            await pilot.click("#password-ok-btn")
            assert app.backend.file_password == (new if accepted else "secret")
            assert bool(app.backend.dirty_bit) == accepted
            assert (app.screen is dialog) == (not accepted)
            if accepted:
                app.action_save_file()
        if accepted:
            reloaded = KrestBackend()
            reloaded.select_file(encrypted_file, new)
            reloaded.load_file()
            reloaded.unload_file()

    asyncio.run(check())


@pytest.mark.parametrize("cancel", ["button", "escape"])
def test_password_dialog_cancel(encrypted_file, cancel):
    async def check():
        app = krest_tui.KrestTui(file_path=encrypted_file, file_password="secret")
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            app.screen.query_one("#old-password", Input).value = "secret"
            app.screen.query_one("#new-password", Input).value = "changed"
            app.screen.query_one("#new-password-again", Input).value = "changed"
            if cancel == "button":
                await pilot.click("#password-cancel-btn")
            else:
                await pilot.press("escape")
            assert not isinstance(app.screen, krest_tui.ChangePassword)
            assert app.backend.file_password == "secret"
            assert not app.backend.dirty_bit

    asyncio.run(check())


def test_password_dialog_requires_loaded_file():
    async def check():
        app = krest_tui.KrestTui()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("ctrl+u")
            assert not isinstance(app.screen, krest_tui.ChangePassword)

    asyncio.run(check())


@pytest.fixture(autouse=True)
def restore_logging():
    disabled_level = logging.root.manager.disable
    yield
    logging.disable(disabled_level)


@pytest.mark.parametrize("loaded", [False, True])
def test_command_palette_exposes_available_bindings(encrypted_file, loaded):
    async def check():
        app = krest_tui.KrestTui(
            file_path=encrypted_file if loaded else None,
            file_password="secret" if loaded else None,
        )
        async with app.run_test() as pilot:
            await pilot.pause()
            commands = {command.title: command for command in app.get_system_commands(app.screen)}
            for binding in krest_tui.Binding.make_bindings(app.BINDINGS):
                if app.check_action(binding.action, ()):
                    assert binding.description in commands
                else:
                    assert binding.description not in commands
            if loaded:
                command = commands["Change Password"]
                assert "ctrl+u" in command.help
                await command.callback()
                await pilot.pause()
                assert isinstance(app.screen, krest_tui.ChangePassword)
                dialog_commands = {
                    command.title: command for command in app.get_system_commands(app.screen)
                }
                await dialog_commands[t(t.CANCEL)].callback()
                await pilot.pause()
                assert not isinstance(app.screen, krest_tui.ChangePassword)

    asyncio.run(check())


@pytest.fixture
def encrypted_file(tmp_path):
    path = str(tmp_path / "project.krest")
    backend = KrestBackend()
    backend.create_file(path, "secret")
    return path


def test_file_lock_lifecycle(encrypted_file):
    lock = krest_tui.Path(encrypted_file + ".krest.lock")
    backend = KrestBackend()
    backend.select_file(encrypted_file, "secret")
    backend.load_file()
    assert lock.read_bytes() == b""
    other = KrestBackend()
    other.select_file(encrypted_file, "secret")
    with pytest.raises(FileExistsError, match="another instance"):
        other.load_file()
    backend.dirty_bit = True
    backend.unload_file()
    assert not lock.exists()
    assert backend.file_data == {}
    assert backend.dirty_bit is False
    backend.unload_file()
    other.load_file()
    other.unload_file()


def test_close_switch_and_locked_file_notification(encrypted_file, tmp_path):
    async def check():
        lock = krest_tui.Path(encrypted_file + ".krest.lock")
        other_path = str(tmp_path / "other.krest")
        KrestBackend().create_file(other_path, "secret")
        other_lock = krest_tui.Path(other_path + ".krest.lock")
        app = krest_tui.KrestTui(file_path=encrypted_file, file_password="secret")
        async with app.run_test() as pilot:
            await pilot.pause()
            app.perform_load(other_path, "secret")
            assert not lock.exists()
            assert other_lock.exists()
            lock.touch()
            app.perform_load(encrypted_file, "secret")
            await pilot.pause()
            assert lock.exists()
            assert not other_lock.exists()
            assert app.backend.file_path is None
            assert any(note.severity == "error" and "another instance" in note.message
                       for note in app._notifications)
            lock.unlink()
            app.perform_load(encrypted_file, "secret")
            await pilot.press("ctrl+w")
            assert not lock.exists()
            assert app.backend.file_data == {}
            app.perform_load(encrypted_file, "secret")
            app.action_quit_krest()
        assert not lock.exists()

    asyncio.run(check())


def test_password_prompt_releases_lock(encrypted_file):
    with patch.object(krest_tui.getpass, "getpass", return_value="secret"):
        assert krest_tui.prompt_file_password(encrypted_file) == "secret"
    assert not krest_tui.Path(encrypted_file + ".krest.lock").exists()


def test_new_file_preserves_locked_destination(encrypted_file):
    owner = KrestBackend()
    owner.select_file(encrypted_file, "secret")
    owner.load_file()
    original = krest_tui.Path(encrypted_file).read_bytes()
    lock = krest_tui.Path(encrypted_file + ".krest.lock")
    app = krest_tui.KrestTui()

    def select_file(screen, callback=None):
        callback((encrypted_file, "secret") if isinstance(screen, krest_tui.OpenFileDialog) else True)

    try:
        with patch.object(app, "push_screen", side_effect=select_file), \
                patch.object(app, "action_refresh_content"), patch.object(app, "notify") as notify:
            app.action_new_file()
        assert krest_tui.Path(encrypted_file).read_bytes() == original
        assert notify.call_args.kwargs["severity"] == "error"
        assert "another instance" in notify.call_args.args[0]
        app.on_unmount()
        assert lock.exists()
    finally:
        owner.unload_file()


@pytest.mark.parametrize("action", ["open", "new"])
def test_failed_unload_preserves_current_file(encrypted_file, tmp_path, action):
    app = krest_tui.KrestTui()
    app.backend.select_file(encrypted_file, "secret")
    app.backend.load_file()
    app.backend.dirty_bit = True
    data = app.backend.file_data
    destination = str(tmp_path / "next.krest")

    def select_file(screen, callback=None):
        callback((destination, "secret") if isinstance(screen, krest_tui.OpenFileDialog) else True)

    try:
        with patch.object(krest_tui.Path, "unlink", side_effect=PermissionError("cannot remove lock")), \
                patch.object(app, "push_screen", side_effect=select_file), \
                patch.object(app, "action_refresh_content"), patch.object(app, "notify") as notify:
            if action == "open":
                app.perform_load(destination, "secret")
            else:
                app.action_new_file()
        assert app.backend.file_path == encrypted_file
        assert app.backend.file_data is data
        assert app.backend.dirty_bit is True
        assert krest_tui.Path(encrypted_file + ".krest.lock").exists()
        assert not krest_tui.Path(destination).exists()
        assert notify.call_args.kwargs["severity"] == "error"
    finally:
        app.on_unmount()
    assert not krest_tui.Path(encrypted_file + ".krest.lock").exists()


@pytest.mark.parametrize("failure", ["action_refresh_content", "notify"])
def test_new_file_ui_failure_preserves_lock_for_shutdown(tmp_path, failure):
    path = str(tmp_path / "new.krest")
    lock = krest_tui.Path(path + ".krest.lock")
    app = krest_tui.KrestTui()

    def select_file(screen, callback=None):
        callback((path, "secret"))

    try:
        with patch.object(app, "push_screen", side_effect=select_file), \
                patch.object(app, "action_refresh_content"), patch.object(app, "notify"), \
                patch.object(app, failure, side_effect=RuntimeError("UI failed")):
            with pytest.raises(RuntimeError, match="UI failed"):
                app.action_new_file()
        assert app.backend.file_path == path
        assert lock.exists()
    finally:
        app.on_unmount()
    assert not lock.exists()


def test_password_accepts_third_attempt(encrypted_file):
    with patch.object(krest_tui.getpass, "getpass", side_effect=["bad", "bad", "secret"]) as prompt:
        assert krest_tui.prompt_file_password(encrypted_file) == "secret"
    assert prompt.call_count == 3


def test_password_exits_after_three_failures(encrypted_file, capsys):
    with patch.object(krest_tui.getpass, "getpass", return_value="bad") as prompt:
        with pytest.raises(SystemExit) as error:
            krest_tui.prompt_file_password(encrypted_file)
    assert error.value.code == 1
    assert prompt.call_count == 3
    assert "(3/3)" in capsys.readouterr().err


def test_missing_file_does_not_retry(tmp_path):
    with patch.object(krest_tui.getpass, "getpass", return_value="secret") as prompt:
        with pytest.raises(SystemExit) as error:
            krest_tui.prompt_file_password(str(tmp_path / "missing.krest"))
    assert error.value.code == 1
    assert prompt.call_count == 1


@pytest.mark.parametrize("interruption", [EOFError, KeyboardInterrupt])
def test_cancelled_password_exits(interruption):
    with patch.object(krest_tui.getpass, "getpass", side_effect=interruption):
        with pytest.raises(SystemExit) as error:
            krest_tui.prompt_file_password("project.krest")
    assert error.value.code == 1


@pytest.mark.parametrize("flag", ["--file", "-f"])
def test_cli_passes_file_to_tui(flag):
    with patch("sys.argv", ["krest", flag, "project.krest"]), \
            patch.object(krest_tui, "prompt_file_password", return_value="secret") as prompt, \
            patch.object(krest_tui, "KrestTui") as app:
        app.return_value.return_code = 0
        krest_tui.tui()
    prompt.assert_called_once_with("project.krest")
    app.assert_called_once_with(file_path="project.krest", file_password="secret")
    app.return_value.run.assert_called_once_with()


def test_cli_without_file_does_not_prompt():
    with patch("sys.argv", ["krest"]), \
            patch.object(krest_tui, "prompt_file_password") as prompt, \
            patch.object(krest_tui, "KrestTui") as app:
        app.return_value.return_code = 0
        krest_tui.tui()
    prompt.assert_not_called()
    app.return_value.run.assert_called_once_with()


def test_cli_logs_textual_event_exception(tmp_path, caplog, encrypted_file):
    log_path = tmp_path / "krest.log"

    class CrashingTui(krest_tui.KrestTui):
        CSS_PATH = krest_tui.Path(krest_tui.__file__).with_suffix(".tcss")

        def on_mount(self):
            self.perform_load(encrypted_file, "secret")
            raise RuntimeError("event handler failed")

        def run(self):
            return super().run(headless=True)

    logging.disable(logging.NOTSET)
    caplog.set_level(logging.INFO)
    handler = logging.FileHandler(log_path)
    root = logging.getLogger()
    root.addHandler(handler)
    try:
        with patch("sys.argv", ["krest", "--debug"]), \
                patch.object(krest_tui, "setup_logging"), \
                patch.object(krest_tui, "KrestTui", CrashingTui):
            with pytest.raises(SystemExit) as error:
                krest_tui.tui()
        assert error.value.code == 1
    finally:
        root.removeHandler(handler)
        handler.close()

    log = log_path.read_text()
    assert "TUI: Unhandled application exception" in log
    assert "Traceback (most recent call last)" in log
    assert "on_mount" in log
    assert "RuntimeError: event handler failed" in log
    assert "TUI: End." not in log
    assert not krest_tui.Path(encrypted_file + ".krest.lock").exists()


@pytest.mark.parametrize("phase", ["initialization", "run"])
def test_cli_logs_propagated_exception(phase, caplog):
    failure = RuntimeError("application failed")
    logging.disable(logging.NOTSET)
    with patch("sys.argv", ["krest", "--debug"]), \
            patch.object(krest_tui, "setup_logging"), \
            patch.object(krest_tui, "KrestTui") as app, \
            caplog.at_level(logging.INFO):
        if phase == "initialization":
            app.side_effect = failure
        else:
            app.return_value.run.side_effect = failure
        with pytest.raises(RuntimeError, match="application failed"):
            krest_tui.tui()

    assert "TUI: Application failed" in caplog.text
    assert "Traceback (most recent call last)" in caplog.text
    assert "RuntimeError: application failed" in caplog.text
    assert "TUI: End." not in caplog.text


def test_cli_logs_normal_exit(caplog):
    logging.disable(logging.NOTSET)
    with patch("sys.argv", ["krest", "--debug"]), \
            patch.object(krest_tui, "setup_logging"), \
            patch.object(krest_tui, "KrestTui") as app, \
            caplog.at_level(logging.INFO):
        app.return_value.return_code = 0
        krest_tui.tui()

    assert "TUI: End." in caplog.text
    assert not any(record.levelno >= logging.ERROR for record in caplog.records)


def test_three_failures_do_not_start_tui(encrypted_file):
    with patch("sys.argv", ["krest", "-f", encrypted_file]), \
            patch.object(krest_tui.getpass, "getpass", return_value="bad"), \
            patch.object(krest_tui, "KrestTui") as app:
        with pytest.raises(SystemExit):
            krest_tui.tui()
    app.assert_not_called()


def test_startup_loads_file_after_widgets_mount(encrypted_file):
    async def check():
        app = krest_tui.KrestTui(file_path=encrypted_file, file_password="secret")
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.backend.file_path == encrypted_file
            assert app.backend.file_password == "secret"
            assert app.startup_file_password is None
            assert app.query_one("#endpoints_filter", Input).display
            assert encrypted_file in str(app.query_one("#opened_file_name", Static).render())
            assert any(t(t.FILE_LOADED, file_path=encrypted_file) == note.message
                       for note in app._notifications)
    asyncio.run(check())


@pytest.mark.parametrize("editor_type", ["endpoint", "basic", "digest", "oauth2"])
@pytest.mark.parametrize("values", [None, (False, True), (True, False)])
def test_editor_boolean_settings_defaults_and_round_trip(editor_type, values):
    from textual.app import App
    from textual.widgets import Button, Select
    from textual.widgets.select import InvalidSelectValueError

    from krest.krest_backend import CredentialType, empty_credential, empty_endpoint

    async def check():
        if editor_type == "endpoint":
            record = empty_endpoint()
            editor = krest_tui.EndpointEditor(endpoint=record)
            apply_id = "#endpoint-apply-btn"
        else:
            credential_type = {
                "basic": CredentialType.BASIC,
                "digest": CredentialType.DIGEST,
                "oauth2": CredentialType.OAUTH2,
            }[editor_type]
            record = empty_credential(credential_type.value)
            editor = krest_tui.CredentialEditor(credential=record)
            apply_id = "#credential-apply-btn"

        fields = ("follow_redirects", "ignore_proxy")
        for index, field in enumerate(fields):
            if values is None:
                record.pop(field, None)
            else:
                record[field] = values[index]
        expected = values if values is not None else (True, False)

        app = App()
        saved = []
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            for field, value in zip(fields, expected):
                select = editor.query_one(f"#{field}", Select)
                assert select.value is value
                # A required selector rejects an empty selection.
                with pytest.raises(InvalidSelectValueError):
                    select.clear()
                assert type(select.value) is bool
                select.value = not value

            editor.action_apply(Button.Pressed(editor.query_one(apply_id, Button)))
            await pilot.pause()
            assert len(saved) == 1
            for field, value in zip(fields, expected):
                assert saved[0][field] is not value

    asyncio.run(check())


@pytest.mark.parametrize("body_type", [None, *krest_tui.BodyType])
def test_endpoint_editor_body_type_defaults_and_round_trip(body_type):
    from textual.app import App
    from textual.widgets import Button, Select, TextArea
    from textual.widgets.select import InvalidSelectValueError

    from krest.krest_backend import BodyType, empty_endpoint

    async def check():
        record = empty_endpoint()
        assert record["body_type"] == BodyType.TEXT.value
        if body_type is None:
            record.pop("body_type")
        else:
            record["body_type"] = body_type.value
        record["body"] = {} if body_type == BodyType.MULTIPART else "original body"
        editor = krest_tui.EndpointEditor(endpoint=record)
        app = App()
        saved = []
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            select = editor.query_one("#body_type", Select)
            assert select.value == (body_type or BodyType.TEXT).value
            with pytest.raises(InvalidSelectValueError):
                select.clear()
            fields = list(select.parent.parent.children)
            assert fields[fields.index(select.parent) + 2] is editor.query_one("#body", TextArea)

            # Saving a legacy endpoint adds TEXT without requiring a selection.
            # Existing endpoints can change to each of the other enum values.
            selected = BodyType.TEXT if body_type is None else list(BodyType)[
                (list(BodyType).index(body_type) + 1) % len(BodyType)
            ]
            select.value = selected.value
            editor.action_apply(Button.Pressed(editor.query_one("#endpoint-apply-btn", Button)))
            await pilot.pause()
            assert len(saved) == 1
            assert saved[0]["body_type"] == selected.value
            crossed_binary = ((body_type or BodyType.TEXT) == BodyType.BINARY) != (selected == BodyType.BINARY)
            if selected == BodyType.MULTIPART:
                expected_body = {}
            elif crossed_binary or body_type == BodyType.MULTIPART:
                expected_body = None
            else:
                expected_body = "original body"
            assert saved[0]["body"] == expected_body

    asyncio.run(check())


@pytest.mark.parametrize("credential_id, available_credentials, expected", [
    (1, [], None),
    (1, [("Other", 2)], None),
    (None, [("First", 0)], None),
    (0, [("First", 0)], 0),
    (1, [("First", 0), ("Second", 1)], 1),
])
def test_endpoint_editor_credential_selection(credential_id, available_credentials, expected):
    from textual.app import App
    from textual.widgets import Button, Select

    from krest.krest_backend import empty_endpoint

    async def check():
        record = empty_endpoint()
        record["credential_id"] = credential_id
        editor = krest_tui.EndpointEditor(record, available_credentials)
        app = App()
        saved = []
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            select = editor.query_one("#credential_id", Select)
            if expected is None:
                assert select.is_blank()
            else:
                assert select.value == expected
            # Opening the editor must not change the saved reference.
            assert record["credential_id"] == credential_id
            editor.action_apply(Button.Pressed(editor.query_one("#endpoint-apply-btn", Button)))
            await pilot.pause()
            assert saved[0]["credential_id"] == expected

    asyncio.run(check())


@pytest.mark.parametrize("credential_type", list(krest_tui.CredentialType))
def test_new_credential_boolean_settings(credential_type):
    from textual.app import App
    from textual.widgets import Button, Select

    async def check():
        app = App()
        editor = krest_tui.CredentialEditor()
        saved = []
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            editor.query_one("#credential_type_selector", Select).value = credential_type.value
            await pilot.pause()
            assert editor.query_one("#follow_redirects", Select).value is True
            assert editor.query_one("#ignore_proxy", Select).value is False
            editor.action_apply(Button.Pressed(editor.query_one("#credential-apply-btn", Button)))
            await pilot.pause()
            assert saved[0]["follow_redirects"] is True
            assert saved[0]["ignore_proxy"] is False

    asyncio.run(check())


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize("content", [b"\x00\xffdownload", b"", None])
def test_binary_body_download_overwrite(tmp_path, overwrite, content):
    import base64
    from textual.app import App
    from textual.widgets import Checkbox, TextArea
    from krest.krest_backend import BodyType, empty_endpoint

    async def check():
        backend = KrestBackend()
        record = empty_endpoint()
        record.update(id=0, body_type=BodyType.BINARY.value,
                      body=base64.b64encode(content).decode("ascii") if content is not None else None)
        backend.file_data["endpoints"].append(record)
        destination = tmp_path / "body.bin"
        destination.write_bytes(b"existing")
        editor = krest_tui.EndpointEditor(record, backend=backend)
        app = App()
        async with app.run_test() as pilot:
            app.push_screen(editor)
            await pilot.pause()
            assert not editor.query_one("#body", TextArea).display
            assert editor.query_one("#binary-body-buttons").display
            editor.download_body()
            await pilot.pause()
            dialog = app.screen
            assert isinstance(dialog, krest_tui.BodyFileDialog)
            checkbox = dialog.query_one("#body-overwrite", Checkbox)
            assert checkbox.value is False
            checkbox.value = overwrite
            dialog.query_one("#body-directory-name", Input).value = str(destination.parent)
            dialog.query_one("#body-file-name", Input).value = destination.name
            with patch.object(editor, "notify") as notify:
                dialog.confirm_file()
                await pilot.pause()
                assert notify.call_args.kwargs["severity"] == ("information" if overwrite else "error")
            assert destination.read_bytes() == ((content or b"") if overwrite else b"existing")

    asyncio.run(check())


@pytest.mark.parametrize("outcome", ["apply", "cancel", "missing"])
def test_binary_body_upload(tmp_path, outcome):
    import base64
    from textual.app import App
    from textual.widgets import Button, Select, TextArea
    from krest.krest_backend import BodyType, empty_endpoint

    async def check():
        source = tmp_path / "body.bin"
        content = b"\x00\xffuploaded"
        if outcome != "missing":
            source.write_bytes(content)
        record = empty_endpoint()
        record.update(body_type=BodyType.BINARY.value, body="b2xk")
        editor = krest_tui.EndpointEditor(record)
        app = App()
        saved = []
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            select = editor.query_one("#body_type", Select)
            select.value = BodyType.TEXT.value
            await pilot.pause()
            assert editor.query_one("#body", TextArea).display
            assert not editor.query_one("#binary-body-buttons").display
            select.value = BodyType.BINARY.value
            await pilot.pause()
            editor.upload_body()
            await pilot.pause()
            dialog = app.screen
            assert not dialog.query("Checkbox")
            dialog.query_one("#body-file-name", Input).value = str(source)
            with patch.object(editor, "notify") as notify:
                dialog.confirm_file()
                await pilot.pause()
                assert notify.call_args.kwargs["severity"] == ("error" if outcome == "missing" else "information")
                if outcome != "missing":
                    assert notify.call_args.args[0] == t(t.FILE_LOADED, file_path=str(source))
            assert record["body"] == "b2xk"
            if outcome == "cancel":
                editor.action_cancel_dialog()
            else:
                editor.action_apply(Button.Pressed(editor.query_one("#endpoint-apply-btn", Button)))
            await pilot.pause()
            if outcome == "cancel":
                assert saved == [None]
            else:
                expected = None if outcome == "missing" else base64.b64encode(content).decode("ascii")
                assert saved[0]["body"] == expected

    asyncio.run(check())


@pytest.mark.parametrize("download", [False, True])
def test_body_file_dialog_browse_and_cancel(tmp_path, download):
    from textual.app import App
    from textual.widgets import Button

    async def check():
        source = tmp_path / "payload.bin"
        source.write_bytes(b"payload")
        dialog = krest_tui.BodyFileDialog(download=download)
        app = App()
        results = []
        with patch.object(krest_tui.Path, "home", return_value=tmp_path):
            async with app.run_test() as pilot:
                app.push_screen(dialog, results.append)
                await pilot.pause()
                if download:
                    dialog.query_one("#body-file-name", Input).value = source.name
                with patch.object(app, "push_screen") as push_screen:
                    dialog.browse_file(Button.Pressed(dialog.query_one("#body-browse-btn", Button)))
                    picker = push_screen.call_args.args[0]
                    assert isinstance(picker, krest_tui.SelectFileDialog)
                    assert picker.all_files
                    assert picker.directories_only is download
                    selected_path = source.parent if download else source
                    push_screen.call_args.kwargs["callback"](selected_path)
                if download:
                    assert dialog.query_one("#body-directory-name", Input).value == str(source.parent)
                    assert dialog.query_one("#body-file-name", Input).value == source.name
                else:
                    assert dialog.query_one("#body-file-name", Input).value == str(source)
                dialog.action_cancel_dialog()
                await pilot.pause()
                assert results == [None]

    asyncio.run(check())


@pytest.mark.parametrize("other_type", [body_type for body_type in krest_tui.BodyType
                                       if body_type != krest_tui.BodyType.BINARY])
@pytest.mark.parametrize("start_binary", [False, True])
def test_body_type_binary_transition_clears_body(other_type, start_binary):
    from textual.app import App
    from textual.widgets import Button, Select, TextArea
    from krest.krest_backend import BodyType, empty_endpoint

    async def check():
        initial = BodyType.BINARY if start_binary else other_type
        target = other_type if start_binary else BodyType.BINARY
        record = empty_endpoint()
        record.update(body_type=initial.value, body={} if initial == BodyType.MULTIPART else "b3JpZ2luYWw=")
        editor = krest_tui.EndpointEditor(record)
        saved = []
        app = App()
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            select = editor.query_one("#body_type", Select)
            assert editor.endpoint_curr["body"] == record["body"]
            select.value = target.value
            await pilot.pause()
            assert editor.endpoint_curr["body"] == ({} if target == BodyType.MULTIPART else None)
            assert editor.query_one("#body", TextArea).text == ""
            # Changes are staged until Apply, and switching back cannot restore the body.
            assert record["body"] == ({} if initial == BodyType.MULTIPART else "b3JpZ2luYWw=")
            select.value = initial.value
            await pilot.pause()
            assert editor.endpoint_curr["body"] == ({} if initial == BodyType.MULTIPART else None)
            assert editor.query_one("#body", TextArea).text == ""
            editor.action_apply(Button.Pressed(editor.query_one("#endpoint-apply-btn", Button)))
            await pilot.pause()
            assert saved[0]["body"] == ({} if initial == BodyType.MULTIPART else None)

    asyncio.run(check())


@pytest.mark.parametrize("apply_changes", [False, True])
def test_multipart_editor_parts_and_files(tmp_path, apply_changes):
    from textual.app import App
    from textual.widgets import Button, Select, TextArea
    from krest.krest_backend import BodyType, MultipartBody, ValueType, empty_endpoint

    async def check():
        body = MultipartBody()
        body.set_part("description", value="[literal] text")
        body.set_part("attachment", "data.bin", ValueType.BINARY.value, b"old", "application/octet-stream")
        record = empty_endpoint()
        record.update(body_type=BodyType.MULTIPART.value, body=body)
        editor = krest_tui.EndpointEditor(record)
        app = App()
        saved = []
        async with app.run_test(size=(150, 60)) as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            assert not editor.query_one("#body", TextArea).display
            assert not editor.query_one("#binary-body-buttons").display
            assert editor.query_one("#multipart-body").display
            rows = list(editor.query(krest_tui.MultipartRow))
            assert len(rows) == 2
            assert not rows[0].query(".multipart-upload")
            assert str(rows[1].query("Label")[3].render()) == ""

            source = tmp_path / "source.bin"
            source.write_bytes(b"\x00\xffbinary")
            rows[1].query_one(".multipart-upload", Button).press()
            await pilot.pause()
            app.screen.query_one("#body-file-name", Input).value = str(source)
            app.screen.confirm_file()
            await pilot.pause()
            rows[1].query_one(".multipart-download", Button).press()
            await pilot.pause()
            app.screen.query_one("#body-directory-name", Input).value = str(tmp_path)
            app.screen.query_one("#body-file-name", Input).value = "saved.bin"
            app.screen.confirm_file()
            await pilot.pause()
            assert (tmp_path / "saved.bin").read_bytes() == source.read_bytes()

            rows[0].query_one(".multipart-delete", Button).press()
            await pilot.pause()
            assert "description" not in editor.endpoint_curr["body"]
            assert len(editor.query(krest_tui.MultipartRow)) == 1
            for name, value_type in (("new text", ValueType.TEXT), ("new binary", ValueType.BINARY)):
                editor.query_one("#multipart-name", Input).value = name
                editor.query_one("#multipart-value", Input).value = "hello"
                editor.query_one("#multipart-value-type", Select).value = value_type.value
                await pilot.pause()
                assert editor.query_one("#multipart-value", Input).display == (value_type == ValueType.TEXT)
                editor.query_one("#multipart-add", Button).press()
                await pilot.pause()
            assert len(editor.query(krest_tui.MultipartRow)) == 3
            parts = MultipartBody(editor.endpoint_curr["body"]).get_parts()
            assert parts["new text"][1] == "hello"
            assert parts["new binary"][1] == b""
            assert parts["attachment"][1] == source.read_bytes()
            assert record["body"] == body
            assert "description" in body
            if apply_changes:
                editor.action_apply(Button.Pressed(editor.query_one("#endpoint-apply-btn", Button)))
            else:
                editor.action_cancel_dialog()
            await pilot.pause()
            assert saved[0]["body"] == editor.endpoint_curr["body"] if apply_changes else saved == [None]

    asyncio.run(check())
