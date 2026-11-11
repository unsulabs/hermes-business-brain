# Area 1 - Business model

## Purpose

Understand how the business actually creates, delivers and captures value today - the real money mechanism, what is deliberately declined, and which assumptions remain untested - so that D01 records the observed model instead of an aspirational pitch.

## Open guided questions

1. Walk me through how an order actually becomes money in your business - from first contact to the payment in the bank. What are the real steps and who does what?
2. Who pays you, who decides to buy, and who actually uses what you deliver? Are they ever different people?
3. What work do you regularly turn down, and why? What signals make an opportunity a fit for you?
4. What could you earn good money at but deliberately don't do?
5. What happened the last time a job ended up costing you more than it was worth? What was the warning sign?
6. What do people choose instead of you - a competitor, a substitute, or doing it themselves?
7. What is genuinely hard for others to copy about how you work, and why?
8. What did you believe about this business a year ago that has changed since?
9. What do you want to build, stop or change in the coming months, and what evidence would change that plan?
10. If someone else had to run the whole business for a month, what would you tell them first?

## Signals to capture

- The actual billing mechanics: who pays, what for, and through which channel.
- Payer vs. buyer vs. user when they differ.
- Rejected opportunities and the criteria that made them a fit or not.
- Trade-offs when price, capacity, reputation, quality and time conflict.
- Activities competitors or substitutes win with, and why the owner still wins some.
- Changed beliefs about the business, with the episode that changed them.
- Future lines kept distinct from current operations.
- Who decides strategy changes, and when the last ones happened.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| How value is created, delivered and captured today; segments; trade-offs | D01 | empresa, modelo_negocio | An aspiration or a single anecdote not backed by activity: keep in source until episodes confirm it |
| A specific deliverable that is actually sold today | D01 (as an offer line) - X01 when it deserves its own living record | oferta, producto, servicio, consultoria | A one-off historical job with no current activity: source only |
| A direction choice already taken (who, when, authority) | X07 for the decision record; D01 for the resulting boundaries | decision, modelo_negocio | A stated intention with no decider or date: K1/K3 gap, not a document |

## External-AI prompt

> You are interviewing the owner of a small business in a natural, plain-language conversation. Ask one open-ended question at a time and refer to the person you are interviewing as "the owner". Avoid business jargon: let them describe things in their own words (do not impose terms like "business model", "value proposition" or "strategy"). Ask for real examples and recent episodes - a real job, a real rejection, a real mistake - rather than general descriptions. Cover: how an order becomes money; who pays, who decides and who uses; work the owner refuses and why; things they could earn money at but do not do; trade-offs when price, capacity, quality and time conflict; what customers choose instead of them; what is genuinely hard to copy; beliefs that changed; what they plan to build or stop and what evidence would change that; and what an outsider must know first to run the business for a month. Two hours maximum, keep questions flowing naturally.

## K-gap hints

- **K1:** how the owner defines a "good" opportunity; the criteria behind declining work; what "profitable" means to them.
- **K2:** real invoices, contracts, price lists, bank or accounting records they authorize; the actual figures behind the money story.
- **K3:** whether a future line will work; untested assumptions about a new market or offer.
- **K4:** idealized mission statements; details of competitors the owner has never actually met in the market.

## Base and development loop

This template is a **base**, not the finish line. The first session extracts the usable minimum for the vault; the business brain is expected to keep growing from it, and later rounds deepen what the first round seeded.

### Base - end of first round (what the vault should already hold)
- A D01 draft under review with sources: the observed money loop, the segments the owner actually works with, the payment rule, and the owner's own fit/decline criteria as stated (no external positioning, no aspirational pitch).
- Each fit/decline criterion traced to an episode (a real yes, a real no, a real costly job), or marked as a K1 gap if not yet stated.
- Pending figures recorded as K2 (invoices, price lists, bank records) with nothing invented in their place.

### Round 2+ - deepening prompts (run in later sessions, one at a time)
1. Walk the order-to-money loop again through a *second recent job* and compare: what differed, and which step is usually the tightest?
2. What was the most expensive mistake in the last year, and what rule exists now so it does not repeat?
3. Which customer recently chose something else instead of you - what did they choose, and at what price?
4. If revenue doubled without adding any working time, how would that look? Which part of the loop would change?
5. What do you know today about this business that you could not have proven a year ago - and what changed it?

### What grows from here (triggers)
- A fit criterion confirmed by a second episode moves from K1 to an explicit D01 criterion (still owner-confirmed).
- An offer line sold more than once becomes a candidate X01 (living record) instead of a source anecdote.
- A direction choice made with a decider and date becomes an X07 decision record; its resulting boundary updates D01.
- A single anecdote, aspiration or unverified figure stays in source - it never opens a document by itself.

### Revisit cadence
- Revisit this area after any significant commercial change (new segment, changed payment rule, a major loss or win) and at least every two to three months through [ce-continuidad](../../../ce-continuidad/SKILL.md).
- Maturity marker: the D01, re-read by someone else, describes the *observed* model with sources - not a pitch and not a questionnaire.
