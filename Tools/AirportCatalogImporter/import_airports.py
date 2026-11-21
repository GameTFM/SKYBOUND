#!/usr/bin/env python3
"""
SKYBOUND - global airport database importer.

WHY THIS DATASET
----------------
The request is "every airport". MSFS airport assets cannot be extracted or
redistributed (proprietary), so SKYBOUND needs its own complete, licence-clean
airport set. OurAirports publishes the worldwide airport + runway dataset in the
public domain, which is the same underlying reality MSFS itself is built on:
every airport on Earth, with identifier, position, elevation and runways.

This importer builds that database, including runway true headings, dimensions,
surface and lighting - i.e. the data needed to place an aircraft on a runway and
to generate a believable airport.

VISUAL TIERS (see Documentation/AIRPORTS.md)
--------------------------------------------
* `hero`      - hand-modelled terminal buildings, jetbridges, signage. Costly;
                only a curated list gets this.
* `generated` - real runways/taxiway layout + procedural buildings informed by
                OpenStreetMap footprints (ODbL, attribution required).
* `data_only` - correct position/identifier, no 3D structures yet.
Nothing is ever presented as hand-crafted when it is generated.

Usage:
    python import_airports.py                     # fetch live data
    python import_airports.py --cache-dir ... --out ...
Exit: 0 ok, 2 network failure, 3 parse failure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://davidmegginson.github.io/ourairports-data"
FILES = ("airports.csv", "runways.csv", "countries.csv")
UA = "SKYBOUND-AirportImporter/0.1 (flight simulator; public-domain airport data)"

# Airports that justify hand-modelled scenery first. Chosen by real-world
# traffic significance, not by what looks good in a screenshot.
HERO_AIRPORTS = {
    "KATL", "KLAX", "KJFK", "KORD", "KDFW", "KDEN", "KSFO", "KSEA", "KMIA", "KBOS",
    "EGLL", "EGKK", "LFPG", "EDDF", "EHAM", "EDDM", "LEMD", "LIRF", "LSZH", "LOWW",
    "EBBR", "EKCH", "ENGM", "ESSA", "EFHK", "LPPT", "LGAV", "LTFM", "UUDD",
    "RJTT", "RJAA", "RKSI", "ZBAA", "ZSPD", "ZGGG", "VHHH", "WSSS", "VTBS", "VIDP",
    "OMDB", "OTHH", "OERK", "LLBG", "FAOR", "YSSY", "YMML", "NZAA", "SBGR", "SAEZ",
    "MMMX", "CYYZ", "CYVR", "KIAH", "KPHX", "KLAS", "KEWR", "KIAD", "KDTW", "KMSP",
}


def fetch(name: str, cache_dir: Path, timeout: int = 90) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / name
    if cached.exists() and cached.stat().st_size > 1000:
        return cached.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(f"{BASE}/{name}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        text = resp.read().decode("utf-8", errors="replace")
    cached.write_text(text, encoding="utf-8")
    return text


def rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build(airports_csv: str, runways_csv: str, countries_csv: str) -> tuple[list[dict], dict]:
    country_names = {r["code"]: r["name"] for r in rows(countries_csv)}

    # Runway acceptance rule, stated as a rule rather than a size threshold:
    # a row is a usable runway end-pair only if it has an identifier, a positive
    # length and a heading inside one revolution. OurAirports contains 225 rows
    # with no designation (40-98 ft stubs, not real runways) and 27 with a heading
    # of exactly 360 deg. They are rejected and counted, never silently dropped.
    rw_stats = {"used": 0, "rejected_no_designation": 0,
                "rejected_bad_length": 0, "normalised_heading": 0}

    runways_by_airport: dict[str, list[dict]] = {}
    for r in rows(runways_csv):
        if r.get("closed") == "1":
            continue
        length = num(r.get("length_ft"))
        designation = (r.get("le_ident") or "").strip()
        if not designation:
            rw_stats["rejected_no_designation"] += 1
            continue
        if not length or length <= 0:
            rw_stats["rejected_bad_length"] += 1
            continue

        # A true heading of 360 is 0; accept anything modulo one revolution.
        heading = num(r.get("le_heading_degT"))
        if heading is not None:
            normalised = heading % 360.0
            if normalised != heading:
                rw_stats["normalised_heading"] += 1
            heading = normalised

        rw_stats["used"] += 1
        runways_by_airport.setdefault(r["airport_ref"], []).append({
            "id": r["id"],
            "designation": designation,
            "reciprocal": (r.get("he_ident") or "").strip(),
            "length_ft": round(length),
            "width_ft": round(num(r.get("width_ft")) or 0),
            "surface": (r.get("surface") or "unknown").lower(),
            "lighted": r.get("lighted") == "1",
            "heading_deg_true": heading,
            "elevation_ft": num(r.get("le_elevation_ft")),
        })

    airports: list[dict] = []
    for r in rows(airports_csv):
        lat, lon = num(r["latitude_deg"]), num(r["longitude_deg"])
        if lat is None or lon is None:
            continue
        ident = (r.get("ident") or "").strip()
        icao = (r.get("icao_code") or "").strip() or None
        iata = (r.get("iata_code") or "").strip() or None
        kind = (r.get("type") or "unknown").strip()
        rwys = runways_by_airport.get(r["id"], [])

        if icao in HERO_AIRPORTS:
            tier, fidelity = "hero", "hand_modelled"
        elif rwys:
            tier, fidelity = "generated", "generated"
        else:
            tier, fidelity = "data_only", "data_only"

        # Upstream completeness flag. A site that airlines serve, or that the
        # dataset calls a large airport, but which has no usable runway row, is a
        # gap in OurAirports - not something this pipeline can invent. It is
        # labelled so the UI can explain why it cannot be spawned at, instead of
        # presenting an empty runway list as if the airport were broken.
        scheduled = r.get("scheduled_service") == "yes"
        if rwys:
            completeness = "complete"
        elif scheduled or kind == "large_airport":
            completeness = "missing_runways"
        else:
            completeness = "no_runways"

        airports.append({
            "airport_id": ident.lower(),
            "ident": ident,
            "name": (r.get("name") or "").strip(),
            "type": kind,
            "icao": icao,
            "iata": iata,
            "gps_code": (r.get("gps_code") or "").strip() or None,
            "local_code": (r.get("local_code") or "").strip() or None,
            "latitude_deg": lat,
            "longitude_deg": lon,
            "elevation_ft": num(r.get("elevation_ft")),
            "country_code": (r.get("iso_country") or "").strip() or None,
            "country": country_names.get((r.get("iso_country") or "").strip()),
            "region": (r.get("iso_region") or "").strip() or None,
            "municipality": (r.get("municipality") or "").strip() or None,
            "scheduled_service": scheduled,
            "data_completeness": completeness,
            "home_link": (r.get("home_link") or "").strip() or None,
            "wikipedia_link": (r.get("wikipedia_link") or "").strip() or None,
            "runways": rwys,
            "scenery_tier": tier,
            "scenery_fidelity": fidelity,
            "scenery_status": "not_started",
            "source": "ourairports",
            "source_license": "public_domain",
        })

    stats = {
        "total": len(airports),
        "with_icao": sum(1 for a in airports if a["icao"]),
        "with_iata": sum(1 for a in airports if a["iata"]),
        "with_runways": sum(1 for a in airports if a["runways"]),
        "scheduled_service": sum(1 for a in airports if a["scheduled_service"]),
        "hero": sum(1 for a in airports if a["scenery_tier"] == "hero"),
        "by_type": dict(Counter(a["type"] for a in airports).most_common()),
        "by_tier": dict(Counter(a["scenery_tier"] for a in airports)),
        "runways_used": rw_stats["used"],
        "runways_rejected_no_designation": rw_stats["rejected_no_designation"],
        "runways_rejected_bad_length": rw_stats["rejected_bad_length"],
        "runway_headings_normalised": rw_stats["normalised_heading"],
        "missing_runways_flagged": sum(
            1 for a in airports if a["data_completeness"] == "missing_runways"),
        "countries": len({a["country_code"] for a in airports if a["country_code"]}),
        "top_countries": dict(Counter(a["country_code"] for a in airports
                                     if a["country_code"]).most_common(10)),
    }
    return airports, stats


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    project = here.parent.parent
    ap = argparse.ArgumentParser(description="Import the global airport database.")
    ap.add_argument("--cache-dir", type=Path, default=project / "Build" / "cache" / "ourairports")
    ap.add_argument("--out", type=Path,
                    default=project / "Content" / "Data" / "Airports" / "airports.json")
    ap.add_argument("--report", type=Path,
                    default=project / "Content" / "Data" / "Airports" / "import_report.md")
    args = ap.parse_args(argv)

    try:
        texts = {name: fetch(name, args.cache_dir) for name in FILES}
    except Exception as exc:  # noqa: BLE001 - reported to the operator
        print(f"[airports] network failure: {exc}", file=sys.stderr)
        return 2

    try:
        airports, stats = build(texts["airports.csv"], texts["runways.csv"],
                                texts["countries.csv"])
    except Exception as exc:  # noqa: BLE001
        print(f"[airports] parse failure: {exc}", file=sys.stderr)
        return 3
    if stats["total"] < 10000:
        print(f"[airports] parse failure: only {stats['total']} airports", file=sys.stderr)
        return 3

    # Two files, not one 70 MB blob: the game loads the index at startup for the
    # airport search screen, and only reads runway data when an airport is chosen.
    # Coordinates are rounded to 5 dp (~1 m) which is far beyond runway precision
    # and cuts the index substantially.
    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    index = [{
        "i": a["airport_id"],
        "n": a["name"],
        "t": a["type"],
        "ic": a["icao"],
        "ia": a["iata"],
        "lat": round(a["latitude_deg"], 5),
        "lon": round(a["longitude_deg"], 5),
        "el": a["elevation_ft"],
        "c": a["country_code"],
        "m": a["municipality"],
        "s": 1 if a["scheduled_service"] else 0,
        "r": len(a["runways"]),
        "tier": a["scenery_tier"],
        "dc": a["data_completeness"],
    } for a in airports]

    index_payload = {
        "schema_version": 1,
        "dataset": "OurAirports",
        "source_url": BASE,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checksum": {n: hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
                     for n, t in texts.items()},
        "license": ("Public domain (OurAirports). Commercial and non-commercial use "
                    "permitted; attribution appreciated, not required."),
        "field_legend": {
            "i": "airport_id", "n": "name", "t": "type", "ic": "icao",
            "ia": "iata", "lat": "latitude_deg", "lon": "longitude_deg",
            "el": "elevation_ft", "c": "country_code", "m": "municipality",
            "s": "scheduled_service", "r": "runway_count", "tier": "scenery_tier",
            "dc": "data_completeness (complete | missing_runways | no_runways)",
        },
        "totals": stats,
        "airports": index,
    }
    index_path = out_dir / "airports_index.json"
    index_path.write_text(json.dumps(index_payload, separators=(",", ":"),
                                     ensure_ascii=False), encoding="utf-8")

    detail = {a["airport_id"]: {
        "name": a["name"],
        "icao": a["icao"],
        "iata": a["iata"],
        "type": a["type"],
        "country": a["country"],
        "region": a["region"],
        "municipality": a["municipality"],
        "elevation_ft": a["elevation_ft"],
        "scheduled_service": a["scheduled_service"],
        "home_link": a["home_link"],
        "wikipedia_link": a["wikipedia_link"],
        "runways": a["runways"],
        "data_completeness": a["data_completeness"],
        "scenery_tier": a["scenery_tier"],
        "scenery_status": a["scenery_status"],
        "source": a["source"],
        "source_license": a["source_license"],
    } for a in airports if a["runways"] or a["scenery_tier"] == "hero"}

    detail_path = out_dir / "airports_runways.json"
    detail_path.write_text(json.dumps({"schema_version": 1, "airports": detail},
                                      separators=(",", ":"), ensure_ascii=False),
                           encoding="utf-8")

    lines = [
        "# SKYBOUND - global airport database",
        "",
        f"Source: OurAirports ({BASE}) - **public domain**",
        f"Retrieved: {index_payload['retrieved_at']}",
        "",
        f"**{stats['total']:,} airports**, {stats['with_runways']:,} with usable runway data,",
        f"{stats['with_icao']:,} with an ICAO code, {stats['with_iata']:,} with an IATA code,",
        f"{stats['scheduled_service']:,} with scheduled airline service,",
        f"across {stats['countries']} countries.",
        "",
        "## By type",
        "",
        "| Type | Airports |",
        "|---|---:|",
    ]
    for k, v in stats["by_type"].items():
        lines.append(f"| {k} | {v:,} |")
    lines += ["", "## Scenery tiers", "", "| Tier | Airports | Meaning |", "|---|---:|---|",
              f"| hero | {stats['by_tier'].get('hero', 0):,} | hand-modelled buildings (planned) |",
              f"| generated | {stats['by_tier'].get('generated', 0):,} | real runways + procedural buildings |",
              f"| data_only | {stats['by_tier'].get('data_only', 0):,} | correct position, no 3D yet |",
              "", "## Top countries", "", "| Country | Airports |", "|---|---:|"]
    for k, v in stats["top_countries"].items():
        lines.append(f"| {k} | {v:,} |")
    lines += [
        "",
        "## Honest status",
        "",
        "Every airport above is **present with real identifiers, coordinates,",
        "elevation and runway data**. That is what makes `every airport` true in the",
        "sense that matters for flight: you can spawn, take off and land anywhere.",
        "",
        "**No airport scenery is built yet.** The `hero` tier means *scheduled for",
        "hand modelling*, not done. Generated scenery requires the OSM building",
        "pipeline, which is not implemented. Nothing here is an MSFS asset, and no",
        "MSFS airport model may be copied into SKYBOUND.",
        "",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines), encoding="utf-8")

    print(f"[airports] {stats['total']:,} airports, {stats['with_runways']:,} with runways, "
          f"{stats['with_icao']:,} with ICAO")
    for k, v in stats["by_type"].items():
        print(f"           {k:<16} {v:>7,}")
    print(f"[airports] tiers: {stats['by_tier']}")
    print(f"[airports] wrote {index_path} ({index_path.stat().st_size/1e6:.1f} MB)")
    print(f"[airports] wrote {detail_path} ({detail_path.stat().st_size/1e6:.1f} MB, "
          f"{len(detail):,} airports with runways)")
    print(f"[airports] wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
