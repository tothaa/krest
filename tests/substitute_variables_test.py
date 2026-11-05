import pytest

from krest.krest_backend import KrestBackend


@pytest.fixture
def backend():
    return KrestBackend()


@pytest.mark.parametrize("marker,value,expected", [
    ("int", "42", 42),
    ("float", "3.5", 3.5),
    ("bool", "true", True),
    ("bool", " FALSE ", False),
    ("bool", False, False),
    ("str", 42, "42"),
    ("json", '{"items": [1, true, null]}', {"items": [1, True, None]}),
    ("json", "null", None),
    ("json", "[1, 2]", [1, 2]),
    ("int", " -12 ", -12),
    ("int", 0, 0),
    ("float", "1e3", 1000.0),
    ("float", 0, 0.0),
    ("bool", True, True),
    ("bool", "TrUe", True),
    ("str", None, "None"),
    ("str", False, "False"),
    ("json", '"hello"', "hello"),
    ("json", "3", 3),
    ("json", "3.5", 3.5),
    ("json", "false", False),
    ("file", "SGVsbG8=", b"Hello"),
    ("file", "AP8=", b"\x00\xff"),
    ("file", "", b""),
])
def test_explicit_type_conversion(backend, marker, value, expected):
    backend.file_data["variables"] = {"value": value}
    result = backend.substitute_variables("${value:" + marker + "}")
    assert result == expected
    assert type(result) is type(expected)


@pytest.mark.parametrize("marker,value", [
    ("int", "3.5"),
    ("float", "invalid"),
    ("bool", "no"),
    ("bool", 1),
    ("json", "{invalid}"),
    ("int", None),
    ("int", ""),
    ("int", []),
    ("int", float("inf")),
    ("float", None),
    ("bool", ""),
    ("bool", None),
    ("bool", []),
    ("json", None),
    ("json", {"already": "parsed"}),
    ("json", "{'not': 'json'}"),
    ("file", "not base64!"),
    ("file", "SGVsbG8"),
    ("file", "%%%"),
    ("file", "árvíz"),
    ("file", None),
    ("file", 123),
])
def test_invalid_conversion_identifies_variable_and_type(backend, marker, value):
    backend.file_data["variables"] = {"value": value}
    with pytest.raises(ValueError, match=f"Cannot convert variable 'value' to {marker}"):
        backend.substitute_variables("${value:" + marker + "}")


def test_unknown_type_is_rejected(backend):
    with pytest.raises(ValueError, match="Unsupported substitution type: integer"):
        backend.substitute_variables("${value:integer}")


def test_ordinary_missing_embedded_and_escaped_placeholders(backend):
    backend.file_data["variables"] = {"count": 3}
    assert backend.substitute_variables("${count}") == "3"
    assert backend.substitute_variables("Count: $count") == "Count: 3"
    assert backend.substitute_variables("${missing:int}") == "${missing:int}"
    assert backend.substitute_variables("${missing}") == "${missing}"
    assert backend.substitute_variables("Count: ${count:int}") == "Count: ${count:int}"
    assert backend.substitute_variables("$${count:int}") == "${count:int}"


def test_nested_payload_and_source_isolation(backend):
    backend.file_data["variables"] = {"key": "items", "count": "3", "items": '[{"id": 1}]'}
    source = {"${key}": ["${count:int}", "${items:json}", None, True]}
    result = backend.substitute_variables(source)
    assert result == {"items": [3, [{"id": 1}], None, True]}
    result["items"][1][0]["id"] = 2
    assert source == {"${key}": ["${count:int}", "${items:json}", None, True]}
    assert backend.file_data["variables"]["items"] == '[{"id": 1}]'


@pytest.mark.parametrize("value", [None, True, False, 0, 12, -1, 3.5])
def test_non_string_scalars_keep_their_types(backend, value):
    result = backend.substitute_variables(value)
    assert result == value
    assert type(result) is type(value)


@pytest.mark.parametrize("marker", ["int", "float", "bool", "str", "json", "file"])
def test_missing_typed_variables_are_preserved(backend, marker):
    placeholder = "${missing:" + marker + "}"
    assert backend.substitute_variables(placeholder) == placeholder


