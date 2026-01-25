#!/usr/bin/env python3

import os
import sys
import time
import unittest
import pytest
import json
from math import pi
from dotenv import load_dotenv
from krest.krest_backend import KrestBackend, Method, CredentialType, empty_endpoint, empty_credential
from krest.__main__ import main as main_gui

print('Start krest_backend_test module...')
load_dotenv()
# load_dotenv(dotenv_path="../.env")

c_TEST_FILE_PATH = "/tmp/krest_test_file.krest"
c_TEST_FILE_PASSWORD = "test_password"
c_WEBPAGE_TEST_URL = "https://kernel.org"
c_TEST_ENDPOINT = empty_endpoint()
c_TEST_ENDPOINT.update({
    "name": "Test Starter Endpoint",
    "description": "This is a test endpoint.",
    "created_at": "2023-10-01T12:00:00Z",
    "updated_at": "2023-10-01T12:00:00Z",
    "url": c_WEBPAGE_TEST_URL
})
c_WS_WITH_HEADERS_AND_BODY__URL = os.getenv("WS_WITH_HEADERS_AND_BODY__URL")
c_WS_WITH_HEADERS_AND_BODY__HEADERS = os.getenv("WS_WITH_HEADERS_AND_BODY__HEADERS")
c_WS_WITH_HEADERS_AND_BODY__BODY = os.getenv("WS_WITH_HEADERS_AND_BODY__BODY")
c_WS_WITH_HEADERS_AND_BODY__RESPONSE_BODY = os.getenv("WS_WITH_HEADERS_AND_BODY__RESPONSE_BODY")
c_WS_WITH_HEADER_KEY__URL = os.getenv("WS_WITH_HEADER_KEY__URL")
c_WS_WITH_HEADER_KEY__HEADER_KEY = os.getenv("WS_WITH_HEADER_KEY__HEADER_KEY")
c_WS_WITH_HEADER_KEY__KEY_VALUE = os.getenv("WS_WITH_HEADER_KEY__KEY_VALUE")
c_WS_WITH_OAUTH__TOKEN_URL = os.getenv("WS_WITH_OAUTH__TOKEN_URL")
c_WS_WITH_OAUTH__CLIENT_ID = os.getenv("WS_WITH_OAUTH__CLIENT_ID")
c_WS_WITH_OAUTH__CLIENT_SECRET = os.getenv("WS_WITH_OAUTH__CLIENT_SECRET")
c_WS_WITH_OAUTH__TOKEN_HEADERS = os.getenv("WS_WITH_OAUTH__TOKEN_HEADERS")
c_WS_WITH_OAUTH__TOKEN_METHOD = os.getenv("WS_WITH_OAUTH__TOKEN_METHOD")
c_WS_WITH_OAUTH__URL = os.getenv("WS_WITH_OAUTH__URL")
c_WS_WITH_OAUTH__METHOD = os.getenv("WS_WITH_OAUTH__METHOD")
c_WS_WITH_OAUTH__BODY = os.getenv("WS_WITH_OAUTH__BODY")
c_WS_WITH_OAUTH__HEADERS = os.getenv("WS_WITH_OAUTH__HEADERS")
c_WS_2_WITH_OAUTH__TOKEN_URL = os.getenv("WS_2_WITH_OAUTH__TOKEN_URL")
c_WS_2_WITH_OAUTH__CLIENT_ID = os.getenv("WS_2_WITH_OAUTH__CLIENT_ID")
c_WS_2_WITH_OAUTH__CLIENT_SECRET = os.getenv("WS_2_WITH_OAUTH__CLIENT_SECRET")
c_WS_2_WITH_OAUTH__TOKEN_HEADERS = os.getenv("WS_2_WITH_OAUTH__TOKEN_HEADERS")
c_WS_2_WITH_OAUTH__TOKEN_METHOD = os.getenv("WS_2_WITH_OAUTH__TOKEN_METHOD")
c_WS_2_WITH_OAUTH__URL = os.getenv("WS_2_WITH_OAUTH__URL")
c_WS_2_WITH_OAUTH__METHOD = os.getenv("WS_2_WITH_OAUTH__METHOD")
c_WS_2_WITH_OAUTH__BODY = os.getenv("WS_2_WITH_OAUTH__BODY")
c_WS_2_WITH_OAUTH__HEADERS = os.getenv("WS_2_WITH_OAUTH__HEADERS")
c_WS_2_WITH_OAUTH__TOKEN_BODY = os.getenv("WS_2_WITH_OAUTH__TOKEN_BODY")
c_WS_2_WITH_OAUTH__TOKEN_JSON_FIELD = os.getenv("WS_2_WITH_OAUTH__TOKEN_JSON_FIELD")


