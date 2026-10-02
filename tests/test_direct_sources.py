import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_clinicaltrials_gov as fetcher
import make_direct_review_sample as sample
import process_direct_sources as processor


def ctg_record(primary_id="NCT00000001", title="Photobiomodulation study", status="RECRUITING"):
    return {
        "protocolSection": {
            "identificationModule": {
                "nctId": primary_id,
                "briefTitle": title,
                "officialTitle": "A photobiomodulation study",
            },
            "statusModule": {
                "overallStatus": status,
                "studyFirstPostDateStruct": {"date": "2024-01-01"},
                "studyLastUpdatePostDateStruct": {"date": "2026-09-01"},
            },
            "designModule": {"studyType": "Interventional"},
            "conditionsModule": {"conditions": ["Pain"]},
            "armsInterventionsModule": {
                "interventions": [{"type": "DEVICE", "name": "Photobiomodulation"}]
            },
            "contactsLocationsModule": {"locations": [{"country": "Finland", "city": "Helsinki"}]},
            "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Example University"}},
            "descriptionModule": {"briefSummary": "Photobiomodulation for pain."},
        }
    }


class DirectSourceTests(unittest.TestCase):
    def test_status_mapping_keeps_distinct_registry_statuses_and_groups(self):
        self.assertEqual(processor.status_group("Recruiting"), ("recruiting", "ongoing"))
        self.assertEqual(processor.status_group("Active, not recruiting"), ("active_not_recruiting", "ongoing"))
        self.assertEqual(processor.status_group("Completed"), ("completed", "historical"))
        self.assertEqual(processor.status_group("Recruitment completed"), ("recruitment_completed", "review"))
        self.assertEqual(processor.status_group("Unknown"), ("status_unknown", "review"))

    def test_public_record_is_a_whitelist_and_omits_contact_and_summary_fields(self):
        record = processor.normalize_ctg(ctg_record(), fetcher.SEARCH_EXPRESSIONS[0], "2026-10-02")
        record["contact_email"] = "private@example.test"
        public = processor.public_record(record)
        self.assertEqual(public["primary_id"], "NCT00000001")
        self.assertNotIn("summary_for_review", public)
        self.assertNotIn("contact_email", public)
        self.assertNotIn("city", json.dumps(public))

    def test_pending_reuse_gate_holds_all_records_but_counts_source_status_separately(self):
        record = processor.normalize_ctg(ctg_record(), fetcher.SEARCH_EXPRESSIONS[0], "2026-10-02")
        metadata = {
            "retrieved_on": "2026-10-02",
            "quality_review": {"status": "passed", "checked_records": 50, "reviewed_on": "2026-10-02"},
            "reuse_review": {"status": "pending", "distribution_permitted": False, "cleared_registries": []},
        }
        payload, _ = processor.process([record], metadata, {})
        self.assertEqual(payload["snapshot_status"], "awaiting_source_review")
        self.assertEqual(payload["records"], [])
        self.assertEqual(payload["sources"][0]["ongoing_status_count"], 1)
        self.assertEqual(payload["sources"][0]["search_hit_count"], 1)
        self.assertNotIn("record_count", payload["sources"][0])

    def test_cleared_gate_publishes_only_whitelisted_ongoing_record(self):
        record = processor.normalize_ctg(ctg_record(), fetcher.SEARCH_EXPRESSIONS[0], "2026-10-02")
        record["contact_email"] = "private@example.test"
        metadata = {
            "retrieved_on": "2026-10-02",
            "quality_review": {"status": "passed", "checked_records": 50, "reviewed_on": "2026-10-02"},
            "reuse_review": {
                "status": "cleared", "distribution_permitted": True,
                "cleared_registries": ["ClinicalTrials.gov"],
            },
        }
        payload, _ = processor.process([record], metadata, {})
        self.assertEqual(payload["snapshot_status"], "ready")
        self.assertEqual(len(payload["records"]), 1)
        self.assertNotIn("contact_email", payload["records"][0])
        self.assertNotIn("summary_for_review", payload["records"][0])

    def test_review_sample_assigns_overlaps_to_first_expression_and_is_reproducible(self):
        queries = fetcher.SEARCH_EXPRESSIONS
        records = []
        for index, query_list in enumerate(([queries[0], queries[1]], [queries[1]], [queries[2]])):
            bucket_size = (21, 21, 11)[index]
            for row_number in range(bucket_size):
                matches = list(query_list)
                records.append({
                    "primary_id": f"NCT{index * 10000000 + row_number:08d}",
                    "registry": "ClinicalTrials.gov",
                    "matched_queries": matches,
                    "triage": "high_specificity_candidate",
                    "status_group": "ongoing" if row_number % 2 else "historical",
                    "status_raw": "Recruiting" if row_number % 2 else "Completed",
                    "title": f"Test title {index}-{row_number}",
                    "conditions": [], "interventions": [], "source_url": "https://example.test/record",
                })
        first = sample.choose_sample(records, "2026-10-02")
        second = sample.choose_sample(records, "2026-10-02")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 50)
        self.assertEqual({key: sum(row["stratum"] == key for row in first) for key, _q, _n in sample.QUERY_BUCKETS}, {
            "q1_explicit_terms": 20,
            "q2_low_level_terms": 20,
            "q3_red_nir_led_terms": 10,
        })
        self.assertEqual(len({row["primary_id"] for row in first}), 50)

    def test_manifest_retains_last_reported_total_when_later_page_omits_it(self):
        responses = [
            {"studies": [{"one": 1}], "totalCount": 1, "nextPageToken": "next"},
            {"studies": [{"two": 2}]},
        ]

        class FakeResponse:
            status = 200

            def __init__(self, payload):
                self.payload = json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.payload

        def opener(_request, timeout):
            self.assertEqual(timeout, 60)
            return FakeResponse(responses.pop(0))

        with tempfile.TemporaryDirectory() as temp:
            manifest = fetcher.fetch_snapshot(
                Path(temp), "2026-10-02", queries=("test",), page_size=1,
                opener=opener, pause_seconds=0,
            )
        query = manifest["queries"][0]
        self.assertEqual(query["total_count"], 1)
        self.assertEqual(query["total_counts_observed"], [1])
        self.assertFalse(query["count_changed_during_fetch"])
        self.assertEqual(query["returned_count"], 2)

    def test_status_conflicts_across_query_snapshots_are_held_for_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = fetcher.SEARCH_EXPRESSIONS[0]
            two = fetcher.SEARCH_EXPRESSIONS[1]
            (root / "page1.json").write_text(json.dumps({"studies": [ctg_record(status="RECRUITING")]}))
            (root / "page2.json").write_text(json.dumps({"studies": [ctg_record(status="COMPLETED")]}))
            manifest = {
                "retrieved_on": "2026-10-02",
                "queries": [
                    {"query": one, "pages": [{"file": "page1.json"}]},
                    {"query": two, "pages": [{"file": "page2.json"}]},
                ],
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            records = processor.parse_ctg_snapshot(manifest_path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], "status_conflict")
        self.assertEqual(records[0]["status_group"], "review")
        self.assertTrue(records[0]["source_snapshot_conflicts"])


if __name__ == "__main__":
    unittest.main()
