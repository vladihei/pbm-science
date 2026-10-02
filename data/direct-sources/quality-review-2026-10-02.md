# Direct-source quality review — 2 October 2026

## Method

The review used 50 records from the saved ClinicalTrials.gov API v2 snapshot. The deterministic sample was stratified across the three user-supplied searches: 20 records found first by the explicit PBM/photobiostimulation query, 20 found only by the low-level laser/light query, and 10 found only by the red/NIR/LED query. Records were assigned once, with earlier queries taking priority when searches overlapped.

An AI-assisted field-level review compared each source title, intervention, condition, summary, original reported status, and the normalized status group. This is a documented screening audit, not an estimate of the full dataset's accuracy and not an independent check of the current status on each registry page.

## Results

- Scope: 39 records were judged in scope, 8 out of scope, and 3 unresolved. Unresolved records remain held.
- Search-stratum observations: 18/20 in scope for the first query; 18/20 in scope and 1 unresolved for the second-only query; 3/10 in scope for the third-only red/NIR/LED query. The last query is broad and produced more measurement, imaging, and non-therapeutic light hits; those require conservative screening.
- Status groups in the sample: 15 records had an ongoing source status, 20 had a historical status, and 15 reported `UNKNOWN`. The 35 known source statuses mapped consistently; all 15 unknown-status records remain out of the ongoing view until checked.
- Seventeen distinct sample rows had at least one hold for scope or status; one record was both scope-unresolved and `UNKNOWN`.

The status shown on a registry can lag behind the actual study. The review preserves what the source reported; it does not treat a monthly snapshot as a real-time status check. “Recruitment completed” is mapped to review rather than historical because completion of recruitment alone does not establish completion of the study.

## Publication state

The 50-record screening audit is complete, but the public snapshot remains empty. ClinicalTrials.gov reuse review is still pending because source processing-date and freshness requirements have not been resolved for this monthly workflow; other registry reuse terms also remain pending. This quality review does not grant redistribution permission.
