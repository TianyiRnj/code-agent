"""Tool registry: @tool decorator, JSON-schema generation, and dispatch."""

from __future__ import annotations

import inspect
import types
import typing
from dataclasses import dataclass
from typing import Any, Callable, TypeVar, get_args, get_origin, get_type_hints

# Parameters that are injected at runtime and must not appear in the schema.
_RUNTIME_PARAMS = frozenset({"guard"})

F = TypeVar("F", bound=Callable[..., Any])

_REGISTRY: list["ToolDef"] = []


@dataclass
class ToolDef:
    """A registered tool with its Claude-API-compatible JSON schema."""

    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., Any]


def tool(fn: F) -> F:
    """Register fn as a tool; the first docstring line becomes its description."""
    raw_doc = fn.__doc__ or ""
    description = raw_doc.strip().splitlines()[0].rstrip(".")
    schema = _schema_from_fn(fn)
    _REGISTRY.append(ToolDef(name=fn.__name__, description=description, input_schema=schema, fn=fn))
    return fn


def all_tools() -> list[ToolDef]:
    """Return all registered tool definitions."""
    return list(_REGISTRY)


def execute(name: str, args: dict[str, Any], **inject: Any) -> Any:
    """Dispatch a tool call by name, injecting runtime params (e.g. guard=...)."""
    for td in _REGISTRY:
        if td.name == name:
            params = inspect.signature(td.fn).parameters
            extra = {k: v for k, v in inject.items() if k in params}
            return td.fn(**args, **extra)
    raise KeyError(f"unknown tool: {name!r}")


# ---------------------------------------------------------------------------
# JSON-schema generation
# ---------------------------------------------------------------------------


def _schema_from_fn(fn: Callable[..., Any]) -> dict[str, Any]:
    sig = inspect.signature(fn)
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        if pname in _RUNTIME_PARAMS:
            continue
        annotation = hints.get(pname)
        properties[pname] = _to_json_schema(annotation)
        if param.default is inspect.Parameter.empty:
            required.append(pname)

    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _to_json_schema(tp: Any) -> dict[str, Any]:
    """Convert a Python type annotation to a JSON Schema dict."""
    if tp is None or tp is type(None):
        return {"type": "null"}
    if tp is str:
        return {"type": "string"}
    if tp is int:
        return {"type": "integer"}
    if tp is bool:
        return {"type": "boolean"}

    origin = get_origin(tp)
    args = get_args(tp)

    # Handle Union (typing.Union and Python 3.10+ X | Y syntax)
    is_union = origin is typing.Union or (
        hasattr(types, "UnionType") and isinstance(tp, types.UnionType)
    )
    if is_union:
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _to_json_schema(non_none[0])

    if origin is list:
        return {"type": "array", "items": _to_json_schema(args[0]) if args else {}}

    return {"type": "string"}  # safe fallback for unknown types