if os.path.exists(c_TEST_FILE_PATH):
    os.remove(c_TEST_FILE_PATH)


def circle_area(r):
    if r < 0:
        raise ValueError("The radius cannot be negative.")
    return pi * (r ** 2)


class TestKrestBackend(unittest.TestCase):
    def setUp(self):
        print(sys._getframe().f_code.co_name + '...')
        self.backend = KrestBackend()

    def tearDown(self):
        print(sys._getframe().f_code.co_name + '...')
        self.backend = None

    def test_example(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertAlmostEqual(1, 1)

    def test_value_exception(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertRaises(ValueError, circle_area, -2)

    def test_type_exception(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertRaises(TypeError, circle_area, "zz")

    @unittest.expectedFailure
    def test_failure(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertEqual(1, 0)

    def test_initialization(self):
        print(sys._getframe().f_code.co_name + '...')
        krestbackend = KrestBackend()
        self.assertIsInstance(krestbackend, KrestBackend)

    def test_initial_file_data(self):
        print(sys._getframe().f_code.co_name + '...')
        print(self.backend.file_data)
        self.assertEqual(1, 1)

    def test_save_file(self):
        print(sys._getframe().f_code.co_name + '...')
        self.backend.file_path = c_TEST_FILE_PATH
        self.backend.file_password = c_TEST_FILE_PASSWORD
        try:
            self.backend.save_file()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"save_file raised an exception: {e}")

    def test_save_file_missing_path(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        backend.file_path = None
        self.assertRaises(ValueError, backend.save_file)

    def test_save_file_missing_data(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        backend.file_path = c_TEST_FILE_PATH
        backend.file_password = c_TEST_FILE_PASSWORD
        backend.file_data = None
        self.assertRaises(ValueError, backend.save_file)

    def test_version(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertEqual(self.backend.file_data["version"], "0.0.1")

    def test_load_file(self):
        print(sys._getframe().f_code.co_name + '...')
        self.backend.file_path = c_TEST_FILE_PATH
        self.backend.file_password = c_TEST_FILE_PASSWORD

        try:
            self.backend.save_file()
        except Exception as e:
            self.fail(f"save_file raised an exception: {e}")

        try:
            self.backend.load_file()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"load_file raised an exception: {e}")

    def test_load_file_bad_file(self):
        print(sys._getframe().f_code.co_name + '...')
        with open("/tmp/krest_test_file_bad.txt", "w") as f:
            f.write("This is not a valid Krest file.")
        backend = KrestBackend()
        backend.file_path = "/tmp/krest_test_file_bad.txt"
        backend.file_password = c_TEST_FILE_PASSWORD
        self.assertRaises(ValueError, backend.load_file)

    def test_load_file_bad_password(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        backend.file_path = c_TEST_FILE_PATH
        backend.file_password = "wrong_password"
        self.assertRaises(ValueError, backend.load_file)

    def test_derive_key(self):
        print(sys._getframe().f_code.co_name + '...')
        salt = b"+\x97l\xd0@\xf8x\xf8'T\x07\x0c\xb0e^\x91"
        # salt = secrets.token_bytes(16)
        password = c_TEST_FILE_PASSWORD
        length = 32
        derive_key = self.backend.derive_key(password=password, salt=salt, length=length)
        self.assertEqual(len(derive_key), length)
        self.assertEqual(derive_key, b"qt_2e\xb8C0)F\x80'0{\r\xd9\xaa\xef \x87>\xdf\x07RE(\xe41\xe2\xc9\x835")

    def test_select_file(self):
        print(sys._getframe().f_code.co_name + '...')
        self.backend.select_file(c_TEST_FILE_PATH, c_TEST_FILE_PASSWORD)
        self.assertEqual(self.backend.file_path, c_TEST_FILE_PATH)
        self.assertEqual(self.backend.file_password, c_TEST_FILE_PASSWORD)

    def test_add_endpoint(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        try:
            backend.save_endpoint(c_TEST_ENDPOINT)
        except Exception as e:
            self.fail(f"add_endpoint raised an exception: {e}")

    def test_update_endpoint(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        try:
            backend.save_endpoint(c_TEST_ENDPOINT)
        except Exception as e:
            self.fail(f"backend.save_endpoint(c_TEST_ENDPOINT) raised an exception: {e}.")

        updated_endpoint = c_TEST_ENDPOINT.copy()
        updated_endpoint["description"] = "Updated description"
        updated_endpoint["id"] = 0

        try:
            backend.save_endpoint(updated_endpoint)
        except Exception as e:
            self.fail(f"backend.save_endpoint(updated_endpoint) raised an exception: {e}.")
        try:
            endpoint = backend.get_endpoint(0)
        except Exception as e:
            self.fail(f"backend.get_endpoint(0) raised an exception: {e}.")

        try:
            self.assertEqual(endpoint["description"], updated_endpoint["description"])
        except Exception as e:
            self.fail(f"self.assertEqual(endpoint[`description`], updated_endpoint[`description`]) raised an exception: {e}.")

        updated_endpoint2 = c_TEST_ENDPOINT.copy()
        updated_endpoint2["description"] = "Updated description again"
        updated_endpoint2["id"] = 0

        try:
            backend.save_endpoint(updated_endpoint2)
        except Exception as e:
            self.fail(f"backend.save_endpoint(updated_endpoint2) raised an exception: {e}.")
        try:
            endpoint = backend.get_endpoint(0)
        except Exception as e:
            self.fail(f"backend.get_endpoint(0) raised an exception: {e}.")
        try:
            self.assertEqual(endpoint["description"], updated_endpoint2["description"])
        except Exception as e:
            self.fail(f"self.assertEqual(endpoint[`description`], updated_endpoint2[`description`]) raised an exception: {e}.")

    def test_get_endpoint(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        try:
            backend.save_endpoint(c_TEST_ENDPOINT)
            print(f"Endpoint: {c_TEST_ENDPOINT}")
            print(f"File data: {backend.file_data}")
            endpoint = backend.get_endpoint(0)
            print(f"endpoint: {endpoint}")

            self.assertIsNotNone(endpoint)
            self.assertEqual(endpoint["name"], c_TEST_ENDPOINT["name"])
            self.assertEqual(endpoint["description"], c_TEST_ENDPOINT["description"])

        except Exception as e:
            self.fail(f"get_endpoint raised an exception: {e}")

    def test_get_endpoint_not_found(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        try:
            endpoint = backend.get_endpoint(999)
            self.assertIsNone(endpoint)
        except Exception as e:
            self.fail(f"get_endpoint raised an exception: {e}")

    def test_add_credential(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        credential = {
            "name": "Test Credential",
            "username": "test_user",
            "password": "test_pass",
            "created_at": "2023-10-01T12:00:00Z",
            "updated_at": "2023-10-01T12:00:00Z"
        }
        try:
            backend.save_credential(credential)
        except Exception as e:
            self.fail(f"add_credential raised an exception: {e}")

    def test_get_credential(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        credential = {
            "name": "Test Credential",
            "username": "test_user",
            "password": "test_pass",
            "created_at": "2023-10-01T12:00:00Z",
            "updated_at": "2023-10-01T12:00:00Z"
        }
        try:
            backend.save_credential(credential)
            retrieved_credential = backend.get_credential(0)
            self.assertEqual(retrieved_credential["username"], credential["username"])
        except Exception as e:
            self.fail(f"get_credential raised an exception: {e}")

    def test_create_empty_endpoint(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        endpoint = empty_endpoint()
        self.assertIsNotNone(endpoint)

    def test_call_endpoint_simple_webpage(self):
        print(sys._getframe().f_code.co_name + '...')
        backend = KrestBackend()
        endpoint = {
            "id": None,
            "name": "Test Simple Webpage",
            "desc": "",
            "labels": [],
            "credential_id": None,
            "method": "get",
            "timeout": 150,
            "url": c_WEBPAGE_TEST_URL,
            "headers": {},
            "body": None,
            "params": [],
            "follow_redirects": True
        }
        id = backend.save_endpoint(endpoint)
        self.assertEqual(id, 0)
        response = backend.run_endpoint(id)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.text)
        print("Webpage Results:")
        print(response.text)

    def test_call_endpoint_with_heads_and_body(self):
        print(sys._getframe().f_code.co_name + '...')
        self.assertIsNotNone(c_WS_WITH_HEADERS_AND_BODY__URL)
        self.assertIsNotNone(c_WS_WITH_HEADERS_AND_BODY__HEADERS)
        self.assertIsNotNone(c_WS_WITH_HEADERS_AND_BODY__BODY)
        self.assertIsNotNone(c_WS_WITH_HEADERS_AND_BODY__RESPONSE_BODY)

        self.assertTrue(len(str(c_WS_WITH_HEADERS_AND_BODY__URL))>0)
        self.assertTrue(len(str(c_WS_WITH_HEADERS_AND_BODY__HEADERS))>0)
        self.assertTrue(len(str(c_WS_WITH_HEADERS_AND_BODY__BODY))>0)
        self.assertTrue(len(str(c_WS_WITH_HEADERS_AND_BODY__RESPONSE_BODY))>0)

        headers = json.loads(c_WS_WITH_HEADERS_AND_BODY__HEADERS)

        self.assertIsNotNone(headers)

        backend = KrestBackend()
        endpoint = {
            "id": None,
            "name": "Test WS Call with Headers and Body definitions",
            "desc": "",
            "labels": [],
            "credential_id": None,
            "method": "post",
            "timeout": 150,
            "url": c_WS_WITH_HEADERS_AND_BODY__URL,
            "headers": headers,
            "body": c_WS_WITH_HEADERS_AND_BODY__BODY,
            "params": [],
            "follow_redirects": True
        }
        id = backend.save_endpoint(endpoint)
        self.assertEqual(id, 0)
        response = backend.run_endpoint(id)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.text)
        print("REST Response:")
        print(response.text)
        self.assertEqual(response.text, c_WS_WITH_HEADERS_AND_BODY__RESPONSE_BODY)

    def test_call_endpoint_with_header_key_auth(self):
        print(sys._getframe().f_code.co_name + '...')

        credential = empty_credential()
        credential["credential_type"] = CredentialType.HEADER_KEY.value
        credential["username"] = c_WS_WITH_HEADER_KEY__HEADER_KEY
        credential["password"] = c_WS_WITH_HEADER_KEY__KEY_VALUE

        credential_id = self.backend.save_credential(credential)

        endpoint = empty_endpoint()
        endpoint["url"] = c_WS_WITH_HEADER_KEY__URL
        endpoint["method"] = Method.GET.value
        endpoint["credential_id"] = credential_id

        endpoint_id = self.backend.save_endpoint(endpoint)

        response = self.backend.run_endpoint(endpoint_id)
        self.assertIsNotNone(response)

        self.assertIsNotNone(response.status_code)
        print("Status Code:", response.status_code)

        self.assertIsNotNone(response.headers)
        print("== Response Header ==")
        for key, value in response.headers.items():
            print(f"{key}: {value}")

        self.assertIsNotNone(response.text)
        print("== Response Text ==")
        print(response.text)

        self.assertIsNotNone(response.cookies)
        print("== Response Cookies ==")
        for cookie in response.cookies:
            print(f"{cookie.name} = {cookie.value}")

    def test_call_endpoint_with_oauth_plain_token_output(self):
        print(sys._getframe().f_code.co_name + '...')

        credential = empty_credential(CredentialType.OAUTH_WITH_BASIC.value)
        credential["credential_type"] = CredentialType.OAUTH_WITH_BASIC.value
        credential["name"] = "Test Credential of oAuth"
        credential["url"] = c_WS_WITH_OAUTH__TOKEN_URL
        credential["username"] = c_WS_WITH_OAUTH__CLIENT_ID
        credential["password"] = c_WS_WITH_OAUTH__CLIENT_SECRET
        credential["headers"] = json.loads(c_WS_WITH_OAUTH__TOKEN_HEADERS)
        credential["method"] = c_WS_WITH_OAUTH__TOKEN_METHOD

        credential_id = self.backend.save_credential(credential)
        self.assertIsNotNone(credential_id)

        endpoint = empty_endpoint()
        endpoint["name"] = "Test Endpoint of oAuth"
        endpoint["url"] = c_WS_WITH_OAUTH__URL
        endpoint["method"] = c_WS_WITH_OAUTH__METHOD
        endpoint["body"] = c_WS_WITH_OAUTH__BODY
        endpoint["headers"] = json.loads(c_WS_WITH_OAUTH__HEADERS)
        endpoint["credential_id"] = credential_id

        endpoint_id = self.backend.save_endpoint(endpoint)
        self.assertIsNotNone(endpoint_id)

        response = self.backend.run_endpoint(endpoint_id)
        self.assertIsNotNone(response)

        self.assertIsNotNone(response.status_code)
        print("Status Code:", response.status_code)

        self.assertIsNotNone(response.headers)
        print("== Response Header ==")
        for key, value in response.headers.items():
            print(f"{key}: {value}")

        self.assertIsNotNone(response.text)
        print("== Response Text ==")
        print(response.text)

        self.assertIsNotNone(response.cookies)
        print("== Response Cookies ==")
        for cookie in response.cookies:
            print(f"{cookie.name} = {cookie.value}")

    def test_call_endpoint_with_oauth_json_token_response(self):
        print(sys._getframe().f_code.co_name + '...')

        credential = empty_credential(CredentialType.OAUTH_WITH_BASIC.value)
        credential["credential_type"] = CredentialType.OAUTH_WITH_BASIC.value
        credential["name"] = "Test Credential of oAuth with JSON Token"
        credential["url"] = c_WS_2_WITH_OAUTH__TOKEN_URL
        credential["username"] = c_WS_2_WITH_OAUTH__CLIENT_ID
        credential["password"] = c_WS_2_WITH_OAUTH__CLIENT_SECRET
        credential["headers"] = json.loads(c_WS_2_WITH_OAUTH__TOKEN_HEADERS)
        credential["method"] = c_WS_2_WITH_OAUTH__TOKEN_METHOD
        credential["body"] = json.loads(c_WS_2_WITH_OAUTH__TOKEN_BODY)
        credential["timeout"] = 300
        credential["response_token_json_field"] = c_WS_2_WITH_OAUTH__TOKEN_JSON_FIELD

        credential_id = self.backend.save_credential(credential)
        self.assertIsNotNone(credential_id)

        endpoint = empty_endpoint()
        endpoint["name"] = "Test Endpoint of oAuth with JSON Token"
        endpoint["url"] = c_WS_2_WITH_OAUTH__URL
        endpoint["method"] = c_WS_2_WITH_OAUTH__METHOD
        endpoint["body"] = c_WS_2_WITH_OAUTH__BODY
        endpoint["headers"] = json.loads(c_WS_2_WITH_OAUTH__HEADERS)
        endpoint["credential_id"] = credential_id
        endpoint["timeout"] = 300

        endpoint_id = self.backend.save_endpoint(endpoint)
        self.assertIsNotNone(endpoint_id)

        response = self.backend.run_endpoint(endpoint_id)
        self.assertIsNotNone(response)

        self.assertIsNotNone(response.status_code)
        print("Status Code:", response.status_code)

        self.assertIsNotNone(response.headers)
        print("== Response Header ==")
        for key, value in response.headers.items():
            print(f"{key}: {value}")

        self.assertIsNotNone(response.text)
        print("== Response Text ==")
        print(response.text)

        self.assertIsNotNone(response.cookies)
        print("== Response Cookies ==")
        for cookie in response.cookies:
            print(f"{cookie.name} = {cookie.value}")

    def test_credential_type_LOV(self):
        v = CredentialType.HEADER_KEY.value
        d = CredentialType.HEADER_KEY.display
        self.assertEqual(v, 'HeaderKey')
        self.assertEqual(d, 'Header Key')


class TestKrestGUI(unittest.TestCase):
    def test_run_gui(self):
        try:
            main_gui()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"run_gui raised an exception: {e}")


@unittest.skip
@pytest.mark.benchmark(
    group="health_check",
    min_time=0.1,
    max_time=0.2,
    min_rounds=5,
    timer=time.time,
    disable_gc=True,
    warmup=False
)
def test_circle_area_speed(benchmark):
    rst = benchmark(circle_area, 2)
    assert rst > 0


@unittest.skip
@pytest.mark.benchmark(group="kerest_backend", max_time=0.2, min_rounds=5, warmup=False, disable_gc=True)
def test_initialization_speed(benchmark):
    backend = benchmark(KrestBackend)
    print(f"Initialization took {backend} seconds")


@unittest.skip
@pytest.mark.benchmark(group="kerest_backend", max_time=0.2, min_rounds=5, warmup=False, disable_gc=True)
def test_bm2_speed(benchmark):
    backend = KrestBackend()
    benchmark(backend.set_password, "test_password")


if __name__ == "__main__":
    unittest.main()
