from collections import UserDict

import pytest

from krest.krest_backend import get_value_by_path


@pytest.fixture
def example_data():
    return {
        "users": [{"name": "Ada"}, {"name": "Grace"}],
        "headers": {"content-type": "application/json"},
        "a.b": "literal dotted key",
        "": 42,
    }


@pytest.mark.parametrize("path,expected", [
    ("$.users[0].name", "Ada"),
    ("$.users[-1].name", "Grace"),
    ("$.headers.content-type", "application/json"),
    ("$['a.b']", "literal dotted key"),
    ('$[""]', 42),
])
def test_documented_examples(example_data, path, expected):
    assert get_value_by_path(example_data, path) == expected


def test_example_root_preserves_identity(example_data):
    assert get_value_by_path(example_data, "$") is example_data


@pytest.mark.parametrize("path,default", [("$.missing", None), ("$.users[99]", [])])
def test_example_fallbacks(example_data, path, default):
    assert get_value_by_path(example_data, path, default=default) is default


@pytest.mark.parametrize("path,error", [
    ("$.missing", KeyError),
    ("$.users[0].name[0]", TypeError),
])
def test_example_lookup_errors(example_data, path, error):
    with pytest.raises(error):
        get_value_by_path(example_data, path)


def test_invalid_suffix_after_missing_key(example_data):
    with pytest.raises(ValueError, match="Invalid path syntax at position"):
        get_value_by_path(example_data, "$.missing[abc]", default=None)


def test_string_key_is_distinct_from_sequence_index():
    assert get_value_by_path({"0": "key"}, "$['0']") == "key"
    assert get_value_by_path(["index"], "$[0]") == "index"
    with pytest.raises(TypeError):
        get_value_by_path({"0": "key"}, "$[0]")
    with pytest.raises(TypeError):
        get_value_by_path(["index"], "$['0']")


@pytest.mark.parametrize("data", [{}, [], None, 42, "text"])
def test_root_returns_original_data(data):
    assert get_value_by_path(data, "$") is data


@pytest.mark.parametrize("data,path,expected", [
    ({"user": {"name": "Ada"}}, "$.user.name", "Ada"),
    ({"items": [{"name": "first"}, {"name": "last"}]}, "$.items[1].name", "last"),
    ([10, 20], "$[0]", 10),
    ([10, 20], "$[-1]", 20),
    ([10, 20], "$[-2]", 10),
    ([[1, 2], [3, 4]], "$[1][0]", 3),
    ((10, 20), "$[1]", 20),
    (UserDict({"name": "Ada"}), "$.name", "Ada"),
    ({"access-token": "token"}, "$.access-token", "token"),
    ({"full name": "Ada"}, "$.full name", "Ada"),
    ({"a.b": {"[key]": 7}}, "$['a.b'][\"[key]\"]", 7),
    ({"": 1}, "$['']", 1),
    ({"": 2}, '$[""]', 2),
    ({"0": "zero"}, "$['0']", "zero"),
    ({"it's": 3}, '$["it\'s"]', 3),
    ({'say "hi"': 4}, "$['say \"hi\"']", 4),
])
def test_resolves_supported_paths(data, path, expected):
    assert get_value_by_path(data, path) == expected


@pytest.mark.parametrize("value", [None, False, 0, "", [], {}])
def test_existing_values_are_not_replaced_by_default(value):
    assert get_value_by_path({"value": value}, "$.value", default=object()) is value


@pytest.mark.parametrize("data,path", [
    ({}, "$.missing"),
    ({"nested": {}}, "$.nested.missing.value"),
    ([], "$[0]"),
    ([1], "$[1]"),
    ([1], "$[-2]"),
    ({0: "zero"}, "$[0]"),
    ([1], "$.key"),
    (None, "$.key"),
    (42, "$[0]"),
    ("text", "$[0]"),
    (b"text", "$[0]"),
    (bytearray(b"text"), "$[0]"),
    ({"value": None}, "$.value.key"),
])
@pytest.mark.parametrize("default", [None, False, 0, "fallback", object()])
def test_failed_lookup_returns_explicit_default(data, path, default):
    assert get_value_by_path(data, path, default=default) is default


@pytest.mark.parametrize("path", [None, 1, [], {}, b"$.key"])
def test_non_string_path_raises_type_error(path):
    with pytest.raises(TypeError, match="path must be a string"):
        get_value_by_path({}, path, default=None)


@pytest.mark.parametrize("path", ["", "key", ".key", "[0]"])
def test_path_without_root_raises_value_error(path):
    with pytest.raises(ValueError, match=r"path must start with \$"):
        get_value_by_path({}, path, default=None)


@pytest.mark.parametrize("path", [
    "$.", "$..key", "$[]", "$[key]", "$[1", "$['key]", '$["key]',
    "$[1.5]", "$[+1]", "$[*]", "$[0:1]", "$[0]trailing", "$.key]",
    "$.missing[",  # Validate the entire path before attempting a lookup.
])
def test_invalid_syntax_raises_even_with_default(path):
    with pytest.raises(ValueError, match="Invalid path syntax at position"):
        get_value_by_path({}, path, default=None)


@pytest.mark.parametrize("data,path,error", [
    ({}, "$.missing", KeyError),
    ([], "$[0]", IndexError),
    (None, "$.key", TypeError),
    ("text", "$[0]", TypeError),
])
def test_failed_lookup_without_default_raises(data, path, error):
    with pytest.raises(error):
        get_value_by_path(data, path)
