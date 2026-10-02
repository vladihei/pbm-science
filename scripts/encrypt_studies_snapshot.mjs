import { readFile, writeFile } from "node:fs/promises";
import { randomBytes, webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_INPUT = path.join(ROOT, "data/direct-sources/private/ongoing-studies.json");
const DEFAULT_OUTPUT = path.join(ROOT, "dist/studies/ongoing-studies.json");
export const ENVELOPE_FORMAT = "pbm-studies-encrypted-v1";

export async function encryptSnapshot(plaintext, dataKeyHex) {
  if (typeof dataKeyHex !== "string" || !/^[a-f0-9]{64}$/i.test(dataKeyHex)) {
    throw new Error("PBM_STUDIES_DATA_KEY must be 64 hexadecimal characters");
  }
  const iv = randomBytes(12);
  const key = await webcrypto.subtle.importKey(
    "raw", Buffer.from(dataKeyHex, "hex"), { name: "AES-GCM" }, false, ["encrypt"],
  );
  const ciphertext = await webcrypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    Buffer.from(plaintext, "utf8"),
  );
  return JSON.stringify({
    format: ENVELOPE_FORMAT,
    algorithm: "AES-256-GCM",
    iv: Buffer.from(iv).toString("base64"),
    ciphertext: Buffer.from(ciphertext).toString("base64"),
  }) + "\n";
}

async function main() {
  const dataKeyHex = process.env.PBM_STUDIES_DATA_KEY;
  if (!dataKeyHex) throw new Error("Set PBM_STUDIES_DATA_KEY in the environment first");
  const input = process.argv[2] ? path.resolve(process.argv[2]) : DEFAULT_INPUT;
  const output = process.argv[3] ? path.resolve(process.argv[3]) : DEFAULT_OUTPUT;
  const plaintext = await readFile(input, "utf8");
  const snapshot = JSON.parse(plaintext);
  if (!Array.isArray(snapshot.records)) {
    throw new Error("Refusing to encrypt a snapshot without a records array");
  }
  if (snapshot.snapshot_status !== "ready" && snapshot.records.length !== 0) {
    throw new Error("Refusing to encrypt unreviewed records; only an empty preview placeholder is allowed");
  }
  await writeFile(output, await encryptSnapshot(plaintext, dataKeyHex), { encoding: "utf8", mode: 0o600 });
  console.log(JSON.stringify({ encrypted: true, records: snapshot.records.length, output: path.relative(ROOT, output) }));
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((error) => {
    console.error(`Snapshot encryption failed: ${error.message}`);
    process.exitCode = 1;
  });
}
