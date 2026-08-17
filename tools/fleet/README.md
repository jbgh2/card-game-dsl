# The fleet's scheduling rung

Standing Roles (docs/harness.md, "Standing Roles") fire from the
machine's own scheduler and run the engine headless — `claude -p` under
the permission charter (.claude/settings.json), in the dedicated fleet
clone at `/Users/benh/Projects/cardlang-fleet`, never in the operator's
working copy. Issue #317 owns the rationale.

Pieces (all in this directory):

- `run-role.sh <warden|dispatcher>` — the wrapper. Owns freshness
  (hard-sync to origin/main), single occupancy (one role in the clone at
  a time; a skipped run posts publicly), a wall-clock watchdog, and the
  delivery guarantee: every run ends with a report on epic #274 or a
  wrapper-posted failure/no-report comment carrying the log tail.
- `prompts/<role>.md` — the versioned prompt each run executes. Thin by
  design: it invokes the role's charter skill and carries only the
  headless adaptations (no pulling, worktrees inside the clone, checks
  via ./tools/verify.sh, foreground PR-watching, denials reported).
- `launchd/com.cardlang.<role>.plist` — the launchd agents: bare stubs
  (cd + exec). All clone sync lives inside the wrapper, after its
  occupancy lock — concurrent agents must not race git in the shared
  clone — and the wrapper is parse-safe against its own in-run update
  (a run executes the previous run's wrapper; changes land one run
  later).

## Installing — the operator's hands, deliberately

Installing or scheduling a launch agent is persistence: it is performed
by the operator, never by an agent. To install or reinstall both:

```
FLEET=/Users/benh/Projects/cardlang-fleet
mkdir -p ~/Library/LaunchAgents "$FLEET/logs"
for role in warden dispatcher; do
  cp "$FLEET/tools/fleet/launchd/com.cardlang.$role.plist" ~/Library/LaunchAgents/
  launchctl bootout "gui/$(id -u)/com.cardlang.$role" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.cardlang.$role.plist
done
```

The Warden's daily slot (Hour 8, Minute 10 — the slot the app scheduler
held) is a `StartCalendarInterval` stanza the operator adds to the
warden plist before installing; the Dispatcher stays kickstart-only
until the operator sets a standing cadence. Manual fire, either role:

```
launchctl kickstart gui/$(id -u)/com.cardlang.warden
```

## Residuals, named

- Runs require the operator's login session (gh auth, SSH key, Keychain)
  and an awake machine — the always-on box is issue #278.
- The fleet clone must be a trusted workspace
  (`projects["…/cardlang-fleet"].hasTrustDialogAccepted` in
  ~/.claude.json), or the charter's allowlist is ignored and every
  liturgy is denied.
- The charter must carry a write permit scoped to the clone
  (`Edit(//…/cardlang-fleet/**)`, `Write(//…/cardlang-fleet/**)`): a
  headless round with no permit for the Edit and Write tools falls
  through to the default-ask and is refused with nobody present — it
  can Lease, read, and run tools, and cannot change a byte (issue #361,
  the first launchd-fired Dispatcher round). Bash rules do not cover
  the file tools; the permit is a separate line.
