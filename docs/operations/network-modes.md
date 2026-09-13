# Network exposure — production and development mode

Date: 13 September 2026.  Applies to all devices from this change on
(`ipr-prod-zero2` verified).  See also `docs/hardware/gpio-wiring.md` (magnet
gestures, LED) and `docs/architecture/led-status-design.md`.

---

## 1. Analysis — what the device exposed before this change

Measured on a provisioned Pi Zero 2 W with `ss -ltnup`:

| Port | Proto | Service | Listening on | Home network | Hotspot |
|---|---|---|---|---|---|
| 22 | TCP | `sshd` | all interfaces | **open** | **open** |
| 443 | TCP | `ipr_keyboard.service` (dashboard + setup portal) | all interfaces | **open** | **open** |
| 5353 | UDP | `avahi-daemon` (mDNS, `<host>.local`) | all interfaces | open | open |
| 53 | UDP/TCP | `dnsmasq` started by NetworkManager for the shared connection | `10.42.0.1` | — | open |
| 67 | UDP | `dnsmasq` DHCP server for hotspot clients | `10.42.0.1` | — | open |

No packet filter was installed (`nftables` package present, no ruleset), so
every listener was reachable from any host on the same network, at all
times.  For a device in a critical environment that is the wrong default:

- SSH (22) is only needed by an administrator, and only occasionally.
- The dashboard (443) on the home network is a convenience; the setup portal
  on the hotspot is the designed maintenance path.
- mDNS (5353) advertises the device name to the whole network.
- DNS (53) on the hotspot is not needed: clients reach the portal by IP
  (`https://10.42.0.1/setup/`).  **DHCP (67) is needed** — without it a phone
  cannot obtain an address on the hotspot at all.  The original request
  named ports 22, 53 and 443 on the hotspot; 53 was DNS, and the address
  hand-out that actually matters is 67, which this design keeps.

Bluetooth (HID over GATT) is not IP traffic and is unaffected by any of this.

## 2. Requirements

1. Ports are opened only on user request.
2. **Production mode** (the normal state): no port reachable on any network.
   When the hotspot is active, only the setup portal (443) on the hotspot.
3. **Development mode**: SSH (22) and the dashboard (443) reachable — on the
   home network and on the hotspot.
4. The mode is switched with the magnet, and the LED shows it.
5. The device must not lock the administrator out during provisioning.

## 3. Design

### 3.1 Policy

One nftables table, `inet ipr_fw`, input chain with **policy drop**, rebuilt
by `/usr/local/sbin/ipr-firewall.sh apply` from two facts: the mode file and
whether the `ipr-hotspot` NetworkManager connection is active.

| | Home network | Hotspot (`wlan0`, from `10.42.0.0/24`) |
|---|---|---|
| **production** | nothing | TCP 443 (setup portal), UDP 67 (DHCP) |
| **development** | TCP 22, TCP 443, UDP 5353 (mDNS) | TCP 22, TCP 443, UDP 67 |

