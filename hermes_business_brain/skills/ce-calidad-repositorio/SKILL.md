---
name: ce-calidad-repositorio
description: "Audit, improve or evolve the master repository's code with tests, migrations and preservation of existing functionality."
---

# ce-calidad-repositorio

1. Read the repository's architecture and roadmap docs and Git state; identify the base version and foreign changes.
2. Run the full suite and create a synthetic instance; never use private data for tests without approval.
3. Choose a reproducible failure linked to a requirement or acceptance case; design a positive and a negative test, and evaluate existing alternatives.
4. Implement the minimal change, updating validators/schemas/templates coherently; do not remove vNext nor change its meaning to ease parsing.
5. If an instance changes, generate a migration with dry-run, backup and rollback before applying. Do not mark a version as ready without GUI experience on the target machine nor agent semantic tests.
6. Update changelog, decisions, documentation and re-run the suite; leave evidence with commands, output and pending tests.
**Output:** verifiable diff, real results, risks and next human decision.
