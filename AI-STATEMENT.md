# Generative AI Usage Statement

This document discloses how generative AI (GenAI) tools have been used in the
development of the **aqmesh** data pipeline. It exists in the interest of
transparency and reproducibility, and to set expectations for contributors and
reviewers.

It is written in accordance with the University of Sheffield
[Principles for Using GenAI in Research and Innovation](https://students.sheffield.ac.uk/research-ethics/ethics-integrity/grip/principles-using-genai-research-and-innovation).

## Summary

Parts of this repository were written with the assistance of
[Claude Code](https://claude.com/claude-code), Anthropic's command-line coding
agent. AI was used as a **tool under human direction**, not as an autonomous
author. Every change — whether AI-assisted or hand-written — was reviewed,
tested, and accepted by a human maintainer before being committed or merged.

## Compliance with university policy

### Appropriateness

GenAI was used selectively where it offered clear value: accelerating the
drafting and refactoring of code and documentation for the pipeline. In every
case, human expertise, critical judgement, and domain knowledge of air-quality
monitoring and the AQMesh platform directed and validated the outputs.
Specifically, AI may have contributed to:

- **Code** — drafting and refactoring modules (ingest/clean flows, the API
  client, storage helpers, transforms) and writing tests.
- **Documentation** — drafting and editing `README.md`, docstrings, code
  comments, and this statement.
- **Pull requests** — drafting PR descriptions, commit messages, and summaries
  of changes.
- **Investigation** — searching the codebase, explaining behaviour, and
  proposing approaches to bugs and features.

Architectural decisions, data-handling choices, and anything touching the AQMesh
API or credentials are human-led; AI is used to implement and refine those
decisions, not to make them.

### Attribution

GenAI tool use is documented in this file and referenced from the repository
`README.md`. Significant AI assistance is noted in pull requests where it is
material to review.

### Accuracy

All GenAI-generated content was reviewed by a human maintainer before use.
Specifically:

- A human reviews every AI-generated diff before it is committed.
- All changes must pass the project's checks (`uv run ruff check .` and
  `uv run pytest`) and be understood by a human reviewer — AI output is never
  merged on trust.
- AI suggestions that are wrong, unclear, or unverifiable are rejected or
  rewritten.

### Data protection

**No real research air-quality measurement data was provided to any GenAI
tool.** AI assisted with the *code* that handles data, not the data itself. The
measurement data retrieved from the AQMesh API and stored under
`AQMESH_DATA_ROOT` was not uploaded to or processed by any external GenAI
service.

No real AQMesh credentials, API keys, or `.env` contents were shared with AI
tools. Only `.env.example` (placeholder values) exists in the repository.
Claude's data usage policies were reviewed before use.

### Accountability

The named author and maintainers remain fully responsible for all content of
this repository. Use of GenAI tools does not diminish the research team's
responsibility for the accuracy, integrity, and rigour of the work. Authorship
and accountability are unchanged by the use of AI: the commit author and
`pyproject.toml` author own the work, regardless of how it was produced.

This project is conducted in accordance with the University of Sheffield
[Good Research and Innovation Practices (GRIP)](https://students.sheffield.ac.uk/research-ethics/ethics-integrity/grip)
policy.

## Provenance and licensing

This project is MIT-licensed (see `LICENSE`). AI-assisted contributions are
released under the same licence. Where AI tools were used, the human maintainers
have satisfied themselves that the resulting code is original to this project
and appropriate to distribute under the MIT licence.

## Guidance for contributors

You are welcome to use generative AI tools when contributing, provided that:

1. You review and understand every line you submit — you are accountable for it.
2. The change passes lint and tests, and you have verified its behaviour.
3. No secrets or non-public research data are shared with third-party AI
   services.
4. You note significant AI assistance in your pull request when it is material
   to the review.

## Contact

Questions about this statement can be directed to the maintainer,
Joe Heffer (`j.heffer@sheffield.ac.uk`), IT Services Research & Innovation team,
University of Sheffield.

_Last updated: 2026-06-05._
