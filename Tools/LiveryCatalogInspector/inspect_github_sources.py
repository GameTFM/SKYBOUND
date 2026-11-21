#!/usr/bin/env python3
"""
SKYBOUND - GeoFS livery-source inspector.

Section 6.1 requires the six listed livery repositories to be *actually
inspected*, and section 6.4 requires license information to be recorded per
source. This tool does that against the live GitHub API and records exactly
what it finds - including repositories that no longer exist.

It deliberately does not download the asset payloads. The largest of these
repositories is ~17 GB; cloning them is unnecessary for cataloguing and would
misrepresent "MIT-licensed code" as "MIT-licensed airline artwork". Airline
liveries are third-party trademarks/artwork regardless of the repository's
code license, which is why each record carries a separate `asset_rights`
verdict.

Usage:
    python inspect_github_sources.py [--out PATH]

Exit codes: 0 success (even if some repos are unreachable - that is recorded),
            2 if the GitHub API could not be reached at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# The six repositories named in SKYBOUND specification section 6.
REPOS = [
    "kolos26/GEOFS-LiverySelector",
    "GeofsExplorer/GeoFS-LiverySelector",
    "RoqueDJ/GEOFS-LiverySelectorUltimate",
    "Ariakim-Taiyo/LiveryChanger",
    "Spice9/Geofs-Multiliveries",
    "iuhairways/GEOFS-LiverySelector-by-kolos26",
]

API = "https://api.github.com"
UA = "SKYBOUND-LiveryInspector/0.1 (+catalog research)"


def api_get(path: str, timeout: int = 30) -> tuple[int, dict | list | None]:
    req = urllib.request.Request(
        API + path,
        headers={"User-Agent": UA, "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return resp.status, json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            body = {"message": exc.reason}
        return exc.code, body
    except Exception as exc:  # noqa: BLE001 - network layer
        return 0, {"message": str(exc)}


def inspect(repo: str) -> dict:
    status, meta = api_get(f"/repos/{repo}")
    record: dict = {
        "repo": repo,
        "github_url": f"https://github.com/{repo}",
        "reachable": status == 200,
        "http_status": status,
        "inspected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    if status != 200 or not isinstance(meta, dict):
        record.update(
            {
                "exists": False,
                "status_note": (
                    "Repository not reachable via the GitHub API "
                    f"(HTTP {status}: {meta.get('message') if isinstance(meta, dict) else ''}). "
                    "Recorded as unavailable; do not assume it exists."
                ),
                "code_license": None,
                "asset_rights": "unavailable",
            }
        )
        return record

    lic = (meta.get("license") or {})
    record.update(
        {
            "exists": True,
            "description": meta.get("description"),
            "default_branch": meta.get("default_branch"),
            "size_kb": meta.get("size"),
            "last_pushed": meta.get("pushed_at"),
            "stars": meta.get("stargazers_count"),
            "archived": meta.get("archived", False),
            "code_license": lic.get("spdx_id"),
            "code_license_name": lic.get("name"),
            "code_license_url": (f"https://github.com/{repo}/blob/"
                                 f"{meta.get('default_branch')}/LICENSE"),
        }
    )

    # What the repository actually contains at the top level - this is the
    # evidence for "which files are required" in spec 6.1.
    cstatus, contents = api_get(f"/repos/{repo}/contents/")
    if cstatus == 200 and isinstance(contents, list):
        record["top_level"] = [
            {"name": c.get("name"), "type": c.get("type"), "size": c.get("size")}
            for c in contents
        ]
        record["top_level_names"] = [c.get("name") for c in contents]
    else:
        record["top_level"] = []
        record["top_level_names"] = []
        record["contents_http_status"] = cstatus

    # Asset-rights verdict. An MIT/Apache licence on the *code* does not grant
    # rights to airline trademarks or third-party paint artwork.
    if record["code_license"] in {"MIT", "Apache-2.0", "BSD-3-Clause"}:
        record["asset_rights"] = "code_only"
        record["asset_rights_note"] = (
            f"Code is {record['code_license']}. Livery artwork and airline marks "
            "inside the repository are third-party content and are NOT covered by "
            "the code licence. Metadata (aircraft/airline names, file layout) may be "
            "used for cataloguing; textures/models require separate permission "
            "or replacement (SKYBOUND spec 6.4/32.5)."
        )
    else:
        record["asset_rights"] = "no_license"
        record["asset_rights_note"] = (
            "No recognised open-source licence. Nothing from this repository may be "
            "redistributed. Research/reference only."
        )
    return record


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    project = here.parent.parent
    ap = argparse.ArgumentParser(description="Inspect GeoFS livery repositories.")
    ap.add_argument("--out", type=Path,
                    default=project / "Content" / "Data" / "AircraftCatalog" / "livery_sources.json")
    args = ap.parse_args(argv)

    records = [inspect(r) for r in REPOS]
    reachable = [r for r in records if r["reachable"]]
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": (
            "GitHub REST API v3: /repos/{owner}/{repo} and /contents/. Asset payloads "
            "were not downloaded; see asset_rights_note per record."
        ),
        "summary": {
            "repositories_listed": len(REPOS),
            "repositories_reachable": len(reachable),
            "repositories_missing": len(REPOS) - len(reachable),
            "open_source_code": sum(1 for r in reachable if r.get("code_license")),
            "usable_metadata_sources": [r["repo"] for r in reachable],
        },
        "repositories": records,
        "skybound_policy": (
            "This file is a *research register*, not an asset library. SKYBOUND ships "
            "no aircraft model or livery texture from these repositories. Each livery "
            "offered in-game must carry its own creator attribution and a recorded "
            "permission or an original replacement paint."
        ),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"[livery] inspected {len(records)} repositories "
          f"({len(reachable)} reachable, {len(REPOS) - len(reachable)} missing)")
    for r in records:
        if r["reachable"]:
            print(f"  OK    {r['repo']:<48} licence={r.get('code_license')} "
                  f"size={r.get('size_kb')}KB files={len(r.get('top_level', []))}")
        else:
            print(f"  MISS  {r['repo']:<48} HTTP {r['http_status']}")
    print(f"[livery] wrote {args.out}")
    return 0 if reachable else 2


if __name__ == "__main__":
    raise SystemExit(main())
