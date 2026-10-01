# Host adapter protocol 1.0.0

The Python helper emits plans, never invokes a native SDK. `prepare_action` makes a proposed internal intent. The host assistant registers the exact proposal via scheduler `step` **before** dispatch, invokes a tool whose schema it actually sees, then passes the actual action ID, physical thread ID and retained receipt reference to `record_receipt`. This records dispatch, not a successful agent result. Results require the separate result event and schema/semantic checks.

Use `isolation_parameters` with the actual exposed spawn fields: v2 `fork_turns: none`, v1 `fork_context: false`; absent controls produce no invented parameter. Model and reasoning parameters are not emitted. Never assume an output plan is a real receipt. Capabilities are caller declarations backed by evidence references, not cryptographic attestation; mocks do not prove observed host capability.

Native preflight requires verified isolation; missing native delegation never silently degrades. An explicitly authorized simulation is labelled single_context, not a native host test. The deterministic scheduler currently emits no native actions for single_context; a separate disclosed simulation driver is required. Unknown thread capacity is one; confirmed physical cleanup is needed before the next slot is reused. Missing close support leaves residual thread IDs and stops further creation once capacity is occupied.

Prompts prohibit nested delegation and tools outside supplied materials. This is a soft instruction, not a sandbox: nested calls and unobserved tokens remain unknown. Unverified read-only enforcement means material analysis only; never run untrusted scripts or use global configuration, credentials, live data, external models or paid APIs. The helper cannot cap unrelated host actions.

No live host test was performed by these modules. `tests/unit/test_scheduler.py` is a synthetic protocol replay only. Production capability evidence and isolation canaries must come from the actual selected host, under the user's permissions.
