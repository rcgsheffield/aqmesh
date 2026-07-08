# Releasing

Releases are automated with
[release-please](https://github.com/googleapis/release-please). You don't tag or
bump versions by hand — the version, `CHANGELOG.md`, the git tag, and the GitHub
release are all derived from commit messages on `main`.

## How it works

1. **Commits use [Conventional Commits](https://www.conventionalcommits.org/).**
   The prefix on each commit determines the version bump:

   | Prefix                          | Example                                  | Bump      |
   | ------------------------------- | ---------------------------------------- | --------- |
   | `fix:`                          | `fix: handle empty LocationData batch`   | patch     |
   | `feat:`                         | `feat: add 5-minute resampling`          | minor     |
   | `feat!:` / `BREAKING CHANGE:`   | `feat!: drop Python 3.11 support`        | major     |
   | `docs:` `chore:` `ci:` `test:`  | `docs: clarify deployment steps`         | none\*    |

   \* These still appear in the changelog under their category but don't trigger a
   release on their own.

2. **release-please opens a "release PR."** As qualifying commits land on `main`,
   a bot keeps an open pull request titled like `chore(main): release 0.2.0`. It
   contains the proposed `CHANGELOG.md` entries and the version bump in
   `pyproject.toml`. Review it like any other PR.

3. **Merging the release PR cuts the release.** On merge, release-please:
   - bumps `version` in `pyproject.toml`,
   - updates `CHANGELOG.md`,
   - creates the git tag (e.g. `v0.2.0`),
   - publishes a GitHub Release with the generated notes.

## Cutting a release

1. Make sure the changes you want are merged to `main` with conventional-commit
   messages, and CI is green.
2. Open the release PR (the one titled `chore(main): release …`), check the
   changelog and version look right, and merge it.
3. That's it — the tag and GitHub Release appear automatically. Deployments pull
   from `main` (see [docs/deployment.md](docs/deployment.md)); check out the new
   tag on the VM if you want to pin to a release.

## Deciding the version

We follow [Semantic Versioning](https://semver.org/). While the project is
pre-1.0 (`0.x`), the public surface (CLI commands, config, data layout) may still
change between minor versions; breaking changes bump the minor rather than the
major. Once the API stabilises we'll release `1.0.0`.

## Notes

- This repo is a uv workspace with two independently released packages, configured as
  separate entries in `release-please-config.json`/`.release-please-manifest.json`:
  the `.` package (`aqmesh-pipeline`, this file's flow above) and
  `packages/aqmesh-client` (`aqmesh-client`), which gets its own component-prefixed
  tags (`aqmesh-client-vX.Y.Z`) and changelog since it bumps independently of the
  pipeline.
- `aqmesh-client` is published to PyPI on each of its releases via
  [`.github/workflows/publish-to-pypi.yml`](.github/workflows/publish-to-pypi.yml),
  using [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) —
  no stored API token. `aqmesh-pipeline` itself isn't published to PyPI; its releases
  remain version markers + changelog + GitHub Releases for the deployed pipeline.
- To force a specific next version, add `Release-As: x.y.z` to a commit body.
- Configuration lives in `release-please-config.json` and
  `.release-please-manifest.json` at the repo root.
