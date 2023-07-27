"""This module provides validation of Incoming requests."""

import functools
from json import JSONDecoder
from pathlib import Path
from typing import Any, Callable, Dict, List

from fastjsonschema import compile
from fastjsonschema import JsonSchemaException
import flask

HERE = Path(__file__).resolve().parent
SCHEMAS = HERE / "schemas"


class Validator:
    def __init__(self, schema: str, base_dir: Path = SCHEMAS) -> None:
        self.base_dir = base_dir
        self.schema = schema

    @functools.cached_property
    def path(self) -> Path:
        """Return path to json schema file."""
        return self.base_dir / self.schema

    @functools.cached_property
    def as_text(self) -> str:
        """Return content of json schema file as utf-8 decoded str."""
        return self.path.read_text(encoding="utf-8")

    @functools.cached_property
    def as_obj(self) -> str:
        return JSONDecoder().decode(
            self.as_text,
        )

    @functools.cached_property
    def compiled(self) -> Callable:
        """Compiles given schema to fastjson validation function."""
        return compile(self.as_obj)

    def __call__(self, json_data: Any) -> None:
        self.compiled(json_data)


@functools.lru_cache(typed=True)
def get_validator(schema: str, base_dir: Path = SCHEMAS) -> Validator:
    return Validator(schema=schema, base_dir=base_dir)


def request_schema(name: str) -> Callable:
    """Validate current request payload with given json schema.

    `request_schema` can be used only as a flask endpoint decorator. Must be
    called within request scope.
    """

    def request_schema_decorator(func: Callable) -> Callable:
        validate = get_validator(name)

        @functools.wraps(func)
        def request_schema_wrapper(*args: List[Any], **kwargs: Dict[str, Any]) -> Any:
            try:
                payload = flask.request.get_json()
                validate(payload)
                return func(*args, **kwargs)
            except JsonSchemaException as e:
                flask.abort(400, e.message)

        return request_schema_wrapper

    return request_schema_decorator
