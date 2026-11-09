# Area 7 - Risks and commitments

## Purpose

Identify what would genuinely hurt if it failed and which commitments are proven by documents - D07 records prioritized risks, real controls and critical dependencies, while X05/X06 keep the agreements and critical resources that deserve their own records, without substituting AI judgment for professional review.

## Open guided questions

1. Which real problem has cost you the most money, rework or reputation?
2. Which dependency would stop delivery if it failed tomorrow?
3. Which risk do you accept deliberately, and which would you never accept?
4. Which control or backup do you assume works but have never tested end to end?
5. What commitments, permits or contracts are in force right now, and where is the paper?
6. What happens if your main supplier or tool disappears this month?
7. What data would hurt if it leaked, and who can see it today?
8. What did you almost lose - a client, money, trust - and what saved it?
9. What would a lawyer or accountant need to review that you cannot judge yourself?
10. If the business stopped for a month, what would still be owed?

## Signals to capture

- Material exposures and commitments that matter today, with their documentary source.
- Risks prioritized by consequence, with reasoned probability or "not estimated".
- Real controls versus gaps; controls taken for granted but never tested.
- Suppliers, systems and resources whose loss interrupts the offer.
- Sensitive data, access, retention and restrictions.
- Continuity measures with a recovery plan and an owner.
- Items requiring a contractual or professional source instead of internal judgment.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| Risks, controls and critical dependencies | D07 | empresa, acuerdo, proveedor, recurso | A worry with no episode behind it: K3 gap, not D07 |
| A standalone agreement or obligation | X05 | acuerdo | An informal mention without the document: keep in source, mark NO VERIFICADO |
| A critical resource, system or supplier | X06 | proveedor, recurso, herramienta | Something cheaply replaceable: keep within D07/source, not X06 |
| A decision to accept, transfer or treat a risk | X07 | decision | A proposal still pending approval: brain_propose, not X07 |

## External-AI prompt

> You are interviewing the owner of a small business about what could go wrong and what they are committed to. Keep it a natural, plain-language conversation, one open-ended question at a time, and refer to the person you are interviewing as "the owner". Ask for real events, not hypotheticals: a problem that actually cost money or reputation, a dependency that almost failed. Cover: the real problems that have cost the most; what would stop delivery if it failed tomorrow; risks they accept on purpose and risks they would never accept; controls or backups they assume work but have never tested; commitments, permits and contracts currently in force and where the paperwork is; what would happen if a main supplier or tool disappeared; data that would hurt if leaked and who can see it; something they almost lost and what saved it; what a lawyer or accountant must review because they cannot judge it alone; and what would still be owed if the business stopped for a month. Keep their account as told; do not turn their memory into verified obligations or legal facts.

## K-gap hints

- **K1:** the owner's threshold - which risks they consciously accept and which they would never accept.
- **K2:** the actual contract, permit, invoice or policy document; the recoverable paper behind each commitment.
- **K3:** whether a control would actually work - it has never been tested end to end.
- **K4:** risks the owner has explicitly decided not to manage.
