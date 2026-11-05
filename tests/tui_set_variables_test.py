import asyncio
import json
from unittest.mock import patch

import pytest
from textual.app import App
from textual.widgets import Button, TextArea
from krest import krest_tui as tui
from krest.krest_backend import empty_endpoint, empty_credential


@pytest.mark.parametrize('kind', ['endpoint', 'Basic', 'DigestAuth', 'OAuth2'])
@pytest.mark.parametrize('initial', [None, {'token': 'response_body.access_token'}])
def test_set_variables_editor(kind, initial):
    async def check():
        record = empty_endpoint() if kind == 'endpoint' else empty_credential(kind)
        if initial is None:
            record.pop('set_variables', None)
        else:
            record['set_variables'] = initial
        editor = tui.EndpointEditor(record) if kind == 'endpoint' else tui.CredentialEditor(record)
        button_id = '#endpoint-apply-btn' if kind == 'endpoint' else '#credential-apply-btn'
        saved = []
        app = App()
        async with app.run_test() as pilot:
            app.push_screen(editor, saved.append)
            await pilot.pause()
            area = editor.query_one('#set_variables', TextArea)
            assert json.loads(area.text) == (initial or {})
            for invalid in ['{', '[]', '{"token": 1}', '{"token": null}']:
                area.load_text(invalid)
                with patch.object(editor, 'notify') as notify:
                    editor.action_apply(Button.Pressed(editor.query_one(button_id, Button)))
                    assert notify.call_args.kwargs['severity'] == 'error'
                assert not saved
                assert record.get('set_variables') == initial
            expected = {'session': 'response_headers.X-Session', 'name': 'response_body.name'}
            area.load_text(json.dumps(expected))
            editor.action_apply(Button.Pressed(editor.query_one(button_id, Button)))
            await pilot.pause()
            assert saved[0]['set_variables'] == expected
    asyncio.run(check())


@pytest.mark.parametrize('updated', [None, {}, {'name': 'Árvíz', 'count': 2, 'nested': [True, None]}])
def test_updated_history_variables(updated):
    async def check():
        record = {} if updated is None else {'variables_updated': updated}
        viewer = tui.CallHistoryDetailsViewer(record)
        app = App()
        async with app.run_test() as pilot:
            app.push_screen(viewer)
            await pilot.pause()
            area = viewer.query_one('#history-variables-updated', TextArea)
            assert area.read_only
            assert json.loads(area.text) == (updated or {})
    asyncio.run(check())
