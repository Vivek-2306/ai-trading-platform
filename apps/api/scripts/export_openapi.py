"""Write the API's OpenAPI schema to a file (or stdout). Used by the typed client and Postman."""

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def main() -> None:
    schema = create_app(Settings(_env_file=None)).openapi()
    text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
