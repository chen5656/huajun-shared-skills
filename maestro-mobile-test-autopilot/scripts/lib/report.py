"""Evidence-first reporting.

Rules:
  * a run report embeds EVERY screenshot, grouped by flow — no cherry-picking a
    representative image;
  * the header count is annotated with the triage verdict, because "7 failed" is
    misleading when six of them are one dead dev server;
  * the report is ONE self-contained file. Screenshots are inlined as data URIs,
    so a report that is copied, attached to a PR or read after the run root is
    cleaned still shows its evidence. A relative <img src> loses the images the
    moment the file moves, and a report without evidence is not a report;
  * the header names the binary and the clock. A green run against an unknown
    version at an unknown time cannot be replayed.
"""
from __future__ import annotations

import base64
import html
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

# Full-size device PNGs are ~1-2 MB each; a 40-flow run would inline to a
# gigabyte. Downscaled JPEG keeps a whole batch in the tens of MB and still
# reads fine — these are screenshots, not pixel diffs.
MAX_WIDTH = 900
JPEG_QUALITY = 60

CSS = """
:root{color-scheme:dark light}
body{background:#0f1115;color:#e6e6e6;font:15px/1.55 -apple-system,Segoe UI,sans-serif;margin:0;padding:32px}
h1,h2,h3{line-height:1.25} h1{margin:0 0 4px} code{background:#1c2029;padding:1px 5px;border-radius:4px}
table{border-collapse:collapse;width:100%;margin:16px 0} th,td{border:1px solid #2a2f3a;padding:7px 10px;text-align:left}
th{background:#171b23} .pass{color:#4ade80} .fail{color:#f87171}
.meta{color:#9aa4b2;margin:2px 0 14px} .meta b{color:#e6e6e6;font-weight:600}
.callout{border-left:3px solid #f59e0b;background:#1e1a10;padding:12px 16px;margin:16px 0;border-radius:0 6px 6px 0}
.shots{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.shot{background:#171b23;border:1px solid #2a2f3a;border-radius:8px;padding:8px}
.shot img{width:100%;border-radius:4px;display:block} .shot span{font-size:11px;color:#9aa4b2;word-break:break-all}
.flow{border:1px solid #2a2f3a;border-radius:10px;padding:16px;margin:16px 0;background:#12151c}
"""


def _hms(seconds: float | None) -> str:
    if not seconds:
        return "—"
    s = int(seconds)
    return f"{s // 3600}h {s % 3600 // 60}m {s % 60}s" if s >= 3600 else \
           (f"{s // 60}m {s % 60}s" if s >= 60 else f"{s}s")


def _encode(src: Path, compress: bool) -> tuple[bytes, str] | None:
    """Downscaled JPEG via sips (macOS, no dependency). Falls back to the PNG."""
    if compress and shutil.which("sips"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s.jpg"
            r = subprocess.run(
                ["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(JPEG_QUALITY),
                 "-Z", str(MAX_WIDTH), str(src), "--out", str(out)],
                capture_output=True, timeout=60,
            )
            if r.returncode == 0 and out.is_file():
                return out.read_bytes(), "image/jpeg"
    try:
        return src.read_bytes(), "image/png"
    except OSError:
        return None


def _data_uri(run_root: Path, rel: str, compress: bool) -> str | None:
    src = run_root / rel
    if not src.is_file():
        return None
    got = _encode(src, compress)
    if not got:
        return None
    payload, mime = got
    return f"data:{mime};base64,{base64.b64encode(payload).decode()}"


def render_html(summary: dict, narrative_md: str | None = None,
                run_root: Path | None = None, compress: bool = True) -> str:
    e = html.escape
    rows = "".join(
        f"<tr><td><code>{e(r['id'])}</code></td>"
        f"<td class='{'pass' if r['passed'] else 'fail'}'>{'pass' if r['passed'] else 'FAIL'}</td>"
        f"<td>{e(r['triage'].get('class',''))}</td>"
        f"<td>{e(r['triage'].get('explain',''))}</td>"
        f"<td>{_hms(r['seconds'])}</td></tr>"
        for r in summary["results"]
    )
    blocks = []
    for r in summary["results"]:
        cells = []
        for s in r["screenshots"]:
            uri = _data_uri(run_root, s, compress) if run_root else s
            if not uri:
                cells.append(f"<div class='shot'><span>missing on disk: {e(s)}</span></div>")
                continue
            cells.append(f"<div class='shot'><img src='{uri}'>"
                         f"<span>{e(Path(s).name)}</span></div>")
        shots = "".join(cells) or "<p>No screenshots captured — debug output was missing.</p>"
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
            f"{'pass' if r['passed'] else 'FAIL'}</span> · {_hms(r['seconds'])}</h3>{note}"
            f"<div class='shots'>{shots}</div></div>"
        )
    narrative = f"<div class='callout'><pre style='white-space:pre-wrap;margin:0'>{e(narrative_md)}</pre></div>" \
        if narrative_md else \
        "<div class='callout'>No RUN-SUMMARY.md was written. A run without a narrative is not reported.</div>"
    wall = summary.get("wall_seconds") or sum(r["seconds"] for r in summary["results"])
    meta = (f"<p class='meta'><b>App</b> {e(str(summary.get('app_id') or 'unknown'))} "
            f"<b>v{e(str(summary.get('app_version') or 'unknown'))}</b> · "
            f"<b>Device</b> <code>{e(str(summary['device']))}</code></p>"
            f"<p class='meta'><b>Started</b> {e(str(summary.get('started_at') or summary['at']))} · "
            f"<b>Finished</b> {e(summary['at'])} · "
            f"<b>Duration</b> {_hms(wall)} · {len(summary['results'])} flows</p>")
    return f"""<!doctype html><meta charset=utf-8><title>Run {e(summary['at'])}</title><style>{CSS}</style>
<h1>{e(summary['platform'])} run — {summary['passed']} passed, {summary['failed']} failed</h1>
{meta}
<div class='callout'><b>Batch verdict:</b> {e(summary['verdict'])}</div>
{narrative}
<h2>Flows</h2><table><tr><th>flow</th><th>result</th><th>class</th><th>why</th><th>time</th></tr>{rows}</table>
<h2>Evidence — every screenshot, grouped by flow</h2>{''.join(blocks)}"""


def write(run_root: Path, compress: bool = True) -> Path:
    """compress=False inlines the original PNGs: full fidelity, a far bigger file.

    Worth it when the screenshots are the artifact under inspection (a pixel-level
    rendering bug); never worth it for a routine batch.
    """
    summary = json.loads((run_root / "summary.json").read_text())
    md = run_root / "RUN-SUMMARY.md"
    out = run_root / "report.html"
    out.write_text(render_html(summary, md.read_text() if md.is_file() else None,
                               run_root, compress))
    return out
