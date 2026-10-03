# Fork notes

Fork of [maestrea76/HA-Dreame-SF25-WiFi-Integration](https://github.com/maestrea76/HA-Dreame-SF25-WiFi-Integration),
branched at **v0.4.3**.

Upstream comments are in Spanish and are left untouched on purpose, so that
merges from upstream stay clean and these changes can be offered back as PRs.
New comments in changed code are written in Spanish to match. This file is the
English account of what differs and why.

The domain stays `dreame_sf25`, so entity IDs, the config entry and any
automations referring to them survive switching between upstream and this fork.

## 1. Automatic Stir fired on *every* lid close, not every N

`modes._async_lid_closed()` compared the running total against the threshold:

```python
if self.lid_count >= LID_COUNT_THRESHOLD:   # 3
    await self.async_start_virtual(PROGRAM_STIR)
```

Nothing in the Stir path resets `lid_count` — by design, since the counter is
also the "unprocessed scraps" signal that the daily Compact and the lid-openings
entity rely on. The result is that the threshold behaves as a **latch rather than
a gate**: it opens on the third lid close and never closes again, so from then on
every close starts another 10-minute Stir.

Measured on a real unit, 2026-09-28 → 09-30: eight lid closes, six full Stirs.
The upstream README describes it as "when the lid closes and at least 3 openings
have accumulated", which reads as once-per-three.

Fixed by comparing against an anchor — the value `lid_count` had when the last
Stir ran — instead of the total. `lid_count` keeps climbing untouched, so the
fill signal is preserved:

```
threshold 3, 12 lid closes
  before: stirs at 3,4,5,6,7,8,9,10,11,12   (10 stirs)
  after:  stirs at 3,6,9,12                 (4 stirs)
```

The anchor is persisted, reset by `async_reset_counter()`, clamped when the
counter is set by hand, and only advances if the Stir actually started.

## 2. A failed write still produced a phantom cycle

`_async_set_program()` caught the exception and only logged it, then
`async_start_virtual()` set `virtual_mode` and started its expiry timer anyway.
HA would display an hour-long Compact that the appliance never ran, with one
line in the log as the only trace.

Note that `api.set_property()` already wakes the device and retries once before
raising, so an exception reaching this point is a genuine failure, not just a
suspended appliance. `_async_set_program()` now propagates, and
`async_start_virtual()` aborts instead of inventing a cycle.

## 3. One-second `self_clean` blip when a virtual mode ended

`_async_finish_virtual()` cleared `virtual_mode` *before* writing idle. In that
window `select.current_option` fell through to the raw program — `self_clean` —
so a 10-minute Stir announced itself as a finished Self-clean. Intermittent, and
only when a state update landed inside that window, which made it look random.

Now the stop is written first, the cached program is optimistically set to idle,
and only then is `virtual_mode` cleared.

## 4. Options flow

There was no options flow at all, and the tunables were module constants in
`const.py` that a HACS update would overwrite. Added, with the historical values
as defaults so an entry with no options behaves exactly as before:

| Option | Default |
|---|---|
| `stir_enabled` | `true` |
| `stir_threshold` | `3` |
| `stir_duration_min` | `10` |
| `compact_enabled` | `true` |
| `compact_threshold` | `3` |
| `compact_duration_min` | `60` |

Saving options reloads the entry, so the daily timer and durations are rebuilt.
