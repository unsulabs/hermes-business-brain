# Area 5 - Economy and finance

## Purpose

Understand how money moves through the business and which figures the owner actually looks at before deciding, keeping the accounting system as the authoritative source - D05 records revenue mechanics, cost drivers, unit economics and cash, never numbers recalled from memory.

## Open guided questions

1. Before all costs are locked in, how do you estimate whether a job is worth it?
2. Which costs do newcomers to your business usually forget?
3. When can a big project be worse business than a small one?
4. What figure do you look at first when deciding financially, and what does it not tell you?
5. What are your rules for advances, discounts, credit and large purchases?
6. Which numbers does anyone besides you know, and where do those numbers live?
7. What would you check the day you suspected money was leaking?
8. In your business, what is the difference between invoiced, accrued and collected?
9. What happens if a large payment arrives a month late?
10. What threshold, if crossed, makes you stop and rethink?

## Signals to capture

- Revenue mechanics: agreed, invoiced, accrued and collected, tracked separately.
- Variable and fixed costs, with how the owner allocates shared costs.
- Unit economics per line or job, and where the numbers come from.
- Cash rhythm: expected inflows and outflows, maturities, what breaks when late.
- Money-decision criteria and who has authority to spend or discount.
- Thresholds and alerts; discrepancies between the narrative and the accounts.
- What the owner does not know, marked rather than invented.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| Revenue, cost, cash and economic criteria | D05 | empresa, indicador | Figures from memory without a recoverable source: record the K2 gap, never draft as verified |
| A measure the owner wants to watch | Entity record when defined (formula, source, frequency) | indicador | A value someone computed once ad hoc: not official data |
| A supplier relationship affecting cost | Entity record | proveedor, recurso | Without a contract or invoice: keep in source, mark NO VERIFICADO |
| An agreement with money obligations | X05 | acuerdo | An email-only mention: source until the actual document exists |

## External-AI prompt

> You are interviewing the owner of a small business about money. Keep it a natural, plain-language conversation, one open-ended question at a time, and refer to the person you are interviewing as "the owner". Avoid financial jargon they do not use - never put words like "cash flow", "EBITDA" or "unit economics" in their mouth; ask how things work in their own words. Ask for real examples: a recent job that was worth it, one that was not, a payment that arrived late. Cover: how they judge whether a job is worth doing before all costs are known; costs that outsiders forget; when a big project is worse than a small one; the figure they look at first and its blind spots; their rules for advances, discounts, credit and big purchases; who else knows the numbers and where they live; what they would check if money was leaking; the difference between invoiced, promised and received; what happens if a large payment is late; and the threshold that makes them stop and rethink. Report what they said; do not convert their memory into financial facts.

## K-gap hints

- **K1:** the owner's economic decision criteria - what makes a job "worth it" in their own terms.
- **K2:** the accounting system, bank records, invoices, quotes and contracts - recoverable figures; demand the source, not the remembered number.
- **K3:** projections for a scenario never measured (e.g. a big payment permanently lost).
- **K4:** accounting refinements the business does not use to decide anything.
