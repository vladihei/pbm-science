#!/usr/bin/env python3
"""Create a reproducible, stratified, contact-free review sample from direct snapshots."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from fetch_clinicaltrials_gov import SEARCH_EXPRESSIONS  # noqa: E402
from process_direct_sources import DEFAULT_MANIFEST_DIR, parse_ctg_snapshot  # noqa: E402

DEFAULT_OUTPUT = ROOT / "data" / "direct-sources" / "processed" / "quality-sample.csv"
QUERY_BUCKETS = (
    ("q1_explicit_terms", SEARCH_EXPRESSIONS[0], 20),
    ("q2_low_level_terms", SEARCH_EXPRESSIONS[1], 20),
    ("q3_red_nir_led_terms", SEARCH_EXPRESSIONS[2], 10),
)


def bucket_for(record: dict[str, Any]) -> str:
    matches = set(record.get("matched_queries") or [])
    for name, query, _quota in QUERY_BUCKETS:
        if query in matches:
            return name
    return "unmatched"


def stable_rank(record: dict[str, Any], retrieved_on: str) -> str:
    return hashlib.sha256(f"{retrieved_on}|{record['registry']}|{record['primary_id']}".encode()).hexdigest()


def choose_sample(records: list[dict[str, Any]], retrieved_on: str, total: int = 50) -> list[dict[str, Any]]:
    by_bucket: dict[str, list[dict[str, Any]]] = {name: [] for name, _query, _quota in QUERY_BUCKETS}
    for record in records:
        if record.get("triage") == "not_candidate":
            continue
        bucket = bucket_for(record)
        if bucket in by_bucket:
            by_bucket[bucket].append(record)

    selected = []
    for bucket_name, _query, quota in QUERY_BUCKETS:
        items = by_bucket[bucket_name]
        strata: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for record in items:
            key = (record.get("status_group", "review"), record.get("triage", "manual_review"))
            strata.setdefault(key, []).append(record)
        for group in strata.values():
            group.sort(key=lambda item: stable_rank(item, retrieved_on))
        ordered_keys = sorted(strata)
        bucket_selection = []
        while len(bucket_selection) < quota and ordered_keys:
            remaining = []
            for key in ordered_keys:
                group = strata[key]
                if group:
                    bucket_selection.append(group.pop(0))
                if group:
                    remaining.append(key)
                if len(bucket_selection) >= quota:
                    break
            ordered_keys = remaining
        selected.extend((bucket_name, record) for record in bucket_selection)
    if len(selected) < total:
        present = {record["primary_id"] for _, record in selected}
        extras = [r for r in records if r.get("triage") != "not_candidate" and r["primary_id"] not in present]
        extras.sort(key=lambda row: stable_rank(row, retrieved_on))
        selected.extend(("overflow", row) for row in extras[: total - len(selected)])
    rows = []
    for bucket, record in selected[:total]:
        rows.append({
            "stratum": bucket,
            "primary_id": record["primary_id"],
            "title": record["title"],
            "status_raw": record["status_raw"],
            "status_group": record["status_group"],
            "source_updated_on": record.get("source_updated_on") or "",
            "source_retrieved_on": record.get("source_retrieved_on") or "",
            "triage": record["triage"],
            "conditions": " | ".join(record.get("conditions", [])),
            "interventions": " | ".join(record.get("interventions", [])),
            "source_url": record["source_url"],
            "scope_review": "",
            "status_mapping_review": "",
            "review_note": "",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--size", type=int, default=50)
    args = parser.parse_args()
    records = parse_ctg_snapshot(args.manifest)
    retrieved_on = args.manifest.stem.removesuffix("-manifest")
    rows = choose_sample(records, retrieved_on, args.size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "stratum", "primary_id", "title", "status_raw", "status_group", "source_updated_on",
        "source_retrieved_on", "triage", "conditions", "interventions", "source_url",
        "scope_review", "status_mapping_review", "review_note",
    ]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} direct-source review rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
