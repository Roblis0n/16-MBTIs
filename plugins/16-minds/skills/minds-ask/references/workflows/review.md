# Evidence-based code review
Use the code-review profile within exact supplied paths and snapshot hash. Record
location, trigger, root cause, impact, evidence, minimal reproduction, remedy,
and proposed regression test. Static findings remain unverified. A claimed
reproduction needs a referenced actual failing execution with collected and run
tests; exit zero with no collection or all skipped proves nothing. Deduplicate by
root cause and trigger. Lead with confirmed findings; disclose blind spots and
say only that no issue was confirmed within the checked scope. Never apply a
patch or run repository scripts without separate authorization and host isolation.
Personas are attention styles, never professional credentials.
