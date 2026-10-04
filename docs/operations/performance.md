# Performance — what the flow costs, and what to expect

Scanning feels slow.  This is where the time goes, what each part should cost,
and which knobs actually move it.

The figures are for a Raspberry Pi Zero 2 W.  Turn `MetricsEnabled` on in the
dashboard to see the live numbers; they come from `src/ipr_keyboard/metrics.py`
and are already rendered on the dashboard's KPI block.

---

## The five stages

```
pen writes the file
      │   (1) detect      poll finds it
      ▼
  detected  ─── (2) read ──▶ text in memory
                                  │  (3) queue
                                  ▼
                            BLE HID daemon
                                  │  (4) type
                                  ▼
                            characters on the PC
```

| # | Metric | What it measures | Target | Why |
|---|---|---|---|---|
| 1 | `detect_latency_ms` | file's mtime → the poll noticing it | **< 1500 ms** | bounded by `PollIntervalSeconds` (1 s) plus one folder listing |
| — | `poll_scan_ms` | one sweep of the watched folders | **< 300 ms** | this is what stops `PollIntervalSeconds` going lower; it is an MTP round trip, not a local `readdir` |
| 2 | `read_ms` | reading the file over MTP | **< 500 ms** | a scan is a few hundred bytes; anything above a second means the MTP mount is struggling |
| 3 | `queue_wait_ms` | FIFO write → the first character going out | **< 200 ms** | the daemon has to be subscribed and reading |
| 4 | `type_ms_per_char` | typing one character over BLE HID | **≤ 15 ms** | two HID reports per character; see below |
| | `type_ms` | the whole scan typed | **< 3 s** for 200 characters | `type_ms_per_char × chars` |
| | `send_ms` | the FIFO write alone | **< 50 ms** | **not the transmission** — see the warning below |
| | `e2e_latency_ms` | mtime → last character typed | **< 5 s** for a typical scan | the number the user actually feels |

## What dominates: the typing

Until now the BLE daemon slept a fixed 20 ms after every HID report:

```python
time.sleep(0.012)
time.sleep(0.008)      # two sleeps, 20 ms, per report
```

Two reports per character (press, then release) make **40 ms per character —
25 characters a second**.  A 500-character scan therefore takes 20 seconds,
and nothing else in the pipeline comes close to that.

The delay is `BT_KEY_DELAY_MS` (default 20, unchanged) in
`/opt/ipr_common.env` — the file `bt_hid_ble.service` already reads — which
sets it for the daemon's lifetime.

**Normally you change it in the dashboard instead**: Settings → Typing
speed, which saves `TypingDelayMs` and writes it to
`/run/ipr_bt_key_delay`.  The daemon re-reads that file once per send, so a
new speed applies to the next scan **without restarting the daemon** — a
restart drops the BLE link and makes the PC pair again, which is far too
much for a settings change and makes tuning by trial impossible.  `/run` is
cleared by a reboot, so the env var stays the default and the application
re-applies the saved setting on its first loop.

Either way, lower it by measurement, not by hope:

| Value | Nominal chars/s | Achievable | Note |
|---|---|---|---|
| 20 ms | 25 | **25** | the default; the delay is what limits the device |
| 12 ms | 42 | **~40** | usually the practical best |
| 8 ms | 62 | ~33–44 | at or below the host's interval: no real gain |
| 4 ms | 125 | ~33–44 | no gain, and expect loss |

**Nominal is not achievable, and the difference is the whole point.**  Each
character is two HID notifications, and a notification cannot be delivered
faster than one connection event:

| Connection interval | Floor | Ceiling |
|---|---|---|
| 7.5 ms | 15 ms/char | 66 chars/s |
| 11.25 ms | 22.5 ms/char | 44 chars/s |
| 15 ms | 30 ms/char | **33 chars/s** |

A trial on a Zero 2 W measured **32.9 characters a second at a 4 ms delay** —
within rounding of the 15 ms floor, and *slower* than the 8 ms step in the same
run.  Below roughly 12 ms the setting has stopped being what limits the device,
so the last two steps mostly raise the risk of dropped characters for nothing.

