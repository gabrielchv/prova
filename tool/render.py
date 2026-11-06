#!/usr/bin/env python3
"""Render validated cases into build/: markdown per case, one static page, and
a projects.json the existing portfolio site can consume.

Rendering trusts the validator. This script does not re-check citations; it
refuses to run at all if any case failed verification, so nothing can reach the
page that was not checkable first.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from model import BUILD_DIR, PILLARS, ROOT, load_cases, load_evidence  # noqa: E402

# A committed copy of the project catalogue, so other repositories (the portfolio)
# can consume a verified artefact without depending on build/, which is ignored.
# It is deliberately free of timestamps: CI regenerates it and fails on any diff,
# which only works if identical inputs produce byte-identical output.
CATALOG_DIR = ROOT / "catalog"

CSS = """
:root {
  color-scheme: dark;
  --bg: #0d1117; --panel: #161b22; --line: #30363d;
  --fg: #e6edf3; --muted: #8b949e; --accent: #58a6ff; --ok: #3fb950;
  --warn: #d29922;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.65 ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 820px; margin: 0 auto; padding: 4rem 1.5rem 6rem; }
header { border-bottom: 1px solid var(--line); padding-bottom: 2rem; margin-bottom: 3rem; }
.kicker {
  margin: 0 0 .75rem; color: var(--accent);
  font: 600 .78rem/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .14em; text-transform: uppercase;
}
h1 { margin: 0 0 1rem; font-size: 2.2rem; line-height: 1.2; letter-spacing: -.02em; }
.lede { margin: 0 0 1.25rem; color: var(--fg); font-size: 1.06rem; max-width: 62ch; }
.stats {
  margin: 0; color: var(--muted);
  font: .82rem/1.6 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.stats b { color: var(--ok); font-weight: 600; }
nav { margin-bottom: 3.5rem; }
nav h2 {
  margin: 0 0 1rem; color: var(--muted);
  font: 600 .74rem/1 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: .12em; text-transform: uppercase;
}
nav ol { margin: 0; padding: 0; list-style: none; }
nav li {
  display: grid; grid-template-columns: 10.5rem 1fr; gap: .15rem 1.25rem;
  align-items: baseline; padding: .7rem 0; border-bottom: 1px solid var(--line);
}
nav a { color: var(--fg); text-decoration: none; font-weight: 600; }
nav a:hover { color: var(--accent); }
nav .tag { color: var(--muted); font-size: .88rem; }
nav .pillars {
  grid-column: 2; color: var(--muted); font-size: .72rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
article { margin-bottom: 4.5rem; padding-top: 1rem; }
article > h2 {
  margin: 0 0 .5rem; font-size: 1.6rem; letter-spacing: -.01em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.tagline { margin: 0 0 1.5rem; font-size: 1.05rem; color: var(--fg); max-width: 64ch; }
dl.facts {
  display: grid; grid-template-columns: 7.5rem 1fr; gap: .45rem 1rem;
  margin: 0 0 2rem; padding: 1.1rem 1.25rem;
  background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
  font-size: .88rem;
}
dl.facts dt { color: var(--muted); font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: .78rem; }
dl.facts dd { margin: 0; }
dl.facts a { color: var(--accent); }
h3 {
  margin: 2.25rem 0 .75rem; font-size: .76rem; letter-spacing: .12em;
  text-transform: uppercase; color: var(--muted);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
p { margin: 0 0 1rem; }
.approach { margin: 0; }
.approach h4 { margin: 1.4rem 0 .35rem; font-size: 1rem; }
ol.claims { margin: 0; padding-left: 1.4rem; }
ol.claims li { margin-bottom: 1.1rem; }
ol.claims li::marker { color: var(--muted); font-family: ui-monospace, monospace; font-size: .8rem; }
.cite {
  display: block; margin-top: .3rem; color: var(--muted);
  font: .78rem/1.7 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.cite::before { content: "\\21B3  "; }
.decision {
  margin-bottom: 1.5rem; padding: 1rem 1.15rem;
  border-left: 2px solid var(--line); background: var(--panel);
}
.decision p { margin: 0 0 .6rem; font-size: .93rem; }
.decision p:last-child { margin-bottom: 0; }
.pill {
  display: inline-block; margin-right: .5rem; padding: .1rem .45rem;
  border-radius: 4px; font: 600 .68rem/1.5 ui-monospace, monospace;
  letter-spacing: .06em; text-transform: uppercase;
}
.pill.chose { background: rgba(63,185,80,.13); color: var(--ok); }
.pill.rejected { background: rgba(210,153,34,.13); color: var(--warn); }
.why { color: var(--muted); }
ul.plain { margin: 0; padding-left: 1.2rem; }
ul.plain li { margin-bottom: .55rem; font-size: .93rem; }
ul.limits { margin: 0; padding-left: 1.2rem; }
ul.limits li { margin-bottom: .55rem; font-size: .93rem; color: var(--muted); }
footer {
  margin-top: 5rem; padding-top: 2rem; border-top: 1px solid var(--line);
  color: var(--muted); font-size: .88rem;
}
footer code { color: var(--fg); }
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .88em; color: var(--fg);
}
@media (max-width: 640px) {
  .wrap { padding: 2.5rem 1.1rem 4rem; }
  h1 { font-size: 1.7rem; }
  dl.facts { grid-template-columns: 1fr; gap: .2rem; }
  dl.facts dt { margin-top: .6rem; }
  nav li { grid-template-columns: 1fr; gap: .1rem; }
  nav .pillars { grid-column: 1; }
}
"""


def e(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in value.lower())


# --------------------------------------------------------------------- markdown
def render_markdown(case: dict, evidence: dict | None) -> str:
    lines: list[str] = [f"# {case['name']}", "", f"> {case['tagline']}", ""]

    facts = [
        ("Role", case["role"]),
        ("Period", case["period"]),
        ("Stack", ", ".join(case["stack"])),
        ("Repository", f"https://github.com/{case['repo']}"),
    ]
    if case.get("live_url"):
        facts.append(("Live", case["live_url"]))
    if evidence:
        facts.append(("Verified at", f"`{evidence.get('head_sha', 'unknown')[:12]}`"))
    for label, value in facts:
        lines.append(f"- **{label}** — {value}")
    lines.append("")

    lines += ["## The problem", "", case["problem"], "", "## How it works", ""]
    for item in case["approach"]:
        lines += [f"### {item['title']}", "", item["body"], ""]

    lines += ["## Claims, and where to check them", ""]
    for index, claim in enumerate(case["claims"], start=1):
        cites = ", ".join(f"`{cite}`" for cite in claim["cite"])
        lines += [f"{index}. {claim['text']}", f"   - Evidence: {cites}", ""]

    lines += ["## Decisions", ""]
    for decision in case["decisions"]:
        lines += [
            f"- **Chose** — {decision['chose']}",
            f"  **Rejected** — {decision['rejected']}",
            f"  **Why** — {decision['why']}",
            "",
        ]

    lines += ["## Verification", ""]
    for item in case["verification"]:
        cites = ", ".join(f"`{cite}`" for cite in item["cite"])
        lines += [f"- {item['what']}", f"  - Evidence: {cites}"]
    lines.append("")

    lines += ["## Limits", ""]
    for limit in case["limits"]:
        lines.append(f"- {limit}")
    lines.append("")

    return "\n".join(lines)


# -------------------------------------------------------------------------- html
def render_case_html(case: dict, evidence: dict | None, index: int) -> str:
    parts: list[str] = [f'<article id="{e(slug(case["id"]))}">']
    parts.append(f"<h2>{e(case['name'])}</h2>")
    parts.append(f'<p class="tagline">{e(case["tagline"])}</p>')

    facts = [
        ("Role", e(case["role"])),
        ("Period", e(case["period"])),
        ("Stack", e(", ".join(case["stack"]))),
        ("Pillars", e(", ".join(case["pillars"]))),
        (
            "Repository",
            f'<a href="https://github.com/{e(case["repo"])}">github.com/{e(case["repo"])}</a>',
        ),
    ]
    if case.get("live_url"):
        facts.append(("Live", f'<a href="{e(case["live_url"])}">{e(case["live_url"])}</a>'))
    if evidence:
        facts.append(("Verified at", f'<code>{e((evidence.get("head_sha") or "unknown")[:12])}</code>'))

    parts.append('<dl class="facts">')
    for label, value in facts:
        parts.append(f"<dt>{e(label)}</dt><dd>{value}</dd>")
    parts.append("</dl>")

    parts.append("<h3>The problem</h3>")
    parts.append(f"<p>{e(case['problem'])}</p>")

    parts.append("<h3>How it works</h3>")
    parts.append('<div class="approach">')
    for item in case["approach"]:
        parts.append(f"<h4>{e(item['title'])}</h4><p>{e(item['body'])}</p>")
    parts.append("</div>")

    parts.append(f"<h3>Claims ({len(case['claims'])}, each with a source)</h3>")
    parts.append('<ol class="claims">')
    for claim in case["claims"]:
        cites = " · ".join(f"<code>{e(cite)}</code>" for cite in claim["cite"])
        parts.append(f'<li><p>{e(claim["text"])}</p><span class="cite">{cites}</span></li>')
    parts.append("</ol>")

    parts.append("<h3>Decisions</h3>")
    for decision in case["decisions"]:
        parts.append('<div class="decision">')
        parts.append(f'<p><span class="pill chose">chose</span>{e(decision["chose"])}</p>')
        parts.append(f'<p><span class="pill rejected">rejected</span>{e(decision["rejected"])}</p>')
        parts.append(f'<p class="why">{e(decision["why"])}</p>')
        parts.append("</div>")

    parts.append("<h3>Verification</h3><ul class=\"plain\">")
    for item in case["verification"]:
        cites = " · ".join(f"<code>{e(cite)}</code>" for cite in item["cite"])
        parts.append(f"<li>{e(item['what'])}<br><span class=\"cite\">{cites}</span></li>")
    parts.append("</ul>")

    parts.append("<h3>Limits</h3><ul class=\"limits\">")
    for limit in case["limits"]:
        parts.append(f"<li>{e(limit)}</li>")
    parts.append("</ul>")

    parts.append("</article>")
    return "\n".join(parts)


def render_index_html(cases: list[dict], evidence_map: dict[str, dict | None]) -> str:
    total_claims = sum(len(case["claims"]) for case in cases)
    total_citations = sum(
        len(claim["cite"]) for case in cases for claim in case["claims"]
    )
    # Verification citations are citations too; the headline must match what the
    # validator actually resolved, or the page understates its own evidence.
    total_citations += sum(
        len(item["cite"]) for case in cases for item in case["verification"]
    )
    shas = {
        (evidence or {}).get("head_sha", "")[:8]
        for evidence in evidence_map.values()
        if evidence and evidence.get("head_sha")
    }

    body: list[str] = ['<div class="wrap">', "<header>"]
    body.append('<p class="kicker">Gabriel Chaves &middot; engineering</p>')
    body.append("<h1>Engineering work, with citations.</h1>")
    body.append(
        '<p class="lede">Every claim on this page cites a file in the repository that '
        "backs it. The build reads each repository from GitHub, records the exact commit, "
        "and fails if a citation no longer resolves to a real file. Nothing here is a "
        "summary of intent &mdash; it is a description of what is in the tree.</p>"
    )
    body.append(
        f'<p class="stats"><b>{len(cases)}</b> projects &middot; '
        f"<b>{total_claims}</b> claims &middot; "
        f"<b>{total_citations}</b> file citations resolved &middot; "
        f"<b>{len(shas)}</b> commits recorded</p>"
    )
    body.append("</header>")

    body.append("<nav><h2>Index</h2><ol>")
    for case in cases:
        body.append(
            f'<li><a href="#{e(slug(case["id"]))}">{e(case["name"])}</a>'
            f'<span class="tag">{e(case["tagline"])}</span>'
            f'<span class="pillars">{e(", ".join(case["pillars"]))}</span></li>'
        )
    body.append("</ol></nav>")

    body.append("<main>")
    for index, case in enumerate(cases):
        body.append(render_case_html(case, evidence_map.get(case["repo"]), index))
    body.append("</main>")

    body.append("<footer>")
    body.append(
        "<p>Generated by <code>prova</code>. Each case is a YAML file whose claims "
        "carry repository paths; <code>tool/collect.py</code> records the tree at a "
        "fixed commit and <code>tool/validate.py</code> refuses to build if any cited "
        "path is missing. The <em>Limits</em> section of each project is the one part "
        "that needs no citation, because an admission does not require proof.</p>"
    )
    body.append(
        f"<p>Rendered {e(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}.</p>"
    )
    body.append("</footer></div>")

    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Gabriel Chaves &mdash; engineering work, with citations</title>\n"
        '<meta name="description" content="Software engineering case studies where every '
        'claim cites a file in the repository that backs it.">\n'
        f"<style>{CSS}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )


def render_projects_json(cases: list[dict], evidence_map: dict[str, dict | None]) -> str:
    """A fragment the existing portfolio site can import, so the site and this
    repository cannot drift apart the way kb.yaml and profile.ts did."""
    payload = {
        "generated_by": "prova",
        "note": (
            "Deterministic output: regenerate with `make build`. Consume this instead "
            "of hand-maintaining project entries. Every claim here has already been "
            "verified against the repository."
        ),
        "projects": [
            {
                "id": case["id"],
                "name": case["name"],
                "repo": case["repo"],
                "tagline": case["tagline"],
                "tagline_pt": case.get("tagline_pt") or case["tagline"],
                "role": case["role"],
                "period": case["period"],
                "pillars": case["pillars"],
                "stack": case["stack"],
                "live_url": case.get("live_url"),
                "claim_count": len(case["claims"]),
                "verified_commit": (evidence_map.get(case["repo"]) or {}).get("head_sha"),
                "case_file": f"cases/{case['_stem']}.yaml",
            }
            for case in cases
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def verify_first() -> bool:
    """Rendering is downstream of verification; never render an unverified case."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "validate.py")],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("refusing to render: validation failed\n", file=sys.stderr)
        print(result.stdout[-4000:], file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr[-2000:], file=sys.stderr)
        return False
    return True


def main() -> int:
    if not verify_first():
        return 1

    cases = load_cases()
    evidence_map = {case["repo"]: load_evidence(case["repo"]) for case in cases}

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)

    for case in cases:
        markdown = render_markdown(case, evidence_map.get(case["repo"]))
        (BUILD_DIR / f"{case['id']}.md").write_text(markdown, encoding="utf-8")

    (BUILD_DIR / "index.html").write_text(
        render_index_html(cases, evidence_map), encoding="utf-8"
    )
    catalog = render_projects_json(cases, evidence_map)
    (BUILD_DIR / "projects.json").write_text(catalog, encoding="utf-8")
    (CATALOG_DIR / "projects.json").write_text(catalog, encoding="utf-8")

    total_claims = sum(len(case["claims"]) for case in cases)
    print(f"rendered {len(cases)} case(s) -> {BUILD_DIR}")
    print(f"  index.html      {len(cases)} articles, {total_claims} cited claims")
    print(f"  projects.json   importable by the portfolio site")
    print(f"  <id>.md         one portable case study per project")
    print(f"  catalog/projects.json  committed copy for downstream consumers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
