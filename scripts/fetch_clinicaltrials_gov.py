#!/usr/bin/env python3
"""Fetch direct ClinicalTrials.gov API v2 search snapshots for PBM terms.

The raw API responses are private review inputs and contain fields that must
never be copied to the public snapshot (including contact/location details).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "direct-sources" / "raw" / "clinicaltrials-gov"
API_URL = "https://clinicaltrials.gov/api/v2/studies"
SEARCH_EXPRESSIONS = (
    "photobiomodulation OR photobiostimulation",
    '"low level laser therapy" OR "low level light therapy" OR LLLT OR "laser phototherapy"',
    '"red light therapy" OR "near infrared light" OR "LED therapy"',
)


def request_page(
    query: str,
    page_token: str | None,
    page_size: int,
    timeout: int,
    opener: Callable[..., Any] = urllib.request.urlopen,
    retry_delay: float = 1.0,
) -> bytes:
    params = {
        "format": "json",
        "query.term": query,
        "pageSize": str(page_size),
        "countTotal": "true",
    }
    if page_token:
        params["pageToken"] = page_token
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "PBM-science-ongoing-studies/1.0 (research index; contact: pbm.science)",
        },
    )
    for attempt in range(5):
        try:
            with opener(req, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"ClinicalTrials.gov API returned HTTP {response.status}")
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 4:
                raise
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else retry_delay * (2**attempt)
            time.sleep(min(delay, 60))
        except (TimeoutError, urllib.error.URLError):
            if attempt == 4:
                raise
            time.sleep(min(retry_delay * (2**attempt), 60))
    raise RuntimeError("ClinicalTrials.gov API retry loop ended unexpectedly")


def fetch_snapshot(
    output_dir: Path,
    retrieved_on: str,
    queries: tuple[str, ...] = SEARCH_EXPRESSIONS,
    page_size: int = 1000,
    timeout: int = 60,
    opener: Callable[..., Any] = urllib.request.urlopen,
    pause_seconds: float = 0.2,
) -> dict[str, Any]:
    if not (1 <= page_size <= 1000):
        raise ValueError("page_size must be from 1 through 1000")
    output_dir.mkdir(parents=True, exist_ok=True)
    query_manifest = []
    for query_number, query in enumerate(queries, start=1):
        query_entry: dict[str, Any] = {
            "query": query,
            "total_count": None,
            "total_counts_observed": [],
            "returned_count": 0,
            "pages": [],
        }
        page_token = None
        page_number = 0
        while True:
            if page_number:
                time.sleep(pause_seconds)
            page_number += 1
            raw = request_page(query, page_token, page_size, timeout, opener=opener)
            body = json.loads(raw)
            if not isinstance(body, dict) or not isinstance(body.get("studies"), list):
                raise ValueError(f"API response for query {query_number} is not a studies result")
            total = body.get("totalCount")
            if total is not None and total not in query_entry["total_counts_observed"]:
                query_entry["total_counts_observed"].append(total)
            if total is not None:
                query_entry["total_count"] = total
            filename = f"{retrieved_on}-q{query_number:02d}-page{page_number:03d}.json"
            file_path = output_dir / filename
            file_path.write_bytes(raw)
            count = len(body["studies"])
            query_entry["returned_count"] += count
            query_entry["pages"].append({
                "file": filename,
                "records": count,
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
            page_token = body.get("nextPageToken")
            if not page_token:
                break
        query_entry["count_changed_during_fetch"] = len(query_entry["total_counts_observed"]) > 1
        query_manifest.append(query_entry)
        print(json.dumps({
            "query_number": query_number,
            "total_count": query_entry["total_count"],
            "pages": len(query_entry["pages"]),
            "saved": query_entry["returned_count"],
        }, sort_keys=True))

    manifest = {
        "schema_version": 1,
        "source": "ClinicalTrials.gov API v2",
        "source_url": "https://clinicaltrials.gov/data-api/about-api",
        "api_url": API_URL,
        "retrieved_on": retrieved_on,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "query_field": "query.term",
        "page_size": page_size,
        "queries": query_manifest,
        "returned_rows_with_duplicates": sum(item["returned_count"] for item in query_manifest),
    }
    (output_dir / f"{retrieved_on}-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--retrieved-on", help="local retrieval date in YYYY-MM-DD format")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    retrieved_on = args.retrieved_on or datetime.now().astimezone().date().isoformat()
    try:
        datetime.strptime(retrieved_on, "%Y-%m-%d")
        manifest = fetch_snapshot(args.output_dir, retrieved_on, page_size=args.page_size, timeout=args.timeout)
        print(json.dumps({
            "retrieved_on": retrieved_on,
            "query_count": len(manifest["queries"]),
            "returned_rows_with_duplicates": manifest["returned_rows_with_duplicates"],
            "manifest": str(args.output_dir / f"{retrieved_on}-manifest.json"),
        }, sort_keys=True))
        return 0
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"Direct-source fetch stopped: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
