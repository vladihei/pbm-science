#!/usr/bin/env python3
"""Turn manual WHO ICTRP CSV exports into a reviewed static PBM snapshot."""

from __future__ import annotations

import argparse
import csv
import html
import io
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "ictrp" / "raw"
DEFAULT_METADATA = ROOT / "data" / "ictrp" / "snapshot-metadata.json"
DEFAULT_DECISIONS = ROOT / "data" / "ictrp" / "review-decisions.csv"
DEFAULT_OUTPUT = ROOT / "data" / "ictrp" / "private" / "ongoing-studies.json"
PROCESSED = ROOT / "data" / "ictrp" / "processed"
ICTRP_URL = "https://trialsearch.who.int/"


FIELD_ALIASES = {
    "primary_id": (
        "main id", "main trial id", "primary id", "primary trial id",
        "primary registration number", "trial id", "trial identifier",
        "trialid", "registration number", "registration id",
    ),
    "title": ("public title", "study title", "trial title", "title"),
    "scientific_title": ("scientific title",),
    "registry": (
        "primary registry", "primary registry name", "registry", "source registry",
        "name of registry", "trial registry", "source register",
    ),
    "secondary_ids": (
        "secondary ids", "secondary id", "secondary identifiers",
        "secondary identification numbers", "other ids", "other identifiers",
    ),
    "status": ("recruitment status", "recruitment", "study status", "trial status", "status"),
    "conditions": (
        "health condition studied", "health conditions studied", "condition",
        "conditions", "condition studied", "condition(s)",
    ),
    "interventions": ("intervention", "interventions", "intervention(s)", "treatment"),
    "countries": (
        "country", "countries", "country of recruitment", "countries of recruitment",
        "recruitment country", "recruitment countries",
    ),
    "locations": ("locations", "study locations", "recruitment locations", "study sites"),
    "study_type": ("study type", "study design", "study type/design", "design"),
    "phase": ("phase", "trial phase", "clinical trial phase"),
    "sample_size": (
        "target sample size", "target sample", "recruitment size", "sample size",
        "number of participants", "enrollment", "target size",
    ),
    "registration_date": (
        "date of registration", "date registration", "registration date", "date registered",
    ),
    "start_date": (
        "date of first enrollment", "date enrollement", "date enrollment",
        "study start date", "start date",
    ),
    "last_enrollment_date": (
        "date of last enrollment", "date of last enrolment", "last enrollment date",
    ),
    "primary_completion_date": ("primary completion date", "primary study completion date"),
    "study_completion_date": (
        "study completion date", "date of study completion", "completion date",
    ),
    "estimated_completion_date": ("estimated completion date", "estimated study completion date"),
    "results_completed_date": ("results date completed", "date results completed"),
    "sponsor": ("primary sponsor", "sponsor", "lead sponsor"),
    "original_url": (
        "link to original record", "original registry url", "original record url",
        "primary registry url", "registry record url", "url of record", "record url",
        "web address",
    ),
    "ictrp_group_id": ("ictrp group id", "linked record group", "trial group id", "utn"),
    "ictrp_processed_date": (
        "date processed by ictrp", "ictrp processing date", "date of last processing",
        "last processed by ictrp", "data processing date",
    ),
    "last_refreshed_on": ("last refreshed on",),
    "summary": (
        "brief summary", "public summary", "scientific summary", "intervention description",
    ),
}

CORE_TERMS = (
    "photobiomodulation",
    "photobiostimulation",
    "low level laser therapy",
    "low level light therapy",
    "low level laser irradiation",
    "low level light irradiation",
    "laser phototherapy",
    "lllt",
)
BROAD_TERMS = (
    "red light therapy",
    "red light",
    "near infrared",
    "near-infrared",
    "nir light",
    "led therapy",
    "light therapy",
    "infrared light",
)
CONFLICT_TERMS = (
    "photodynamic",
    "laser ablation",
    "laser coagulation",
    "laser surgery",
    "surgical laser",
    "high intensity laser",
    "high-intensity laser",
    "diagnostic laser",
    "laser imaging",
    "thermal laser",
    "laser resurfacing",
)
SCOPE_REVIEW_TERMS = (
    "blue light",
    "blue led",
    "green light",
    "violet light",
    "ultraviolet",
    "uv light",
    "nd:yag",
    "er:yag",
    "co2 laser",
    "excimer laser",
)

