# prova

[![verify](https://github.com/gabrielchv/prova/actions/workflows/verify.yml/badge.svg)](https://github.com/gabrielchv/prova/actions/workflows/verify.yml)

**A portfolio where every claim cites a file that exists in the repository — and
the build fails if it doesn't.**

`prova` (Portuguese for *proof*) is a claim-verification layer for a developer
portfolio. Each project is a YAML case study whose statements carry repository
paths. A collector records each repository's file tree from GitHub at a fixed
commit. A validator refuses to render anything if a cited path is not there.

The output is a static page, one markdown case study per project, and a
`projects.json` that other sites can consume.

---

## Why this exists

Most portfolios fail in the same way: they are a list of adjectives that nobody
can check. "Built a scalable distributed system" is unfalsifiable. A reader who
wants to verify it has to clone the repository, read the code, and guess which
part the sentence was about.

The problem is not modesty, it is untraceability. Claiming less is not the
answer; claiming things that can be *checked* is.

So the rule here is mechanical rather than aspirational:

> A claim about a project is only allowed if it cites at least one path in that
> project's repository, and every cited path must exist at the recorded commit.

This is the same constraint applied to LLM output in
[InquilinoIA](https://github.com/gabrielchv/inquilino-ia) and
[AutoApply](https://github.com/gabrielchv/AutoApply): the model may not state
something it cannot source. Applied to a portfolio, it means the page cannot
drift from the code, because drift is a build failure.

## What the validator enforces

| Rule | Type |
| --- | --- |
| Every claim cites at least one path | error |
| Every cited path exists in the tree at the recorded commit | error |
| Every verification entry cites at least one path | error |
| Every project states at least one limit | error |
| Every decision names the alternative it rejected | error |
| A claim stays under 280 characters | error |
| Pillars come from a closed vocabulary | error |
| Case id matches its filename | error |
| Claim ids are unique within a case | error |
| No overclaiming vocabulary ("world-class", "10x", …) | warning |
| At least one claim or verification cites a test | warning |

`limits` is the one section that needs no citation. An admission does not
require proof, and a project with no stated limits has not been examined.

## The cases

Eight repositories, 61 claims, 185 file citations.

- **hookrelay** — reliable webhook delivery, Kafka/SQS behind one port, retries, dead-lettering, signed payloads
- **status-page** — uptime monitoring with an incident state machine and an SSE status page
- **caderno** — real-time collaborative editing with versioned sync, observability and an accessibility gate
- **bookcerto** — multi-tenant scheduling where the double-booking guarantee is a PostgreSQL exclusion constraint
- **jobpipe** — Java 21 / Spring Boot pipeline tracker with a server-enforced status state machine
- **spring-rabbit-saga** — choreographed saga across three services with explicit compensation and dead-lettering
- **InquilinoIA** — RAG over Brazilian tenancy law where citations are verified in code, not trusted
- **AutoApply** — browser extension that fills job forms through a schema-validated plan the model cannot fabricate

## Quickstart

```bash
pip install pyyaml

make test       # the validator's own rules, 21 tests
make verify     # check every claim against the committed evidence
make build      # render build/index.html, build/<id>.md, build/projects.json
```

`make verify` runs entirely offline against `evidence/`. To refresh what the
claims are checked against, you need GitHub access:

```bash
export GITHUB_TOKEN=...    # or authenticate with `gh auth login`
make refresh               # collect -> verify -> build
```

`make build` refuses to run if verification fails. Rendering is downstream of
proof, not parallel to it.

## Adding a case

Copy an existing file in `cases/` and fill it in. Then:

1. `make refresh` — collect the new repository's tree.
2. `make verify` — every citation you wrote must resolve.
3. `make build`.

The validator will reject a claim whose path you guessed. That is the intended
first experience: it is the same feedback a reader would otherwise have to
produce by hand.

## Layout

```
cases/            one YAML case study per project — the source of truth
evidence/         recorded repository trees, committed, one file per repo
tool/collect.py   GitHub API -> evidence manifests
tool/validate.py  schema rules + citation resolution
tool/render.py    markdown, static HTML, projects.json
tests/            the validator's own test suite
schema/           JSON Schema for editor assistance
build/            generated output (git-ignored)
```

Evidence is committed on purpose. It makes verification reproducible on any
machine, lets a reviewer diff what the claims were checked against, and turns
repository drift into a visible change rather than silence. CI re-collects
weekly and fails if a claim no longer resolves.

## Feeding the portfolio site

`build/projects.json` is shaped for direct import by the existing portfolio
(`gabrielchv/portfolio`, `src/data/profile.ts`). Project entries there were
seeded by hand from a knowledge base once, which is how a site ends up claiming
things the resumes have stopped claiming. Consuming this file removes that
drift: a project appears on the site only after its claims have been verified.

## What this is not

- **Not a proof of quality.** A citation proves that a file exists and that the
  claim is about something real in the tree. It does not prove the code is good.
  Reviewing the code is still the reader's job — this only removes the part where
  they have to guess what the sentence refers to.
- **Not a test runner.** `make verify` checks that citations resolve; it does not
  run the projects' test suites. "Has tests" is checkable here. "Tests pass" is
  a claim for CI, and each repository's own workflow is the evidence for it.
- **Not static.** The weekly drift job exists because repositories change. A
  claim that stops resolving is a claim that should stop being shown.

## Licence

MIT.
