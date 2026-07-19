# Deterministic, value-independent structure fingerprint shared by the recorder (T5)
# and the divergence detector (T19).

import hashlib
from typing import Any


def canonical_structure(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, dict):
        fields = ",".join(f"{k}:{canonical_structure(value[k])}" for k in sorted(value))
        return "{" + fields + "}"
    if isinstance(value, (list, tuple)):
        distinct = sorted({canonical_structure(e) for e in value})
        return "[" + ",".join(distinct) + "]"
    raise TypeError(f"schema_fingerprint: unsupported type {type(value).__name__!r}")


def schema_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_structure(value).encode("utf-8")).hexdigest()[:16]
