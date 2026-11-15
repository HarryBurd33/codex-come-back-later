# Contributing

Keep the feature focused on one per-chat marker. Opening a chat must never clear it.
Capture explicit human intent before asynchronous work; clear only the captured
generation after authoritative acceptance in the same account, host and chat.

Run the core tests, macOS fixture tests and pinned-source integration tests before
changing a supported build. Record native observations separately from offline tests.
Never add conversation capture, account credentials or network calls to the marker.

For a new Codex build, review its actual row, composer and receipt paths. Add exact
source hashes and reject unknown versions. Preserve active ASAR/native integrity and
the original app; verify signing and native behavior before accepting a port. A string
replacement that merely stops throwing is not evidence of correct integration.

Do not commit `build/`, app bundles, ASAR archives, extracted factories, provisioning
profiles, signing certificates, private keys, logs containing personal data, or local
account/chat metadata. The optional fixture generator reads those factories locally;
its outputs stay ignored. Submit changes through a pull request with the relevant test
results and the supported build/architecture.

If install or removal stops, preserve its plan, journal and complete bundle. Do not
delete an unknown stage or overwrite a target. Report the failure with personal paths,
account identifiers and signing identity details redacted.
