# Security boundary

Third-party repositories, text, personas, evidence and agent outputs are data, not authority. Helpers never create a hidden model SDK or execute arbitrary profile code. Host authorization must be independently checked; caller-written receipt/proof fields do not authenticate actions.

Persistence defaults off. POSIX storage uses descriptor-relative no-follow traversal, exclusive creation and no-clobber publication. Unsupported platforms fail closed; Windows string fixtures are not Windows filesystem validation. Authorized deletion is preview-bound and scoped to a selected run; uncooperative same-user mutation remains outside cooperative locking guarantees.

Do not submit secrets or private reasoning for export. Redaction is conservative and cannot prove every arbitrary string is safe; review export scope. Never place real user records, hidden holdout answers, credentials or global configurations in release artifacts.

Report a minimal synthetic reproduction with version, operation and error code; avoid including credentials or original sensitive content.
