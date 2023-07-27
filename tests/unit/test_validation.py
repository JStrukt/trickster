from fastjsonschema.exceptions import JsonSchemaValueException
import flask
import pytest
from trickster.validation import get_validator, request_schema


@pytest.mark.unit
class TestJsonSchemaValidation:
    def test_schema_path_returns_absolute_path(self):
        path = get_validator("route.schema.json").path
        assert path.name == "route.schema.json"
        assert path.is_absolute
        assert path.exists()

    def test_compiled_json_schema_is_cached(self):
        validator1 = get_validator("route.schema.json").compiled
        validator2 = get_validator("route.schema.json").compiled
        assert validator1 is validator2

    def test_compile_valid_json_schema(self, tmpdir):
        schema = tmpdir.join("test.schema.json")
        schema.write(
            """{
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"property": {"type": "number"}},
            "required": ["property"]
        }"""
        )
        validate = get_validator("test.schema.json", base_dir=tmpdir).compiled
        validate({"property": 2})

    def test_compile_invalid_json_schema(self, tmpdir):
        schema = tmpdir.join("test.schema.json")
        schema.write(
            """{
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {"property": {"type": "number"}},
            "required": ["property"]
        }"""
        )
        validate = get_validator("test.schema.json", base_dir=tmpdir).compiled
        with pytest.raises(JsonSchemaValueException):
            validate({"property": "string"})

    def test_valid_schema_decorator(self):
        app = flask.Flask(__name__)

        @app.route("/", methods=["POST"])
        @request_schema("request.schema.json")
        def endpoint():
            return "success"

        with app.test_client() as client:
            response = client.post("/", json={"path": "/", "method": "GET"})
            assert response.data == b"success"
            assert response.status_code == 200

    def test_invalid_schema_decorator(self):
        app = flask.Flask(__name__)

        @app.route("/", methods=["POST"])
        @request_schema("request.schema.json")
        def endpoint():
            return "success"

        with app.test_client() as client:
            response = client.post("/", json={"invalid": True})
            assert response.status_code == 400
