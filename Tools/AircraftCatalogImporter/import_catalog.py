#!/usr/bin/env python3
"""
SKYBOUND - MSFS Addons aircraft catalog importer.

Purpose
-------
Section 32 of the SKYBOUND specification requires that the complete MSFS Addons
aircraft list (https://msfsaddons.com/msfs-aircraft-list/) is represented in
SKYBOUND's aircraft database - not a hand-picked "best of" subset.

This tool performs that ingestion for real:
  * retrieves the public catalog page (politely, single request, identifying UA),
  * parses every aircraft row in every aircraft-category table,
  * normalises names / developers and derives stable IDs,
  * detects duplicate entries,
  * writes the structured catalog consumed by the Unreal project,
  * writes a human-readable ingestion report and a change report vs. the
    previous run.

What this tool deliberately does NOT do
--------------------------------------
The source page is a *reference catalog*. It is not a license to redistribute
aircraft assets (spec 32.5). Therefore every imported record is written with
implementation_status = "catalogued" and asset_license = "unknown". No field
that the source does not actually publish is invented: msfs_2020_status,
engine_type, seating etc. are written as null ("unknown") rather than guessed.

Usage
-----
    python import_catalog.py                     # fetch live page, write DB
    python import_catalog.py --html page.html     # parse a saved copy
    python import_catalog.py --cache-dir ... --out ... --report ...

Exit codes: 0 success, 2 network failure, 3 parse failure (no aircraft found).
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import unicodedata
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://msfsaddons.com/msfs-aircraft-list/"
USER_AGENT = (
    "SKYBOUND-CatalogImporter/0.1 (+https://github.com/; flight simulator "
    "catalog research; single polite request per run)"
)

# The nine aircraft sections of the page, in document order. These are the
# authoritative categories *as published by the source*, so they are recorded
# verbatim in category_source and mapped to a normalised SKYBOUND category.
CATEGORY_MAP = [
    ("Single-engine general aviation aircraft", "single_engine_ga", "fixed_wing_ga"),
    ("Multi-engine and utility aircraft", "multi_engine_utility", "fixed_wing_ga"),
    ("Airliners", "airliners", "airliner"),
    ("Business jets", "business_jets", "business_jet"),
    ("Military aircraft", "military", "military"),
    ("Gliders", "gliders", "glider"),
    ("Vintage aircraft", "vintage", "vintage"),
    ("Helicopters", "helicopters", "helicopter"),
    ("Airships, balloons, eVTOLs and everything else", "airships_balloons_evtol", "other"),
]

# Markers that end the aircraft portion of the document.
SECTION_TERMINATORS = [
    "Frequently asked questions",
    "How we keep this list",
    "Changelog",
    "RECENT HIGHLIGHTS",
]

TAG_RE = re.compile(r"<[^>]+>")
ROW_RE = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.S | re.I)
CELL_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.S | re.I)
HREF_RE = re.compile(r'<a\b[^>]*href="([^"]+)"', re.I)
H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S | re.I)
DATA_S_RE = re.compile(r'data-s="([^"]*)"', re.I)
NEW_CLASS_RE = re.compile(r"acl-is-new", re.I)
BADGE_RE = re.compile(r'<span class="acl-badge[^"]*">.*?</span>', re.S | re.I)


def clean_text(fragment: str) -> str:
    """Strip tags/entities/badges from an HTML fragment and collapse whitespace."""
    fragment = BADGE_RE.sub("", fragment)
    text = TAG_RE.sub(" ", fragment)
    text = html_mod.unescape(text)
    text = text.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip()


def slug(text: str) -> str:
    """ASCII slug used to build stable, human-readable IDs."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^A-Za-z0-9]+", "-", norm).strip("-").lower()
    return re.sub(r"-{2,}", "-", norm)


@dataclass
class Aircraft:
    name: str
    developer: str
    category: str
    category_source: str
    source_url: str | None
    source_row_key: str
    flagged_new: bool


