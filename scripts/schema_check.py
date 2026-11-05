"""Minimal JSON Schema checker, standard library only.

triply's scripts must run on Python 3.9 with nothing else installed, so this
module implements the small subset of JSON Schema (draft 2020-12) that
triply's own schemas use. Any keyword outside the subset raises an error, so a
schema can never silently rely on something that is not checked.
"""

from __future__ import annotations

import datetime
import re
from typing import Any, Dict, Iterator, List, Tuple

# Keywords that only document the schema and are not checked.
ANNOTATIONS = {"$schema", "$id", "title", "description"}

# Keywords that are checked.
SUPPORTED = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "propertyNames",
    "items",
    "enum",
    "const",
    "minimum",
    "maximum",
    "minLength",
    "minItems",
    "pattern",
    "format",
    "$ref",
    "$defs",
}

FORMATS = {"date"}

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "null": lambda v: v is None,
}


class SchemaError(Exception):
    """The schema itself uses something this checker does not support."""


def unsupported_keywords(schema: Any, path: str = "#") -> List[str]:
    """Return the paths of keywords in ``schema`` that this checker cannot check."""
    found: List[str] = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            here = f"{path}/{key}"
            if key in ANNOTATIONS:
                continue
            if key not in SUPPORTED:
                found.append(here)
                continue
            if key == "format" and value not in FORMATS:
                found.append(here)
            if key in ("properties", "$defs"):
                for name, sub in value.items():
                    found.extend(unsupported_keywords(sub, f"{here}/{name}"))
            elif key in ("items", "additionalProperties", "propertyNames"):
                if isinstance(value, dict):
                    found.extend(unsupported_keywords(value, here))
    return found


def check(instance: Any, schema: Dict[str, Any]) -> List[Tuple[str, str]]:
    """Check ``instance`` against ``schema``.

    Returns a list of ``(path, message)`` pairs, empty when the instance is
    valid. Paths use JSON Pointer notation, for example ``/days/0/date``.
    """
    bad = unsupported_keywords(schema)
    if bad:
        raise SchemaError("unsupported schema keywords: " + ", ".join(bad))
    return list(_check(instance, schema, schema, ""))


def _resolve(root: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise SchemaError(f"only local references are supported: {ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _show(value: Any) -> str:
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _check(value: Any, schema: Dict[str, Any], root: Dict[str, Any], path: str) -> Iterator[Tuple[str, str]]:
    where = path or "/"

    if "$ref" in schema:
        yield from _check(value, _resolve(root, schema["$ref"]), root, path)

    if "const" in schema and value != schema["const"]:
        yield where, f"must be {_show(schema['const'])}, found {_show(value)}"
        return

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(str(v) for v in schema["enum"])
        yield where, f"must be one of: {allowed}; found {_show(value)}"
        return

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPES[t](value) for t in types):
            yield where, f"must be of type {' or '.join(types)}, found {_show(value)}"
            return

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            yield where, f"must have at least {schema['minLength']} character(s)"
        if "pattern" in schema and not re.search(schema["pattern"], value):
            yield where, f"does not match the pattern {schema['pattern']}: {_show(value)}"
        if schema.get("format") == "date" and not _is_date(value):
            yield where, f"must be a date in the form YYYY-MM-DD, found {_show(value)}"

    if _TYPES["number"](value):
        if "minimum" in schema and value < schema["minimum"]:
            yield where, f"must be at least {schema['minimum']}, found {value}"
        if "maximum" in schema and value > schema["maximum"]:
            yield where, f"must be at most {schema['maximum']}, found {value}"

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            yield where, f"must have at least {schema['minItems']} item(s)"
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                yield from _check(item, schema["items"], root, f"{path}/{index}")

    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                yield where, f"missing required field '{name}'"
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        names = schema.get("propertyNames")
        for name, item in value.items():
            child = f"{path}/{name}"
            if isinstance(names, dict):
                for _, message in _check(name, names, root, child):
                    yield child, f"invalid key: {message}"
            if name in properties:
                yield from _check(item, properties[name], root, child)
            elif extra is False:
                yield child, "unknown field"
            elif isinstance(extra, dict):
                yield from _check(item, extra, root, child)


def _is_date(text: str) -> bool:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return False
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True
