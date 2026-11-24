"""Generate the Postman collection and environment from the API's OpenAPI schema.

Output is deterministic (no random IDs), so CI can fail when the committed files are stale.
Usage: python scripts/export_postman.py <output directory>
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import Settings
from app.main import create_app

HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _request_item(path: str, method: str, op: dict[str, Any]) -> dict[str, Any]:
    expected = sorted(int(code) for code in op.get("responses", {}) if code.isdigit())
    ok = next((code for code in expected if 200 <= code < 300), 200)
    description = "\n\n".join(p for p in (op.get("summary"), op.get("description")) if p)
    codes = ", ".join(str(code) for code in expected)
    return {
        "name": op.get("summary") or f"{method.upper()} {path}",
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": [
                        f'pm.test("status is {ok}", () => pm.response.to.have.status({ok}));',
                        'pm.test("has request id",'
                        ' () => pm.response.to.have.header("X-Request-ID"));',
                    ],
                },
            }
        ],
        "request": {
            "method": method.upper(),
            "header": [{"key": "Accept", "value": "application/json"}],
            "url": {
                "raw": "{{baseUrl}}" + path,
                "host": ["{{baseUrl}}"],
                "path": [part for part in path.split("/") if part],
            },
            "description": f"{description}\n\nDocumented responses: {codes}".strip(),
        },
    }


def build_collection(schema: dict[str, Any]) -> dict[str, Any]:
    folders: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(schema["paths"]):
        for method in HTTP_METHODS:
            op = schema["paths"][path].get(method)
            if op:
                folder = (op.get("tags") or ["other"])[0]
                folders.setdefault(folder, []).append(_request_item(path, method, op))
    info = schema["info"]
    return {
        "info": {
            "name": f"{info['title']} (API {info['version']})",
            "description": "Generated from the OpenAPI schema. Do not edit by hand: "
            "run `pnpm api:postman`.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [{"name": name, "item": items} for name, items in sorted(folders.items())],
        "variable": [{"key": "baseUrl", "value": "http://localhost:8000"}],
    }


def build_environment() -> dict[str, Any]:
    return {
        "name": "AI Trading Platform - local",
        "values": [{"key": "baseUrl", "value": "http://localhost:8000", "enabled": True}],
        "_postman_variable_scope": "environment",
    }


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    schema = create_app(Settings(_env_file=None)).openapi()
    files = {
        "postman_collection.json": build_collection(schema),
        "local.postman_environment.json": build_environment(),
    }
    for name, content in files.items():
        (out / name).write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