@dataclass
class ImportResult:
    aircraft: list[Aircraft] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)
    rows_without_developer: int = 0
    duplicates_removed: int = 0
    source_page_bytes: int = 0
    published_counts: dict[str, int | None] = field(default_factory=dict)

    def integrity(self) -> list[str]:
        """Compare parsed row counts with the counts the publisher prints."""
        problems = []
        for cat_id, parsed in self.category_counts.items():
            pub = self.published_counts.get(cat_id)
            if pub is not None and pub != parsed:
                problems.append(
                    f"{cat_id}: parsed {parsed} rows but page states {pub}"
                )
        return problems


def fetch(url: str, timeout: int = 45) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed URL)
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def locate_sections(page: str) -> list[tuple[int, str, str, str, int | None]]:
    """Return (position, source_title, category_id, skybound_class, published_count).

    Each source heading ends with the number of aircraft the site itself counts
    in that section (e.g. "Airliners 116"). That number is captured so the
    importer can cross-check what it actually parsed against the publisher's
    own total - a real integrity check, not a cosmetic one.
    """
    found: list[tuple[int, str, str, str, int | None]] = []
    for m in H2_RE.finditer(page):
        raw = clean_text(m.group(1))
        published: int | None = None
        count_m = re.search(r"\s+(\d{1,4})$", raw)
        if count_m:
            published = int(count_m.group(1))
            raw = raw[: count_m.start()]
        for source_title, cat_id, sky_class in CATEGORY_MAP:
            if raw.lower() == source_title.lower():
                found.append((m.start(), source_title, cat_id, sky_class, published))
    found.sort(key=lambda t: t[0])
    return found


def section_end(page: str, start: int,
                sections: list[tuple[int, str, str, str, int | None]]) -> int:
    """The aircraft section runs until the next category heading or a terminator."""
    later = [s[0] for s in sections if s[0] > start]
    end = min(later) if later else len(page)
    for terminator in SECTION_TERMINATORS:
        m = re.search(r"<h2[^>]*>\s*" + re.escape(terminator), page[start:end], re.I)
        if m:
            end = start + m.start()
    return end


def parse(page: str) -> ImportResult:
    result = ImportResult(source_page_bytes=len(page.encode("utf-8")))
    sections = locate_sections(page)
    if not sections:
        raise RuntimeError(
            "No aircraft category headings found. The source page layout has "
            "changed and the parser must be updated (see ARCHITECTURE.md)."
        )

    seen: dict[str, Aircraft] = {}
    result.published_counts: dict[str, int | None] = {}
    for pos, source_title, cat_id, _sky_class, published in sections:
        end = section_end(page, pos, sections)
        chunk = page[pos:end]
        count = 0
        for row_m in ROW_RE.finditer(chunk):
            attrs, body = row_m.group(1), row_m.group(2)
            cells = CELL_RE.findall(body)
            if len(cells) < 2:
                continue  # header row / layout row
            name = clean_text(cells[0])
            developer = clean_text(cells[1])
            if not name or name.lower() in {"aircraft", "name"}:
                continue
            href_m = HREF_RE.search(cells[0])
            href = href_m.group(1) if href_m else None
            if href and href.startswith("/"):
                href = "https://msfsaddons.com" + href
            row_key_m = DATA_S_RE.search(attrs)
            key = row_key_m.group(1).strip() if row_key_m else slug(f"{name} {developer}")
            if not developer:
                result.rows_without_developer += 1

            # De-duplicate on the source's own normalised row key; the same
            # aircraft can legitimately appear under two variants, so the key
            # (which the source derives from name+developer) is the right unit.
            dedupe_key = f"{cat_id}::{key}"
            if dedupe_key in seen:
                result.duplicates_removed += 1
                continue
            entry = Aircraft(
                name=name,
                developer=developer or "Unknown",
                category=cat_id,
                category_source=source_title,
                source_url=href,
                source_row_key=key,
                flagged_new=bool(NEW_CLASS_RE.search(attrs)),
            )
            seen[dedupe_key] = entry
            count += 1
        result.category_counts[cat_id] = count
        result.published_counts[cat_id] = published
        result.aircraft.extend(a for a in seen.values() if a.category == cat_id)

    return result


