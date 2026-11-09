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
