"""The Postman collection must cover every endpoint the API exposes."""

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from app.core.config import Settings
from app.main import create_app

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_postman.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_postman", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collection_has_every_endpoint() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    collection = _load_script().build_collection(schema)

    urls = {
        item["request"]["url"]["raw"] for folder in collection["item"] for item in folder["item"]
    }

    # Postman writes path parameters as :name where OpenAPI writes {name}.
    expected = {"{{baseUrl}}" + re.sub(r"{(\w+)}", r":\1", path) for path in schema["paths"]}
    assert urls == expected


def test_collection_is_deterministic() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    module = _load_script()

    assert module.build_collection(schema) == module.build_collection(schema)


def test_path_parameters_use_postman_syntax() -> None:
    schema = {
        "info": {"title": "T", "version": "1"},
        "paths": {"/items/{item_id}": {"get": {"summary": "Get item", "responses": {"200": {}}}}},
    }

    url = _load_script().build_collection(schema)["item"][0]["item"][0]["request"]["url"]

    assert url["raw"] == "{{baseUrl}}/items/:item_id"
    assert url["path"] == ["items", ":item_id"]
    assert [v["key"] for v in url["variable"]] == ["item_id"]
