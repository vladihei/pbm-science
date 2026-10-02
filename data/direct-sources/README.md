# Ongoing studies: direct-registry pilot

This is now the canonical source workflow for the password-protected `/studies/` page. The page is intended to use records retrieved from their original registries. WHO ICTRP exports are retained only as a historical search-coverage comparison; they are not the source of records in the site's snapshot.

## What is implemented

- `scripts/fetch_clinicaltrials_gov.py` runs the three search expressions in `search-strategy.json` against the official ClinicalTrials.gov API v2. It follows every `nextPageToken`, saves unchanged source responses, and writes a manifest with request dates, row counts, and hashes.
- Raw API responses are ignored under `raw/`. They contain more fields than the site needs, including contact and location details. Do not commit them or expose them in build logs.
- `scripts/process_direct_sources.py` normalizes direct API results and records entered from source-specific exports. It deduplicates only by registry + exact record identifier, preserves the source-reported status, and copies a narrow whitelist to the output. Summary text, contact fields, phone numbers, and email addresses are not published.
- Publication is held until both a source-specific 50-record review and reuse review pass. The former ICTRP review does not satisfy the new source-mix gate.
- An approved snapshot is encrypted at `dist/studies/ongoing-studies.json`. While source reuse remains pending, no study records are included in the website build; secrets stay in Cloudflare, not GitHub.

## Status on 2 October 2026

ClinicalTrials.gov returned 2,943 rows over the three searches before deduplication. The fetch completed through all API pages. ReBEC's advanced-search page loaded and exposed CSV/Excel export controls, but the search API called by that page returned an error and showed no results in this environment. ChiCTR's individual record page loaded, while its search page blocked this browser at its WAF. Neither result proves that a human using an ordinary browser cannot complete the search. Exact next steps and the evidence are in `source-feasibility-2026-10-02.md`.

The broader source check found that ANZCTR requires continuously current data, its own processing date and change notes, and restricts unauthorised software collection. ISRCTN offers CSV/XML access but its terms need clarification before building a database from records. DRKS has a dated multi-record export, with download terms still to review. CTIS needs a separate search because the old ICTRP files contain no CTIS records. These are coverage priorities, not completed searches.

No source's reuse rights are marked cleared yet. The site snapshot remains empty until the direct-source audit and per-source reuse review are completed. Password protection does not itself grant permission to redistribute registry metadata.

## Important monthly files

- `MONTHLY-UPDATE.md`: repeatable first-of-month steps and the prompt to reuse.
- `search-strategy.json`: exact queries and scope rules.
- `registry-coverage.csv`: direct-source feasibility and next-action tracker.
- `snapshot-metadata.json`: the publication gate and current retrieval date.
- `manual-records-template.csv`: minimal, contact-free fields for a manually exported source that has no usable API.
- `review-decisions.csv`: explicit per-record scope decisions.
