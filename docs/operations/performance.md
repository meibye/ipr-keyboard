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

The delay is now `BT_KEY_DELAY_MS` (default 20, unchanged), set in
`/opt/ipr_common.env` — the file `bt_hid_ble.service` already reads — and
picked up when the daemon restarts.  Lower it by
measurement, not by hope:

| Value | Characters/s | Note |
|---|---|---|
| 20 ms | 25 | the historical default |
| 12 ms | 42 | comfortably above a typical 7.5–15 ms connection interval |
| 8 ms | 62 | at or below some hosts' interval; verify no dropped characters |
| 4 ms | 125 | expect loss — the host cannot acknowledge that fast |

The floor is the **BLE connection interval** the host negotiates: a
notification cannot be delivered faster than one interval, and Windows
commonly settles at 7.5–15 ms.  Below that, reports queue and the stack may
drop or reorder them, which shows up as missing or transposed characters —
much worse than slow.

**How to tune it safely**

```bash
# on the device
sudo sed -i 's/^BT_KEY_DELAY_MS=.*/BT_KEY_DELAY_MS=12/' /etc/default/bt_hid_ble \
  || echo 'BT_KEY_DELAY_MS=12' | sudo tee -a /etc/default/bt_hid_ble
sudo systemctl restart bt_hid_ble.service
```

Then scan a page of known text, at each value, and check the result character
for character.  Keep the lowest value that is still perfect over ten scans,
then add one step back for margin.  **Typing, per character** on the
dashboard's Performance panel confirms what you actually got.

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

Two 250-character scans on 3 October 2026, `BT_KEY_DELAY_MS=20`, one BLE host
connected:

| Stage | Measured |
|---|---|
| `queue_wait_ms` | ~200 ms — the text is typed from the next radio slot |
| `type_ms` | 10.0 s for 397 characters, 6.2 s for 250 |
| `type_ms_per_char` | **24.8 ms** against a 20 ms configured delay |

The 4.8 ms above the configured delay is the two HID reports per character plus
the connection interval, so the delay is the only part worth tuning and the
table in *What dominates* holds.  At the default, a page of 1 500 characters
takes about 37 s; at 12 ms it would take about 22 s.

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

## Still not measured

- **The negotiated connection interval** — knowing it would turn the delay
  tuning above from trial and error into arithmetic.  It is readable from
  `btmon` during a connection.

## Reading the numbers

`MetricsEnabled` must be on (dashboard → Settings).  The dashboard shows count,
mean, p50 and p95 per metric; p95 is the one to judge, since a single slow MTP
round trip skews the mean.  `scripts/perf/perf_report.py` prints the same
figures from the command line, and `scripts/perf/perf_e2e_latency.sh` drives an
end-to-end measurement.
