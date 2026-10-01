# Generated files

The processor writes `qa-report.json`, a local `review-queue.csv`, a sample-audit record, and the plaintext site snapshot under the ignored `data/ictrp/private/` directory. Run `scripts/encrypt_studies_snapshot.mjs` with `PBM_STUDIES_DATA_KEY` set to create the encrypted asset at `dist/studies/ongoing-studies.json`.

The review queue and raw exports are for curation only. They contain records that did not pass the current inclusion rules, including uncertain status and broad-search hits. Do not copy the queue or raw CSV files into the public site.

The website snapshot has passed the documented dataset-level quality gate. This does not mean every published record was manually verified. The site labels it as a pilot, displays the source dates, and links to the original registry or ICTRP record.