Always accepted: loopback; established/related replies to the device's own
outbound connections (apt, NTP, the app's own health poll); ICMP and ICMPv6
(path MTU, IPv6 neighbour discovery); DHCP *client* replies (UDP 67→68) so
the device can join the home network.  Outbound traffic is not filtered.
DNS 53 is never opened.

Rule order: the service ports (22, 443, 5353) are decided *before* the
generic "established" accept.  In production, packets of sessions that were
already open on 22/443 are answered with a **TCP reset** (the remote SSH
client prints "Connection reset by peer" immediately), while new connection
attempts are **dropped silently** (no reply, the device stays invisible to a
port scan).  Conntrack would otherwise have kept open sessions alive until
they closed by themselves — the first version of the rules had the
established accept first and an open SSH session survived the switch; a
plain drop of the established packets then left the session *hanging* rather
than closed, which looked like "SSH did not drop" until a command was typed.

Even the reset rule only answers packets that *arrive*, so a quiet session
would live until the client's next keystroke or keepalive.  `ipr_mode_ctl.sh
production` therefore also destroys the device's own sockets on 22/443
(`ss -K`, kernel sends the RST; outbound is unfiltered) and terminates the
`sshd` session processes — the remote terminal sees "Connection reset by
peer" immediately.

`nft -f` loads the table atomically; a syntax error leaves the previous table
in force rather than opening everything.  If `nft` is missing the script
exits non-zero and says so — phase L of `test_provision.sh` catches it.

### 3.2 When the policy is (re)applied

| Trigger | Mechanism |
|---|---|
| Boot, before any interface is up | `ipr-firewall.service` (`DefaultDependencies=no`, `Before=network-pre.target`) |
| Any connection up/down (hotspot start/stop, home Wi-Fi reconnect) | NetworkManager dispatcher hook `/etc/NetworkManager/dispatcher.d/90-ipr-firewall` |
| Hotspot start/stop | `ipr-provision.sh` also calls `apply` directly, so the portal port opens the moment the AP is up |
| Mode change | `ipr_mode_ctl.sh` calls `apply` |

### 3.3 The mode

`/var/lib/ipr-keyboard/mode` contains `production` or `development`
(anything else, or no file, counts as production).  World-readable so the
application can show it (LED heartbeat, setup portal).

```
sudo ipr_mode_ctl.sh production
sudo ipr_mode_ctl.sh development
sudo ipr_mode_ctl.sh toggle
sudo ipr_mode_ctl.sh status       # prints the mode; exit 0 = production, 3 = development
sudo ipr-firewall.sh status       # mode, hotspot, loaded rules
```

The mode persists across reboots.  Switching to production over an SSH
session on the home network ends that session within a few seconds —
intentionally.

### Seeing the hotspot state in production mode

SSH is closed in production, so the ways to tell whether the hotspot is up
are the physical and the client-side ones:

- **LED solid blue** — the hotspot is up (it stays blue for as long as it
  is; a tap of the magnet does not change it).  Any other colour, or off
  with no reaction beyond the status colour on a tap: hotspot is down.
- The SSID `ipr-setup-xxxx` is visible in a phone's Wi-Fi list.
- The setup portal's *Status* page (`https://10.42.0.1/setup/status`)
  shows the hotspot as *up* — read from NetworkManager, not from the unit.
- After switching to development mode: `sudo ipr-firewall.sh status`.

### Testing the LED in development mode

1. Switch to development (magnet 6 s → purple blink → release → solid
   purple 3 s).  From then on the LED gives a short **purple blip every
   4 s**, also while it is otherwise off.  No blip = production.
2. Tap the magnet: status colour for 30 s, the purple blip continues on top.
3. From another machine `ssh` to the device and open the dashboard — both
   work in development, both time out in production.
4. `sudo ipr-firewall.sh status` (over that SSH session) prints the mode,
   the hotspot state and the loaded rules; `sudo ipr_mode_ctl.sh status`
   prints the mode alone.
5. Switch back with the magnet (6 s): the SSH session dies within seconds
   and the blip stops.

### 3.4 Magnet and LED

The hold ladder gains a step; the existing 3 s and 10 s gestures are
unchanged:

| Hold | LED while held | On release |
|---|---|---|
| < 3 s (tap) | status colour | status for 30 s |
| ≥ 3 s | blue fast blink | hotspot on/off |
| **≥ 6 s** | **purple fast blink** | **mode toggle**; LED solid purple 3 s to confirm, then status |
| ≥ 10 s | red fast blink | Wi-Fi reset + reboot |

In **development mode** the LED gives a short purple blip every 4 s — on top
of whatever it otherwise shows, including "off" — so an open device cannot go
unnoticed.  No blip in production mode.

The setup portal home page shows the mode next to the hostname.

### 3.5 Provisioning and commissioning

`install_firewall.sh` (run by `provision/04_enable_services.sh` and
`deploy_full_update.sh`) seeds the mode file as **development** when it does
not exist, because provisioning runs over SSH and production mode would cut
that session before the administrator is done.  Commissioning therefore ends
with:

```
sudo ipr_mode_ctl.sh production        # or: hold the magnet 6 s
```

`test_provision.sh` warns while a device is still in development mode.

### 3.6 Consequences to be aware of

- In production mode the **dashboard is not reachable on the home network**.
  Users who relied on `https://<host>.local/` must either use the setup
  portal over the hotspot, or the administrator puts the device into
  development mode with the magnet for the duration of the work.
- `<host>.local` (mDNS) does not resolve in production mode; the pinned IP in
  `~/.ssh/config` is irrelevant there too, since SSH is closed.
- Hotspot clients get no DNS; a phone may report "no internet" on the
  hotspot.  That is true and harmless — the portal is reached by IP.
- The dashboard's *own* health poll (`127.0.0.1:443`) and the LED boot
  hand-over are on loopback and unaffected.
- `Restart`/`Shutdown` in the portal, and `apt`, `git` etc. initiated from
  the device keep working (outbound is open, replies are established).

## 4. Alternatives considered

- **Stop the listeners instead of filtering** (mask `sshd`, bind the
  dashboard to `10.42.0.1` only): needs service restarts on every mode/hotspot
  change and still leaves avahi and dnsmasq; a filter is simpler and
  uniform.
- **`ufw`/`firewalld`**: extra packages and daemons on a Zero W; nftables is
  already installed and one table is enough.
- **Time-limited development mode** (auto-revert after N hours): tempting for
  a critical environment, but an administrator mid-way through an update
  losing SSH is worse.  The purple heartbeat makes an open device visible;
  revisit if devices are found left in development mode.
- **Web toggle for the mode**: deliberately not offered.  The mode is a
  physical decision (magnet at the device) or an SSH decision by someone who
  already has access.

## 5. Files

| Area | Files |
|---|---|
| Firewall | `scripts/headless/ipr_fw_ctl.sh` → `/usr/local/sbin/ipr-firewall.sh`, `ipr-firewall.service`, `90-ipr-firewall` (dispatcher) |
| Mode | `scripts/headless/ipr_mode_ctl.sh` → `/usr/local/bin/ipr_mode_ctl.sh`, sudoers `/etc/sudoers.d/<user>-ipr-mode`, `/var/lib/ipr-keyboard/mode` |
| Installer | `scripts/headless/install_firewall.sh` (from `provision/04_enable_services.sh`, `deploy_full_update.sh`) |
| Hotspot | `scripts/headless/net_provision_hotspot.sh` calls `apply` on start/stop |
| Application | `src/ipr_keyboard/gpio_monitor.py` (6 s gesture, purple, heartbeat), `web/setup.py` + `templates/setup/home.html` (mode display) |
| Validation | `scripts/headless/test_provision.sh` phase L |
