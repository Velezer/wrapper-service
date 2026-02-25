# AGENTS.md

## Repository scope
These instructions apply to the entire repository.

## Development guidelines
- Keep changes small and focused.
- Prefer straightforward Python with explicit, readable control flow.
- Add or update tests for behavior changes.

## Test and CI expectations
- Run `pytest` locally before committing.
- Keep GitHub Actions workflows minimal and deterministic.

## Notes for e2e tests
- End-to-end tests should exercise the HTTP API through a running server process.
- Avoid monkeypatching or mocking subprocess execution in e2e tests.
