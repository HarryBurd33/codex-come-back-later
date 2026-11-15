# Verification scope

The feature was developed against Codex 26.1111.21308/build 27194 on Apple Silicon.
Package inputs are pinned in `compatibility/build-27194.json`. The public repository
contains original tools and tests; full app binaries and extracted source fixtures are
generated locally and remain ignored.

## Offline checks

- 33 core JavaScript tests: marker identity/generations, explicit submission origin,
  receipt ordering, storage failure behavior, UI metadata, bootstrap path isolation.
- 80 JavaScript tests including locally generated pinned-source integration fixtures:
  row/host selection, direct and queued receipts, ticket survival, configuration queue
  account changes, image submission origin and confirmation paths.
- 27 Python tests: archive readback/corruption, enabled native digest metadata, launcher
  version/state/receipt guards, policy/evidence drift, create-only installation,
  interrupted renames and recoverable removal, plus exported helper import checks.

The factory harness supplies inert services and uses an isolated JavaScript realm. It
does not contact a live app server or automate the native application. Launcher fixtures
execute only an owned inert engine.

## Portable release build

The standalone public builder produced a complete candidate and original backup on the
verified host. All 16 feature-overlay files exactly matched the human-tested installed
implementation. Its separate 38-object signing workflow passed native signatures,
entitlement/payload checks and full-bundle preservation checks. That additional portable
candidate was not launched or installed; native UI evidence below belongs to the tested
implementation and alongside installer described there.

## Human native observations

The privately signed implementation passed normal launch/sign-in, native context-menu
toggle and amber chat-row placement, retention on reading/drafting/switching, manual
removal, direct accepted-prompt clearing, rename/move/restart, independent chats, unread
coexistence, keyboard use, both themes and tooltip. Marking during a response survived
its completion; an accepted queued user prompt cleared the marker immediately.

The alongside app subsequently opened normally with existing chats. Marker and restart
checks passed there and from the final installed Applications icon. A live install,
recoverable removal and fresh-plan reinstall passed native signature and full-copy
verification. The original app's pinned package files and native signature remained valid.

Failed submissions, automated continuations, delayed receipts across account/host
transitions and some alternative-composer paths have offline coverage but incomplete
native observations. No cross-machine compatibility is claimed.

## Signing and recovery limits

All changed native loading objects use the builder's Apple-issued identity and preserve
hardened runtime. Original vendor-only entitlements are omitted where the new identity
cannot claim them. Other vendor executables remain byte-preserved. The package-time
native ASAR digest changes only its 32 metadata bytes, retaining the enabled flag,
supported version and validation code.

Native signatures pass. Gatekeeper distribution assessment rejected the development
build, while normal human launches worked without changing security settings. If a
machine blocks a build, use the original app; this repository supplies no bypass.

Removal recognizes only the observed system root MACL metadata change through an
in-memory comparison, still requiring native signatures. It then freezes the actual
complete fingerprint for the operation. No system metadata is removed or reset.
Operations preserve partial/unknown outcomes. They assume cooperative stopped-app use
and do not promise exclusion of arbitrary writers or sudden power-loss durability.
