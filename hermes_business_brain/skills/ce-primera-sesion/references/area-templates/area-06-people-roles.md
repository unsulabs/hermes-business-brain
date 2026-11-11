# Area 6 - People and roles

## Purpose

Establish who actually does what and who can decide what, based on observed functions rather than an org chart - D06 records the real decision matrix, tacit-knowledge dependencies and continuity limits without inventing titles or authority.

## Open guided questions

1. If you left for two weeks tomorrow, what keeps running and what stops?
2. Which decision can only one specific person make today, and why?
3. What task could you delegate if you wrote down your criteria?
4. What critical knowledge lives in one person's head, and how do you recognize someone has learned it?
5. In your business, what is the difference between doing a task and having the authority to commit?
6. Who has keys, access or the ability to spend, and who decides they get it?
7. What does a new person need to learn before they stop asking you?
8. Which responsibility has changed hands recently, and what broke or improved?
9. What would you do if your main assistant was hired away next month?
10. Who actually decides when a customer gets an exception?

## Signals to capture

- Functions actually performed, not departments or invented titles.
- Simple decision matrix: subject, who decides, who prepares, who acts, and limits.
- Commitments that require approval, and current delegations.
- Dependency on tacit knowledge, access and capacity.
- Realistic substitutions and where continuity breaks.
- Learning transfer: how someone proves they have learned the task.
- Responsibility changes with what broke or improved afterwards.

## Mapping table

| Matter heard | Suggested class | Entity type ids | When NOT to create a doc (keep in source) |
|---|---|---|---|
| How work is organized and who decides what | D06 | persona, organizacion, sesion, reunion | Roles never observed, proposed as if real: keep out until episodes confirm them |
| A person's role or authority | Entity record, minimal personal data | persona, organizacion | Contact data with no proven authority: a persona record stays minimal; do not assume decisions |
| A committed action with owner and date | Entity record | tarea | A vague intention with no owner or date: K1 pending, not a record |
| What a meeting or session agreed | Entity records | reunion, sesion, decision | A statement in a meeting is not an approved decision: keep the meeting as source |

## External-AI prompt

> You are interviewing the owner of a small business about the people who do the work and who decides what. Keep it a plain-language conversation, one open-ended question at a time, and refer to the person you are interviewing as "the owner". Ask about real people and real situations, not an ideal organization: no titles unless they use them. Cover: what keeps running and what stops if they disappear for two weeks; decisions only one specific person can make today and why; tasks they could delegate if their criteria were written down; knowledge that lives in one person's head and how you can tell someone has learned it; the difference between doing a task and having the authority to commit the business; who has keys, access or spending ability and who grants it; what a newcomer must learn before they stop asking; a recent change of responsibility and what broke or improved; what would happen if their main assistant were hired away; and who really decides when a customer gets an exception. Keep their account as told; do not turn people or roles into confirmed facts.

## K-gap hints

- **K1:** the owner's criteria for delegating; what "authority to commit" means in their business.
- **K2:** an actual delegation document, access log, or the person's own testimony where authorized.
- **K3:** how a substitution would actually work - it has never been tested end to end.
- **K4:** personal details irrelevant to roles, responsibilities and continuity.

## Base and development loop

This template is a **base**, not the finish line. The first session extracts the usable minimum for the vault; the business brain is expected to keep growing from it, and later rounds deepen what the first round seeded.
### Base - end of first round (what the vault should already hold)
- A D06 draft under review with sources: the real people the business runs on (fixed core vs per-event), the payroll structure (weekly base vs piecework extras) as actually run, and who decides what - commercial, design, administration, execution.
- Authority episodes: who can commit money, change scope, or make promises to a client when the owner is absent.
- Each role traced to a real task or event; open authority questions marked K1.

### Round 2+ - deepening prompts (run in later sessions, one at a time)
1. Map every role you leaned on last year: which were fixed, which per event, which trusted with money?
2. Who can make a commitment to a client when you are absent, and what is the rule for when they should not?
3. What would each key person say they are responsible for, in their own words?
4. Which task can only you do, and what would it take to hand it off?
5. How do you decide someone's rate, and is that decision recorded anywhere?

### What grows from here (triggers)
- A role with real responsibilities becomes an entity card for the person or role (persona, tarea), with sources.
- An authority episode becomes an explicit D06 authority statement (owner-confirmed) - who may and who may not commit.
- A hand-off feasibility explored in episodes becomes a future line for D04 or D08, not a promise.
- A single mention of a person without a real role stays in source.

### Revisit cadence
- Revisit after any hire, departure or shift in responsibilities, and at least twice a year through [ce-continuidad](../../../ce-continuidad/SKILL.md).
- Maturity marker: someone else can open D06 and know exactly who decides what and who may commit what.
