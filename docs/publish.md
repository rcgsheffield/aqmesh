# Publishing releases

This repo publishes two independent artifacts on release, each with its own
workflow: the **aqmesh-pipeline** repo snapshot is archived to **ORDA** for a
citable DOI, and the **aqmesh-client** package is published to **PyPI**. See
[RELEASING.md](../RELEASING.md) for how release-please cuts releases for each
package.

## Publishing a citable release (ORDA + DOI)

This pipeline is archived in **[ORDA](https://orda.shef.ac.uk)**, the University of
Sheffield's institutional research repository, so each release gets a persistent,
version-pinned **DOI** and can be cited in papers. ORDA is the University's
Figshare instance; it is managed by the Library's Research Data Management team
and mints a DataCite DOI for every record.

The GitHub side is automated: when you publish a GitHub Release, the
[`release-to-orda`](../.github/workflows/release-to-orda.yml) workflow uploads the
release archives to a pre-created ORDA item, which ORDA records as a new version.
The workflow skips `aqmesh-client-vX.Y.Z` releases — the ORDA item is for the
pipeline, not the standalone client library (see
[Publishing aqmesh-client to PyPI](#publishing-aqmesh-client-to-pypi) below).

> **Why a GitHub Action and not Figshare's "Connect to GitHub" button?** That
> connector is a feature of the public `figshare.com`; ORDA (the institutional
> instance) does not expose it. The supported route — used by the University's RSE
> team in [`RSE-Sheffield/release_to_ORDA`](https://github.com/RSE-Sheffield/release_to_ORDA)
> — is to push release archives to ORDA over the Figshare API via
> [`figshare/github-upload-action`](https://github.com/figshare/github-upload-action),
> which is what the workflow here does.

### One-time setup

You need a Sheffield account: only current staff and research students can deposit
in ORDA, and access ends when your contract does.

#### 1. Create the ORDA item

1. Log in to [orda.shef.ac.uk](https://orda.shef.ac.uk) with your Sheffield SSO.
2. Create a new item (item type **Software**) and fill in the metadata — title,
   authors, description, keywords, license (MIT, to match this repository).
   Keep it consistent with [`CITATION.cff`](../CITATION.cff).
3. **Do not upload any files** — the workflow uploads the release archives. Reserve
   the DOI / save the item.
4. Note the **article ID**: it is the integer at the end of the DOI. For example
   the DOI `10.15131/shef.data.17113328` has article ID `17113328`.

#### 2. Generate a Figshare API token

From your ORDA account, go to **Account settings → Applications → Create Personal
Token**, give it a description, and copy the token (you only see it once). See
Figshare's [how to connect Figshare with your GitHub account](https://info.figshare.com/user-guide/how-to-connect-figshare-with-your-github-account/)
guide for reference.

#### 3. Configure the GitHub repository

In the repo's **Settings → Secrets and variables → Actions**:

| Kind     | Name                  | Value                                              |
| -------- | --------------------- | -------------------------------------------------- |
| Secret   | `FIGSHARE_TOKEN`      | the personal token from step 2                     |
| Variable | `FIGSHARE_ARTICLE_ID` | the article ID from step 1 (e.g. `17113328`)       |

The article ID is public (it's part of the DOI), so it's a repository **variable**;
the token is sensitive, so it's a **secret**. Until `FIGSHARE_ARTICLE_ID` is set,
the workflow stays dormant and the release process is unaffected.

### Publishing a release

There's nothing extra to do per release — cut a release the normal way (see
[`../RELEASING.md`](../RELEASING.md)). When the GitHub Release is published, the
`release-to-orda` workflow runs automatically: it downloads the release `.zip` and
`.tar.gz`, uploads them to your ORDA item, and ORDA records a new version of the
DOI.

> **Keep versions aligned.** The action does **not** check that the release tag
> matches the ORDA version number — that coordination is manual. Always publish to
> ORDA from the GitHub Release for the matching tag, and don't upload to the ORDA
> item by hand in between.

### After the first DOI is minted

Once ORDA has minted the DOI, wire it into the repository so the "Cite this
repository" metadata and badge are complete.

1. **README badge** — add a DOI badge near the top of [`../README.md`](../README.md),
   alongside the CI badge (replace the IDs with your own):

   ```markdown
   [![DOI](https://img.shields.io/badge/DOI-10.15131%2Fshef.data.17113328-blue)](https://doi.org/10.15131/shef.data.17113328)
   ```

2. **`CITATION.cff`** — record the DOI so GitHub's "Cite this repository" panel
   shows it. Add an `identifiers` block, e.g.:

   ```yaml
   identifiers:
     - type: doi
       value: 10.15131/shef.data.17113328
       description: Concept DOI for all versions
   ```

   ORDA issues a versioned DOI per release; the "concept" DOI resolves to the
   latest version. Use the concept DOI here so the citation always points at the
   newest release.

### Manual fallback

If the automation can't be used (no token, or a one-off deposit), you can deposit
by hand: on the GitHub Release page, download the **Source code (zip)** /
**(tar.gz)** assets, then upload them to the ORDA item and publish a new version.
The result is the same — only the upload step is manual.

## Publishing aqmesh-client to PyPI

The **`aqmesh-client`** package ([`packages/aqmesh-client/`](../packages/aqmesh-client))
is published to PyPI as [`aqmesh`](https://pypi.org/project/aqmesh/) independently of
the pipeline, so it can be installed with `pip install aqmesh` in other projects.
It has its own release cadence — see [RELEASING.md](../RELEASING.md) — and its
GitHub Releases use a `aqmesh-client-vX.Y.Z` tag, distinct from the pipeline's
`vX.Y.Z` tags.

Publishing is automated by
[`publish-to-pypi`](../.github/workflows/publish-to-pypi.yml), which triggers on
any published GitHub Release whose tag starts with `aqmesh-client-v`, builds the
package with `uv build --package aqmesh`, and uploads it using
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC) — there
is no stored PyPI API token.

### One-time setup

1. **Create the project on PyPI** — either publish a first release manually
   (`uv build --package aqmesh && uv publish`) to reserve the `aqmesh`
   name, or use PyPI's
   [pending publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
   flow to create the project from the trusted-publisher form before any release
   exists.
2. **Add a trusted publisher** on the project's PyPI page (**Publishing** settings),
   configured with:

   | Field            | Value                        |
   | ---------------- | ----------------------------- |
   | Owner            | the GitHub org/user for this repo |
   | Repository name  | this repo's name              |
   | Workflow name    | `publish-to-pypi.yml`         |
   | Environment name | `pypi`                        |

3. **Create a `pypi` environment** in the repo's **Settings → Environments** to
   match the `environment: pypi` the workflow runs under. Add protection rules
   (e.g. required reviewers) here if you want a manual gate before publishing.

### Publishing a release

Nothing extra to do per release — when release-please cuts a
`aqmesh-client-vX.Y.Z` release (see [RELEASING.md](../RELEASING.md)), the GitHub
Release publish event triggers `publish-to-pypi` automatically, and the new
version appears on PyPI within a few minutes.