If a device must go faster than ~40 characters a second, the delay is the wrong
lever: see *Halving the reports* below.

The floor is the **BLE connection interval** the host negotiates: a
notification cannot be delivered faster than one interval, and Windows
commonly settles at 7.5–15 ms.  Below that, reports queue and the stack may
drop or reorder them, which shows up as missing or transposed characters —
much worse than slow.

**How to tune it safely**

Use **Debug → Typing speed trial** on the dashboard.  It types the same
known sentence at each speed in turn, labelled with the speed that produced
it, times each one, and puts the saved setting back when it finishes.  The PC
stays connected throughout.

Then read what arrived on the PC.  Keep the **lowest** speed whose text is
perfect and choose it in Settings → Typing speed.  The timings alone do not
decide it: every speed is faster than the one above it, and the failure mode
is dropped or transposed characters, which only reading the text reveals.
For a production device, go one step back from the fastest that worked.
**Typing, per character** on the Performance panel confirms what you got.

An earlier version of this file named `/etc/default/bt_hid_ble` here.  Nothing
reads that file: `bt_hid_ble.service` has
`EnvironmentFile=-/opt/ipr_common.env`, and the leading `-` means a missing
file is not an error — so editing the wrong path changed nothing, silently.
To change the boot default by hand:

```bash
# on the device.  Only needed for the DEFAULT: the dashboard is the normal
# route and needs no restart.
sudo sed -i 's/^BT_KEY_DELAY_MS=.*/BT_KEY_DELAY_MS=12/' /opt/ipr_common.env \
  || echo 'BT_KEY_DELAY_MS=12' | sudo tee -a /opt/ipr_common.env
sudo systemctl restart bt_hid_ble.service   # this drops the BLE link
```

## What else is worth doing

- **`PollIntervalSeconds`** (default 1 s) sets up to a second of detect
  latency.  It is only worth lowering if `poll_scan_ms` is comfortably under
  it — on MTP a listing can cost hundreds of milliseconds, and polling faster
  than the listing takes just burns the single core.
- **Deleting after send** costs an MTP round trip, but happens after the text
  has been typed, so it does not add to what the user waits for.
- **A long scan is one send.**  There is no chunking, so the first character
  appears after stages 1–3 and the rest stream at the typing rate.  If the
  *first* character is slow, look at stages 1–2; if the *rest* is slow, it is
  stage 4 and nothing else.

## `send_ms` measured the wrong thing

Worth knowing when reading older numbers: `bt_kb_send.sh` hands the text to the
daemon's FIFO and returns at once, so `send_ms` timed **the enqueue**, not the
transmission — the one part of the chain that is instant.  A send therefore
looked finished in milliseconds while the host was still receiving characters,
the panel showed no progress, and the dashboard could not show where the time
went.

The daemon now publishes its progress (`/run/ipr_bt_progress.json`, rewritten
at most every 200 ms) and the application waits for it, so `queue_wait_ms` and
`type_ms` measure the two real stages.  `type_ms_per_char` is the number to
watch: it is what `BT_KEY_DELAY_MS` moves.

A daemon that publishes nothing — an older one — simply leaves the application
behaving as before; progress reporting can never make a send hang.

## Measured on a Zero 2 W

Two sends on 3 October 2026, one BLE host connected.  The device was running
`BT_KEY_DELAY_MS=12`, **not** the 20 ms default — worth stating, because the
figures only make sense against the right setting:

| Stage | Measured |
|---|---|
| `queue_wait_ms` | ~200 ms — the text is typed from the next radio slot |
| `type_ms` | 10.0 s for 397 characters, 6.2 s for 250 |
| `type_ms_per_char` | **24.8 ms** at a 12 ms delay (two reports = 24 ms) |

So the model holds: 0.8 ms per character above the two HID reports, which is
the connection interval and the report itself.  Measured throughput was 39.5
characters a second against the 41.7 the table predicts for 12 ms.

