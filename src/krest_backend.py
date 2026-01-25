#!/usr/bin/env python3

import os
import json
import shutil
# import time
import base64
from typing import Callable, List, Dict, Optional, Any, Self
from enum import Enum
from datetime import datetime
from importlib.metadata import version
import secrets
import httpx
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from krest.translations import t

print(t(t.REPLY_NAME, name=t(t.K_USER))) # testing i18n solution

def developer_log(message):
    with open("/home/antototh/Downloads/krest_debug_log_developer.log", "a") as f:
        f.write(message + "\n")

class CredentialType(Enum):
    BASIC = ("Basic", "Basic Auth (" + t(t.BASICAUTH_DESC) + ")")
    DIGEST = ("DigestAuth", "Digest Auth (" + t(t.DIGESTAUTH_DESC) + ")")
    OAUTH2 = ("OAuth2", "OAuth 2.0 (" + t(t.OAUTH_DESC) + ")")
    # HEADER_KEY = ("HeaderKey", "Header Key")

    def __new__(cls: type["CredentialType"], value: str, display: str) -> "CredentialType":
        obj = object.__new__(cls)
        obj._value_ = value
        obj.display = display
        return obj


class Method(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    PATCH = "PATCH"


def empty_endpoint() -> Dict[str, Any]:
    return {
        "id": None,
        "name": "",
        "desc": "",
        "labels": [],
        "credential_id": None,
        "method": Method.GET.value,
        "timeout": 150,
        "url": "",
        "headers": {"Accept": "text/html", "Accept-Charset": "utf-8", "Connection": "close", "Content-Type": "application/json"},
        "body": None,
        "params": {},
        "follow_redirects": True,
        "created_at": None,
        "updated_at": None,
    }

def empty_credential(credential_type: str) -> Dict[str, Any]:
    empty_credential = {}

    if credential_type == CredentialType.BASIC.value:
        empty_credential = {
            "id": None,
            "name": "",
            "desc": "",
            "labels": [],
            "credential_type": credential_type,
            "username": "",
            "password": "",
            "created_at": None,
            "updated_at": None,
        }
    elif credential_type == CredentialType.DIGEST.value:
        empty_credential = {
            "id": None,
            "name": "",
            "desc": "",
            "labels": [],
            "credential_type": credential_type,
            "username": "",
            "password": "",
            "created_at": None,
            "updated_at": None,
        }
    elif credential_type == CredentialType.OAUTH2.value:
        empty_credential = {
            "id": None,
            "name": "",
            "desc": "",
            "labels": [],
            "credential_type": credential_type,
            "token_url": "",
            "scope": None, # e.g. "urn:opc:idm:__myscopes__"
            "client_id": "",
            "client_secret": "",
            "created_at": None,
            "updated_at": None,
        }

    return empty_credential


MAGIC_BYTES = b"KREST01"
FILE_EXTENSION = "krest"
CREDENTIAL_TYPES = [credential.value for credential in CredentialType]
METHODS = [method.value for method in Method]
EMPTY_FILE_DATA = {
            "application": "krest",
            "version": version("krest"),
            "settings": {"is_backup_enabled": True},
            "max_endpoint_id": -1,
            "max_credential_id": -1,
            "max_call_history_id": -1,
            "credentials": [],
            "endpoints": [],
            "call_history": [],
        }


class KrestBackend:
    """Backend for the Krest application, handling file operations, business functions."""

    __slots__ = ("file_path", "file_password", "file_data", "dirty_bit")

    @staticmethod
    def derive_key(password: str, salt: bytes, length=32, iterations=600_000) -> bytes:
        """Derive a key from a password and salt."""

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=length,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(password.encode())

    def __init__(self):
        """Constructor to initialize the backend."""
        self.file_path: str|None = None
        self.file_password: str|None = None
        self.dirty_bit: int|None = None
        self.file_data: Dict[str, Any]|None = EMPTY_FILE_DATA.copy()

    def delete_endpoint(self, id: int) -> None:
        """Delete an endpoint from the file data."""

        to_remove = next((d for d in self.file_data["endpoints"] if d["id"] == id), None)

        if to_remove:
            self.file_data["endpoints"].remove(to_remove)
            self.dirty_bit = True

    def save_endpoint(self, endpoint: Dict[str, Any]) -> int|None:
        """Add an endpoint to the file data."""

        self.dirty_bit = True

        if endpoint.get("id") is None:
            next_id = self.file_data["max_endpoint_id"] + 1
            new_endpoint = endpoint.copy()
            new_endpoint["created_at"] = datetime.now().isoformat()
            new_endpoint["id"] = next_id
            self.file_data["endpoints"].append(new_endpoint)
            self.file_data["max_endpoint_id"] = next_id
            return next_id
        else:
            for i, act_endpoint in enumerate(self.file_data["endpoints"]):
                if act_endpoint.get("id") == endpoint.get("id"):
                    endpoint["updated_at"] = datetime.now().isoformat()
                    self.file_data["endpoints"][i].update(endpoint)
                    break
            return endpoint.get("id")

    def save_credential(self, credential: Dict[str, Any]) -> int|None:
        """Add a credential to the file data."""

        self.dirty_bit = True

        if credential.get("id") is None:
            next_id = self.file_data["max_credential_id"] + 1
            new_credential = credential.copy()
            new_credential["created_at"] = datetime.now().isoformat()
            new_credential["id"] = next_id
            self.file_data["credentials"].append(new_credential)
            self.file_data["max_credential_id"] = next_id
            return next_id
        else:
            for i, act_credential in enumerate(self.file_data["credentials"]):
                if act_credential.get("id") == credential.get("id"):
                    credential["updated_at"] = datetime.now().isoformat()
                    self.file_data["credentials"][i].update(credential)
                    break
            return credential.get("id")

    def get_endpoint(self, id: int) -> Dict[str, Any]|None:
        """Get an endpoint by its ID."""
        result = [endpoint for endpoint in self.file_data["endpoints"] if endpoint.get("id") == id]
        return result[0] if result else None

    def get_credential(self, id: int) -> Dict[str, Any]|None:
        """Get a credential by its ID."""
        result = [cred for cred in self.file_data["credentials"] if cred["id"] == id]
        return result[0] if result else None

    def select_file(self, file_path: str|None = None, file_password: str|None = None):
        """Set the file path and password for the backend."""
        if file_path is None:
            raise ValueError(t(t.ERR_MISSING_FILEPATH))
        self.file_path = file_path
        self.file_password = file_password

    def create_file(self, file_path: str|None = None, file_password: str|None = None):
        """Create an Empty File; """
        self.file_data = EMPTY_FILE_DATA.copy()
        self.select_file(file_path, file_password)
        self.save_file()

    def save_file(self):
        """Save the file data to the specified file path with encryption."""
        # Check if file_path and file_password are set
        # Check if file_data is not empty
        # Create directory if it does not exist
        # Check if backup file sign is enabled and create a backup if the file exists

        if not self.file_path:
            raise ValueError(t(t.ERR_MISSING_FILEPATH))
        if not self.file_data:
            raise ValueError(t(t.ERR_NODATA))

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        salt = secrets.token_bytes(16)
        key = self.derive_key(self.file_password, salt)
        aesgcm = AESGCM(key)
        iv = secrets.token_bytes(12)
        json_bytes = json.dumps(self.file_data).encode()
        ciphertext = aesgcm.encrypt(iv, json_bytes, None)
        encrypted_data = MAGIC_BYTES + salt + iv + ciphertext

        with open(self.file_path + '.tmp', "wb") as f:
            f.write(encrypted_data)

        if self.file_data["settings"]["is_backup_enabled"] and os.path.exists(self.file_path):
            backup_file_path = self.file_path + "." + str(datetime.now().strftime('%Y%m%dT%H%M%S')) + ".bak"
            shutil.copy2(self.file_path, backup_file_path)

        shutil.move(self.file_path + '.tmp', self.file_path)

        self.dirty_bit = None

    def load_file(self):
        """Load the file data from the specified file path with decryption."""

        with open(self.file_path, "rb") as f:
            encrypted_data = f.read()
        magic_bytes, salt, iv, ciphertext = encrypted_data[:7], encrypted_data[7:23], encrypted_data[23:35], encrypted_data[35:]
        if magic_bytes != MAGIC_BYTES:
            # developer_log(f"Expected magic bytes: {MAGIC_BYTES}, found: {magic_bytes}")
            raise ValueError(t(t.ERR_MAGICBYTES))
        key = self.derive_key(self.file_password, salt)
        aesgcm = AESGCM(key)
        try:
            json_bytes = aesgcm.decrypt(iv, ciphertext, None)
        except Exception:
            raise ValueError(t(t.ERR_INVALID_PASSWD))
        self.file_data = json.loads(json_bytes)

        self.dirty_bit = None

    def log_response(self, call_type: str, endpoint_id: int, response: httpx.Response, endpoint: dict|None = None, credential: dict|None = None):
        next_id = self.file_data["max_call_history_id"] + 1

        # try:
        #     content = response.json()
        # except ValueError:
        #     content = response.text

        cookie_list = [vars(c) for c in response.cookies.jar]

        self.file_data["call_history"].append({
            "id": next_id,
            "call_type": call_type,
            "endpoint_id": endpoint_id,
            "run_date": datetime.now().isoformat(),
            "endpoint": (endpoint or {}).copy(),
            "credential": (credential or {}).copy(),
            "elapsed_time": response.elapsed.total_seconds() if response.elapsed else 0,

            # "request_url": str(response.request.url),
            # "request_headers": dict(response.request.headers),                       - endpoint should include
            # "request_method": response.request.method,                               - endpoint should include
            # "request_body": response.request.body if response.request.body else "",  - endpoint should include

            #"response_url": str(response.url),
            "response_status_code": response.status_code,
            "response_reason_phrase": response.reason_phrase,

            "response_content_length": len(response.content) if response.content else 0,
            "response_encoding": response.encoding,
            "response_charset_encoding": response.charset_encoding,
            # "response_ssl_version": response.raw.version if hasattr(response.raw, "version") else "",
            "response_headers": dict(response.headers),
            "cookies": cookie_list,
            "response_body": response.text,
            "response_content_base64": base64.b64encode(response.content).decode("ascii"),  # Original byte Data: base64.b64decode(response_content_base64)
            # "response_json": response.json(),
            "response_http_version": response.http_version,
            "response_links": response.links.copy(),
            "response_has_redirect_location": response.has_redirect_location,
        })
        self.file_data["max_call_history_id"] = next_id
        return next_id


    def run_endpoint(self, endpoint_id):

        endpoint = self.get_endpoint(endpoint_id)
        if endpoint == None:
            raise ValueError(t(t.ERR_INVALID_ENDPOINT_ID, endpoint_id=endpoint_id))

        def log_event(name):
            return lambda *args, **kwargs: None #developer_log(f"{time.time():.2f} - {name}")
        hooks = {
            'request': [log_event('Request Started')],
            'response': [log_event('Response Received')]
        }
        transport = httpx.HTTPTransport(local_address="0.0.0.0")  # Force IPv4 transport

        auth = None
        request_headers = endpoint.get("headers", {})
        request_data = endpoint.get("body")
        credential_id = endpoint.get("credential_id", None)
        credential = self.get_credential(credential_id)
        credential_type = None
        if credential:
            credential_type = credential.get("credential_type", None)

        if credential_type == CredentialType.BASIC.value:
            auth = httpx.BasicAuth(credential.get("username", ""), credential.get("password", ""))

        if credential_type == CredentialType.DIGEST.value:
            auth = httpx.DigestAuth(username=credential.get("username", ""), password=credential.get("password", ""))

        # if credential_type == CredentialType.HEADER_KEY.value:
        #     auth = None
        #     headers[credential.get("username")] = credential.get("password")

        if credential_type == CredentialType.OAUTH2.value:

            token_body = "grant_type=client_credentials"
            if credential.get("scope", None):
                token_body += "&scope=" + credential["scope"]

            token_response = None
            with httpx.Client(event_hooks=hooks, transport=transport) as client:
                token_response = client.request(
                    method="POST",
                    url=credential.get("token_url"),
                    auth=httpx.BasicAuth(credential.get("client_id"), credential.get("client_secret")),
                    timeout=endpoint.get("timeout"),
                    headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
                    data=token_body,
                    follow_redirects=endpoint.get("follow_redirects")
                )

            self.log_response(t(t.TOKEN_REQUEST), endpoint_id, token_response, endpoint, credential)
            token_response.raise_for_status()

            token_json = token_response.json()
            access_token = token_json["access_token"]

            if access_token is None or access_token=="":
                # developer_log(token_response.text)
                raise ValueError(t(t.ERR_ACCESS_TOKEN))

            auth = None
            request_headers["Authorization"] = f"Bearer {access_token}"

        response = None
        with httpx.Client(event_hooks=hooks, transport=transport) as client:
            response = client.request(
                method=endpoint.get("method"),
                url=endpoint.get("url"),
                auth=auth,
                timeout=endpoint.get("timeout"),
                headers=request_headers,
                data=request_data,
                params=endpoint.get("params"),
                follow_redirects=endpoint.get("follow_redirects")
            )

        self.log_response(t(t.SERVICE_REQUEST), endpoint_id, response, endpoint, credential)
        self.dirty_bit = True
        response.raise_for_status()

        return response
