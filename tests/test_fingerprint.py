import pytest

from habit.schemas import schema_fingerprint


def test_value_independence() -> None:
    a = schema_fingerprint({"a": 1, "b": "x"})
    b = schema_fingerprint({"a": 99, "b": "yyyy"})
    assert a == b


def test_key_order_independence() -> None:
    assert schema_fingerprint({"a": 1, "b": 2}) == schema_fingerprint({"b": 2, "a": 1})


def test_structure_sensitivity() -> None:
    assert schema_fingerprint({"a": 1}) != schema_fingerprint({"a": 1, "b": 2})


def test_type_sensitivity() -> None:
    assert schema_fingerprint({"a": 1}) != schema_fingerprint({"a": "1"})


def test_nested_deterministic() -> None:
    value = {
        "rows": [{"id": 1, "tags": ["x", "y"]}, {"id": 2, "tags": ["z"]}],
        "ok": True,
    }
    assert schema_fingerprint(value) == schema_fingerprint(value)


def test_unsupported_type_raises() -> None:
    with pytest.raises(TypeError):
        schema_fingerprint({1, 2, 3})
