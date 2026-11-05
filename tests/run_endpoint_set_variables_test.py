"""Exercise response variable extraction for service and OAuth2 requests."""
from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest

from krest.krest_backend import BodyType, CredentialType, KrestBackend, empty_endpoint


@pytest.mark.parametrize("source", ["endpoint", "credential"])
@pytest.mark.parametrize("status", [200, 400])
@pytest.mark.parametrize("bad_path", ["$.missing", "$.response_body_json[", None, 42])
def test_set_variables_continues_after_invalid_path(source, status, bad_path):
    backend = KrestBackend()
    mappings = {
        "existing": "$.response_body_json.items[1].name",
        "broken": bad_path,
        "after_error": "$.response_headers['x-result']",
        "zero": "$.response_body_json.zero",
        "false": "$.response_body_json.false",
        "null": "$.response_body_json.null",
        "empty": "$.response_body_json.empty",
        "status": "$.response_status_code",
    }
    endpoint = empty_endpoint()
    endpoint.update(id=1, url="https://example.com/service", method="GET",
                    body_type=BodyType.TEXT.value, body="")
    backend.file_data["endpoints"] = [endpoint]
    backend.file_data["variables"] = {"existing": "old", "untouched": "keep"}
    if source == "endpoint":
        endpoint["set_variables"] = mappings
    else:
        endpoint["credential_id"] = 1
        backend.file_data["credentials"] = [{
            "id": 1, "credential_type": CredentialType.OAUTH2.value,
            "client_id": "client", "client_secret": "secret",
            "token_url": "https://example.com/token",
            "token_body": "grant_type=client_credentials", "token_headers": {},
            "set_variables": mappings,
        }]

    requests = []

    def handler(request):
        requests.append(request)
        is_target = source == "endpoint" or request.url.path == "/token"
        response = httpx.Response(status if is_target else 200, json={
            "access_token": "token", "items": [{"name": "first"}, {"name": "second"}],
            "zero": 0, "false": False, "null": None, "empty": "",
        }, headers={"X-Result": "header value"})
        response.elapsed = timedelta(milliseconds=1)
        return response

    with patch("krest.krest_backend.httpx.HTTPTransport", return_value=httpx.MockTransport(handler)):
        if status >= 400:
            with pytest.raises(httpx.HTTPStatusError):
                backend.run_endpoint(1)
        else:
            assert backend.run_endpoint(1).status_code == 200

    expected = {"existing": "second", "broken": "---ERROR---", "after_error": "header value",
                "zero": 0, "false": False, "null": None, "empty": "", "status": status}
    assert backend.file_data["variables"] == {"untouched": "keep", **expected}
    history = backend.file_data["call_history"]
    assert history[0]["variables_updated"] == expected
    assert backend.dirty_bit is True
    if source == "credential" and status == 200:
        assert len(requests) == 2
        assert requests[1].headers["Authorization"] == "Bearer token"
        assert history[1]["variables_updated"] == {}
    else:
        assert len(requests) == 1
