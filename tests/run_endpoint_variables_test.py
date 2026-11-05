import json
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest

from krest.krest_backend import BodyType, CredentialType, KrestBackend, empty_endpoint


def mock_response(*args, **kwargs):
    result = httpx.Response(*args, **kwargs)
    result.elapsed = timedelta(milliseconds=1)
    return result


def backend_with_endpoint(**fields):
    backend = KrestBackend()
    endpoint = empty_endpoint()
    endpoint.update(id=1, url="https://${host}/api", method="POST", **fields)
    backend.file_data["endpoints"] = [endpoint]
    backend.file_data["variables"] = {"host": "example.com", "payload": "hello", "unused": "secret"}
    return backend


@pytest.mark.parametrize("body_type,body", [
    (BodyType.JSON.value, {"items": ["${payload}"]}),
    (BodyType.DATA.value, {"value": "$payload"}),
    (BodyType.TEXT.value, "${payload}"),
    (BodyType.MULTIPART.value, {"part": {"value_type": "TEXT", "value": "${payload}"}}),
    ("legacy", "${payload}"),
])
def test_run_endpoint_logs_only_used_variables_across_payload_types(body_type, body):
    backend = backend_with_endpoint(body_type=body_type, body=body,
                                    headers={"X-Test": "$header"}, params={"search": "${query}"})
    backend.file_data["variables"].update(header="header value", query="query value")
    requests = []

    def handler(request):
        requests.append(request)
        return mock_response(200, text="OK")

    with patch("krest.krest_backend.httpx.HTTPTransport", return_value=httpx.MockTransport(handler)):
        backend.run_endpoint(1)

    history = backend.file_data["call_history"]
    assert len(history) == 1
    assert history[0]["variables_curr"] == {
        "host": "example.com", "payload": "hello", "header": "header value", "query": "query value",
    }
    assert history[0]["endpoint"]["body"] == body
    assert requests[0].headers["X-Test"] == "header value"
    assert requests[0].url.params["search"] == "query value"


def test_file_conversion_snapshot_remains_base64_and_captures_pre_response_values():
    backend = backend_with_endpoint(body_type=BodyType.TEXT.value, body="${payload:file}")
    backend.file_data["variables"]["payload"] = "AP8="

    def handler(request):
        assert request.content == b"\x00\xff"
        backend.file_data["variables"]["host"] = "changed.example.com"
        backend.file_data["variables"]["payload"] = "changed"
        return mock_response(200, text="OK")

    with patch("krest.krest_backend.httpx.HTTPTransport", return_value=httpx.MockTransport(handler)):
        backend.run_endpoint(1)
    assert backend.file_data["call_history"][0]["variables_curr"] == {"host": "example.com", "payload": "AP8="}
    # File bytes never enter the variables snapshot, so it stays JSON serializable.
    json.dumps(backend.file_data["call_history"])


def test_separate_runs_do_not_leak_used_variables():
    backend = backend_with_endpoint(body_type=BodyType.TEXT.value, body="${payload}")
    with patch("krest.krest_backend.httpx.HTTPTransport",
               side_effect=lambda **kwargs: httpx.MockTransport(lambda request: mock_response(200))):
        backend.run_endpoint(1)
        endpoint = backend.file_data["endpoints"][0]
        endpoint.update(url="https://example.com", body="literal")
        backend.run_endpoint(1)
    assert backend.file_data["call_history"][0]["variables_curr"] == {"host": "example.com", "payload": "hello"}
    assert backend.file_data["call_history"][1]["variables_curr"] == {}


def test_oauth_token_and_service_history_capture_separate_variables():
    backend = backend_with_endpoint(body_type=BodyType.TEXT.value, body="${payload}", credential_id=1)
    backend.file_data["variables"].update(token_host="auth.example.com", grant="client_credentials", token_header="token header")
    backend.file_data["credentials"] = [{
        "id": 1, "credential_type": CredentialType.OAUTH2.value,
        "client_id": "client", "client_secret": "secret",
        "token_url": "https://${token_host}/token", "token_body": "grant_type=${grant}",
        "token_headers": {"X-Test": "$token_header"},
    }]

    def handler(request):
        if request.url.path == "/token":
            assert request.url.host == "auth.example.com"
            return mock_response(200, json={"access_token": "token"})
        assert request.headers["Authorization"] == "Bearer token"
        return mock_response(200, text="OK")

    with patch("krest.krest_backend.httpx.HTTPTransport", return_value=httpx.MockTransport(handler)):
        backend.run_endpoint(1)
    token, service = backend.file_data["call_history"]
    assert token["variables_curr"] == {"token_host": "auth.example.com", "grant": "client_credentials", "token_header": "token header"}
    assert service["variables_curr"] == {"host": "example.com", "payload": "hello"}


def test_legacy_file_without_variables_records_empty_snapshot():
    backend = backend_with_endpoint(body_type=BodyType.TEXT.value, body="literal")
    backend.file_data["variables"] = {}
    backend.file_data["endpoints"][0]["url"] = "https://example.com"
    backend.file_data.pop("variables")
    with patch("krest.krest_backend.httpx.HTTPTransport",
               return_value=httpx.MockTransport(lambda request: mock_response(200))):
        backend.run_endpoint(1)
    assert backend.file_data["call_history"][0]["variables_curr"] == {}
