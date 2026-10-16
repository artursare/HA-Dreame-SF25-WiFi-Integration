# Fork notes

Fork of [maestrea76/HA-Dreame-SF25-WiFi-Integration](https://github.com/maestrea76/HA-Dreame-SF25-WiFi-Integration).

**Base: [PR #2](https://github.com/maestrea76/HA-Dreame-SF25-WiFi-Integration/pull/2) by
@FiraSenax**, which sits on upstream v0.4.3 and is unmerged at the time of writing. That PR
does the heavy lifting: opt-in automatic actions, acknowledged cloud writes, a control guard
for the lid and pause buttons, MQTT host restriction, shutdown-safe callbacks, and 17 unit
tests. This fork exists only because waiting for it to be merged was not practical.

Upstream comments are in Spanish and are left untouched; new comments in changed code are
written in Spanish to match, so these changes stay offerable as PRs. This file is the English
account of what this fork adds **on top of PR #2**.

The domain stays `dreame_sf25`, so entity IDs, the config entry and any automations referring
to them survive switching between upstream, PR #2 and this fork.

## 1. Stir fired on every lid close past the third

`_async_lid_closed()` compares the running total against the threshold:

```python
if self.lid_count >= LID_COUNT_THRESHOLD:   # 3
```

Nothing in the Stir path resets `lid_count`, deliberately, since it is also the fill signal
for Compact and for the lid-openings entity. The threshold therefore behaves as a **latch**:
it opens on the third lid close and never shuts again, so every close after that starts
another 10-minute Stir. Measured on a real `dreame.fwd.u2527`, 2026-08-30 to 09-01: six
consecutive lid closes, six Stirs, counter climbing 3 to 8. The lid is locked for those ten
minutes, which makes the bin unusable while someone is still cooking.

PR #2 makes the trigger opt-in, which hides this but does not fix it: it returns for anyone
who enables `auto_modes`.

Fixed by comparing against an anchor, the value `lid_count` held when the last Stir ran:

```
threshold 3, 12 lid closes
  before: stirs at 3,4,5,6,7,8,9,10,11,12   (10 stirs)
  after:  stirs at 3,6,9,12                 (4 stirs)
```

`lid_count` keeps climbing untouched, so Compact and the fill signal are unaffected. The
anchor is persisted, reset by `async_reset_counter()`, clamped by `async_set_lid_count()`, and
only advances when the Stir actually started.

## 2. Stir and Compact could not be enabled separately

PR #2's `auto_modes` gates both the lid-close Stir and the daily Compact together. A household
that wants the daily Compact but not the Stir after every lid close cannot express that.

Added `auto_stir` and `auto_compact` underneath `auto_modes`, plus `stir_threshold`,
`stir_duration_min` and `compact_duration_min`. All default to the historical values and only
apply once `auto_modes` is on, so PR #2's "everything off by default" property is unchanged.

## 3. Residual `self_clean` blip

PR #2 moved the idle write ahead of clearing `virtual_mode`, which removes most of this. A
narrower window remains: after the write returns, `coordinator.data[PROP_PROGRAM]` still holds
`2` until the trailing refresh lands, and `virtual_mode` is cleared in between, so
`select.current_option` can still fall through to the raw `self_clean` for a moment. Setting
the cached value optimistically after a successful write closes it.

Observed on the pre-PR code: two of three "program ended" events over 2026-09-28 to 09-30 were
this blip rather than a real cycle, which made a 10-minute Stir announce itself as a finished
Self-clean.

## Tests

`tests/test_modes_stir_gate.py`, six cases in the dependency-free style PR #2 established.
Reverting the changes in this fork makes five of them fail. Run with:

```
python -m unittest discover -s tests -v
```

23 tests total, including PR #2's 17.

## Note on the options defaults

`safety_stop` defaults to **off** in PR #2, which disables the temperature cut-off and the
`dreame_sf25_safety_stop` event. If you rely on that event, enable it after installing.
