import asyncio
from copy import deepcopy
from datetime import timedelta
import json

import httpx
import pytest
from textual.app import App
from textual.widgets import TextArea

from krest.krest_backend import KrestBackend
from krest.krest_tui import CallHistoryDetailsViewer


def response():
    result = httpx.Response(200, text="OK", request=httpx.Request("GET", "https://example.com"))
    result.elapsed = timedelta(milliseconds=10)
    return result


def test_history_variables_are_independent_snapshots():
    backend = KrestBackend()
    backend.file_data["variables"] = {"host": "example.com", "payload": {"items": [1]}}
    endpoint = {"url": "https://${host}", "body": "${payload:json}"}
    expected = deepcopy(backend.file_data["variables"])
    backend.save_history("request", 1, response(), endpoint, variables_curr=backend.file_data["variables"])
    first = backend.file_data["call_history"][0]
    assert first["variables_curr"] == expected
    assert first["endpoint"] == endpoint

    backend.file_data["variables"]["host"] = "changed.example.com"
    backend.file_data["variables"]["payload"]["items"].append(2)
    backend.save_history("request", 1, response(), endpoint, variables_curr=backend.file_data["variables"])
    assert first["variables_curr"] == expected
    second = backend.file_data["call_history"][1]
    assert second["variables_curr"] == backend.file_data["variables"]
    first["variables_curr"]["payload"]["items"].append(3)
    assert backend.file_data["variables"]["payload"]["items"] == [1, 2]
    assert second["variables_curr"]["payload"]["items"] == [1, 2]


def test_history_defaults_to_empty_variables_for_legacy_files():
    backend = KrestBackend()
    backend.file_data.pop("variables")
    backend.save_history("request", 1, response())
    assert backend.file_data["call_history"][0]["variables_curr"] == {}


def test_history_does_not_implicitly_capture_all_variables():
    backend = KrestBackend()
    backend.file_data["variables"] = {"unused": "secret"}
    backend.save_history("request", 1, response())
    assert backend.file_data["call_history"][0]["variables_curr"] == {}


@pytest.mark.parametrize("record", [
    {},
    {"variables_curr": {}},
    {"variables_curr": None},
    {"variables_curr": {"host": "example.com", "count": 3, "enabled": False,
                         "payload": {"items": [None, "árvíz", "[bold]literal[/bold]"]}}},
])
def test_history_details_show_read_only_variables_and_handle_old_records(record):
    async def check():
        original = deepcopy(record)
        app = App()
        async with app.run_test() as pilot:
            viewer = CallHistoryDetailsViewer(record)
            app.push_screen(viewer)
            await pilot.pause()
            variables = viewer.query_one("#history-variables", TextArea)
            assert json.loads(variables.text) == (record.get("variables_curr") or {})
            assert variables.read_only is True
            assert record == original

    asyncio.run(check())
