# Contributing to aqmesh

Thanks for your interest in improving **aqmesh**. Contributions — bug reports, fixes,
docs, and features — are welcome. Please be respectful and constructive in all
interactions.

The repository is [`rcgsheffield/aqmesh`](https://github.com/rcgsheffield/aqmesh).

## Reporting issues and suggesting changes

Open a [GitHub issue](https://github.com/rcgsheffield/aqmesh/issues). For bugs, include:

- what you did (steps to reproduce),
- what you expected vs. what happened,
- your environment (OS, Python version, `test` or `prod`).

For larger changes, please open an issue to discuss before sending a pull request.

## Development setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+. See the
[README](README.md#development) for full details. In short:

```bash
uv sync                       # create venv + install deps
cp .env.example .env          # fill in AQMESH_USERNAME / AQMESH_PASSWORD
uv run ruff check .           # lint
uv run pytest                 # tests
```

> [!WARNING]
> Always use **test credentials** (`AQMESH_ENVIRONMENT=test`) when running the pipeline
> locally. The AQMesh API advances the data cursor server-side on every successful
> request; running with production credentials during local development will modify
> production state and may cause the live pipeline to skip data.

We use [pre-commit](https://pre-commit.com/) to keep `uv.lock` in sync with
`pyproject.toml` (CI rejects a stale lockfile). Install and enable the hooks once per
clone:

```bash
uv tool install pre-commit    # one-time, installs the tool
pre-commit install            # enable the hooks in this clone
```

If you edit dependencies, run `uv lock` to regenerate `uv.lock` and commit it alongside
`pyproject.toml`.

## Coding standards

- **Lint:** code must pass `uv run ruff check .` (rules and 100-char line length are
  configured in `pyproject.toml`).
- **Tests:** add or update tests under `tests/` for any behaviour change, and make
  sure `uv run pytest` passes.
- **Layout:** this is a uv workspace with two packages — the pipeline lives under
  `src/aqmesh_pipeline/`, the standalone API client under
  `packages/aqmesh-client/src/aqmesh_client/`. Keep new modules in the package they
  belong to; only the client may be imported by the pipeline, never the reverse.

## Submitting changes

1. Branch off `main` and keep each pull request focused on one change.
2. Make sure lint and tests pass locally.
3. Write a clear PR description explaining what changed and why.
4. Note significant AI assistance in the PR when it's material to review
   (see below).

## Generative AI

You're welcome to use AI tools when contributing — please follow the contributor
guidance in [AI-STATEMENT.md](AI-STATEMENT.md): review and understand every line you
submit, keep lint and tests passing, and never share secrets or non-public research
data with third-party AI services.

## Licence

By contributing, you agree that your contributions are licensed under the MIT
[LICENSE](LICENSE).

## Contact

Questions can be directed to the IT Services Research & Innovation team at
`research-it@sheffield.ac.uk`, University of Sheffield.
