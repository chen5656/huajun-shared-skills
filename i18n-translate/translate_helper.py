#!/usr/bin/env python3
"""
translate_helper.py — Extract untranslated .po entries to JSON sessions,
and apply translated JSON back into .po files.

Usage:
    python translate_helper.py extract --po-dir <path> --project <name> [--session-size 50] [--sessions-dir .translation]
    python translate_helper.py apply   --po-dir <path> --project <name> [--sessions-dir .translation]
    python translate_helper.py audit   --project <name> [--locale es --locale fr --locale it] [--sessions-dir .translation]

JSON session files are stored under:
    <sessions_dir>/<project>/<locale>/session_N.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_SESSIONS_DIR = ".translation"


def _sessions_root(sessions_dir):
    base_dir = Path(sessions_dir).expanduser()
    if not base_dir.is_absolute():
        base_dir = Path.cwd() / base_dir
    return base_dir.resolve()


def _project_sessions_dir(project, sessions_dir):
    return _sessions_root(sessions_dir) / project


def read_session_json(session_path):
    with open(session_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── .po parsing ────────────────────────────────────────────────────────────

def parse_po(filepath):
    """Parse a .po file into a list of entry dicts.

    Each entry:
        {
            "comments": ["#: src/foo.tsx:12", "#. placeholder ..."],
            "msgid": "Hello",
            "msgid_plural": None | str,
            "msgstr": "Hola"  |  {"0": "...", "1": "..."} for plurals,
            "raw_lines": [original lines for this block],
        }
    The first entry (header) has msgid == "".
    """
    entries = []
    current_lines = []

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    def flush():
        if not current_lines:
            return
        entry = _parse_entry_lines(current_lines)
        if entry is not None:
            entries.append(entry)

    for line in lines:
        stripped = line.rstrip("\n")
        # Blank line → flush current entry
        if stripped == "":
            flush()
            current_lines = []
        else:
            current_lines.append(stripped)
    flush()
    return entries


def _parse_entry_lines(lines):
    """Parse a single block of .po lines into an entry dict."""
    comments = []
    msgid_lines = []
    msgid_plural_lines = []
    msgstr_lines = []  # for non-plural
    msgstr_plural = {}  # index → list of string lines
    current_key = None
    current_plural_idx = None

    for line in lines:
        if line.startswith("#"):
            comments.append(line)
            continue

        m_msgid = re.match(r'^msgid\s+"(.*)"$', line)
        m_msgid_plural = re.match(r'^msgid_plural\s+"(.*)"$', line)
        m_msgstr_idx = re.match(r'^msgstr\[(\d+)\]\s+"(.*)"$', line)
        m_msgstr = re.match(r'^msgstr\s+"(.*)"$', line)
        m_cont = re.match(r'^"(.*)"$', line)

        if m_msgid:
            current_key = "msgid"
            current_plural_idx = None
            msgid_lines.append(m_msgid.group(1))
        elif m_msgid_plural:
            current_key = "msgid_plural"
            current_plural_idx = None
            msgid_plural_lines.append(m_msgid_plural.group(1))
        elif m_msgstr_idx:
            idx = int(m_msgstr_idx.group(1))
            current_key = "msgstr_plural"
            current_plural_idx = idx
            msgstr_plural.setdefault(idx, []).append(m_msgstr_idx.group(2))
        elif m_msgstr:
            current_key = "msgstr"
            current_plural_idx = None
            msgstr_lines.append(m_msgstr.group(1))
        elif m_cont:
            val = m_cont.group(1)
            if current_key == "msgid":
                msgid_lines.append(val)
            elif current_key == "msgid_plural":
                msgid_plural_lines.append(val)
            elif current_key == "msgstr" and current_plural_idx is None:
                msgstr_lines.append(val)
            elif current_key == "msgstr_plural" and current_plural_idx is not None:
                msgstr_plural.setdefault(current_plural_idx, []).append(val)

    msgid = _join_po_strings(msgid_lines)
    msgid_plural = _join_po_strings(msgid_plural_lines) if msgid_plural_lines else None

    if msgstr_plural:
        msgstr = {str(k): _join_po_strings(v) for k, v in sorted(msgstr_plural.items())}
    else:
        msgstr = _join_po_strings(msgstr_lines)

    return {
        "comments": comments,
        "msgid": msgid,
        "msgid_plural": msgid_plural,
        "msgstr": msgstr,
        "raw_lines": lines,
    }


def _join_po_strings(parts):
    """Join .po continuation strings (already unescaped from quotes)."""
    return "".join(parts)


def _is_empty_msgstr(msgstr):
    """Check if msgstr is empty (untranslated)."""
    if isinstance(msgstr, dict):
        return all(v.strip() == "" for v in msgstr.values())
    return msgstr.strip() == ""


# ─── extract command ────────────────────────────────────────────────────────

def cmd_extract(args):
    po_dir = Path(args.po_dir).resolve()
    project = args.project
    session_size = args.session_size
    translations_root = _project_sessions_dir(project, args.sessions_dir)

    if not po_dir.exists():
        print(f"Error: {po_dir} does not exist", file=sys.stderr)
        sys.exit(1)

    locales = sorted([
        d.name for d in po_dir.iterdir()
        if d.is_dir() and d.name != "en" and (d / "messages.po").exists()
    ])

    if not locales:
        print("No non-English locales found.")
        return

    # Locale display names (best-effort)
    locale_names = _locale_display_names()

    total_files = 0
    total_entries = 0

    for locale in locales:
        po_path = po_dir / locale / "messages.po"
        entries = parse_po(po_path)

        # Filter to untranslated (skip header entry with msgid "")
        untranslated = []
        for e in entries:
            if e["msgid"] == "":
                continue
            if _is_empty_msgstr(e["msgstr"]):
                untranslated.append({
                    "msgid": e["msgid"],
                    "msgid_plural": e["msgid_plural"],
                    "comments": e["comments"],
                    "msgstr": "" if not isinstance(e["msgstr"], dict) else {k: "" for k in e["msgstr"]},
                })

        # Always clean old session files for this locale
        out_dir = translations_root / locale
        if out_dir.exists():
            for old in out_dir.glob("session_*.json"):
                old.unlink()

        if not untranslated:
            continue

        # Split into sessions
        sessions = [
            untranslated[i:i + session_size]
            for i in range(0, len(untranslated), session_size)
        ]

        out_dir.mkdir(parents=True, exist_ok=True)

        for idx, batch in enumerate(sessions, 1):
            session_data = {
                "locale": locale,
                "locale_name": locale_names.get(locale, locale),
                "session": idx,
                "total_sessions": len(sessions),
                "entries": batch,
            }
            out_path = out_dir / f"session_{idx}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            total_files += 1
            total_entries += len(batch)

        print(f"  {locale}: {len(untranslated)} untranslated -> {len(sessions)} session(s)")

    print(f"\nTotal: {total_entries} entries across {total_files} session files")
    print(f"Output: {translations_root}")


# ─── apply command ──────────────────────────────────────────────────────────

def cmd_apply(args):
    po_dir = Path(args.po_dir).resolve()
    project = args.project
    translations_root = _project_sessions_dir(project, args.sessions_dir)

    if not translations_root.exists():
        print(f"Error: No translations found at {translations_root}", file=sys.stderr)
        sys.exit(1)

    locales = sorted([
        d.name for d in translations_root.iterdir() if d.is_dir()
    ])

    for locale in locales:
        session_dir = translations_root / locale
        session_files = sorted(session_dir.glob("session_*.json"))
        if not session_files:
            continue

        # Build lookup: msgid → msgstr from all session files
        lookup = {}
        for sf in session_files:
            with open(sf, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data["entries"]:
                msgstr = entry.get("msgstr", "")
                if isinstance(msgstr, dict):
                    if not all(v.strip() == "" for v in msgstr.values()):
                        lookup[entry["msgid"]] = msgstr
                elif msgstr.strip():
                    lookup[entry["msgid"]] = msgstr

        if not lookup:
            print(f"  {locale}: no translations found in session files, skipping")
            continue

        # Read and patch .po file
        po_path = po_dir / locale / "messages.po"
        if not po_path.exists():
            print(f"  {locale}: {po_path} not found, skipping")
            continue

        patched = _patch_po_file(po_path, lookup)
        with open(po_path, "w", encoding="utf-8") as f:
            f.write(patched)

        print(f"  {locale}: applied {len(lookup)} translation(s)")

    print(f"\nDone. Run 'npm run lingui:compile' to compile.")


def cmd_audit(args):
    project = args.project
    translations_root = _project_sessions_dir(project, args.sessions_dir)

    if not translations_root.exists():
        print(f"Error: No translations found at {translations_root}", file=sys.stderr)
        sys.exit(1)

    requested_locales = args.locale or []
    locales = sorted([
        d.name for d in translations_root.iterdir()
        if d.is_dir() and (not requested_locales or d.name in requested_locales)
    ])

    if not locales:
        print("No matching locales found.")
        return

    locale_names = _locale_display_names()
    warned = False

    for locale in locales:
        session_dir = translations_root / locale
        session_files = sorted(session_dir.glob("session_*.json"))
        if not session_files:
            continue

        rows = []
        total_entries = 0
        translated_entries = 0

        for sf in session_files:
            with open(sf, "r", encoding="utf-8") as f:
                data = json.load(f)

            for entry in data.get("entries", []):
                total_entries += 1
                msgid = entry.get("msgid", "")
                msgstr = entry.get("msgstr", "")
                comments = entry.get("comments", [])

                if isinstance(msgstr, dict):
                    variants = [v for v in msgstr.values() if isinstance(v, str) and v.strip()]
                    if not variants:
                        continue
                    translated_entries += 1
                    target_text = max(variants, key=len)
                else:
                    if not isinstance(msgstr, str) or not msgstr.strip():
                        continue
                    translated_entries += 1
                    target_text = msgstr

                source_len = _display_length(msgid)
                target_len = _display_length(target_text)
                if source_len == 0 or target_len == 0:
                    continue

                ratio = target_len / source_len
                abs_growth = target_len - source_len
                line_break_change = target_text.count("\n") - msgid.count("\n")
                risk = _expansion_risk(locale, ratio, abs_growth, line_break_change)
                if risk is None:
                    continue

                rows.append({
                    "risk": risk,
                    "ratio": ratio,
                    "abs_growth": abs_growth,
                    "msgid": _single_line(msgid),
                    "msgstr": _single_line(target_text),
                    "ref": _best_source_ref(comments),
                })

        print(f"\n{locale} ({locale_names.get(locale, locale)})")
        print(f"  translated entries audited: {translated_entries}/{total_entries}")

        if not rows:
            print("  no high-risk expansion candidates found")
            continue

        warned = True
        rows.sort(
            key=lambda row: (
                _risk_rank(row["risk"]),
                -row["ratio"],
                -row["abs_growth"],
                row["msgid"],
            )
        )

        print("  high-risk text-expansion candidates:")
        for row in rows[: args.limit]:
            print(
                "   - "
                f"[{row['risk']}] "
                f"{row['ref']} | "
                f"{row['ratio']:.2f}x / +{row['abs_growth']} chars | "
                f"EN: {row['msgid']} | "
                f"{locale.upper()}: {row['msgstr']}"
            )

    if warned:
        print(
            "\nReview the referenced screens for clipping, wrapping, truncated labels, "
            "crowded button rows, and fixed-height cards before compiling."
        )
    else:
        print("\nNo high-risk expansion candidates were found in the audited sessions.")


def _patch_po_file(po_path, lookup):
    """Read a .po file and replace msgstr for entries matching lookup keys."""
    with open(po_path, "r", encoding="utf-8") as f:
        content = f.read()

    entries = parse_po(po_path)
    lines = content.split("\n")
    result_lines = list(lines)

    # We need to find each entry's position in the file and replace msgstr
    # Strategy: rebuild the file from parsed entries
    output_blocks = []
    raw_content = content

    # Re-read and rebuild block by block
    blocks = _split_po_blocks(content)

    for block in blocks:
        entry = _parse_entry_lines(block.strip().split("\n")) if block.strip() else None

        if entry is None or entry["msgid"] == "" or entry["msgid"] not in lookup:
            output_blocks.append(block)
            continue

        new_msgstr = lookup[entry["msgid"]]

        if isinstance(new_msgstr, dict):
            # Plural form
            new_block = _rebuild_block_plural(block, new_msgstr)
        else:
            new_block = _rebuild_block(block, new_msgstr)

        output_blocks.append(new_block)

    return "\n".join(b.rstrip("\n") for b in output_blocks if b is not None)


def _split_po_blocks(content):
    """Split .po content into blocks separated by blank lines."""
    blocks = []
    current = []
    for line in content.split("\n"):
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
            blocks.append("")  # preserve blank line
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _rebuild_block(block, new_msgstr):
    """Replace msgstr in a .po block with new_msgstr (non-plural)."""
    lines = block.split("\n")
    result = []
    in_msgstr = False
    msgstr_written = False

    for line in lines:
        if re.match(r'^msgstr\s+"', line) and not re.match(r'^msgstr\[\d+\]', line):
            in_msgstr = True
            if not msgstr_written:
                # Write new msgstr
                escaped = _escape_po_string(new_msgstr)
                if "\n" in new_msgstr:
                    # Multi-line: use continuation strings
                    parts = new_msgstr.split("\n")
                    result.append('msgstr ""')
                    for p in parts[:-1]:
                        result.append(f'"{_escape_po_value(p)}\\n"')
                    if parts[-1]:
                        result.append(f'"{_escape_po_value(parts[-1])}"')
                else:
                    result.append(f'msgstr "{escaped}"')
                msgstr_written = True
            continue
        elif in_msgstr and re.match(r'^"', line):
            # continuation of old msgstr, skip
            continue
        else:
            in_msgstr = False
            result.append(line)

    return "\n".join(result)


def _rebuild_block_plural(block, new_msgstr_dict):
    """Replace msgstr[N] in a .po block with new plural forms."""
    lines = block.split("\n")
    result = []
    in_msgstr = False
    written_indices = set()

    for line in lines:
        m = re.match(r'^msgstr\[(\d+)\]\s+"', line)
        if m:
            idx = m.group(1)
            in_msgstr = True
            if idx in new_msgstr_dict and idx not in written_indices:
                val = new_msgstr_dict[idx]
                escaped = _escape_po_string(val)
                result.append(f'msgstr[{idx}] "{escaped}"')
                written_indices.add(idx)
            else:
                result.append(line)
            continue
        elif in_msgstr and re.match(r'^"', line):
            continue
        else:
            in_msgstr = False
            result.append(line)

    return "\n".join(result)


def _escape_po_string(s):
    """Escape a string for .po msgstr (single line)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _escape_po_value(s):
    """Escape a string part for .po continuation line (no \\n added)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _display_length(text):
    """Best-effort visible text length for expansion heuristics."""
    collapsed = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return len(collapsed)


def _single_line(text, limit=70):
    collapsed = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def _best_source_ref(comments):
    for comment in comments:
        if comment.startswith("#: "):
            return comment[3:]
    return "(no source ref)"


def _expansion_risk(locale, ratio, abs_growth, line_break_change):
    romance_locale = locale in {"es", "fr", "it"}
    high_ratio = 1.35 if romance_locale else 1.5
    medium_ratio = 1.2 if romance_locale else 1.3
    high_growth = 18 if romance_locale else 22
    medium_growth = 10 if romance_locale else 14

    if line_break_change > 0 and (ratio >= medium_ratio or abs_growth >= medium_growth):
        return "high"
    if ratio >= high_ratio or abs_growth >= high_growth:
        return "high"
    if ratio >= medium_ratio or abs_growth >= medium_growth:
        return "medium"
    return None


def _risk_rank(risk):
    return {"high": 0, "medium": 1}.get(risk, 99)


# ─── locale names ───────────────────────────────────────────────────────────

def _locale_display_names():
    return {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "id": "Indonesian",
        "it": "Italian",
        "ja": "Japanese",
        "ko": "Korean",
        "nl": "Dutch",
        "pl": "Polish",
        "pt": "Portuguese",
        "ru": "Russian",
        "sv": "Swedish",
        "tr": "Turkish",
        "vi": "Vietnamese",
        "zh-Hans": "Chinese Simplified",
        "zh-Hant": "Chinese Traditional",
    }


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PO translation helper")
    sub = parser.add_subparsers(dest="command")

    p_extract = sub.add_parser("extract", help="Extract untranslated entries to JSON sessions")
    p_extract.add_argument("--po-dir", required=True, help="Path to src/locales/ directory")
    p_extract.add_argument("--project", required=True, help="Project name for organizing output")
    p_extract.add_argument("--session-size", type=int, default=50, help="Entries per session (default: 50)")
    p_extract.add_argument(
        "--sessions-dir",
        default=DEFAULT_SESSIONS_DIR,
        help=f"Directory for JSON session files (default: {DEFAULT_SESSIONS_DIR})",
    )

    p_apply = sub.add_parser("apply", help="Apply translated JSON sessions back to .po files")
    p_apply.add_argument("--po-dir", required=True, help="Path to src/locales/ directory")
    p_apply.add_argument("--project", required=True, help="Project name")
    p_apply.add_argument(
        "--sessions-dir",
        default=DEFAULT_SESSIONS_DIR,
        help=f"Directory for JSON session files (default: {DEFAULT_SESSIONS_DIR})",
    )

    p_audit = sub.add_parser("audit", help="Audit translated session files for text expansion risk")
    p_audit.add_argument("--project", required=True, help="Project name")
    p_audit.add_argument(
        "--sessions-dir",
        default=DEFAULT_SESSIONS_DIR,
        help=f"Directory for JSON session files (default: {DEFAULT_SESSIONS_DIR})",
    )
    p_audit.add_argument(
        "--locale",
        action="append",
        help="Locale(s) to audit. Repeat for multiple locales. Defaults to all locales with sessions.",
    )
    p_audit.add_argument(
        "--limit",
        type=int,
        default=15,
        help="Maximum number of risky entries to print per locale (default: 15)",
    )

    args = parser.parse_args()

    if args.command == "extract":
        cmd_extract(args)
    elif args.command == "apply":
        cmd_apply(args)
    elif args.command == "audit":
        cmd_audit(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
