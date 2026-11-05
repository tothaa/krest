#!/usr/bin/env python3

import os
from pathlib import Path
from string import Template
from collections.abc import Mapping, Sequence
import json
import re
import base64
import shutil
# import time
from typing import Callable, List, Dict, Optional, Any, Self
from enum import Enum
from datetime import datetime, timedelta
from importlib.metadata import version
from copy import deepcopy
import logging
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

USER_KREST_DIR = Path.home() / ".krest"
USER_KREST_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = USER_KREST_DIR / 'krest.log'
DEFAULT_OBJECT = object()

LOG_LEVELS = {1: logging.DEBUG, 2: logging.INFO, 3: logging.WARNING, 4: logging.ERROR, 5: logging.CRITICAL}

def setup_logging(log_level):
    logging.basicConfig(filename=LOG_FILE, level=log_level, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S", force=True)
    print("Logs will be saved here:", LOG_FILE)

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

class ValueType(Enum):
    TEXT = ("TEXT", t(t.TEXT))
    BINARY = ("BINARY", t(t.BINARY))

    def __new__(cls: type["ValueType"], value: str, display: str) -> "ValueType":
        obj = object.__new__(cls)
        obj._value_ = value
        obj.display = display
        return obj

class BodyType(Enum):
    JSON = ("JSON", t(t.JSON))
    DATA = ("DATA", t(t.FORM_DATA))                   # Content-Type: application/x-www-form-urlencoded  - URL-encodes dict: {"user": "john"} becomes user=john.
    BINARY = ("BINARY", t(t.BINARY))
    TEXT = ("TEXT", t(t.TEXT))
    MULTIPART = ("MULTIPART", t(t.MULTIPART))         # Content-Type: Multipart/mixed; boundary=gc0p4Jq0M2Yt08jU534c0p  - or multipart/form-data...

    def __new__(cls: type["BodyType"], value: str, display: str) -> "BodyType":
        obj = object.__new__(cls)
        obj._value_ = value
        obj.display = display
        return obj

def empty_endpoint() -> Dict[str, Any]:
    return {
        "id": None,
        "name": "",
        "desc": "",
        "labels": [],
        "credential_id": None,
        "method": Method.GET.value,
        "timeout": 30,
        "url": "",
        "headers": {"Accept": "text/html", "Accept-Charset": "utf-8", "Connection": "close", "Content-Type": "application/json"},
        "body_type": BodyType.TEXT.value,
        "body": None,
        "params": {},
        "response_type": ValueType.TEXT.value,
        "follow_redirects": True,
        "ignore_proxy": False,
        "set_variables": {},
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
            "token_body": "grant_type=client_credentials&scope=*",
            "token_headers": {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
            "client_id": "",
            "client_secret": "",
            "follow_redirects": True,
            "ignore_proxy": False,
            "set_variables": {},
            "created_at": None,
            "updated_at": None,
        }

    return empty_credential

def empty_workflow() -> Dict[str, Any]:
    return {
        "id": None,
        "name": "",
        "desc": "",
        "labels": [],
        "steps": [],
        "created_at": None,
        "updated_at": None,
    }

MAGIC_BYTES = b"KREST01"
FILE_EXTENSION = "krest"
CREDENTIAL_TYPES = [credential.value for credential in CredentialType]
METHODS = [method.value for method in Method]
BODY_TYPES = [body_type.value for body_type in BodyType]
VALUE_TYPES = [value_type.value for value_type in ValueType]

EMPTY_FILE_DATA = {
            "application": "krest",
            "version": version("krest-utils"),
            "settings": {"is_backup_enabled": True, "history_retention_days": 50},
            "max_endpoint_id": -1,
            "max_credential_id": -1,
            "max_call_history_id": -1,
            "max_workflow_id": -1,
            "credentials": [],
            "endpoints": [],
            "call_history": [],
            "variables": {},
            "workflows": [],
        }

def get_value_by_path(data: Any, path: str, default: Any = DEFAULT_OBJECT) -> Any:
    """Read a value using a small JSONPath-like syntax."""
    if not isinstance(path, str):
        raise TypeError(t(t.ERR_PATH_NOT_STR))
    if not path.startswith("$"):
        raise ValueError(t(t.ERR_PATH_NOT_START_WITH_DOLLAR))

    keys: list[str | int] = []
    pos = 1
    while pos < len(path):
        match = re.compile(
                r"""\.([^.\[\]]+) | \[(-?[0-9]+)\] | \['([^']*)'\] | \["([^"]*)"\]""" # .key, including hyphens and spaces | [0], [123], or [-1] | ['key'], including empty keys | ["key"], including empty keys
                , re.VERBOSE
            ).match(path, pos)
        if match is None:
            raise ValueError(t(t.ERR_INVALID_PATH, pos=str(pos), val=str(path[pos:])))

        key, index, single_quoted, double_quoted = match.groups()
        if key is not None:
            keys.append(key)
        elif index is not None:
            keys.append(int(index))
        elif single_quoted is not None:
            keys.append(single_quoted)
        else:
            if double_quoted is None:
                raise ValueError(t(t.ERR_PATH_QUOTED_NONE))
            keys.append(double_quoted)

        pos = match.end()

    current = data
    for key in keys:
        try:
            if isinstance(key, int):
                if (not isinstance(current, Sequence) or isinstance(current, (str, bytes, bytearray))):
                    raise TypeError(t(t.ERR_PATH_SEQUENCE, key=key, name=type(current).__name__))
            elif not isinstance(current, Mapping):
                raise TypeError(t(t.ERR_PATH_MAPPING, key=key, name=type(current).__name__))
            current = current[key]
        except (KeyError, IndexError, TypeError):
            if default is DEFAULT_OBJECT:
                raise
            return default
    return current


class MultipartBody(dict):
    def set_part(self: Self, attribute_name: str, filename: str | None = None, value_type: str = ValueType.TEXT.value, value: str | bytes = "", mime_type: str | None = None) -> None:
        self[attribute_name] = {
            "filename": filename,
            "value_type": value_type,
            "value": value if value_type==ValueType.TEXT.value else base64.b64encode(value).decode("ascii"),
            "mime_type": mime_type
        }

    def get_parts(self: Self) -> dict[str, tuple[str | None, tuple[str | bytes | None], str | None]]:
        ret = {}
        for key in self.keys():
            filename = self[key].get("filename", None)
            value_type = self[key].get("value_type", None)
            value = self[key].get("value", None)
            value = value if value_type==ValueType.TEXT.value else base64.b64decode(value)
            mime_type = self[key].get("mime_type", None)
            ret[key] = (filename, value, mime_type)
        return ret


class KrestBackend:
    """Backend for the Krest application, handling file operations, business functions."""

    __slots__ = ("file_path", "file_password", "file_data", "dirty_bit")

    @staticmethod
    def export_file(content_base64: str | bytes | bytearray | None, path: str | os.PathLike[str], force: bool = False) -> None:
        """Export base64 content to file."""
        if path is None:
            raise ValueError(t(t.ERR_MISSING_FILENAME))
        file_path = os.fspath(path)
        if not isinstance(file_path, str):
            raise TypeError(t(t.ERR_INVALID_FILENAME_FORMAT))
        if (not file_path.strip() or "\x00" in file_path or os.path.basename(file_path) in ("", ".", "..")):
            raise ValueError(t(t.ERR_INVALID_FILENAME))
        if os.path.isdir(file_path):
            raise IsADirectoryError(t(t.ERR_DIRECTORY, file_path=file_path))
        if not force and os.path.lexists(file_path):
            raise FileExistsError(t(t.ERR_FILE_EXISTS, file_path=file_path))
        content = b"" if content_base64 is None else base64.b64decode(content_base64)
        with open(file_path, "wb" if force else "xb") as f:
            f.write(content)

    @staticmethod
    def import_file(path: str | os.PathLike[str]) -> str:
        """Read a file and convert to base64 what it returns."""
        if not path:
            raise ValueError(t(t.ERR_MISSING_FILEPATH))
        if not os.path.isfile(path):
            raise FileNotFoundError(t(t.ERR_FILE_NOT_EXISTS, path=path))

        content = ""
        with open(path, "rb") as f:
            content = f.read()
        content_base64 = base64.b64encode(content).decode("ascii")
        return content_base64

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

    @staticmethod
    def response_to_dict(response: httpx.Response) -> dict:
        """Convert a Response object to a Dict"""

        elapsed = None
        try:
            elapsed = response.elapsed.total_seconds()
        except RuntimeError:
            elapsed = None

        body_json = None
        try:
            body_json = response.json()
        except ValueError:
            body_json = None

        return {
            "response_elapsed_seconds": elapsed,
            "response_url": str(response.url),
            "response_status_code": response.status_code,
            "response_reason_phrase": response.reason_phrase,
            "response_content_length": len(response.content) if response.content else 0,
            "response_encoding": response.encoding,
            "response_charset_encoding": response.charset_encoding,
            "response_headers": dict(response.headers),
            "response_cookies": [vars(c) for c in response.cookies.jar],
            "response_body_text": response.text,
            "response_body_json": body_json,
            "response_body_base64": base64.b64encode(response.content).decode("ascii"),
            "response_http_version": response.http_version,
            "response_links": deepcopy(response.links),
            "response_has_redirect_location": response.has_redirect_location,
            "response_is_redirect": response.is_redirect,
            "response_is_error": response.is_error,
            "response_is_success": response.is_success,
        }

    def __init__(self):
        """Constructor to initialize the backend."""
        self.file_path: str|None = None
        self.file_password: str|None = None
        self.dirty_bit: bool|None = None
        self.file_data: Dict[str, Any]|None = deepcopy(EMPTY_FILE_DATA)

    def save_settings(self, settings: Dict[str, Any]) -> None:
        """Replace the settings and mark the file as changed."""
        if not isinstance(settings, dict):
            logging.warning("Rejected settings: expected a dictionary")
            raise TypeError(t(t.ERR_SETTINGS_FORMAT))
        self.file_data["settings"] = settings
        self.dirty_bit = True
        logging.info("Settings updated")

    def save_variables(self, variables: Dict[str, Any]) -> None:
        """Replace the variables and mark the file as changed."""
        if not isinstance(variables, dict):
            raise TypeError(t(t.ERR_VARIABLES_FORMAT))
        self.file_data["variables"] = deepcopy(variables)
        self.dirty_bit = True

    def substitute_variables(self, data: str | dict | list | int | float | bool | None, used_variables: dict | None = None) -> str | bytes | dict | list | int | float | bool | None:
        """Replace ${} strings in input with the values in the variables dict

        Usage:
            * $name or ${name} - return substituted value as string
            * ${name:int}, ${name:float}, ${name:bool}, ${name:json}, ${name:str} - return the substituted value as a specific type
            * ${name:file} - decode a base64 variable into bytes. File Content is stored as Base64 Encoded String in variables, logs...
        Note: substitution texts for missing variable values remain unchanged in the output.
        Note: unexpected data will raise exception.
        When supplied, used_variables collects snapshots of substituted values.
        """

        variables = self.file_data.get("variables", {})
        if isinstance(data, str):
            variable_with_type_marker = re.fullmatch(r"\$\{([a-zA-Z_][a-zA-Z0-9_]*):([a-zA-Z_][a-zA-Z0-9_]*)\}", data)
            if variable_with_type_marker:
                variable_name, value_type = variable_with_type_marker.groups()
                if value_type not in ("int", "float", "str", "json", "bool", "file"):
                    raise ValueError(t(t.ERR_VARIABLE_SUBSTITUTION_TYPE, value_type=value_type))
                if variable_name not in variables:
                    return data
                value = variables[variable_name]
                if used_variables is not None:
                    used_variables[variable_name] = deepcopy(value)
                try:
                    match value_type:
                        case "int":
                            return int(value)
                        case "float":
                            return float(value)
                        case "str":
                            return str(value)
                        case "json":
                            return json.loads(value)
                        case "file":
                            return base64.b64decode(value, validate=True)
                        case "bool":
                            if isinstance(value, bool):
                                return value
                            if isinstance(value, str) and value.strip().lower() in ("true", "false"):
                                return value.strip().lower() == "true"
                            raise ValueError(t(t.ERR_VARIABLE_TRUE_FALSE))
                except (TypeError, ValueError, OverflowError) as error:
                    raise ValueError(t(t.ERR_VARIABLE_CONVERSION, variable_name=variable_name, value_type=value_type)) from error
            else:
                data_as_template = Template(data)
                data_substituted = data_as_template.safe_substitute(variables)
                if used_variables is not None:
                    for match in data_as_template.pattern.finditer(data):
                        name = match.group("named") or match.group("braced")
                        if name is not None and name in variables:
                            used_variables[name] = deepcopy(variables[name])
                return data_substituted

        elif isinstance(data, dict):
            return {self.substitute_variables(k, used_variables): self.substitute_variables(v, used_variables) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.substitute_variables(v, used_variables) for v in data]
        elif isinstance(data, (int, float, bool, type(None))):
            return data
        else:
            raise Exception(t(t.ERR_VARIABLE_WRONG_TYPE, name=type(data).__name__))

    def delete_endpoint(self, id: int) -> None:
        """Delete an endpoint from the file data."""

        to_remove = next((d for d in self.file_data["endpoints"] if d["id"] == id), None)

        if to_remove:
            self.file_data["endpoints"].remove(to_remove)
            self.dirty_bit = True
            logging.info("Deleted endpoint id=%s", id)

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
            logging.info("Created endpoint id=%s", next_id)
            return next_id
        else:
            for i, act_endpoint in enumerate(self.file_data["endpoints"]):
                if act_endpoint.get("id") == endpoint.get("id"):
                    endpoint["updated_at"] = datetime.now().isoformat()
                    self.file_data["endpoints"][i].update(endpoint)
                    logging.info("Updated endpoint id=%s", endpoint.get("id"))
                    break
            return endpoint.get("id")

    def delete_credential(self, id: int) -> None:
        """Delete a credential from the file data."""

        to_remove = next((d for d in self.file_data["credentials"] if d["id"] == id), None)

        if to_remove:
            self.file_data["credentials"].remove(to_remove)
            self.dirty_bit = True
            logging.info("Deleted credential id=%s", id)

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
            logging.info("Created credential id=%s", next_id)
            return next_id
        else:
            for i, act_credential in enumerate(self.file_data["credentials"]):
                if act_credential.get("id") == credential.get("id"):
                    credential["updated_at"] = datetime.now().isoformat()
                    self.file_data["credentials"][i].update(credential)
                    logging.info("Updated credential id=%s", credential.get("id"))
                    break
            return credential.get("id")

    def delete_workflow(self, id: int) -> None:
        """Delete a workflow from the file data."""

        to_remove = next((d for d in self.file_data["workflows"] if d["id"] == id), None)

        if to_remove:
            self.file_data["workflows"].remove(to_remove)
            self.dirty_bit = True
            logging.info("Deleted workflow id=%s", id)

    def save_workflow(self, workflow: Dict[str, Any]) -> int|None:
        """Add a workflow to the file data."""

        self.dirty_bit = True

        if workflow.get("id") is None:
            next_id = self.file_data["max_workflow_id"] + 1
            new_workflow = workflow.copy()
            new_workflow["created_at"] = datetime.now().isoformat()
            new_workflow["id"] = next_id
            self.file_data["workflows"].append(new_workflow)
            self.file_data["max_workflow_id"] = next_id
            logging.info("Created workflow id=%s", next_id)
            return next_id
        else:
            for i, act_workflow in enumerate(self.file_data["workflows"]):
                if act_workflow.get("id") == workflow.get("id"):
                    workflow["updated_at"] = datetime.now().isoformat()
                    self.file_data["workflows"][i].update(workflow)
                    logging.info("Updated workflow id=%s", workflow.get("id"))
                    break
            return workflow.get("id")

    def get_endpoint(self, id: int) -> Dict[str, Any]|None:
        """Get an endpoint by its ID."""
        result = [endpoint for endpoint in self.file_data["endpoints"] if endpoint.get("id") == id]
        return result[0] if result else None

    def get_credential(self, id: int) -> Dict[str, Any]|None:
        """Get a credential by its ID."""
        result = [cred for cred in self.file_data["credentials"] if cred["id"] == id]
        return result[0] if result else None

    def get_workflow(self, id: int) -> Dict[str, Any]|None:
        """Get a workflow by its ID."""
        result = [workflow for workflow in self.file_data["workflows"] if workflow["id"] == id]
        return result[0] if result else None

    def select_file(self, file_path: str|None = None, file_password: str|None = None):
        """Set the file path and password for the backend."""
        if file_path is None:
            raise ValueError(t(t.ERR_MISSING_FILEPATH))
        self.file_path = file_path
        self.file_password = file_password
        logging.debug("Selected file path=%s", file_path)

    def create_file(self, file_path: str|None = None, file_password: str|None = None):
        """Create an Empty File; """
        self.file_data = deepcopy(EMPTY_FILE_DATA)
        self.select_file(file_path, file_password)
        self.save_file()
        logging.info("Created file path=%s", self.file_path)

    def save_file(self):
        """Save the file data to the specified file path with encryption."""
        # Check if file_path and file_password are set
        # Check if file_data is not empty
        # Create directory if it does not exist
        # Check if backup file sign is enabled and create a backup if the file exists

        if not self.file_path:
            logging.error("Cannot save file: no file path selected")
            raise ValueError(t(t.ERR_MISSING_FILEPATH))
        if not self.file_data:
            logging.error("Cannot save file: no data available")
            raise ValueError(t(t.ERR_NODATA))

        logging.debug("Saving encrypted file path=%s", self.file_path)
        Path(self.file_path).parent.mkdir(parents=True, exist_ok=True) # check if parent dir exists and create.

        salt = secrets.token_bytes(16)
        key = self.derive_key(self.file_password, salt)
        aesgcm = AESGCM(key)
        iv = secrets.token_bytes(12)
        json_bytes = json.dumps(self.file_data).encode()
        ciphertext = aesgcm.encrypt(iv, json_bytes, None)
        encrypted_data = MAGIC_BYTES + salt + iv + ciphertext

        with open(self.file_path + '.tmp', "wb") as f:
            f.write(encrypted_data)

        if self.file_data["settings"].get("is_backup_enabled", None) and os.path.exists(self.file_path):
            backup_file_path = self.file_path + "." + str(datetime.now().strftime('%Y%m%dT%H%M%S')) + ".bak"
            shutil.copy2(self.file_path, backup_file_path)
            logging.debug("Created backup path=%s", backup_file_path)

        shutil.move(self.file_path + '.tmp', self.file_path)

        self.dirty_bit = False
        logging.info("Saved file path=%s", self.file_path)

    def load_file(self):
        """Load the file data from the specified file path with decryption."""

        if Path(self.file_path + ".krest.lock").exists():
            raise FileExistsError(t(t.ERR_FILE_LOCKED))

        self.file_data = deepcopy(EMPTY_FILE_DATA)
        self.dirty_bit = False

        logging.debug("Loading encrypted file path=%s", self.file_path)
        with open(self.file_path, "rb") as f:
            encrypted_data = f.read()
        magic_bytes, salt, iv, ciphertext = encrypted_data[:7], encrypted_data[7:23], encrypted_data[23:35], encrypted_data[35:]
        if magic_bytes != MAGIC_BYTES:
            logging.error("Cannot load file: invalid signature path=%s", self.file_path)
            raise ValueError(t(t.ERR_MAGICBYTES))
        key = self.derive_key(self.file_password, salt)
        aesgcm = AESGCM(key)
        try:
            json_bytes = aesgcm.decrypt(iv, ciphertext, None)
        except Exception:
            logging.warning("Cannot decrypt file path=%s", self.file_path)
            raise ValueError(t(t.ERR_INVALID_PASSWD))
        self.file_data = json.loads(json_bytes)
        self.file_data.setdefault("variables", {})
        self.file_data.setdefault("workflows", [])
        self.file_data.setdefault("max_workflow_id", -1)
        logging.info("Loaded file path=%s", self.file_path)

        self.purge_call_history_older_than(self.file_data["settings"].get("history_retention_days", None))
        Path(self.file_path + ".krest.lock").touch(exist_ok=False)

    def unload_file(self):
        """Release the file lock and clear the loaded file."""
        if self.file_path:
            Path(self.file_path + ".krest.lock").unlink(missing_ok=True)
        self.file_path = None
        self.file_password = None
        self.file_data = {}
        self.dirty_bit = False

    def purge_call_history_older_than(self, days: int) -> None:
        """Delete history older than the given number of days."""
        if not days:
            logging.debug("Call history purge skipped: retention is zero")
            return

        retained_history = []
        if days > 0:
            retained_history = [history_record for history_record in self.file_data["call_history"] if datetime.fromisoformat(history_record["run_date"]) >= (datetime.now() - timedelta(days=days))]

        if len(retained_history) != len(self.file_data["call_history"]):
            logging.info("Purging %s call history records; retention_days=%s",
                         len(self.file_data["call_history"]) - len(retained_history), days)
            self.dirty_bit = True
            self.file_data["call_history"] = retained_history

    def save_history(self, call_type: str, endpoint_id: int, response: httpx.Response, endpoint: dict|None = None, credential: dict|None = None, variables_curr: dict|None = None, variables_updated: dict|None = None):
        """Add a call and its captured substituted variables to the History."""

        next_id = self.file_data["max_call_history_id"] + 1

        cookie_list = [vars(c) for c in response.cookies.jar]

        history_record = {
            "id": next_id,
            "call_type": call_type,
            "endpoint_id": endpoint_id,
            "run_date": datetime.now().isoformat(),
            "endpoint": deepcopy(endpoint or {}),
            "credential": deepcopy(credential or {}),
            "variables_curr": deepcopy(variables_curr or {}),
            "variables_updated": deepcopy(variables_updated or {}),
            "elapsed_time": response.elapsed.total_seconds() if response.elapsed else 0,
            "response_url": str(response.url),
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
            "response_http_version": response.http_version,
            "response_links": deepcopy(response.links),
            "response_has_redirect_location": response.has_redirect_location,
        }

        self.file_data["call_history"].append(history_record)
        self.file_data["max_call_history_id"] = next_id

        self.dirty_bit = True

        logging.debug(history_record) # Note: might save sensitive data to logs. TODO: review, if we really want this.

        return next_id

    def run_workflow(self, workflow_id: int) -> None:
        """Run the workflow steps."""
        workflow = self.get_workflow(workflow_id)
        if workflow is None:
            raise ValueError(t(t.ERR_INVALID_WORKFLOW_ID, workflow_id=workflow_id))

        for endpoint_id in workflow["steps"]:
            logging.debug('workflow running id=' + str(endpoint_id) + '...')
            self.run_endpoint(endpoint_id)

    def run_endpoint(self, endpoint_id):
        """Call endpoint identified by id."""

        ### backward compatibility, if variables missing:
        try:
            v = self.file_data["variables"]
        except Exception:
            self.file_data["variables"] = {}
        ###

        logging.debug('prepare endpoint setup...')
        endpoint = self.get_endpoint(endpoint_id)
        if endpoint == None:
            logging.error("Cannot execute missing endpoint id=%s", endpoint_id)
            raise ValueError(t(t.ERR_INVALID_ENDPOINT_ID, endpoint_id=endpoint_id))


        def log_event(name):
            return lambda *args, **kwargs: None #developer_log(f"{time.time():.2f} - {name}")
        hooks = {
            'request': [log_event('Request Started')],
            'response': [log_event('Response Received')]
        }
        transport = httpx.HTTPTransport(local_address="0.0.0.0")  # Force IPv4 transport

        auth = None
        service_variables = {}
        request_headers = self.substitute_variables(endpoint.get("headers", {}), service_variables)

        request_data_kwargs = {}

        match endpoint.get("body_type", None):
            case BodyType.JSON.value:
                request_data_kwargs["json"] = self.substitute_variables(endpoint.get("body"), service_variables)
            case BodyType.DATA.value:
                # data=* attribute URL-encodes the dict: {"user": "john"} becomes user=john
                request_data_kwargs["data"] = self.substitute_variables(endpoint.get("body"), service_variables)
            case BodyType.BINARY.value:
                request_data_kwargs["content"] = base64.b64decode(endpoint.get("body"))
            case BodyType.TEXT.value:
                request_data_kwargs["content"] = self.substitute_variables(endpoint.get("body"), service_variables)
            case BodyType.MULTIPART.value:
                multipart = MultipartBody(self.substitute_variables(endpoint.get("body"), service_variables))
                request_data_kwargs["files"] = multipart.get_parts()
            case _:
                # for backward compatibility, we assume and set to Text type.
                request_data_kwargs["content"] = self.substitute_variables(endpoint.get("body"), service_variables)
                endpoint["body_type"] = BodyType.TEXT.value

        credential_id = endpoint.get("credential_id", None)
        credential = self.get_credential(credential_id)
        credential_type = None
        if credential:
            credential_type = credential.get("credential_type", None)

        logging.debug("Endpoint id=%s credential_id=%s authentication=%s",
                      endpoint_id, credential_id, credential_type)

        if credential_type == CredentialType.BASIC.value:
            auth = httpx.BasicAuth(credential.get("username", ""), credential.get("password", ""))

        elif credential_type == CredentialType.DIGEST.value:
            auth = httpx.DigestAuth(username=credential.get("username", ""), password=credential.get("password", ""))

        # elif credential_type == CredentialType.HEADER_KEY.value:
        #     auth = None
        #     headers[credential.get("username")] = credential.get("password")

        elif credential_type == CredentialType.OAUTH2.value:

            token_variables = {}
            token_body = self.substitute_variables(credential.get("token_body", None), token_variables)
            token_headers = self.substitute_variables(credential.get("token_headers", None), token_variables)

            ### for backward compatibility with 1.0.2:
            if not token_body and not token_headers:
                token_body = "grant_type=client_credentials"
                token_headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
                if credential.get("scope", None):
                    token_body += "&scope=" + credential["scope"]
                credential.pop("scope", None)
                credential["token_body"] = token_body
                credential["token_headers"] = token_headers
                self.save_credential(credential)
                logging.info("Migrated legacy OAuth2 credential id=%s", credential_id)
            ###

            token_response = None
            with httpx.Client(event_hooks=hooks, transport=transport, trust_env=(not credential.get("ignore_proxy", False))) as client:
                logging.debug('token request...')
                token_response = client.request(
                    method="POST",
                    url=self.substitute_variables(credential.get("token_url"), token_variables),
                    auth=httpx.BasicAuth(credential.get("client_id"), credential.get("client_secret")),
                    timeout=endpoint.get("timeout"),
                    headers=token_headers,
                    data=token_body,
                    follow_redirects=credential.get("follow_redirects", True)
                )
                logging.debug('got token response.')
                logging.info("OAuth2 token response endpoint_id=%s status=%s", endpoint_id, token_response.status_code)

                logging.debug('convert token_response to dict...')
                token_response_dict = self.response_to_dict(token_response)
                logging.info('updating variables...')
                variables_updated = {}
                calculated_value = None
                for variable_name, path in credential.get("set_variables", {}).items():
                    logging.debug('calculate values...')
                    try:
                        calculated_value = get_value_by_path(token_response_dict, path)
                    except Exception as e:
                        logging.error('Failed to calculate variable %s expression: %r Error: %s', variable_name, path, e)
                        calculated_value = "---ERROR---"

                    variables_updated[variable_name] = calculated_value
                    self.file_data["variables"][variable_name] = calculated_value

            self.save_history(t(t.TOKEN_REQUEST), endpoint_id, token_response, endpoint, credential, variables_curr=token_variables, variables_updated=variables_updated)
            self.dirty_bit = True
            token_response.raise_for_status()

            token_json = token_response.json()
            access_token = token_json["access_token"]

            if access_token is None or access_token=="":
                logging.error("OAuth2 response has an empty access token endpoint_id=%s", endpoint_id)
                # developer_log(token_response.text)
                raise ValueError(t(t.ERR_ACCESS_TOKEN))

            auth = None
            request_headers["Authorization"] = f"Bearer {access_token}"

        elif not credential_type:
            pass
        else:
            logging.error("Unsupported authentication for endpoint id=%s credential_id=%s", endpoint_id, credential_id)
            raise Exception(t(t.ERR_CREDENTIAL_TYPE, credential_type=credential_type))

        response = None
        with httpx.Client(event_hooks=hooks, transport=transport, trust_env=(not endpoint.get("ignore_proxy", False))) as client:
            logging.info("Executing endpoint id=%s method=%s", endpoint_id, endpoint.get("method"))
            response = client.request(
                method=endpoint.get("method"),
                url=self.substitute_variables(endpoint.get("url"), service_variables),
                auth=auth,
                timeout=endpoint.get("timeout"),
                headers=request_headers,
                params=self.substitute_variables(endpoint.get("params"), service_variables),
                follow_redirects=endpoint.get("follow_redirects"),
                **request_data_kwargs
            )
            logging.info("Endpoint response id=%s status=%s", endpoint_id, response.status_code)

        logging.debug('convert response to dict...')
        response_dict = self.response_to_dict(response)
        logging.info('updating variables...')
        variables_updated = {}
        calculated_value = None
        for variable_name, path in endpoint.get("set_variables", {}).items():
            logging.debug('calculate values...')
            try:
                calculated_value = get_value_by_path(response_dict, path)
            except Exception as e:
                logging.error('Failed to calculate variable %s expression: %r Error: %s', variable_name, path, e)
                calculated_value = "---ERROR---"

            variables_updated[variable_name] = calculated_value
            self.file_data["variables"][variable_name] = calculated_value

        logging.info('saving history...')
        self.save_history(t(t.SERVICE_REQUEST), endpoint_id, response, endpoint, credential, variables_curr=service_variables, variables_updated=variables_updated)
        self.dirty_bit = True
        response.raise_for_status()

        return response