At the **20 ms default** that is 25 characters a second, so a 1 500-character
page takes about **60 s**; at 12 ms about 37 s, and at 8 ms about 24 s.  The
delay is the only part of the chain worth tuning.

## A measurement must not be able to cost a scan

`record_typing` appended to three KPI keys that were never added to `KPIS`.
`_samples` is built from `KPIS` alone, so it raised `KeyError` — *after* the
text had been typed, which put the raise between the typing and
`transmission.set_success()`.  The scan was typed correctly, then reported as
failed and left on the pen looking undelivered.

Two guards now: `tests/test_metrics.py` calls every recorder and requires the
keys to exist, and the call in `bluetooth/keyboard.py` is wrapped so a metrics
fault is logged and the send still completes.  Anything added to the recording
path belongs behind both.

## Two writers, one file

The application re-applies `TypingDelayMs` to `/run/ipr_bt_key_delay` on every
loop iteration, roughly once a second.  The Debug trial sets a speed per step.
Those fought, and the loop won: each step's choice survived less than a second,
so the whole ladder was typed at the configured speed and every row measured
the same thing:

| Speed set | Expected | Measured |
|---|---|---|
| 20 ms | 25/s | 34.2/s |
| 12 ms | 41.7/s | 34.0/s |
| 8 ms | 62.5/s | 34.9/s |
| 4 ms | 125/s | 37.9/s |

The 20 ms row is the tell: 34/s is **faster** than that setting can go, since
two 20 ms sleeps per character cap it at 25/s.  A measurement above its own
ceiling means the setting was not in force.

The trial now takes an expiring hold that the main loop honours; Settings overrides it, because that is the user speaking.
The hold expires on its own, so a request that dies mid-trial cannot leave the
device at a speed nobody chose.

The hold lives in **`/dev/shm`**, not `/run`.  The first attempt put it in
`/run`, where it could not be created at all: that directory is `root:root`,
and the application can write `/run/ipr_bt_key_delay` only because the daemon
creates that file and chowns it.  So the hold silently failed, the main loop
went on resetting the speed between steps, and a second run produced the same
four-identical-rows result:

```
19:28:46  Typing delay set to 20 ms   <- the trial's step
19:28:46  Typing delay set to 12 ms   <- the main loop, the same second
19:29:14  Typing delay set to 8 ms
19:29:15  Typing delay set to 12 ms
```

A failed hold is now a warning rather than a debug line, and the trial
**refuses to run** without one: measuring one speed four times while reporting
four is worse than not measuring.

The rates were wrong a second way: they divided by the characters the 100 ms
poll *observed*, and a whole drain can begin and end between two polls -- a
blank line is one character and takes about 25 ms.  That undercounted every
row and marked them all "incomplete".  Rates now divide by the characters
actually sent; the observed count is kept for diagnosis only.

## Halving the reports — the one real optimisation left

The device sends **two** notifications per character: the key pressed, then all
keys released.  A HID keyboard report carries the *set* of keys currently down,
so for "ab" the host is equally happy with press-a, press-b (a is released by
its absence from the second report), release.  That is *n + 1* reports instead
of *2n* — close to **double** the throughput at the connection-interval floor,
which no delay setting can buy.

Repeated characters are the exception: "aa" needs an empty report between the
two, or the host sees one keypress.  Auto-repeat behaviour would need checking
on every host that matters, and a host that mis-handles it would drop or double
characters, so this is not a change to make without a measured trial on each
target PC.  The trial on the Debug screen is the place to prove it.

## Still not measured

- **The negotiated connection interval** — knowing it would turn the delay
  tuning above from trial and error into arithmetic.  It is readable from
  `btmon` during a connection, and `floor_chars_per_second()` in
  `keydelay.py` turns it into the ceiling.

## Reading the numbers

`MetricsEnabled` must be on (dashboard → Settings).  The dashboard shows count,
mean, p50 and p95 per metric; p95 is the one to judge, since a single slow MTP
round trip skews the mean.  `scripts/perf/perf_report.py` prints the same
figures from the command line, and `scripts/perf/perf_e2e_latency.sh` drives an
end-to-end measurement.
