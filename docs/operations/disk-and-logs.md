# Disk and logs — does anything need cleaning up?

**Short answer: no automatic cleanup is needed, and adding one would be the
wrong fix.** Everything on the device that grows is already bounded. This page
records what was measured, so the question does not have to be re-opened from
scratch, and names the one thing that is not bounded.

Measured on the production Zero 2 W on 3 October 2026, after provisioning and
a day of testing.

## What is on the card

```
/dev/mmcblk0p2   29G   2.8G used   25G free   10%
```

## Everything that grows, and what bounds it

| What | Size now | Bound | Set by |
|---|---|---|---|
| systemd journal | 25 MB | **64 MB**, and 1 month | `SystemMaxUse=64M`, `MaxRetentionSec=1month` |
| `logs/ipr_keyboard.log` | 48 KB | **1.5 MB** (256 KB × 6) | `RotatingFileHandler` in `ipr_keyboard/logging/logger.py` |
| `pen_state.json` (delivery log) | 264 B | ~45 KB | `MAX_KEYS_PER_FOLDER = 1000` in `delivery.py` |
| Performance KPIs | in RAM | 200 samples per metric | `_MAXLEN` in `metrics.py` |
| Scans on the pen | — | deleted after delivery | `DeleteFiles` |
| `/opt/ipr_state` (provisioning reports) | 204 KB | written once per provisioning run | — |
| `/var/cache/apt/archives` | **57 MB** | **nothing** | — |

The journal is the one that would have been a problem, and it was capped during
provisioning. At 64 MB it cannot crowd out anything on a card this size.

## The one unbounded item: the apt cache

`/var/cache/apt/archives` keeps every `.deb` that has been installed or
upgraded, and nothing ever removes them. It is 57 MB after one provisioning
run and grows with every `apt upgrade`.

This is not urgent — 57 MB is 0.2 % of the card — but it is pure waste, it is
the only thing here with no ceiling, and clearing it costs nothing. Provisioning
therefore ends with `apt-get clean`. On a device that has been upgraded a few
times since:

```bash
sudo apt-get clean          # drops the downloaded .deb files
sudo journalctl --vacuum-time=7d   # only if you want the journal smaller now
```

Neither is needed on a schedule.

## Why not a cleanup timer

A timer would be a service to install, start, monitor and get wrong, standing
guard over about 60 MB on a 29 GB card where the only genuinely unbounded
consumer is an apt cache that one line of provisioning removes. It would also
hide the real signal: if disk use ever does climb, that is a *fault* to
diagnose — a log loop, a stuck mount, scans that are no longer being deleted —
and a timer quietly deleting the evidence makes it harder to find.

The dashboard already shows disk use on the Home screen, amber above 75 % and
red above 90 %, which is the warning that matters.

## If the disk does fill up

In order of likelihood:

1. **Scans not being deleted** — check `DeleteFiles` in Settings, and that the
   pen is still mounted (`systemctl status irispen-mount.service`). An
   unmounted pen means `/mnt/irispen` writes land on the SD card instead.
2. **A log loop** — `journalctl --disk-usage` then
   `journalctl -p err --since -1h`; a service restarting in a tight loop can
   write a lot inside the cap, and the cap means the *older* evidence is what
   gets lost.
3. **The apt cache** — `sudo apt-get clean`.
4. **A smaller card.** All of the above is comfortable on 8 GB too, but there
   is much less headroom for anything unexpected; 16 GB or more is the
   recommendation.
