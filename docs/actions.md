# Actions

## The action abstraction

`ActionDefinition` (`handwave/actions/action_definition.py`) is a validated,
serializable, side-effect-free description of one action. `ActionExecutor`
(`handwave/actions/action_executor.py`) is the only thing that ever touches
the OS, and it only accepts an `ActionDefinition` — recognition code never
constructs OS calls directly. Supported types:

| Type | Value | Notes |
|---|---|---|
| `media` | one of `play_pause`, `next_track`, `previous_track`, `volume_up`, `volume_down`, `mute` | pyautogui media keys, `keyboard` package fallback for track skip |
| `key` | a single key name (`Space`, `F5`, `Esc`, ...) | normalized case/alias table |
| `hotkey` | e.g. `Ctrl+Shift+S` | must start with a modifier, 2-5 keys, no duplicates |
| `mouse` | `left_click`, `right_click`, `middle_click`, `scroll_up`, `scroll_down` | |
| `text` | a string, 1-1000 chars | typed via pyautogui |
| `command` | a program + arguments | **always** requires confirmation or hold (see below) |

Windows navigation defaults use the existing `key` and `hotkey` action types
(`Esc`, `Alt+Tab`, `Win+Tab`, and `Win+Ctrl+Left/Right`); they are configured
like every other gesture binding rather than executed by a recognizer. If local
input injection is unavailable, `ActionExecutor` logs the failure and safely
does nothing. No application-specific automation or installed application is
assumed.

## Safety

- `command` actions are parsed into an argv list (`shlex.split`) and launched
  with `subprocess.Popen(argv, shell=False)` — never a shell string. This is
  enforced in `ActionDefinition.__post_init__`, not just convention.
  `ActionDefinition.describe()` always labels a command action as "Launch
  `<program>`" so it is visually distinct from a keyboard action anywhere it's
  displayed.
- Any `command` action, and hotkeys matching `alt+f4` or `ctrl+alt+delete`,
  cannot be constructed with less than `ActionDefinition.CONFIRMATION_HOLD`
  (1.5s) of hold time — either `requires_confirmation=True` (which raises the
  effective hold to 1.5s) or an explicit `hold_duration >= 1.5`. This is a
  validation rule, not a UI-only nicety: constructing the object directly
  raises `ValueError` if you try to skip it.
- Cooldown, hold-duration, and re-arm are enforced by `ActionMapper`
  (`handwave/actions/action_mapper.py`) regardless of action type — a custom
  gesture's action gets the same protection as a built-in one, because both
  flow through the same mapper (see [gesture-recognition.md](gesture-recognition.md)).

## Non-blocking execution

`ActionMapper.execute()` never calls the OS directly — it hands a callback to
a dispatcher (`ActionQueue.submit`), which `ActionWorker` drains on its own
thread. A slow `command` launch or a hung keyboard call cannot stall
recognition; see the frame-latency/action-dispatch numbers in
[benchmarking.md](benchmarking.md).

## Why an action was, or wasn't, executed

`ActionMapper.execute()` sets `self.last_outcome` (an `ActionOutcome`) on
every call, whether or not it fired:

| `blocked_reason` | Meaning |
|---|---|
| `gesture disabled` | this gesture is turned off in settings |
| `no action bound` | enabled, but bound to "none" |
| `gesture not re-armed` | same gesture is still active from last time; release and re-pose to re-arm |
| `hold duration not met` | needs to be held longer (confirmation gestures) |
| `cooldown active` | too soon since the last action (global or per-gesture cooldown) |
| `action failed: <error>` | the executor raised; recognition keeps running regardless |

`GestureWorker` emits this as `action_outcome`, forwarded through
`CameraManager.action_outcome_updated` to `MainWindow._record_action_outcome`,
which appends a bounded `ActionHistory` entry (`handwave/services/
action_history.py`, a fixed-capacity ring buffer — it cannot grow without
limit) and shows blocked actions in the dashboard's Action Log, not just
executed ones.

## Extending the action abstraction

Adding a new action type means: add it to `ACTION_TYPES` and the
`__post_init__` validation branch in `action_definition.py`, add an
`ActionExecutor.execute()` branch, and add a UI case in
`ActionEditorRow._sync_value_widget()` (`handwave/ui/settings_dialog.py`).
Nothing in `GestureFilter`, `ActionMapper`'s cooldown/re-arm state machine, or
`ActionQueue` needs to change — they operate on the gesture *name* and the
`ActionDefinition`, never on a specific type.
