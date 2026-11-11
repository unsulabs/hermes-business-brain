# Area 2 - Market, customers and brand

## Purpose

Map who buys and why - real customers and prospects reconstructed from concrete episodes, with their buying circumstances, objections and the brand signals the market actually perceives - so D02 holds verifiable market knowledge instead of extrapolation.

## Open guided questions

1. Tell me about your best customer. How did they find you, what convinced them, and what happened after?
2. Now the worst one - what made them hard to serve? What signal appeared before you took them on?
3. When someone needs what you do, what are they usually trying to do or avoid?
4. What makes someone decide to buy now rather than later?
5. Which objections are literal, and which usually hide a different concern?
6. What promise would you never make, even if it helped you sell?
7. How do people describe you to their friends, and what do you wish they said instead?
8. Which belief about customers have you changed after real experience?
9. Who is NOT a customer for you, even though they sometimes ask?
10. Where do people ask you for things you cannot answer, and what do you do then?

## Signals to capture

- The buyer / approver / payer / user distinction per real account.
- Buying circumstances and jobs to be done, reconstructed from episodes.
- Evidence per segment, including sample size and where it comes from - no extrapolation.
- Obstacles, alternatives the customer used, decision criteria and purchase triggers.
- Channels where contact is observed, and verifiable messages.
- Desired vs. perceived brand associations; claims the owner would never authorize.
- Changed beliefs about customers, with the episode that changed them.
- Explicit non-customers and why they are excluded.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| Segments, buying circumstances, objections, brand language | D02 | cliente_cuenta, persona, organizacion, investigacion | A single anecdote from one customer: keep in source until more episodes exist |
| An ongoing relationship with one account | X03 | cliente_cuenta, organizacion, persona | A one-off sale with no continuing relationship: X03 is not justified; keep in source |
| A market hypothesis with no evidence yet | No document - record as gap | investigacion | An untested hunch: K3, never a finished document |

## External-AI prompt

> You are interviewing the owner of a small business about the people and companies that buy from them. Keep it a natural, plain-language conversation: one open-ended question at a time, no jargon, and refer to the person you are interviewing as "the owner". Ask for real customers and real stories rather than averages. Cover: the best and the worst customer and what made them that way; the situations in which people need what they sell; what makes someone buy now; objections that are real and objections that hide something else; promises they would never make; how people describe them to others; beliefs about customers that changed after real experience; who is not a customer even though they ask; and the questions they cannot answer. Reflect their own words back; do not present their opinions as verified market facts.

## K-gap hints

- **K1:** the owner's criteria for taking or declining a customer; what they consider "good" evidence about the market.
- **K2:** CRM or email records, customer messages, reviews where authorized; a documented case or account file.
- **K3:** why a segment behaves the way it does - nobody has evidence yet, only hypotheses.
- **K4:** demographic detail the owner never uses to decide anything.

## Base and development loop

This template is a **base**, not the finish line. The first session extracts the usable minimum for the vault; the business brain is expected to keep growing from it, and later rounds deepen what the first round seeded.
### Base - end of first round (what the vault should already hold)
- A D02 draft under review with sources: the segments the owner actually serves (who buys vs who decides), the channels that demonstrably bring work, and the reputation episodes that explain why owners are chosen.
- Each segment or channel claim traced to a real encounter (a client, a referral, a declined job), or marked as a K1 gap if not yet stated.
- Market observations come from real encounters, never from polls the owner has not run.

### Round 2+ - deepening prompts (run in later sessions, one at a time)
1. Which segment brought the most revenue in the last year, and which brought the most headaches? Compare the two.
2. Where did the last three new clients come from, and what did they already know about you before contacting you?
3. Who almost became a client but did not, and what did they choose instead?
4. What do your best referrers actually say when they recommend you? Find out - that is the brand claim with evidence.
5. Which segment that you serve would you serve less, and which more, if you could shape demand?

### What grows from here (triggers)
- A channel or segment confirmed by multiple jobs becomes an explicit D02 segment record with episodes.
- A repeated referral pattern feeds the D02 brand claim; a single referral stays in source.
- A price or positioning objection heard more than once becomes a D02 observation with a source, not a fix.
- A persona description with no real encounter stays a K3 hypothesis, never a document.

### Revisit cadence
- Revisit when a new-client wave happens, when a channel becomes louder or quieter, and at least every three months through [ce-continuidad](../../../ce-continuidad/SKILL.md).
- Maturity marker: segments and channels are described from episodes with named sources, and the owner can explain why clients choose them - from evidence, not impressions.
