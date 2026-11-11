# Area 8 - Direction and decisions

## Purpose

Capture the strategic boundaries, priorities and the decision record - what was decided, who had the authority, and what evidence would change it - so D01 holds the direction and X07 preserves decisions, experiments and lessons with their own identity, keeping intentions distinct from decisions.

## Open guided questions

1. What is this business trying to become, and what is it deliberately not becoming?
2. When did you last change something central - price, offer, market, way of working - and what triggered it?
3. What decision are you putting off right now, and what would settle it?
4. What have you tried recently that did not work, and what did you learn from it?
5. What would make you stop a current line of work entirely?
6. What should the business be doing a year from now that it is not, and what evidence would convince you?
7. Which past decision, if reversed today, would hurt the least - and why?
8. What do you keep saying "not yet" to, and what would change that?
9. Who besides you is allowed to make decisions that commit the business?
10. If you had to choose between a sure small win and a risky big one, how would you choose?

## Signals to capture

- Priorities and the criteria behind them; what is deliberately excluded.
- Strategic boundaries with their reason and effective date.
- Decision history: subject, decider, date, scope, replacement.
- Experiments with their outcome and what was learned - separate observed result from interpretation.
- Hypotheses and the evidence that would falsify them.
- Open decisions with owner and what would settle them.
- Change triggers: the signal that made the owner act.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| Strategic boundaries, priorities, trade-offs, change history | D01 | empresa, modelo_negocio, decision | An aspiration with no activity behind it: keep in source until episodes confirm it |
| A decision, experiment or lesson with its own identity | X07 | decision, investigacion | A proposal not yet authorized: brain_propose, never X07 |
| Open questions needing study | No document - record as gap | investigacion | Everything unknown: the K3 list, not a stack of documents |

## External-AI prompt

> You are interviewing the owner of a small business about where they are taking the business and how they decide. Keep it a plain-language conversation, one open-ended question at a time, and refer to the person you are interviewing as "the owner". Ask for real changes and real decisions with dates and reasons, not intentions. No jargon (avoid words like "strategy", "roadmap" or "vision"); let them speak in their own words. Cover: what the business is becoming and deliberately not becoming; the last central change and what triggered it; a decision they are putting off and what would settle it; something they tried recently that did not work and what they learned; what would make them stop a current line of work; what the business should be doing a year from now and what evidence would convince them; a past decision that reversing would hurt least; things they keep saying "not yet" to; who besides them can commit the business; and how they choose between a sure small win and a risky big one. Report what they said; do not turn intentions or proposals into decisions.

## K-gap hints

- **K1:** the owner's priorities and selection criteria; what "commitment" means and who can make it.
- **K2:** an actual decision record, experiment log, or the dated message where the change was announced.
- **K3:** whether a future direction will pay off - no evidence exists yet.
- **K4:** strategic theory the owner never applies to a real choice.

## Base and development loop

This template is a **base**, not the finish line. The first session extracts the usable minimum for the vault; the business brain is expected to keep growing from it, and later rounds deepen what the first round seeded.
### Base - end of first round (what the vault should already hold)
- The decision trail so far: each direction choice already taken recorded with who decided and when (X07), and future lines named but kept distinct from current operations (X04 when explored).
- Selection criteria for future moves as stated by the owner (K1 if missing), and unverified hopes marked K3.
- No future line is presented as current reality - it stays a named intention until there is evidence.

### Round 2+ - deepening prompts (run in later sessions, one at a time)
1. Which decision changed the business most last year, and what would you do differently with what you know now?
2. Which future line would you greenlight tomorrow if cash were ready, and what evidence would kill it?
3. Who is involved when a big decision is made, and is that recorded anywhere?
4. What would make you stop a current line that still brings money?
5. What is the one number you want to know twelve months from now?

### What grows from here (triggers)
- A decision made with a decider and date becomes an X07 decision record; its boundary updates the relevant D/X.
- A future line with real exploration (a test, a quote, a market contact) becomes an X04 or investigation record with sources.
- A direction change updates D01; a direction intention without action stays K3.
- A stated resolution without a decider or date is a gap, not a document.

### Revisit cadence
- Revisit after every strategic decision and at least quarterly as the direction review, through [ce-continuidad](../../../ce-continuidad/SKILL.md).
- Maturity marker: decisions are recorded with decider, date and evidence, and future lines are visibly separated from current operations.
