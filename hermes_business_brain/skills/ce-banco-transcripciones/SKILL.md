---
name: ce-banco-transcripciones
description: "Preserve and drive the complete cycle of a new conversation/transcript or continuation by parts, up to authorized integration; don't ingest ordinary documents for their length."
---

# ce-banco-transcripciones

Read the [common contract](../ce-banco-transcripciones/references/contrato-comun.md) for states, permissions, context and availability.

For a new delivery, run the [complete default flow](references/flujo-predeterminado.md), recovering the instance's private configuration and authorizations. Custody is the first step: continue analysis of all matters, background, architecture and authorized integration; don't close with only a summary or candidates. A specific instruction of the delivery may limit the scope.

- **Trigger:** file, pasted text, link or batch presented as conversation; continuation of pending parts. Detect monologue without inventing a meeting.
- **Inputs:** exact received representation, locator/occurrence, business, account if known, purpose, sensitivity, permission evidence and declaration of expected parts. Unknown identity is recorded, not guessed.
- **Outputs:** immutable original, catalog/versioning record, byte-level dedupe separate from identity, independent states, extraction/segmentation jobs or missing ones. For parts, keep each delivery and a derived assembly manifest.
- **Errors:** `INPUT_EMPTY`, `UNSAFE_PATH`, `IDENTITY_AMBIGUOUS`, `PART_MISSING`, `HASH_MISMATCH`, `PURPOSE_DENIED`; partial doesn't destroy what was already received.
- **Gate:** copy hash equals input, idempotent re-import, two meetings with identical text not accidentally fused; interruption and resumption without overwriting originals. Test with synthetic fixtures and manifest evidence.

## Execution

Before interpreting, distinguish an ordinary request from material presented to preserve/analyze. Length or the presence of a colon is only a signal, never a conclusive detector. Long text without turns may be a monologue; record the received text if meeting evidence is missing. Don't invent speakers, date, account nor factual title. A long question about the system doesn't enter the corpus because it is long.

In paste-by-parts, keep each exact delivery with declared ordinal, reception order, hash and locator. Detect duplicates, gaps, version change and declared closure; without all expected parts or without closure it stays partial/unknown. A correction creates a version, doesn't replace bytes. Assembly is derived with a map to each part; don't insert separators as if they were original text. If you only received a link, you haven't preserved the content yet. For MeetGeek use [ce-extraer-meetgeek](../ce-extraer-meetgeek/SKILL.md); then [ce-analizar-transcripcion](../ce-analizar-transcripcion/SKILL.md).
