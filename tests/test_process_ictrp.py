import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "process_ictrp.py"
SPEC = importlib.util.spec_from_file_location("process_ictrp", SCRIPT)
processor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(processor)


def record(primary_id, title, status, triage="high_specificity_candidate", **extra):
    base = {
        "primary_id": primary_id,
        "registry": "ClinicalTrials.gov",
        "secondary_ids": [],
        "title": title,
        "status_raw": status,
        "status": processor.status_group(status)[0],
        "status_group": processor.status_group(status)[1],
        "conditions": [],
        "conditions_raw": "",
        "interventions": [],
        "interventions_raw": "",
        "countries": [],
        "study_type": None,
        "phase": None,
        "target_sample_size": None,
        "registration_date": None,
        "start_date": None,
        "last_enrollment_date": None,
        "primary_completion_date": None,
        "study_completion_date": None,
        "estimated_completion_date": None,
        "results_completed_date": None,
        "sponsor": None,
        "original_url": None,
        "ictrp_group_id": None,
        "data_processed_by_ictrp_on": None,
        "summary_raw": "",
        "source_file": "q1-core.csv",
        "ictrp_url": "https://trialsearch.who.int/Trial2.aspx?TrialID=" + primary_id,
        "triage": triage,
        "triage_reasons": ["fixture"],
    }
    base.update(extra)
    return base