@pytest.mark.parametrize("text,expected", [
    ("", ""),
    ("plain text", "plain text"),
    ("$", "$"),
    ("$$", "$"),
    ("$${count}", "${count}"),
    ("${count", "${count"),
    ("${}", "${}"),
    ("${count} / $count", "3 / 3"),
    ("${count:int} items", "${count:int} items"),
    ("${count:}", "${count:}"),
])
def test_template_syntax_and_escaping(backend, text, expected):
    backend.file_data["variables"] = {"count": 3}
    assert backend.substitute_variables(text) == expected


def test_substitution_is_not_recursive_inside_variable_values(backend):
    backend.file_data["variables"] = {"first": "${second}", "second": "expanded"}
    assert backend.substitute_variables("${first}") == "${second}"


def test_empty_variables_and_empty_containers(backend):
    backend.file_data.pop("variables")
    assert backend.substitute_variables("${missing}") == "${missing}"
    for source in ({}, []):
        result = backend.substitute_variables(source)
        assert result == source
        assert result is not source


def test_nested_containers_are_copied_even_without_placeholders(backend):
    source = {"items": [{"values": [1, 2]}]}
    result = backend.substitute_variables(source)
    result["items"][0]["values"].append(3)
    assert source == {"items": [{"values": [1, 2]}]}


def test_json_conversion_returns_independent_containers(backend):
    backend.file_data["variables"] = {"payload": '{"items": []}'}
    first = backend.substitute_variables("${payload:json}")
    second = backend.substitute_variables("${payload:json}")
    first["items"].append(1)
    assert second == {"items": []}


@pytest.mark.parametrize("value", [b"binary", (1, 2), {1, 2}])
def test_unsupported_input_types_are_rejected(backend, value):
    with pytest.raises(Exception, match="Wrong type of data: " + type(value).__name__):
        backend.substitute_variables(value)


def test_conversion_error_preserves_original_cause(backend):
    backend.file_data["variables"] = {"count": "invalid"}
    with pytest.raises(ValueError) as error:
        backend.substitute_variables("${count:int}")
    assert isinstance(error.value.__cause__, ValueError)


@pytest.mark.parametrize("value,expected", [(None, "None"), (False, "False"), (0, "0"), ("", "")])
def test_present_falsy_values_are_not_treated_as_missing(backend, value, expected):
    backend.file_data["variables"] = {"value": value}
    assert backend.substitute_variables("${value:str}") == expected


def test_underscore_and_digit_variable_names(backend):
    backend.file_data["variables"] = {"_count2": "7"}
    assert backend.substitute_variables("${_count2:int}") == 7
    assert backend.substitute_variables("${_count2}") == "7"


def test_file_substitution_in_nested_payload_preserves_source(backend):
    backend.file_data["variables"] = {"attachment": "AP8="}
    source = {"files": ["${attachment:file}"]}
    assert backend.substitute_variables(source) == {"files": [b"\x00\xff"]}
    assert source == {"files": ["${attachment:file}"]}
    assert backend.file_data["variables"]["attachment"] == "AP8="


def test_tracking_records_only_substituted_variables_in_keys_and_nested_values(backend):
    backend.file_data["variables"] = {
        "key": "items", "count": "3", "plain": "hello", "unused": "secret",
        "file": "AP8=", "escaped": "secret", "embedded": "4",
    }
    used = {}
    result = backend.substitute_variables({
        "${key}": ["${count:int}", "$plain ${plain}", "${file:file}",
                    "${missing}", "${missing:int}", "$${escaped}", "text ${embedded:int}"],
    }, used)
    assert result["items"][:3] == [3, "hello hello", b"\x00\xff"]
    assert used == {"key": "items", "count": "3", "plain": "hello", "file": "AP8="}


def test_tracking_does_not_expand_references_inside_variable_values(backend):
    backend.file_data["variables"] = {"first": "${second}", "second": "not expanded"}
    used = {}
    assert backend.substitute_variables("${first}", used) == "${second}"
    assert used == {"first": "${second}"}


def test_tracking_copies_mutable_values_at_substitution_time(backend):
    backend.file_data["variables"] = {"payload": {"items": [1]}}
    used = {}
    backend.substitute_variables("${payload}", used)
    backend.file_data["variables"]["payload"]["items"].append(2)
    assert used == {"payload": {"items": [1]}}


def test_tracking_keeps_falsy_values_and_excludes_escaped_placeholders(backend):
    backend.file_data["variables"] = {"false": False, "zero": 0, "empty": "", "none": None}
    used = {}
    backend.substitute_variables(["$false", "$zero", "$empty", "${none:str}", "$$"], used)
    assert used == backend.file_data["variables"]
