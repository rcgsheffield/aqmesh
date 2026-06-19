[![Python CI](https://github.com/rcgsheffield/aqmesh/actions/workflows/python-ci.yml/badge.svg)](https://github.com/rcgsheffield/aqmesh/actions/workflows/python-ci.yml)
[![DOI](https://img.shields.io/badge/DOI-10.15131%2Fshef.data.17113328-blue)](https://doi.org/10.15131/shef.data.17113328)

# AQMesh Data Pipeline

Outdoor air quality sensors data pipeline for the [AQMesh](https://www.aqmesh.com) platform.

It downloads all raw readings from the AQMesh API to a shared storage volume and cleans them into
research-ready CSV. Orchestrated with [Prefect 3](https://docs.prefect.io/v3/get-started).

```
AQMesh API ──► client.py ──► flows/ingest.py ──► raw/   (append-only JSON)
                                                      │
                                                      ▼
                                         flows/clean.py ──► clean/ (calibrated CSVs)

Scheduled hourly at :06 (Europe/London) by Prefect 3
CLI: aqmesh pipeline | ingest | clean | check
```

## Documentation

| | |
| --- | --- |
| **[docs/](docs/README.md)** | Operator index — deployment, service management, troubleshooting |
| **[docs/architecture.md](docs/architecture.md)** | System internals — modules, infrastructure, data layout |

## Development

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the full guide to setting up your environment,
coding standards, and submitting changes. Quick start:

```bash
uv sync                       # create venv + install deps
cp .env.example .env          # then fill in AQMESH_USERNAME / AQMESH_PASSWORD
uv run ruff check .           # lint
uv run pytest                 # tests

# Run flows locally without a Prefect server (uses the test API by default):
uv run aqmesh ingest          # download raw data only
uv run aqmesh clean           # rebuild CSVs from the raw store
uv run aqmesh pipeline        # ingest + clean (default)
```

Configuration is environment-driven (see `.env.example`); set `AQMESH_ENVIRONMENT=test` to target
`apitest.aqmeshdata.net` or `prod` for `api.aqmeshdata.net`.

## Production deployment (Ubuntu 24.04 VPS)

Self-hosted Prefect server + worker, managed by systemd. From a checkout on the VM:

```bash
sudo APP_DIR=/opt/aqmesh DATA_ROOT=/mnt/aqmesh-data bash deploy/bootstrap.sh
```

See **[docs/deployment.md](docs/deployment.md)** for the full deployment and verification guide.

## Citation

If you use this software in research, please cite it. Citation metadata lives in
[CITATION.cff](CITATION.cff) (GitHub shows a "Cite this repository" button from it).

Releases are archived in [ORDA](https://orda.shef.ac.uk), the University of
Sheffield's institutional repository, which mints a DOI per version. See
[docs/publish.md](docs/publish.md) for how that works. A DOI badge will be added
here once the first release is deposited.

## Generative AI usage

Parts of this repository were written with AI assistance under human direction. See
[AI-STATEMENT.md](AI-STATEMENT.md) for details.