def build_records(result: ImportResult, ingested_at: str) -> list[dict]:
    """Map parsed rows onto the aircraft database schema (spec 32.3)."""
    records: list[dict] = []
    class_by_cat = {c[1]: c[2] for c in CATEGORY_MAP}
    used_ids: dict[str, int] = {}
    for a in sorted(result.aircraft, key=lambda x: (x.category, x.name.lower())):
        base = slug(f"{a.name}-{a.developer}")
        n = used_ids.get(base, 0) + 1
        used_ids[base] = n
        aircraft_id = base if n == 1 else f"{base}-{n}"
        records.append(
            {
                "aircraft_id": aircraft_id,
                "aircraft_name": a.name,
                "manufacturer": None,          # not published by the source
                "developer": a.developer,
                "variant": None,               # not published by the source
                "category": a.category,
                "category_source": a.category_source,
                "sub_category": class_by_cat.get(a.category),
                "engine_type": None,           # never guessed - spec 32.3
                "msfs_2020_status": None,
                "msfs_2024_status": None,
                "release_status": "released" if not a.flagged_new else "new",
                "pricing_status": None,        # not published per row
                "source_url": a.source_url,
                "source_row_key": a.source_row_key,
                "developer_url": None,
                "documentation_url": None,
                "asset_source": None,
                "asset_license": "unknown",
                "model_status": "not_started",
                "cockpit_status": "not_started",
                "flight_model_status": "not_started",
                "livery_status": "not_started",
                "implementation_status": "catalogued",
                "skybound_capability": "catalog_only",  # NOT flyable (spec 32.9)
                "skybound_version": None,
                "notes": (
                    "Imported from the public MSFS Addons reference catalog. "
                    "Reference only - no asset rights are granted by listing."
                ),
                "ingested_at": ingested_at,
            }
        )
    return records