class ProcessorTests(unittest.TestCase):
    def test_status_terms_do_not_treat_ambiguous_not_recruiting_as_ongoing(self):
        self.assertEqual(processor.status_group("Recruiting"), ("recruiting", "ongoing"))
        self.assertEqual(processor.status_group("Not recruiting"), ("status_unclear", "review"))
        self.assertEqual(processor.status_group("Completed"), ("completed", "historical"))

    def test_identifier_placeholders_are_not_shown_as_secondary_ids(self):
        self.assertEqual(processor.split_values("NIL; RBR-123; None", comma=True), ["RBR-123"])

    def test_merge_uses_identifiers_and_not_title_similarity(self):
        a = record("NCT00000001", "Similar title", "Recruiting")
        b = record("NCT00000001", "Similar title", "Recruiting", source_file="q2-therapy.csv",
                   secondary_ids=["RBR-123"])
        c = record("NCT00000002", "Similar title", "Recruiting")
        merged = processor.merge_records([a, b, c])
        self.assertEqual(len(merged), 2)
        first = next(item for item in merged if item["primary_id"] == "NCT00000001")
        self.assertEqual(first["secondary_ids"], ["RBR-123"])
        self.assertEqual(len(first["source_files"]), 2)

    def test_strong_candidates_stay_private_until_quality_sample_passes(self):
        candidate = record("NCT00000003", "Photobiomodulation for wound healing", "Recruiting")
        unvalidated = {"quality_review": {"status": "not_started", "checked_records": 0}}
        payload, queue = processor.process_records([candidate], unvalidated, {})
        self.assertEqual(payload["snapshot_status"], "awaiting_validation")
        self.assertEqual(payload["records"], [])
        self.assertEqual(len(queue), 1)

    def test_validated_core_candidate_is_published_but_ambiguous_status_is_not(self):
        good = record("NCT00000004", "Low-level laser therapy", "Recruiting")
        unclear = record("NCT00000005", "Photobiomodulation pilot", "Not recruiting")
        metadata = {
            "retrieved_on": "2026-10-01",
            "data_processed_by_ictrp_on": "2026-09-21",
            "quality_review": {"status": "passed", "checked_records": 50, "reviewed_on": "2026-10-01"},
        }
        payload, queue = processor.process_records([good, unclear], metadata, {})
        self.assertEqual(payload["snapshot_status"], "ready")
        self.assertEqual([item["primary_id"] for item in payload["records"]], ["NCT00000004"])
        self.assertEqual([item["primary_id"] for item in queue], ["NCT00000005"])

    def test_manual_include_cannot_bypass_snapshot_quality_gate(self):
        candidate = record("NCT00000009", "Photobiomodulation for wound healing", "Recruiting")
        decisions = {
            "nct00000009": {"decision": "include", "reviewed_on": "2026-10-01", "note": "Relevant"}
        }
        payload, queue = processor.process_records(
            [candidate], {"quality_review": {"status": "not_started"}}, decisions
        )
        self.assertEqual(payload["records"], [])
        self.assertEqual([item["primary_id"] for item in queue], ["NCT00000009"])

    def test_query_hits_without_exported_terms_are_sent_to_manual_review(self):
        candidate = record(
            "NCT00000011", "Study of recovery outcomes", "Recruiting",
            source_file="2026-10-01_q1-core.csv",
        )
        triage, reasons = processor.triage_text(candidate)
        self.assertEqual(triage, "manual_review")
        self.assertIn("synonym-expanded match", reasons[0])

    def test_q3_only_records_stay_manual_even_when_they_contain_pbm_terms(self):
        candidate = record("NCT00000017", "Photobiomodulation for pain", "Recruiting",
                           source_file="2026-10-01_q3-descriptors.csv")
        triage, reasons = processor.triage_text(candidate)
        self.assertEqual(triage, "manual_review")
        self.assertIn("broad q3", reasons[0])

    def test_historical_record_stays_out_of_ongoing_view_even_when_included(self):
        candidate = record("NCT00000010", "Photobiomodulation for wound healing", "Completed")
        metadata = {
            "retrieved_on": "2026-10-01",
            "data_processed_by_ictrp_on": "2026-09-21",
            "quality_review": {"status": "passed", "checked_records": 50, "reviewed_on": "2026-10-01"},
        }
        decisions = {
            "nct00000010": {"decision": "include", "reviewed_on": "2026-10-01", "note": "Relevant"}
        }
        payload, queue = processor.process_records([candidate], metadata, decisions)
        self.assertEqual(payload["snapshot_status"], "ready")
        self.assertEqual(payload["records"], [])
        self.assertIn("outside the Ongoing studies view", queue[0]["reasons"])

    def test_broad_term_and_photodynamic_conflict_need_manual_decisions(self):
        broad = record("NCT00000006", "Red light therapy", "Recruiting", triage="manual_review")
        mixed = record("NCT00000007", "Photobiomodulation and photodynamic therapy", "Recruiting",
                       triage="manual_review")
        metadata = {
            "quality_review": {"status": "passed", "checked_records": 60, "reviewed_on": "2026-10-01"}
        }
        payload, queue = processor.process_records([broad, mixed], metadata, {})
        self.assertEqual(payload["records"], [])
        self.assertEqual(len(queue), 2)

    def test_blue_light_and_nd_yag_candidates_need_scope_review(self):
        blue = record("NCT00000014", "Photobiomodulation with 467 nm blue light", "Recruiting")
        laser = record("NCT00000015", "Photobiomodulation using Nd:YAG", "Recruiting")
        for candidate in (blue, laser):
            triage, reasons = processor.triage_text(candidate)
            self.assertEqual(triage, "manual_review")
            self.assertIn("scope review", " ".join(reasons))

    def test_excimer_and_implausible_10_nm_wavelength_need_scope_review(self):
        excimer = record("NCT00000016", "Low Level Laser Versus Polarized Light", "Recruiting",
                         conditions_raw="Acne vulgaris",
                         interventions_raw="Device: Excimer laser; Device: Bioptron")
        impossible = record("IRCT0000000001", "Laser for jaw pain", "Recruiting",
                            interventions_raw="laser specifications: 10nm wavelength")
        for candidate in (excimer, impossible):
            triage, reasons = processor.triage_text(candidate)
            self.assertEqual(triage, "manual_review")

    def test_quality_gate_requires_retrieval_and_ictrp_source_dates(self):
        metadata = {
            "retrieved_on": "2026-10-01",
            "quality_review": {"status": "passed", "checked_records": 50, "reviewed_on": "2026-10-01"},
        }
        self.assertFalse(processor.quality_review_passed(metadata))
        metadata["registry_import_dates"] = {"ClinicalTrials.gov": "2026-09-21"}
        self.assertTrue(processor.quality_review_passed(metadata))
        self.assertFalse(processor.quality_review_passed(metadata, ["ClinicalTrials.gov", "CTIS"]))
        metadata["registry_import_dates"]["CTIS"] = "2026-09-21"
        self.assertTrue(processor.quality_review_passed(metadata, ["ClinicalTrials.gov", "CTIS"]))

    def test_registry_normalization_uses_provider_map_and_rejects_unknown_values(self):
        self.assertEqual(processor.normalize_registry("ClinicalTrials.gov"), "ClinicalTrials.gov")
        self.assertEqual(processor.normalize_registry("CRIS"), "Clinical Research Information Service - Republic of Korea")
        self.assertIsNone(processor.normalize_registry("10/01/2026 19:10:44"))

    def test_required_csv_headers_are_mapped_without_discarding_status(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "q1.csv"
            path.write_text(
                "Main ID,Public Title,Recruitment status,Condition,Intervention,Countries\n"
                "NCT00000008,Photobiomodulation wound trial,Recruiting,Leg ulcer,LLLT,Sweden\n",
                encoding="utf-8",
            )
            rows = processor.read_csv_file(path)
        self.assertEqual(rows[0]["primary_id"], "NCT00000008")
        self.assertEqual(rows[0]["conditions"], ["Leg ulcer"])
        self.assertEqual(rows[0]["countries"], ["Sweden"])
        self.assertEqual(rows[0]["status"], "recruiting")

    def test_actual_ictrp_export_headers_and_scientific_title_are_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "2026-10-01_q1-core.csv"
            path.write_text(
                "TrialID,Last Refreshed on,Public title,Scientific title,Primary sponsor,"
                "Date registration,Source Register,web address,Recruitment Status,Target size,"
                "Date enrollement,Study type,Phase,Countries,Condition,Intervention\n"
                "NCT00000012,21 September 2026,General light study,"
                "Photobiomodulation for pain,University,13/09/2026,ClinicalTrials.gov,"
                "https://clinicaltrials.gov/study/NCT00000012,Recruiting,45,01/05/2027,"
                "Interventional,N/A,US,Condition,LED treatment\n",
                encoding="utf-8",
            )
            rows = processor.read_csv_file(path)
        self.assertEqual(rows[0]["primary_id"], "NCT00000012")
        self.assertEqual(rows[0]["registry"], "ClinicalTrials.gov")
        self.assertEqual(rows[0]["status"], "recruiting")
        self.assertEqual(rows[0]["registration_date"], "2026-09-13")
        self.assertEqual(rows[0]["start_date"], "2027-05-01")
        self.assertEqual(rows[0]["last_refreshed_on"], "2026-09-21")
        self.assertEqual(rows[0]["target_sample_size"], 45)
        self.assertEqual(rows[0]["original_url"], "https://clinicaltrials.gov/study/NCT00000012")
        self.assertEqual(rows[0]["triage"], "high_specificity_candidate")

    def test_last_enrollment_is_not_misreported_as_study_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last-enrollment.csv"
            path.write_text(
                "TrialID,Public title,Recruitment Status,Source Register,Date of last enrollment,"
                "Primary completion date,Study completion date,Estimated completion date\n"
                "NCT00000018,Photobiomodulation trial,Recruiting,ClinicalTrials.gov,"
                "2026-03-01,2026-06-01,2026-12-01,2027-01-01\n",
                encoding="utf-8",
            )
            row = processor.read_csv_file(path)[0]
        self.assertEqual(row["last_enrollment_date"], "2026-03-01")
        self.assertEqual(row["primary_completion_date"], "2026-06-01")
        self.assertEqual(row["study_completion_date"], "2026-12-01")
        self.assertEqual(row["estimated_completion_date"], "2027-01-01")

    def test_japan_and_netherlands_provider_labels_are_not_misstated(self):
        self.assertEqual(processor.normalize_registry("JPRN"), "Japan Primary Registries Network (JPRN/jRCT)")
        self.assertEqual(processor.normalize_registry("NL-OMON"), "Overview of Medical Research in the Netherlands (OMON)")

    def test_export_row_with_unheaded_values_is_held_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "q1-core.csv"
            path.write_text(
                "TrialID,Public title,Recruitment Status,Source Register,Condition,Intervention\n"
                "NCT00000013,Photobiomodulation for pain,Recruiting,ClinicalTrials.gov,"
                "Pain,Light treatment,unmapped\n",
                encoding="utf-8",
            )
            rows = processor.read_csv_file(path)
        self.assertEqual(rows[0]["triage"], "manual_review")
        self.assertIn("outside the export headers", rows[0]["triage_reasons"][-1])


if __name__ == "__main__":
    unittest.main()
