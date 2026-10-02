#!/usr/bin/env python3
"""Normalize direct clinical-trial registry snapshots into a private PBM index."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_clinicaltrials_gov import DEFAULT_OUTPUT as CTG_RAW_DEFAULT


DEFAULT_MANIFEST_DIR = CTG_RAW_DEFAULT
DEFAULT_MANUAL_CSV = ROOT / "data" / "direct-sources" / "raw" / "manual-direct-records.csv"
DEFAULT_METADATA = ROOT / "data" / "direct-sources" / "snapshot-metadata.json"
DEFAULT_OUTPUT = ROOT / "data" / "direct-sources" / "private" / "ongoing-studies.json"
DEFAULT_REVIEW_QUEUE = ROOT / "data" / "direct-sources" / "processed" / "review-queue.csv"

REGISTRY_URLS = {
    "ClinicalTrials.gov": "https://clinicaltrials.gov/study/",
    "ReBEC": "https://ensaiosclinicos.gov.br/rg/",
    "ChiCTR": "https://www.chictr.org.cn/searchprojEN.html",
    "CTRI": "https://ctri.nic.in/Clinicaltrials/",
    "IRCT": "https://www.irct.ir/",
}

ACTIVE_STATUS = {
    "recruiting": ("recruiting", "ongoing"),
    "not yet recruiting": ("not_yet_recruiting", "ongoing"),
    "enrolling by invitation": ("enrolling_by_invitation", "ongoing"),
    "active not recruiting": ("active_not_recruiting", "ongoing"),
    "ongoing not recruiting": ("active_not_recruiting", "ongoing"),
    "suspended": ("suspended", "ongoing"),
    "completed": ("completed", "historical"),
    # Recruitment ending does not by itself prove that the study has ended.
    "recruitment completed": ("recruitment_completed", "review"),
    "complete": ("completed", "historical"),
    "terminated": ("terminated", "historical"),
    "withdrawn": ("withdrawn", "historical"),
    "unknown": ("status_unknown", "review"),
    "not reported": ("status_unknown", "review"),
    "not recruiting": ("status_unclear", "review"),
    "no longer recruiting": ("status_unclear", "review"),
}

CORE_TERMS = (
    "photobiomodulation", "photobiostimulation", "low level laser therapy",
    "low level light therapy", "laser phototherapy", "low level laser irradiation",
    "low level light irradiation", "lllt", "lilt",
)
BROAD_TERMS = (
    "red light therapy", "red light", "near infrared", "near-infrared", "nir light",
    "led therapy", "light therapy", "infrared light",
)
CONFLICT_TERMS = (
    "photodynamic", "laser ablation", "laser coagulation", "laser surgery",
    "surgical laser", "high intensity laser", "high-intensity laser",
    "diagnostic laser", "laser imaging", "thermal laser", "laser resurfacing",
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def iso_date(value: Any) -> str | None:
    value = clean(value)
    if not value:
        return None
    match = re.fullmatch(r"(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", value)
    if match:
        return value
    return None


def status_group(raw: Any) -> tuple[str, str]:
    key = re.sub(r"[^a-z]+", " ", clean(raw).casefold()).strip()
    return ACTIVE_STATUS.get(key, ("status_unmapped", "review"))


def values(value: Any) -> list[str]:
    if isinstance(value, list):
        seq = value
    elif value is None or clean(value) == "":
        seq = []
    else:
        seq = re.split(r"[;|\n\r]+", str(value))
    result: list[str] = []
    seen: set[str] = set()
    for item in seq:
        item = clean(item)
        key = item.casefold()
        if item and key not in seen and key not in {"n/a", "none", "not reported", "-"}:
            result.append(item)
            seen.add(key)
    return result


def normalized_search(text: str) -> str:
    text = text.casefold().replace("‐", "-").replace("‑", "-").replace("–", "-")
    return re.sub(r"[\s-]+", " ", text)


def contains_term(text: str, term: str) -> bool:
    candidate = normalized_search(text)
    key = normalized_search(term)
    if key in {"lllt", "lilt"}:
        return bool(re.search(rf"\b{re.escape(key)}\b", candidate))
    return bool(re.search(rf"\b{re.escape(key)}\b", candidate))


def triage(record: dict[str, Any]) -> tuple[str, list[str]]:
    title_fields = " ".join([record.get("title", ""), record.get("scientific_title", "")])
    treatment_fields = " ".join(record.get("interventions", []))
    other_fields = " ".join([
        " ".join(record.get("conditions", [])),
        record.get("summary_for_review", ""),
    ])
    whole = " ".join([title_fields, treatment_fields, other_fields])
    core = [term for term in CORE_TERMS if contains_term(whole, term)]
    broad = [term for term in BROAD_TERMS if contains_term(whole, term)]
    conflict = [term for term in CONFLICT_TERMS if contains_term(whole, term)]
    reasons: list[str] = []
    if not core and not broad:
        return "not_candidate", ["No documented PBM or relevant light-therapy term in the source record"]
    if core:
        reasons.append("Explicit PBM/low-level therapy term: " + ", ".join(core))
        level = "high_specificity_candidate" if core and any(
            contains_term(" ".join([title_fields, treatment_fields]), term) for term in core
        ) else "manual_review"
        if level == "manual_review":
            reasons.append("PBM wording appears only in condition/summary fields")
    else:
        reasons.append("Broad light descriptor needs manual confirmation: " + ", ".join(broad))
        level = "manual_review"
    if conflict:
        reasons.append("Potential non-PBM/mixed intervention: " + ", ".join(conflict))
        level = "manual_review"
    return level, reasons


def ctg_date(struct: Any) -> str | None:
    if not isinstance(struct, dict):
        return None
    return iso_date(struct.get("date"))


def normalize_ctg(study: dict[str, Any], query: str, retrieved_on: str) -> dict[str, Any] | None:
    protocol = study.get("protocolSection") or {}
    identification = protocol.get("identificationModule") or {}
    status = protocol.get("statusModule") or {}
    design = protocol.get("designModule") or {}
    conditions = protocol.get("conditionsModule") or {}
    arms = protocol.get("armsInterventionsModule") or {}
    sponsor = protocol.get("sponsorCollaboratorsModule") or {}
    locations_module = protocol.get("contactsLocationsModule") or {}
    primary_id = clean(identification.get("nctId"))
    title = clean(identification.get("briefTitle"))
    if not re.fullmatch(r"NCT\d{8}", primary_id) or not title:
        return None
    interventions = []
    for item in arms.get("interventions") or []:
        parts = [clean(item.get("type")), clean(item.get("name"))]
        value = ": ".join(x for x in parts if x)
        interventions.append(value)
    locations = locations_module.get("locations") or []
    countries = values([loc.get("country") for loc in locations if isinstance(loc, dict)])
    enrollment = (design.get("enrollmentInfo") or {}).get("count")
    try:
        enrollment = int(enrollment) if enrollment is not None else None
    except (TypeError, ValueError):
        enrollment = None
    phases = values(design.get("phases"))
    primary_id_info = identification.get("orgStudyIdInfo") or {}
    secondary = values([x.get("id") for x in identification.get("secondaryIdInfos") or [] if isinstance(x, dict)])
    conditions_text = values(conditions.get("conditions"))
    brief_summary = clean((protocol.get("descriptionModule") or {}).get("briefSummary"))
    official_title = clean(identification.get("officialTitle"))
    raw_status = clean(status.get("overallStatus"))
    normalized_status, group = status_group(raw_status)
    record = {
        "registry": "ClinicalTrials.gov",
        "registry_code": "NCT",
        "primary_id": primary_id,
        "secondary_ids": secondary,
        "title": title,
        "scientific_title": official_title,
        "status_raw": raw_status,
        "status": normalized_status,
        "status_group": group,
        "conditions": conditions_text,
        "interventions": values(interventions),
        "countries": countries,
        "study_type": clean(design.get("studyType")) or None,
        "phase": ", ".join(phases) or None,
        "target_sample_size": enrollment,
        "registration_date": ctg_date(status.get("studyFirstPostDateStruct")),
        "start_date": ctg_date(status.get("startDateStruct")),
        "primary_completion_date": ctg_date(status.get("primaryCompletionDateStruct")),
        "study_completion_date": ctg_date(status.get("completionDateStruct")),
        "results_posted_on": ctg_date(status.get("studyResultsFirstPostDateStruct")),
        "sponsor": clean((sponsor.get("leadSponsor") or {}).get("name")) or None,
        "source_url": REGISTRY_URLS["ClinicalTrials.gov"] + primary_id,
        "source_retrieved_on": retrieved_on,
        "source_updated_on": ctg_date(status.get("lastUpdatePostDateStruct")),
        "matched_queries": [query],
        "summary_for_review": brief_summary,
        "registry_record_identifier": clean(primary_id_info.get("id")),
    }
    record["triage"], record["triage_reasons"] = triage(record)
    return record


def parse_ctg_snapshot(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    retrieved_on = iso_date(manifest.get("retrieved_on"))
    if not retrieved_on:
        raise ValueError("ClinicalTrials.gov manifest lacks a valid retrieved_on date")
    records: dict[str, dict[str, Any]] = {}
    for query_info in manifest.get("queries") or []:
        query = clean(query_info.get("query"))
        for page in query_info.get("pages") or []:
            path = manifest_path.parent / page["file"]
            body = json.loads(path.read_text(encoding="utf-8"))
            for study in body.get("studies") or []:
                normalized = normalize_ctg(study, query, retrieved_on)
                if normalized is None:
                    continue
                key = normalized["primary_id"]
                if key not in records:
                    records[key] = normalized
                else:
                    current = records[key]
                    if query not in current["matched_queries"]:
                        current["matched_queries"].append(query)
                    if normalized["status_raw"] != current["status_raw"]:
                        current.setdefault("source_snapshot_conflicts", []).append({
                            "query": query,
                            "status_raw": normalized["status_raw"],
                            "retrieved_on": retrieved_on,
                        })
                        current["status"] = "status_conflict"
                        current["status_group"] = "review"
                        current.setdefault("triage_reasons", []).append(
                            "Registry status changed during this multi-query snapshot; refresh before classifying"
                        )
    return sorted(records.values(), key=lambda row: row["primary_id"])


def normalize_manual_record(row: dict[str, str]) -> dict[str, Any]:
    """Normalize a source-screened record entered from ReBEC/ChiCTR/other registry.

    The input CSV deliberately has no contact fields. Keep it under the ignored
    raw directory; only the whitelist below is copied to an output record.
    """
    registry = clean(row.get("registry"))
    primary_id = clean(row.get("primary_id"))
    title = clean(row.get("title"))
    if registry not in {"ReBEC", "ChiCTR", "CTRI", "IRCT", "Other"}:
        raise ValueError(f"Unsupported direct registry label: {registry!r}")
    if not primary_id or not title or not clean(row.get("source_url")):
        raise ValueError("manual direct record requires registry, primary_id, title, and source_url")
    raw_status = clean(row.get("status_raw"))
    normalized_status, group = status_group(raw_status)
    record = {
        "registry": registry,
        "registry_code": registry,
        "primary_id": primary_id,
        "secondary_ids": values(row.get("secondary_ids")),
        "title": title,
        "scientific_title": clean(row.get("scientific_title")),
        "status_raw": raw_status,
        "status": normalized_status,
        "status_group": group,
        "conditions": values(row.get("conditions")),
        "interventions": values(row.get("interventions")),
        "countries": values(row.get("countries")),
        "study_type": clean(row.get("study_type")) or None,
        "phase": clean(row.get("phase")) or None,
        "target_sample_size": safe_int(row.get("target_sample_size")),
        "registration_date": iso_date(row.get("registration_date")),
        "start_date": iso_date(row.get("start_date")),
        "primary_completion_date": iso_date(row.get("primary_completion_date")),
        "study_completion_date": iso_date(row.get("study_completion_date")),
        "source_updated_on": iso_date(row.get("source_updated_on")),
        "source_record_last_updated_on": iso_date(row.get("source_record_last_updated_on")),
        "sponsor": clean(row.get("sponsor")) or None,
        "source_url": clean(row.get("source_url")),
        "source_retrieved_on": iso_date(row.get("source_retrieved_on")),
        "matched_queries": values(row.get("matched_queries")),
        "summary_for_review": "",
    }
    if not record["source_url"].startswith("https://"):
        raise ValueError(f"source_url must use HTTPS for {registry}:{primary_id}")
    record["triage"], record["triage_reasons"] = triage(record)
    return record


def safe_int(value: Any) -> int | None:
    try:
        return int(clean(value))
    except (TypeError, ValueError):
        return None


def read_manual_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    output = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"registry", "primary_id", "title", "status_raw", "source_url"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"manual records file must include headers: {sorted(required)}")
        for row in reader:
            if any(clean(value) for value in row.values()):
                output.append(normalize_manual_record(row))
    return output


def merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        key = f"{record['registry']}|{record['primary_id']}".casefold()
        if key not in merged:
            merged[key] = dict(record)
            continue
        current = merged[key]
        for field in ("matched_queries", "secondary_ids", "conditions", "interventions", "countries"):
            for value in record.get(field) or []:
                if value and value.casefold() not in {x.casefold() for x in current.get(field, [])}:
                    current.setdefault(field, []).append(value)
        if current["status_raw"] != record["status_raw"]:
            current.setdefault("source_snapshot_conflicts", []).append({
                "status_raw": record["status_raw"], "source_url": record["source_url"]
            })
            current["status"] = "status_conflict"
            current["status_group"] = "review"
            current.setdefault("triage_reasons", []).append(
                "Registry status differs across records for this exact registry identifier"
            )
    return sorted(merged.values(), key=lambda row: (row["registry"], row["primary_id"]))


def load_decisions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        decisions = {}
        for row in reader:
            key = f"{clean(row.get('registry')).casefold()}|{clean(row.get('primary_id')).casefold()}"
            decision = clean(row.get("decision")).casefold()
            if key.strip("|") and decision in {"include", "exclude"}:
                decisions[key] = {
                    "decision": decision,
                    "reviewed_on": clean(row.get("reviewed_on")),
                    "note": clean(row.get("note")),
                }
        return decisions


def valid_date(value: Any) -> bool:
    try:
        return date.fromisoformat(clean(value)) is not None
    except ValueError:
        return False


def publication_gate(metadata: dict[str, Any], registry_names: list[str]) -> tuple[bool, list[str]]:
    blockers = []
    review = metadata.get("quality_review") or {}
    if review.get("status") != "passed" or int(review.get("checked_records") or 0) < 50:
        blockers.append("a source-specific, documented review of at least 50 records")
    if not valid_date(review.get("reviewed_on")):
        blockers.append("a valid quality-review date")
    reuse = metadata.get("reuse_review") or {}
    if reuse.get("status") != "cleared" or reuse.get("distribution_permitted") is not True:
        blockers.append("a verified reuse basis for every source")
    cleared = set(reuse.get("cleared_registries") or [])
    missing = sorted(set(registry_names) - cleared)
    if missing:
        blockers.append("reuse review for: " + ", ".join(missing))
    if not valid_date(metadata.get("retrieved_on")):
        blockers.append("a valid retrieval date")
    if "ClinicalTrials.gov" in set(registry_names) and not clean(metadata.get("source_data_timestamp")):
        blockers.append("the ClinicalTrials.gov API data timestamp")
    return not blockers, blockers


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    """Strict output whitelist. Never copy API payloads, contacts, locations, or summaries."""
    return {
        "registry": record["registry"],
        "registry_code": record.get("registry_code"),
        "primary_id": record["primary_id"],
        "secondary_ids": record.get("secondary_ids", []),
        "title": record["title"],
        "status_raw": record["status_raw"],
        "status": record["status"],
        "status_group": record["status_group"],
        "conditions": record.get("conditions", []),
        "interventions": record.get("interventions", []),
        "countries": record.get("countries", []),
        "study_type": record.get("study_type"),
        "phase": record.get("phase"),
        "target_sample_size": record.get("target_sample_size"),
        "registration_date": record.get("registration_date"),
        "start_date": record.get("start_date"),
        "primary_completion_date": record.get("primary_completion_date"),
        "study_completion_date": record.get("study_completion_date"),
        "source_updated_on": record.get("source_updated_on"),
        "source_record_last_updated_on": record.get("source_record_last_updated_on"),
        "source_retrieved_on": record.get("source_retrieved_on"),
        "sponsor": record.get("sponsor"),
        "source_url": record["source_url"],
    }


def process(records: list[dict[str, Any]], metadata: dict[str, Any], decisions: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    records = merge_records(records)
    registries = sorted({r["registry"] for r in records})
    passed, blockers = publication_gate(metadata, registries)
    approved = []
    review_rows = []
    counts = Counter()
    for record in records:
        decision_key = f"{record['registry'].casefold()}|{record['primary_id'].casefold()}"
        decision = decisions.get(decision_key)
        if record["triage"] == "not_candidate":
            counts["not_candidates"] += 1
            continue
        counts["candidates"] += 1
        if record["status_group"] == "ongoing":
            counts["ongoing_candidates"] += 1
        elif record["status_group"] == "historical":
            counts["historical_candidates"] += 1
        else:
            record["triage_reasons"].append("Source-reported status needs review or mapping")
        allowed_scope = record["triage"] == "high_specificity_candidate"
        if decision and decision["decision"] == "exclude":
            counts["manually_excluded"] += 1
            continue
        include = (
            passed
            and record["status_group"] == "ongoing"
            and (allowed_scope or bool(decision and decision["decision"] == "include"))
        )
        if include:
            approved.append(public_record(record))
            counts["published_candidates"] += 1
        elif record["status_group"] != "ongoing":
            counts["held_non_ongoing_or_unclear"] += 1
            review_rows.append(review_row(record, decision))
        elif not allowed_scope and not (decision and decision["decision"] == "include"):
            counts["held_scope_review"] += 1
            review_rows.append(review_row(record, decision))
        elif not passed:
            counts["held_publication_gate"] += 1
            review_rows.append(review_row(record, decision))
    source_summaries = []
    for registry in registries:
        subset = [r for r in records if r["registry"] == registry]
        source_summaries.append({
            "registry": registry,
            "search_hit_count": len(subset),
            "ongoing_status_count": sum(r["status_group"] == "ongoing" for r in subset),
            "retrieved_on": metadata.get("retrieved_on"),
            "data_timestamp": metadata.get("source_data_timestamp"),
            "rights_status": (metadata.get("reuse_review") or {}).get("status", "not_checked"),
        })
    counts["source_records"] = len(records)
    counts["unique_registry_records"] = len(records)
    payload = {
        "schema_version": 2,
        "source_strategy": "direct_original_registries",
        "snapshot_status": "ready" if passed else "awaiting_source_review",
        "retrieved_on": metadata.get("retrieved_on"),
        "source_data_timestamp": metadata.get("source_data_timestamp"),
        "sources": source_summaries,
        "quality_review": metadata.get("quality_review") or {},
        "reuse_review": metadata.get("reuse_review") or {"status": "not_checked"},
        "publication_blockers": blockers,
        "counts": dict(counts),
        "records": approved,
    }
    return payload, review_rows


def review_row(record: dict[str, Any], decision: dict[str, str] | None) -> dict[str, Any]:
    return {
        "registry": record["registry"],
        "primary_id": record["primary_id"],
        "title": record["title"],
        "status_raw": record["status_raw"],
        "countries": " | ".join(record.get("countries", [])),
        "conditions": " | ".join(record.get("conditions", [])),
        "interventions": " | ".join(record.get("interventions", [])),
        "triage": record["triage"],
        "reasons": " | ".join(record["triage_reasons"]),
        "source_url": record["source_url"],
        "decision": (decision or {}).get("decision", ""),
        "reviewed_on": (decision or {}).get("reviewed_on", ""),
        "note": (decision or {}).get("note", ""),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="date-specific ClinicalTrials.gov fetch manifest")
    parser.add_argument("--manual-records", type=Path, default=DEFAULT_MANUAL_CSV)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--decisions", type=Path, default=ROOT / "data" / "direct-sources" / "review-decisions.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--review-queue", type=Path, default=DEFAULT_REVIEW_QUEUE)
    args = parser.parse_args()
    try:
        if not args.metadata.exists():
            raise ValueError(f"metadata file not found: {args.metadata}")
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        manifest_path = args.manifest
        if manifest_path is None:
            manifests = sorted(DEFAULT_MANIFEST_DIR.glob("*-manifest.json"))
            if manifests:
                manifest_path = manifests[-1]
        records = parse_ctg_snapshot(manifest_path) if manifest_path else []
        if manifest_path:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            metadata["source_data_timestamp"] = manifest.get("source_data_timestamp")
        records.extend(read_manual_records(args.manual_records))
        decisions = load_decisions(args.decisions)
        payload, queue = process(records, metadata, decisions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        write_csv(args.review_queue, queue, [
            "registry", "primary_id", "title", "status_raw", "countries", "conditions",
            "interventions", "triage", "reasons", "source_url", "decision", "reviewed_on", "note",
        ])
        print(json.dumps({
            "snapshot_status": payload["snapshot_status"],
            "counts": payload["counts"],
            "publication_blockers": payload["publication_blockers"],
            "output": str(args.output),
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, csv.Error, ValueError, KeyError, TypeError) as exc:
        print(f"Direct-source processing stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
