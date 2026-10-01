# Ongoing studies: monthly update

Use this guide on the first day of each month. The goal is both to refresh the searchable database and to test whether broader collection from the original registries is practical. Do not treat the current 489-record snapshot as a complete census.

## Start the task

In a new conversation, ask:

> Päivitä pbm.science-sivuston Ongoing studies -tietokanta kuukausiohjeen mukaan. Vertaa alkuperäisrekistereitä WHO ICTRP -hakuun, tee uudet haut suoraan rekistereissä, päivitä aiempien tietueiden statukset lähteistä, ja raportoi myös laajemman aineiston kattavuus sekä lataamisen, käyttöehtojen ja päivitystyön esteet. Tee kaikki itse minkä pystyt. Pyydä minulta vain täsmälliset lataukset tai selainhaut, joita et pysty tekemään.

The assistant should read this guide, the previous snapshot, `search-strategy.json`, `snapshot-metadata.json`, the source-feasibility notes, and the current site code before collecting data.

## Collection each month

1. Record the local retrieval date, exact query, source, URL, export format, and any access or reuse restriction.
2. Search the five largest sources from the current snapshot directly: ClinicalTrials.gov, ReBEC, CTRI, IRCT, and ChiCTR. Use each registry's own search and export/API where available. Save a raw copy of every export unchanged. Do not include personal contact fields in the public database.
3. Run the three documented high-recall ICTRP searches as a comparison and backstop. Identify records found in ICTRP but not in a direct source search, and direct-source records absent from the ICTRP export. Keep both ID-level matches and unresolved potential duplicates.
4. Search the remaining providers in `registry-coverage.csv` in priority order. For a registry without a usable API or bulk export, record what was searched and ask the user for the smallest useful export, result list, or specific browser action. Do not imply that a registry was searched if it was only present in ICTRP.
5. For every continuing candidate, retrieve the current source record and record its reported status and last-updated date. Do not assume that the ICTRP status is current. A missing result is not evidence that a study is complete.
6. Keep recruitment status distinct from overall study status. Keep last enrollment, primary completion, study completion, and results-posted dates in separate fields.
7. Deduplicate only by confirmed cross-registry identifiers or a documented record link. Similar titles alone are a review lead, not a merge rule.
8. Document search changes and manually review a fresh stratified sample if the strategy or source mix changes. A sample audit does not certify every record.
9. Run the processor to create the plaintext snapshot under `data/ictrp/private/`, then set `PBM_STUDIES_DATA_KEY` from the password manager in the local shell without echoing it and run `node scripts/encrypt_studies_snapshot.mjs`. Commit only the encrypted `dist/studies/ongoing-studies.json`; never commit the private directory, raw exports, review queue, or key. Update the page's retrieval metadata, `registry-coverage.csv`, and this month's change log. Run the processor, encryption, and all tests; inspect the private plaintext for contact fields before encryption.

## Search strategy

Use the exact ICTRP searches in `search-strategy.json` as the recurring baseline. In original registries, test their own search syntax with at least: photobiomodulation, photobiostimulation, low-level laser therapy, low-level light therapy, LLLT, laser phototherapy, low-intensity laser, low-power laser, LILT, cold laser, red light therapy, near-infrared light, LED therapy, and common spelling variants. Search terms are discovery tools; screen the actual intervention to distinguish therapeutic PBM from photodynamic, diagnostic, surgical, ablative, or thermal uses.

## Publishable pilot boundary

The current site snapshot contains 489 records reported as recruiting in the 1 October 2026 ICTRP exports. It is an incomplete keyword-based pilot from 12 provider registries, not 489 individually confirmed ongoing studies. The 50-record audit is reported on the page. The ICTRP processing date was not present in the supplied export, so provider import dates and the retrieval date are shown separately; do not invent an ICTRP processing date. Refresh statuses from original sources before calling them current.

The page must remain noindex and password protected. Store `PBM_STUDIES_PASSWORD` and `PBM_STUDIES_DATA_KEY` as Cloudflare Worker secrets (Workers & Pages → `pbm-science` → Settings → Variables and Secrets), outside GitHub. The random 256-bit data key encrypts the JSON with AES-GCM, so the public repository contains only ciphertext; the Worker decrypts it only after verifying the session. `wrangler.jsonc` runs the Worker before assets only on `/studies` and `/studies/*`. Never place either secret, a reversible password hash, plaintext snapshot, or session tokens in the repository, build logs, or client JavaScript.

## Monthly close-out

Report the count of unique registry records separately from the estimated count of unique studies. Give counts for new records, status changes, duplicates, excluded records, unresolved records, and source coverage. Explain what the direct searches added compared with ICTRP. List only concrete user tasks, each with a direct URL, exact search, what to click, and the requested download format. Preserve the last successful source snapshot when a source is temporarily inaccessible.