def write_database(records: list[dict], out_path: Path, source_sha: str) -> None:
    payload = {
        "schema_version": 1,
        "catalog_name": "MSFS Addons aircraft reference catalog (SKYBOUND ingestion)",
        "source": {
            "url": SOURCE_URL,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "content_sha256": source_sha,
            "terms_note": (
                "Reference/verification source only. Listing an aircraft here "
                "does not grant redistribution rights (SKYBOUND spec 32.5)."
            ),
        },
        "totals": {
            "aircraft": len(records),
            "flyable_in_skybound": sum(
                1 for r in records if r["implementation_status"] == "playable"
            ),
        },
        "aircraft": records,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def diff_previous(records: list[dict], out_path: Path) -> dict:
    """Change report vs. the previous ingestion (spec 32.11)."""
    if not out_path.exists():
        return {"previous_run": False, "added": [], "removed": [], "changed": []}
    try:
        old = json.loads(out_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"previous_run": False, "added": [], "removed": [], "changed": []}
    old_ids = {r["aircraft_id"] for r in old.get("aircraft", [])}
    new_ids = {r["aircraft_id"] for r in records}
    old_by_id = {r["aircraft_id"]: r for r in old.get("aircraft", [])}
    changed = []
    for r in records:
        o = old_by_id.get(r["aircraft_id"])
        if not o:
            continue
        # Only source-owned fields are compared; verified SKYBOUND
        # implementation data must never be reported as "changed" by a refresh.
        for f in ("aircraft_name", "developer", "source_url", "release_status"):
            if o.get(f) != r.get(f):
                changed.append({"aircraft_id": r["aircraft_id"], "field": f,
                                "old": o.get(f), "new": r.get(f)})
    return {
        "previous_run": True,
        "added": sorted(new_ids - old_ids),
        "removed": sorted(old_ids - new_ids),
        "changed": changed,
    }


def write_report(result: ImportResult, records: list[dict], diff: dict,
                 report_path: Path, sha: str) -> None:
    import hashlib  # noqa: F401  (kept local to the report writer)

    cat_titles = {c[1]: c[0] for c in CATEGORY_MAP}
    lines = [
        "# SKYBOUND - aircraft catalog ingestion report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"Source: {SOURCE_URL}",
        f"Source page size: {result.source_page_bytes:,} bytes  ",
        f"Source SHA-256: `{sha}`",
        "",
        f"**Aircraft ingested: {len(records)}** across {len(result.category_counts)} categories.",
        "",
        "| Category | Aircraft |",
        "|---|---:|",
    ]
    for cat_id, n in result.category_counts.items():
        pub = result.published_counts.get(cat_id)
        mark = "" if pub is None or pub == n else f" (page states {pub})"
        lines.append(f"| {cat_titles.get(cat_id, cat_id)} | {n}{mark} |")
    lines += [
        f"| **Total** | **{sum(result.category_counts.values())}** |",
        "",
        f"- Duplicate rows collapsed: {result.duplicates_removed}",
        f"- Rows missing a developer string: {result.rows_without_developer}",
        "- Records with source link captured: "
        f"{sum(1 for r in records if r['source_url'])} / {len(records)}",
        f"- Flyable in SKYBOUND today: {sum(1 for r in records if r['implementation_status'] == 'playable')}",
        "",
        "## Change report vs. previous ingestion",
        "",
    ]
    if not diff["previous_run"]:
        lines.append("No previous database found - this is a baseline ingestion.")
    else:
        lines.append(f"- New aircraft: {len(diff['added'])}")
        for a in diff["added"][:40]:
            lines.append(f"  - `{a}`")
        lines.append(f"- Removed aircraft: {len(diff['removed'])}")
        for a in diff["removed"][:40]:
            lines.append(f"  - `{a}`")
        lines.append(f"- Changed source fields: {len(diff['changed'])}")
        for c in diff["changed"][:40]:
            lines.append(f"  - `{c['aircraft_id']}` {c['field']}: {c['old']!r} -> {c['new']!r}")
    lines += [
        "",
        "## Honest status",
        "",
        "Every record above is `catalogued` with `skybound_capability = catalog_only`.",
        "Appearing in this database does **not** mean the aircraft is flyable, and the",
        "Aircraft Browser must never offer a catalogued-only entry for selection",
        "(spec 32.9). Promotion to `playable` requires a licensed or original model,",
        "a validated flight model and a tested cockpit - see DEVELOPMENT_LOG.md.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    project = here.parent.parent
    ap = argparse.ArgumentParser(description="Import the MSFS Addons aircraft catalog.")
    ap.add_argument("--html", type=Path, help="parse a saved HTML copy instead of fetching")
    ap.add_argument("--cache-dir", type=Path, default=project / "Build" / "cache",
                    help="where the downloaded page is cached for reproducibility")
    ap.add_argument("--out", type=Path,
                    default=project / "Content" / "Data" / "AircraftCatalog" / "aircraft_catalog.json")
    ap.add_argument("--report", type=Path,
                    default=project / "Content" / "Data" / "AircraftCatalog" / "import_report.md")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    if args.html:
        page = args.html.read_text(encoding="utf-8", errors="replace")
        origin = f"saved file {args.html}"
    else:
        try:
            page = fetch(SOURCE_URL)
        except Exception as exc:  # noqa: BLE001 - reported to the operator
            print(f"[importer] network failure: {exc}", file=sys.stderr)
            return 2
        origin = SOURCE_URL
        args.cache_dir.mkdir(parents=True, exist_ok=True)
        (args.cache_dir / "msfs-aircraft-list.html").write_text(page, encoding="utf-8")

    import hashlib

    sha = hashlib.sha256(page.encode("utf-8")).hexdigest()
    try:
        result = parse(page)
    except RuntimeError as exc:
        print(f"[importer] parse failure: {exc}", file=sys.stderr)
        return 3
    if not result.aircraft:
        print("[importer] parse failure: zero aircraft extracted", file=sys.stderr)
        return 3

    records = build_records(result, datetime.now(timezone.utc).isoformat(timespec="seconds"))
    diff = diff_previous(records, args.out)
    write_database(records, args.out, sha)
    write_report(result, records, diff, args.report, sha)

    if not args.quiet:
        print(f"[importer] source: {origin}")
        print(f"[importer] aircraft ingested: {len(records)}")
        for cat_id, n in result.category_counts.items():
            print(f"           {cat_id:<24} {n:>4}")
        print(f"[importer] duplicates collapsed: {result.duplicates_removed}")
        for problem in result.integrity():
            print(f"[importer] INTEGRITY: {problem}", file=sys.stderr)
        print(f"[importer] wrote {args.out}")
        print(f"[importer] wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
