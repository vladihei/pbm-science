# Ongoing studies: direct-registry pilot

This is now the canonical source workflow for the password-protected `/studies/` page. The page is intended to use records retrieved from their original registries. WHO ICTRP exports are retained only as a historical search-coverage comparison; they are not the source of records in the site's snapshot.

## What is implemented

- `scripts/fetch_clinicaltrials_gov.py` runs the three search expressions in `search-strategy.json` against the official ClinicalTrials.gov API v2. It follows every `nextPageToken`, saves unchanged source responses, and writes a manifest with request dates, row counts, and hashes.
- Raw API responses are ignored under `raw/`. They contain more fields than the site needs, including contact and location details. Do not commit them or expose them in build logs.
- `scripts/process_direct_sources.py` normalizes direct API results and records entered from source-specific exports. It deduplicates only by registry + exact record identifier, preserves the source-reported status, and copies a narrow whitelist to the output. Summary text, contact fields, phone numbers, and email addresses are not published.
- Publication is held until both a source-specific 50-record review and reuse review pass. The former ICTRP review does not satisfy the new source-mix gate.
- The scheduled workflow creates an AES-256-GCM encrypted snapshot at `dist/studies/ongoing-studies.json`. Plaintext exports and the encryption key remain outside Git; the key must be configured separately in GitHub Actions and the Cloudflare Worker.

## Status on 2 October 2026

ClinicalTrials.gov returned 2,943 rows over the three searches before deduplication. The fetch completed through all API pages. The official `/api/v2/version` endpoint returned a dataset processing timestamp, which the pipeline now captures before and after retrieval and the page displays separately from our retrieval date. The local candidate set has 216 explicit-term records with an ongoing source-reported status after the current screen. The password-protected website payload is generated only by the workflow after the repository secret is configured; no plaintext source export or private review file is committed. This is one registry's coverage, not a worldwide census. ReBEC's `/busca` page is used only to discover candidate IDs; the earlier `/api2/` advanced-search request returned 404. ChiCTR's individual record page loaded, while its search page blocked this browser at its WAF. Exact next steps and the evidence are in `source-feasibility-2026-10-02.md`.

The broader source check found that ANZCTR requires continuously current data, its own processing date and change notes, and restricts unauthorised software collection. ISRCTN offers CSV/XML access but its terms need clarification before building a database from records. DRKS has a dated multi-record export, with download terms still to review. CTIS needs a separate search because the old ICTRP files contain no CTIS records. These are coverage priorities, not completed searches.

The pilot is limited to selected ClinicalTrials.gov structured fields, with source attribution, the official source data timestamp, retrieval date, a description of the queries and transformations, original-record links, and an output whitelist that omits contact details and full descriptions. The daily workflow is intended to keep the snapshot close to the current API dataset; monitor the source terms and pause publication if that cadence or the required disclosures cannot be maintained. ReBEC, ChiCTR, and every other registry remain excluded until their own reuse basis and complete retrieval route are confirmed. Password protection does not itself grant permission to redistribute registry metadata.

## Important monthly files

- `MONTHLY-UPDATE.md`: repeatable first-of-month steps and the prompt to reuse.
- `search-strategy.json`: exact queries and scope rules.
- `registry-coverage.csv`: direct-source feasibility and next-action tracker.
- `snapshot-metadata.json`: the publication gate and current retrieval date.
- `manual-records-template.csv`: minimal, contact-free fields for a manually exported source that has no usable API.
- `review-decisions.csv`: explicit per-record scope decisions.
