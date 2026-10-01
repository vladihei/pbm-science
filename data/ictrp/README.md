# Ongoing studies data

This directory stores the recurring search method and the private review inputs for the password-protected Ongoing studies pilot. Follow [MONTHLY-UPDATE.md](MONTHLY-UPDATE.md) at the start of each month. The processor writes the plaintext snapshot to the ignored `private/` directory; `scripts/encrypt_studies_snapshot.mjs` encrypts it to `dist/studies/ongoing-studies.json` before it is committed.

## Current snapshot

The 1 October 2026 pilot was built from three manually exported WHO ICTRP searches. The exports contained 2,428 rows and 2,235 distinct registry IDs. Processing kept 489 records whose source status was Recruiting and whose keyword rule passed the initial sample audit; 1,746 additional records remain outside the page pending review of relevance or status. Distinct registry IDs are not necessarily distinct studies across registries.

The snapshot includes 12 provider registries. Their source import dates are shown on the page. The ICTRP processing date was not included in the supplied export and is not inferred from those provider dates. The 50-record stratified audit found 37 in scope, 9 unresolved, and 4 out of scope. This is not a record-by-record verification or a statistical estimate of precision. The page calls the entries pilot records and tells readers to check the linked registry.

## Collection and scope

The ICTRP query expressions are in `search-strategy.json`; preserve the exact phrase, source, export, and retrieval date each month. The current snapshot focuses on human therapeutic PBM interventions, with a red and near-infrared emphasis. Ambiguous light types, broad descriptor-only hits, mixed treatments, unclear statuses, and malformed rows remain in a local review queue. Do not treat “Not Recruiting” as study completion.

Use the individual source pages, APIs, and export controls as described in `MONTHLY-UPDATE.md` and `registry-coverage.csv`. The ICTRP results provide a broad comparison source; presence in that aggregate is not evidence that every original registry has been searched directly. The source-specific pilot findings and blockers are in `source-feasibility-2026-10-01.md`.

## Privacy, reuse, and publishing

ICTRP input CSV files contain public and scientific contact fields. Keep raw exports private and out of the published build. The processor publishes only selected registry metadata and URLs; inspect the generated JSON before deployment. Do not publish contact names, emails, telephone numbers, or postal addresses.

Attribute WHO ICTRP and its source registries; display retrieval and source dates accurately; do not claim ownership of registry records, use WHO branding, or use ICTRP-derived data for marketing, promotional, or commercial purposes. WHO's terms also require the ICTRP processing date and current data for distribution. The current export omitted that date, so the snapshot is private-test-only and not cleared for wider distribution. Source-specific reuse terms must be checked before incorporating direct-source records. A password does not replace licensing or attribution requirements.

The page's authentication uses a Cloudflare Workers secret named `PBM_STUDIES_PASSWORD`; a separate random 256-bit `PBM_STUDIES_DATA_KEY` encrypts the static snapshot. Keep both in a password manager and Cloudflare, never Git. If the data key is rotated, re-encrypt the snapshot before deployment. Never commit either secret, a password hash, plaintext exports, contact fields, or session tokens.
