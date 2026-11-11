# Area 3 - Offer and commercial system

## Purpose

Establish what can be contracted today - scope, exclusions, price rules and validity - and the real commercial path from opportunity to agreement, so D03 reflects the true portfolio and D/X records stay purchasable facts rather than templates.

## Open guided questions

1. What can a customer actually buy from you right now, and what would they get for their money?
2. Walk me through the last three proposals you sent. What did you quote, what did you leave out, and which ones closed?
3. What is excluded from what you sell - what would a customer wrongly assume is included?
4. How do you build a price when the work does not match a standard offer?
5. When do you use a flat price, a breakdown, a package, or a custom quote?
6. Which discount or exception can you grant alone, and which needs another approval?
7. What signals that a proposal is not ready to send yet?
8. What did you sell last year that you no longer offer, and why did it drop?
9. What almost-sold thing keeps coming back but never closes?
10. What do you promise in writing, and what is only implied?

## Signals to capture

- Real offer lines with commercial state: sold, pilot, in development, internal tool, discontinued.
- Promise and scope per modality, with exclusions and conditions.
- Price mechanics: authority, currency, taxes, validity, discount rules.
- Commercial path steps: origin, qualification, diagnosis, offer, approval, closing, follow-up.
- Exceptions and who may authorize each one.
- Readiness signals and never-omit components when quoting.
- Handoff rules from commercial to delivery.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| Portfolio, pricing rules, commercial path | D03 | oferta, producto, servicio, consultoria | A single price quoted once: keep in source, not D03 |
| One specific offer that deserves its own living record | X01 | oferta | An internal tool or component never sold: producto entity / source, not X01 |
| A particular proposal sent to a recipient | No document (register commercial state) | propuesta_comercial, cliente_cuenta | A proposal the owner later rejected: never rebuild from rejected wording |
| Commercial-delivery handoff rules | D03 (commercial-operational delivery rules) | oferta, proceso | A handoff nobody can describe concretely: K1/K2 gap, not a document |

## External-AI prompt

> You are interviewing the owner of a small business about what they sell and how they sell it. Speak plainly, one open-ended question at a time, and refer to the person you are interviewing as "the owner". Avoid sales jargon (do not use words like "funnel", "pipeline" or "value proposition"); let them use their own words. Ask for the last real proposals and what happened with each. Cover: what someone can buy today and what they receive for the money; what is always excluded; how a price is built when there is no standard offer; when they use a fixed price versus an itemized quote or a package; which discounts or exceptions they can approve alone; when a proposal is not ready to send; offers they stopped selling and why; things that almost sell but never close; and what is promised in writing versus only implied. Keep their account as given; do not tidy it into claims of fact.

## K-gap hints

- **K1:** the owner's internal rule for pricing unusual work; the minimum components a quote must always include.
- **K2:** the last proposals, price lists, or the quote/estimates files - a recoverable commercial source.
- **K3:** whether a planned offer will sell; the right price for a line never actually sold.
- **K4:** marketing decorations that never influence a single transaction.

## Base and development loop

This template is a **base**, not the finish line. The first session extracts the usable minimum for the vault; the business brain is expected to keep growing from it, and later rounds deepen what the first round seeded.
### Base - end of first round (what the vault should already hold)
- A D03 draft under review with sources: the offer lines actually sold (with price examples from real quotes), the way the owner prices (global, per unit, per area), and the proposal-to-acceptance flow actually used.
- Any commission or referral mechanic recorded as variable by event, never as a fixed constant.
- Price references only from real quotes or invoices the owner recognizes; K2 for a real price list if absent.

### Round 2+ - deepening prompts (run in later sessions, one at a time)
1. List every service line actually sold in the last twelve months; which are recurring and which are one-offs?
2. When does a proposal become a booked event - what has to happen between sending and accepting?
3. How do you handle a client who keeps adjusting scope or budget? Where is the line, and who decides it?
4. Which of your prices would you defend to a friend, and which are guesswork?
5. What would it take to sell a known line again without rebuilding it from scratch?

### What grows from here (triggers)
- An offer line sold more than once becomes a candidate X01 (living record) instead of a source anecdote.
- A pricing rule the owner states from episodes becomes an explicit D03 criterion (owner-confirmed).
- A variability in commissions stays a recorded pattern in D03 - never hard-coded into the brain.
- A single quote or one-time job stays in source; it does not open a document by itself.

### Revisit cadence
- Revisit after any change in how the owner quotes or sells, and at least every three months through [ce-continuidad](../../../ce-continuidad/SKILL.md).
- Maturity marker: the offer lines, pricing logic and acceptance flow are described from real quotes and episodes, and the reader can price a new lead the way the owner would.
