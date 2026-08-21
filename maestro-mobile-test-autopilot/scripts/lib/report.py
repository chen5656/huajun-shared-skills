"""Evidence-first reporting.

Rule: a run report embeds EVERY screenshot, grouped by flow. No cherry-picking a
representative image. The header count is annotated with the triage verdict,
because "7 failed" is misleading when six of them are one dead dev server.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

CSS = """
:root{color-scheme:dark light}
body{background:#0f1115;color:#e6e6e6;font:15px/1.55 -apple-system,Segoe UI,sans-serif;margin:0;padding:32px}
h1,h2,h3{line-height:1.25} h1{margin:0 0 4px} code{background:#1c2029;padding:1px 5px;border-radius:4px}
table{border-collapse:collapse;width:100%;margin:16px 0} th,td{border:1px solid #2a2f3a;padding:7px 10px;text-align:left}
th{background:#171b23} .pass{color:#4ade80} .fail{color:#f87171}
.callout{border-left:3px solid #f59e0b;background:#1e1a10;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.shot{background:#171b23;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
.shot img{width:100%;border-radius:4px;display:block} .shot span{font-size:11px;color:#9aa4b2;word-break:break-all}
.flow{border:1px solid #2a2f3a;border-radius:10px;padding:16px;margin:16px 0;background:#12151c}
"""


def render_html(summary: dict, narrative_md: str | None = None) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td><code>{e(r['id'])}</code></td>"
        f"<td class='{'pass' if r['passed'] else 'fail'}'>{'pass' if r['passed'] else 'FAIL'}</td>"
        f"<td>{e(r['triage'].get('class',''))}</td>"
        f"<td>{e(r['triage'].get('explain',''))}</td>"
        f"<td>{r['seconds']:.0f}s</td></tr>"
        for r in summary["results"]
    )
    blocks = []
    for r in summary["results"]:
        shots = "".join(
            f"<div class='shot'><a href='{e(s)}' target='_blank'><img src='{e(s)}' loading='lazy'></a>"
            f"<span>{e(Path(s).name)}</span></div>" for s in r["screenshots"]
        ) or "<p>No screenshots captured — debug output was missing.</p>"
        t = r["triage"]
        note = ""
        if not r["passed"]:
            conf = "" if t.get("confident", True) else \
                " <em>(log alone cannot prove this class — check the screenshots.)</em>"
            note = (f"<div class='callout'><b>{e(t.get('class',''))}</b> · "
                    f"{e(t.get('explain',''))}{conf}<br>{e(t.get('fix',''))}</div>")
        blocks.append(
            f"<div class='flow'><h3><code>{e(r['id'])}</code> — "
            f"<span class='{'pass' if r['passed'] else 'fail'}'>"
            f"{'pass' if r['passed'] else 'FAIL'}</span></h3>{note}"
            f"<div class='shots'>{shots}</div></div>"
        )
    narrative = f"<div class='callout'><pre style='white-space:pre-wrap;margin:0'>{e(narrative_md)}</pre></div>" \
        if narrative_md else \
        "<div class='callout'>No RUN-SUMMARY.md was written. A run without a narrative is not reported.</div>"
    return f"""<!doctype html><meta charset=utf-8><title>Run {e(summary['at'])}</title><style>{CSS}</style>
<h1>{e(summary['platform'])} run — {summary['passed']} passed, {summary['failed']} failed</h1>
<p>Device <code>{e(str(summary['device']))}</code> · {e(summary['at'])}</p>
<div class='callout'><b>Batch verdict:</b> {e(summary['verdict'])}</div>
{narrative}
<h2>Flows</h2><table><tr><th>flow</th><th>result</th><th>class</th><th>why</th><th>time</th></tr>{rows}</table>
<h2>Evidence — every screenshot, grouped by flow</h2>{''.join(blocks)}"""


def write(run_root: Path) -> Path:
    summary = json.loads((run_root / "summary.json").read_text())
    md = run_root / "RUN-SUMMARY.md"
    out = run_root / "report.html"
    out.write_text(render_html(summary, md.read_text() if md.is_file() else None))
    return out