ACTIVE_STATUSES = {
    "recruiting": "recruiting",
    "not yet recruiting": "not_yet_recruiting",
    "enrolling by invitation": "enrolling_by_invitation",
    "recruiting by invitation": "enrolling_by_invitation",
    "active not recruiting": "active_not_recruiting",
    "ongoing not recruiting": "active_not_recruiting",
    "suspended": "suspended",
}
HISTORICAL_STATUSES = {
    "completed": "completed",
    "complete": "completed",
    "terminated": "terminated",
    "withdrawn": "withdrawn",
}


def normalized_header(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def header_map(headers: list[str]) -> dict[str, str]:
    by_normalized = {normalized_header(h): h for h in headers if h}
    result: dict[str, str] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            key = normalized_header(alias)
            if key in by_normalized:
                result[field] = by_normalized[key]
                break
    return result


def split_values(value: str | None, comma: bool = False) -> list[str]:
    if not value:
        return []
    separators = r"[;|\n\r]+" if not comma else r"[;,|\n\r]+"
    values = []
    seen = set()
    for item in re.split(separators, value):
        item = re.sub(r"\s+", " ", item).strip()
        key = item.casefold()
        if key in {"nil", "nil known", "none", "n/a", "na", "not applicable", "not reported", "-"}:
            continue
        if item and key not in seen:
            values.append(item)
            seen.add(key)
    return values


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(re.sub(r"<[^>]*>", " ", value))
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if re.fullmatch(r"\d{4}(?:-\d{2}){0,2}", value):
        return value
    if re.fullmatch(r"\d{8}", value):
        try:
            return datetime.strptime(value, "%Y%m%d").date().isoformat()
        except ValueError:
            pass
    for fmt in (
        "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y/%m/%d",
        "%d %B %Y", "%d %b %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return value


def parse_sample_size(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"\d[\d, ]*", value)
    if not match:
        return None
    try:
        return int(re.sub(r"[, ]", "", match.group(0)))
    except ValueError:
        return None


def safe_url(value: str | None) -> str | None:
    value = (value or "").strip()
    return value if value.startswith(("https://", "http://")) else None


def infer_registry(registry: str | None, primary_id: str) -> str:
    if registry and registry.strip():
        return re.sub(r"\s+", " ", registry).strip()
    prefix = primary_id.upper()
    mappings = (
        (r"^NCT\d+", "ClinicalTrials.gov"),
        (r"^ACTRN\d+", "Australian New Zealand Clinical Trials Registry"),
        (r"^ISRCTN", "ISRCTN"),
        (r"^RBR-", "Brazilian Clinical Trials Registry (ReBEC)"),
        (r"^CHICTR", "Chinese Clinical Trial Registry"),
        (r"^CTRI/", "Clinical Trials Registry - India"),
        (r"^IRCT", "Iranian Registry of Clinical Trials"),
        (r"^PACTR", "Pan African Clinical Trial Registry"),
        (r"^TCTR", "Thai Clinical Trials Registry"),
        (r"^KCT", "Clinical Research Information Service (Republic of Korea)"),
        (r"^JPRN", "Japan Primary Registries Network (JPRN/jRCT)"),
    )
    for pattern, name in mappings:
        if re.search(pattern, prefix):
            return name
    return "Not reported"


def status_group(raw_status: str | None) -> tuple[str, str]:
    key = re.sub(r"[^a-z]+", " ", (raw_status or "").casefold()).strip()
    if key in ACTIVE_STATUSES:
        return ACTIVE_STATUSES[key], "ongoing"
    if key in HISTORICAL_STATUSES:
        return HISTORICAL_STATUSES[key], "historical"
    if key in {"not recruiting", "no longer recruiting", "not active", "active not recruiting"}:
        return "status_unclear", "review"
    if key in {"not applicable", "unknown", "not reported", ""}:
        return "status_unknown", "review"
    return "status_unmapped", "review"


def normalize_registry(value: str | None) -> str | None:
    """Normalize ICTRP Search Portal source names to its Data Providers labels."""
    key = re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()
    aliases = {
        "anzctr": "Australian New Zealand Clinical Trials Registry",
        "australian new zealand clinical trials registry": "Australian New Zealand Clinical Trials Registry",
        "chictr": "Chinese Clinical Trial Registry",
        "chinese clinical trial registry": "Chinese Clinical Trial Registry",
        "clinicaltrials gov": "ClinicalTrials.gov",
        "clinicaltrials gov": "ClinicalTrials.gov",
        "ctis": "Clinical Trials Information System (CTIS)",
        "clinical trials information system ctis": "Clinical Trials Information System (CTIS)",
        "eu ctr": "EU Clinical Trials Register (EU-CTR)",
        "eu clinical trials register": "EU Clinical Trials Register (EU-CTR)",
        "isrctn": "ISRCTN",
        "netherlands national trial register": "Overview of Medical Research in the Netherlands (OMON)",
        "nl omon": "Overview of Medical Research in the Netherlands (OMON)",
        "omon": "Overview of Medical Research in the Netherlands (OMON)",
        "rebec": "Brazilian Clinical Trials Registry (ReBEC)",
        "brazilian clinical trials registry rebec": "Brazilian Clinical Trials Registry (ReBEC)",
        "ctri": "Clinical Trials Registry - India",
        "clinical trials registry india": "Clinical Trials Registry - India",
        "cris": "Clinical Research Information Service - Republic of Korea",
        "clinical research information service republic of korea": "Clinical Research Information Service - Republic of Korea",
        "cuban public registry of clinical trials": "Cuban Public Registry of Clinical Trials",
        "german clinical trials register": "German Clinical Trials Register",
        "irct": "Iranian Registry of Clinical Trials",
        "iranian registry of clinical trials": "Iranian Registry of Clinical Trials",
        "jprn": "Japan Primary Registries Network (JPRN/jRCT)",
        "jrct": "Japan Primary Registries Network (JPRN/jRCT)",
        "japan registry of clinical trials jrct": "Japan Primary Registries Network (JPRN/jRCT)",
        "japan primary registries network jprn jrct": "Japan Primary Registries Network (JPRN/jRCT)",
        "pactr": "Pan African Clinical Trial Registry",
        "pan african clinical trial registry": "Pan African Clinical Trial Registry",
        "slctr": "Sri Lanka Clinical Trials Registry",
        "sri lanka clinical trials registry": "Sri Lanka Clinical Trials Registry",
        "tctr": "Thai Clinical Trials Registry (TCTR)",
        "thai clinical trials registry tctr": "Thai Clinical Trials Registry (TCTR)",
        "itmctr": "International Traditional Medicine Clinical Trial Registry (ITMCTR)",
        "international traditional medicine clinical trial registry itmctr": "International Traditional Medicine Clinical Trial Registry (ITMCTR)",
        "repec": "Peruvian Clinical Trials Registry (REPEC)",
        "peruvian clinical trials registry repec": "Peruvian Clinical Trials Registry (REPEC)",
        "lbctr": "Lebanese Clinical Trials Registry (LBCTR)",
        "lebanese clinical trials registry lbctr": "Lebanese Clinical Trials Registry (LBCTR)",
    }
    return aliases.get(key)


def triage_text(record: dict[str, Any]) -> tuple[str, list[str]]:
    text = " ".join(
        str(record.get(field) or "")
        for field in (
            "title", "scientific_title", "conditions_raw", "interventions_raw", "summary_raw",
        )
    ).casefold()
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    compact = re.sub(r"[\s-]+", " ", text)
    reasons: list[str] = []
    source_file = str(record.get("source_file") or "").casefold()
    if "q3-descriptors" in source_file and not any(
        query in source_file for query in ("q1-core", "q2-therapy")
    ):
        return "manual_review", [
            "Returned only by the broad q3-descriptors search; verify that the record itself describes therapeutic PBM"
        ]
    def matches(term: str) -> bool:
        normalized = re.sub(r"[\s-]+", " ", term.casefold())
        return bool(re.search(rf"\b{re.escape(normalized)}\b", compact))

    core = [term for term in CORE_TERMS if matches(term)]
    broad = [term for term in BROAD_TERMS if matches(term)]
    conflicts = [term for term in CONFLICT_TERMS if matches(term)]
    scope_review = [term for term in SCOPE_REVIEW_TERMS if matches(term)]
    if not core and not broad:
        source_file = str(record.get("source_file") or "").casefold()
        query_id = next(
            (name for name in ("q1-core", "q2-therapy", "q3-descriptors") if name in source_file),
            None,
        )
        if query_id:
            return "manual_review", [
                f"Returned by {query_id}, but no PBM term appears in mapped export text; verify synonym-expanded match"
            ]
        return "not_candidate", ["No documented PBM search term in title, condition, intervention, or summary"]
    if core:
        reasons.append("Explicit PBM or low-level therapy term: " + ", ".join(core))
        level = "high_specificity_candidate"
    else:
        reasons.append("Broad light descriptor requires review: " + ", ".join(broad))
        level = "manual_review"
    if conflicts:
        reasons.append("Potential non-PBM or mixed intervention: " + ", ".join(conflicts))
        level = "manual_review"
    if scope_review:
        reasons.append("Wavelength or device needs scope review: " + ", ".join(scope_review))
        level = "manual_review"
    if re.search(r"\b10\s*nm\b[^.]{0,40}\bwavelength\b", text):
        reasons.append("Reported 10 nm treatment wavelength is implausible for PBM; verify source record")
        level = "manual_review"
    return level, reasons


def read_csv_file(path: Path) -> list[dict[str, str]]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        detected = csv.Sniffer().sniff(raw[:8192], delimiters=",;\t")
        delimiter = detected.delimiter
    except csv.Error:
        delimiter = ","
    # Sniffer sometimes mistakes quote handling in long-text ICTRP fields and
    # disables doubled-quote escaping. Detect only the separator; keep normal
    # RFC-style CSV quote handling for the actual records.
    reader = csv.DictReader(
        io.StringIO(raw), delimiter=delimiter, quotechar='"', doublequote=True,
        quoting=csv.QUOTE_MINIMAL,
    )
    headers = reader.fieldnames or []
    mapping = header_map(headers)
    missing = [name for name in ("primary_id", "title", "status") if name not in mapping]
    if missing:
        raise ValueError(
            f"{path.name}: could not map required fields {missing}; export headers were {headers!r}"
        )
    output = []
    for row in reader:
        if not any((value or "").strip() for value in row.values()):
            continue
        get = lambda key: clean_text(row.get(mapping.get(key, ""), ""))
        primary_id = get("primary_id")
        title = get("title") or get("scientific_title")
        if not primary_id or not title:
            continue
        status_raw = get("status")
        normalized, group = status_group(status_raw)
        row_issues = []
        extra_values = row.get(None) or []
        if any(str(value).strip() for value in extra_values):
            row_issues.append("CSV row contains extra value(s) outside the export headers")
        if status_raw.startswith(("http://", "https://")):
            row_issues.append("Recruitment Status field contains a URL")
        registry_raw = get("registry")
        registry = normalize_registry(registry_raw)
        if registry is None:
            if registry_raw:
                row_issues.append("Source Register value is not in the approved provider-date map")
            registry = infer_registry(None, primary_id)
        countries = split_values(get("countries"))
        if not countries:
            countries = split_values(get("locations"))
        record = {
            "primary_id": primary_id,
            "registry": registry,
            "secondary_ids": split_values(get("secondary_ids"), comma=True),
            "title": title,
            "scientific_title": get("scientific_title"),
            "status_raw": status_raw,
            "status": normalized,
            "status_group": group,
            "conditions": split_values(get("conditions")),
            "conditions_raw": get("conditions"),
            "interventions": split_values(get("interventions")),
            "interventions_raw": get("interventions"),
            "countries": countries,
            "study_type": get("study_type") or None,
            "phase": get("phase") or None,
            "target_sample_size": parse_sample_size(get("sample_size")),
            "registration_date": parse_date(get("registration_date")),
            "start_date": parse_date(get("start_date")),
            "last_enrollment_date": parse_date(get("last_enrollment_date")),
            "primary_completion_date": parse_date(get("primary_completion_date")),
            "study_completion_date": parse_date(get("study_completion_date")),
            "estimated_completion_date": parse_date(get("estimated_completion_date")),
            "results_completed_date": parse_date(get("results_completed_date")),
            "sponsor": get("sponsor") or None,
            "original_url": safe_url(get("original_url")),
            "ictrp_group_id": get("ictrp_group_id") or None,
            "data_processed_by_ictrp_on": parse_date(get("ictrp_processed_date")),
            "last_refreshed_on": parse_date(get("last_refreshed_on")),
            "summary_raw": get("summary"),
            "source_file": path.name,
            "row_issues": row_issues,
        }
        record["ictrp_url"] = ICTRP_URL + "Trial2.aspx?TrialID=" + quote(record["primary_id"], safe="")
        record["triage"], record["triage_reasons"] = triage_text(record)
        if row_issues:
            record["triage"] = "manual_review"
            record["triage_reasons"].extend(row_issues)
        output.append(record)
    return output


def canonical_key(record: dict[str, Any]) -> str:
    group = str(record.get("ictrp_group_id") or "").strip().casefold()
    if group:
        return "group:" + group
    return "id:" + re.sub(r"\s+", "", str(record.get("primary_id", "")).casefold())


def merge_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for record in records:
        key = canonical_key(record)
        if key not in merged:
            merged[key] = dict(record)
            merged[key]["secondary_ids"] = list(record["secondary_ids"])
            merged[key]["source_files"] = [record["source_file"]]
            continue
        current = merged[key]
        for field in (
            "secondary_ids", "conditions", "interventions", "countries", "source_files", "row_issues",
        ):
            additions = record.get(field, []) if field != "source_files" else [record["source_file"]]
            existing_keys = {str(x).casefold() for x in current.get(field, [])}
            current.setdefault(field, [])
            for value in additions:
                if value and str(value).casefold() not in existing_keys:
                    current[field].append(value)
                    existing_keys.add(str(value).casefold())
        if current.get("original_url") is None and record.get("original_url"):
            current["original_url"] = record["original_url"]
        if not current.get("sponsor") and record.get("sponsor"):
            current["sponsor"] = record["sponsor"]
        refreshed_on = record.get("last_refreshed_on")
        if valid_iso_date(refreshed_on) and (
            not valid_iso_date(current.get("last_refreshed_on"))
            or refreshed_on > current["last_refreshed_on"]
        ):
            current["last_refreshed_on"] = refreshed_on
        if current.get("status_group") == "review" and record.get("status_group") != "review":
            current["status"] = record["status"]
            current["status_raw"] = record["status_raw"]
            current["status_group"] = record["status_group"]
        if current["triage"] == "not_candidate" and record["triage"] != "not_candidate":
            current["triage"] = record["triage"]
            current["triage_reasons"] = record["triage_reasons"]
    return sorted(merged.values(), key=lambda r: (r["title"].casefold(), r["primary_id"].casefold()))


def load_decisions(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        decisions = {}
        for row in reader:
            key = (row.get("primary_id") or "").strip().casefold()
            decision = (row.get("decision") or "").strip().casefold()
            if key and decision in {"include", "exclude"}:
                decisions[key] = {
                    "decision": decision,
                    "reviewed_on": (row.get("reviewed_on") or "").strip(),
                    "note": (row.get("note") or "").strip(),
                }
        return decisions


def valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def quality_review_passed(metadata: dict[str, Any], registries: list[str] | None = None) -> bool:
    review = metadata.get("quality_review") or {}
    try:
        checked = int(review.get("checked_records", 0))
    except (TypeError, ValueError):
        return False
    has_processing_date = valid_iso_date(metadata.get("data_processed_by_ictrp_on"))
    import_dates = metadata.get("registry_import_dates") or {}
    valid_imports = {
        name: value for name, value in import_dates.items() if valid_iso_date(value)
    }
    if registries:
        has_import_date = all(registry in valid_imports for registry in registries)
    else:
        has_import_date = bool(valid_imports)
    return (
        review.get("status") == "passed"
        and checked >= 50
        and valid_iso_date(review.get("reviewed_on"))
        and valid_iso_date(metadata.get("retrieved_on"))
        and (has_processing_date or has_import_date)
    )


def public_record(record: dict[str, Any], decision: dict[str, str] | None) -> dict[str, Any]:
    link = record.get("original_url") or record["ictrp_url"]
    return {
        "primary_id": record["primary_id"],
        "registry": record["registry"],
        "secondary_ids": record["secondary_ids"],
        "title": record["title"],
        "status": record["status"],
        "status_raw": record["status_raw"],
        "status_group": record["status_group"],
        "conditions": record["conditions"],
        "interventions": record["interventions"],
        "countries": record["countries"],
        "study_type": record["study_type"],
        "phase": record["phase"],
        "target_sample_size": record["target_sample_size"],
        "registration_date": record["registration_date"],
        "start_date": record["start_date"],
        "last_enrollment_date": record.get("last_enrollment_date"),
        "primary_completion_date": record.get("primary_completion_date"),
        "study_completion_date": record.get("study_completion_date"),
        "estimated_completion_date": record.get("estimated_completion_date"),
        "results_completed_date": record.get("results_completed_date"),
        "data_processed_by_ictrp_on": record["data_processed_by_ictrp_on"],
        "last_refreshed_on": record.get("last_refreshed_on"),
        "sponsor": record["sponsor"],
        "source_url": link,
        "source_link_kind": "original_registry" if record.get("original_url") else "ictrp",
        "ictrp_url": record["ictrp_url"],
        "source_files": record["source_files"],
    }


def process_records(
    raw_records: list[dict[str, Any]],
    metadata: dict[str, Any],
    decisions: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    records = merge_records(raw_records)
    effective_metadata = dict(metadata)
    import_dates = dict(metadata.get("registry_import_dates") or {})
    for record in records:
        registry = record.get("registry")
        processed_on = record.get("data_processed_by_ictrp_on")
        if registry and valid_iso_date(processed_on):
            current = import_dates.get(registry)
            if not valid_iso_date(current) or processed_on > current:
                import_dates[registry] = processed_on
    effective_metadata["registry_import_dates"] = import_dates
    candidate_registries = sorted({
        record["registry"] for record in records if record["triage"] != "not_candidate"
    })
    included_sources = set(effective_metadata.get("included_source_files") or [])
    if included_sources:
        records = [
            record for record in records
            if included_sources.intersection(record.get("source_files", []))
            and record.get("registry") in import_dates
        ]
    candidate_registries = sorted({
        record["registry"] for record in records if record["triage"] != "not_candidate"
    })
    validated = quality_review_passed(effective_metadata, candidate_registries)
    approved = []
    review_rows = []
    counts = defaultdict(int)

    for record in records:
        decision = decisions.get(record["primary_id"].casefold())
        if record["triage"] == "not_candidate":
            counts["not_candidates"] += 1
            continue
        counts["candidates"] += 1
        if record["status_group"] == "review":
            record["triage_reasons"].append("Recruitment status needs interpretation")
        elif record["status_group"] == "historical":
            record["triage_reasons"].append(
                "Historical recruitment status is outside the Ongoing studies view"
            )
        if decision and decision["decision"] == "exclude":
            counts["manually_excluded"] += 1
            continue
        manually_included = bool(decision and decision["decision"] == "include")
        allowed_by_terms = record["triage"] == "high_specificity_candidate"
        allowed_by_quality_gate = validated and allowed_by_terms
        # Manual decisions resolve relevance questions, but must not bypass
        # snapshot validation or put non-ongoing records on this page.
        allowed_by_status = record["status_group"] == "ongoing"
        if validated and allowed_by_status and (manually_included or allowed_by_quality_gate):
            approved.append(public_record(record, decision))
            counts["approved"] += 1
            continue
        counts["pending_review"] += 1
        review_rows.append({
            "primary_id": record["primary_id"],
            "registry": record["registry"],
            "title": record["title"],
            "status_raw": record["status_raw"],
            "conditions": " | ".join(record["conditions"]),
            "interventions": " | ".join(record["interventions"]),
            "countries": " | ".join(record["countries"]),
            "triage": record["triage"],
            "reasons": " | ".join(record["triage_reasons"]),
            "decision": decision["decision"] if decision else "",
            "reviewed_on": decision["reviewed_on"] if decision else "",
            "note": decision["note"] if decision else "",
        })

    report = {
        "processed_records": len(records),
        "candidate_records": counts["candidates"],
        "approved_records": counts["approved"],
        "pending_review": counts["pending_review"],
        "manually_excluded": counts["manually_excluded"],
        "not_candidates": counts["not_candidates"],
        "quality_gate_passed": validated,
    }
    payload = {
        "schema_version": 1,
        "source": "WHO International Clinical Trials Registry Platform (ICTRP) Search Portal",
        "source_url": ICTRP_URL,
        "snapshot_status": (
            "ready" if validated else "awaiting_validation" if raw_records else "awaiting_export"
        ),
        "retrieved_on": effective_metadata.get("retrieved_on"),
        "data_processed_by_ictrp_on": effective_metadata.get("data_processed_by_ictrp_on"),
        "registry_import_dates": effective_metadata["registry_import_dates"],
        "quality_review": metadata.get("quality_review") or {},
        "counts": report,
        "records": approved,
    }
    return payload, review_rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "primary_id", "registry", "title", "status_raw", "conditions",
        "interventions", "countries", "triage", "reasons", "decision",
        "reviewed_on", "note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
        csv_files = sorted(args.raw_dir.glob("*.csv"))
        if csv_files and not valid_iso_date(metadata.get("retrieved_on")):
            raise ValueError("snapshot metadata needs retrieved_on in YYYY-MM-DD format")
        import_dates = metadata.get("registry_import_dates") or {}
        has_import_date = any(valid_iso_date(value) for value in import_dates.values())
        if csv_files and not (
            valid_iso_date(metadata.get("data_processed_by_ictrp_on")) or has_import_date
        ):
            raise ValueError(
                "record the ICTRP processing date or at least one provider import date in the snapshot metadata"
            )
        raw_records = [row for path in csv_files for row in read_csv_file(path)]
        if csv_files:
            metadata["included_source_files"] = [path.name for path in csv_files]
        decisions = load_decisions(args.decisions)
        payload, review_rows = process_records(raw_records, metadata, decisions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_csv(PROCESSED / "review-queue.csv", review_rows)
        (PROCESSED / "qa-report.json").write_text(
            json.dumps(payload["counts"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload["counts"], sort_keys=True))
        if payload["snapshot_status"] != "ready":
            print(
                "Public records remain empty until the 50-record sample review is marked passed.",
                file=sys.stderr,
            )
        return 0
    except (OSError, json.JSONDecodeError, csv.Error, ValueError) as exc:
        print(f"ICTRP processing stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
