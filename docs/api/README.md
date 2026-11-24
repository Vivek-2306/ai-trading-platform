# API collection (Postman)

- `postman_collection.json`: every API endpoint, grouped by tag, with basic status checks.
- `local.postman_environment.json`: the `baseUrl` variable (default `http://localhost:8000`).

**Generated, do not edit by hand.** After any API change run `pnpm api:postman` and commit the result.
CI fails if the committed files are out of date.

Import: Postman → Import → select both files → choose the "AI Trading Platform - local" environment.
For the phone tunnel, set `baseUrl` to the tunnel URL plus `/api`.

The endpoint details (request, response, errors) live in the Notion "API Reference" database.
