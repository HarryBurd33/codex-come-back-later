# Come back later for Codex

A persistent amber bookmark in the **existing Codex desktop chat list**. Right-click a
chat and choose **Come back later**. Open it, read it, switch away, rename it or restart:
the marker stays. Remove it manually or send a successfully accepted prompt to clear it.
Unread status stays independent.

This is an **unofficial, experimental local modification** for macOS. Build your own
alongside app from your installed Codex copy, using your own Apple-issued signing
identity. The original app remains available. No Codex application, signing certificate,
conversation data or extracted application source is distributed in this repository.

## Compatibility

| Requirement | Supported |
| --- | --- |
| Original Codex version | **26.1111.21308, build 27194**, exact pinned package bytes |
| Platform | Apple Silicon, macOS 14 or later |
| Build tools | Python 3.11+, Node.js 22+, Xcode Command Line Tools |
| Signing | Valid Apple Development or other eligible Apple-issued code-signing identity in your Keychain |

Other builds are refused until a compatibility port is reviewed. Updating the original
Codex app also stops this modified app from launching until its version guard is reviewed.
The modified app's updater is disabled; the original app's updater is unchanged.

Personal signing omits OpenAI-only Keychain, push and app-group entitlements. Fresh sign-in
may be required; notifications, Computer Use or other vendor integrations may be unavailable.
Gatekeeper distribution assessment rejected the development build tested here, while
normal human launches worked. **If macOS blocks your build, stop and use the original app.**
The workflow does not change security settings, remove quarantine, disable signature
validation or export private keys.

## Build and install alongside

Clone this repository and run commands from its directory. No npm dependencies are needed.
Use the actual absolute path to your original app; the tested package was named
`ChatGPT.app` on disk even though its interface is Codex.

```sh
python3 scripts/marker.py inspect --app /Applications/ChatGPT.app
python3 scripts/marker.py identities
python3 scripts/marker.py prepare my-build --app /Applications/ChatGPT.app
python3 scripts/marker.py sign my-build --identity YOUR_40_CHARACTER_IDENTITY_SHA1
```

Preparation creates a complete verified original backup and a separate candidate under
`build/candidates/my-build/`. Allow several minutes and several GB of free disk space.
It never writes to the original app or reads chat contents. Signing uses the existing
Keychain identity. It does not create certificates or change trust settings.

The default chat home is `~/.codex`. If yours differs, supply its absolute path with
`prepare ... --codex-home /absolute/path`. Browser/UI and marker state remain separate at
`~/Library/Application Support/local.codexmarker.app`. A custom `--bundle-id` also chooses
the private state directory; it must be distinct from OpenAI's bundle identities.

Open `build/candidates/my-build/Codex Marker.app` **normally through Finder**. Verify:

1. It opens, shows your existing chats, and supports the native marker and manual removal.
2. Accepted direct and queued prompts clear their chat's marker. Drafts and an assistant
   response finishing retain it.
3. Quit and reopen normally: the marker remains. Check light/dark appearance and keyboard
   selection of the menu toggle.

Only after these checks pass and the development limitations above are acceptable:

```sh
python3 scripts/marker.py accept my-build --native-checks-passed
```

This records **your human attestation**, not an automated native verification result.
Quit only the modified app before proceeding. The original can remain open.

```sh
python3 scripts/marker.py plan my-install my-build --target "/Applications/Codex Marker.app"
python3 scripts/marker.py install my-install
```

The target must be absent. Installation verifies a staged copy, then uses an exclusive
rename that cannot overwrite another app. It refuses running app/updater jobs, changed
files, stale acceptance, an updated original, or uncertain prior operations. It never
launches or quits Codex. Open the installed icon normally and confirm your chats and marker.

If your Applications directory is not writable, select an existing user-owned Applications
directory with `--target`. Keep your repository, build records and backup for recovery.
Do not use a new label to bypass an uncertain or failed transaction; preserve it for review.

## Disable or remove

Quit the modified app and run:

```sh
python3 scripts/marker.py disable my-install
```

This recoverably moves only the verified modified app into the installation transaction's
`removed.app` folder. It preserves the original app, chats, sign-in data and private marker
state. The installation plan becomes retired and cannot replay itself. Reinstallation
uses a fresh reviewed plan. Removal remains available after the original updates.

## How it works

The marker stores only account/host/chat keys and a fresh generation per marking in its
private IndexedDB. It makes no model calls. Explicit composer actions capture a private
in-memory ticket. Only an accepted send or server-confirmed queue receipt clears that
ticket's generation in the same chat. Drafts, automation and old receipts cannot clear a
newer generation. Storage errors retain the marker rather than falsely showing it cleared.

The version-pinned patch inserts the toggle and bookmark into the native row renderer,
then connects explicit user submissions to their acceptance results. Packaging regenerates
ASAR metadata and its active native integrity digest; validation remains enabled. The
native loading closure is signed with the builder's identity. The alongside launcher
selects the intended chat home and its separate UI profile before the engine starts.

## Tests and evidence

```sh
npm test
npm run test:macos
```

These cover the original marker runtime, bootstrap, launcher, archive integrity and
transaction recovery using owned fixtures. The native launcher tests execute only an
inert test engine. They do not launch Codex.

For the supported local Codex build, generate ignored application-factory fixtures and
run the integration tests:

```sh
python3 scripts/local_fixtures.py --app /Applications/ChatGPT.app
npm run test:integration
```

Generated fixtures stay under ignored `build/`; do not upload them. See
[verification details](docs/VERIFICATION.md) and [contributing](CONTRIBUTING.md).

The original implementation was human-tested with native menu/amber row placement,
direct/queued clearing, draft/assistant retention, rename/move/restart, unread coexistence,
both themes, tooltip and keyboard use. An alongside installation using existing chats and
live recoverable removal/reinstallation also passed. Less common failed-send, automated,
late-receipt, account/host and alternative-composer cases have offline coverage, with
incomplete native observations. Other machines and newer Codex builds have not been verified.

## License

[MIT](LICENSE) for this project's original code. Codex and its application assets are
not included. This project is not affiliated with or endorsed by OpenAI.
