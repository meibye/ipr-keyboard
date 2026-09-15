# Using the IPR Keyboard Setup Interface

This page explains how to reach the device's setup screen to configure WiFi,
check status, view logs, and manage the device.

---

## Two ways to reach the setup screen

### Option 1 — Via the management hotspot (no home network needed)

Use this when the device has no WiFi connection, for example during initial
setup or after a WiFi password change.

**Step 1 — Activate the hotspot**

The hotspot is off by default to keep the device invisible.  Start it using
one of these methods:

| Method | When to use |
|--------|-------------|
| **Hold magnet near the reed switch for 3 seconds** | Normal use — magnet stored on or near the device |
| **Power-cycle the device 3 times within 2 minutes** | Magnet not available or device in an enclosure |
| **Create a file named `IPR_SETUP` on the SD card** | Last resort — requires a PC and SD card reader |

While you hold the magnet the LED blinks blue from the 3-second mark; release
it and the LED keeps blinking blue while the hotspot starts (a few seconds).
When the hotspot is up the LED turns **solid blue** and stays on until the
hotspot is stopped.  A short red flash means the hotspot could not start —
try again, or ask your administrator to check the device log.

**Step 2 — Connect your phone or laptop to the hotspot**

Open your WiFi settings and look for a network named `ipr-setup-xxxx`
(where xxxx is unique to your device).  The password is printed on the
device label, or you can find it on the setup home page after connecting.

**Step 3 — Open the setup page**

In your browser, go to: **http://10.42.0.1/setup/**

You may see a security warning (self-signed certificate).  To remove this
warning permanently, download and install the device's CA certificate from
**http://10.42.0.1/setup/ca.crt** — see the setup home page for instructions.

**Step 4 — Log in**

- Username: `ipr`
- Password: printed on the device label (or shown on the setup home page)

**Reaching the main dashboard over the hotspot**

Opening `https://10.42.0.1/` on the hotspot takes you to the *setup* login
on purpose.  For the main dashboard go to **`https://10.42.0.1/login`** and
sign in with a dashboard account (e.g. `admin`); `https://10.42.0.1/` then
shows the dashboard.  The setup home page shows this address too.

**Step 5 — When done**

Hold the magnet near the reed switch for 3 seconds again to turn off the
hotspot.  The LED blinks blue briefly and then shows the normal status
colour for 30 seconds before going off.  Alternatively, use the
Reboot button on the System page — the hotspot does not restart automatically.

---

**From the dashboard:** the home page's *Device* card shows the mode, whether
the hotspot is on, the network the device is on, and any recorded incidents;
administrators get *Start hotspot* / *Stop hotspot* buttons there.  Starting
it from the home network disconnects that page — reconnect via the hotspot.

### Option 2 — Via the main dashboard (requires home network and development mode)

The device normally runs in **production mode**, in which nothing is
reachable on the home network — not the dashboard, not SSH.  Only the
hotspot route above works then.  An administrator can put the device into
**development mode** (hold the magnet for 10 seconds — the LED turns solid purple,
release, and it lights solid purple for 3 seconds), after which the dashboard
and SSH are reachable on the home network.  In development mode the LED gives
a short purple blip every 4 seconds as a reminder; hold the magnet 10 seconds
again to return to production mode.  Details:
`docs/operations/network-modes.md`.

If the device is in development mode and connected to your home network, you
can reach the setup pages directly from the main dashboard without activating
the hotspot.

1. Open the main dashboard and sign in as an administrator.
2. Click **Setup** in the navigation bar.
3. You are taken directly to the setup home page — no second login required.
4. When done, click **← Dashboard** to return.

---

## LED status indicator

The small LED on the device shows the current state whenever you bring the
magnet near, for 30 seconds after the device has finished starting, and
for as long as the hotspot is on.

| LED colour | Meaning |
|------------|---------|
| Off | Device running normally, no action needed (also: dark while you hold the magnet, until a threshold is reached) |
| White solid | Power is on, the device is starting (first seconds) |
| White blinking | Device is starting up (about a minute) |
| Green solid | WiFi connected and Bluetooth paired — all good |
| Amber solid | WiFi connected, waiting for Bluetooth |
| Red blinking slowly | No WiFi connection — setup needed |
| Red solid | Something on the device is not running — power-cycle it; if it stays red, tell your administrator |
| Blue solid while you hold the magnet | 3 s reached — release to switch the hotspot on/off |
| Blue blinking | Hotspot is being switched on or off |
| Blue solid | Hotspot active — you can connect. The device is **not** on the home network while this is on |
| White solid while you hold | 6 s reached — release for a controlled shutdown |
| White solid | Shutting down — wait until the LED is off, then unplug |
| Purple solid while you hold | 10 s reached — release to switch production ↔ development mode |
| Purple solid (3 s) | Mode changed |
| Purple blip every 4 s | Development mode — SSH and dashboard are open on the network |
| Red solid while you hold | 15 s reached — release for the network reset |
| Red blinking fast | Network reset in progress — or a hotspot request failed |
| Off while holding | Magnet held 20 s — release does nothing (cancel) |

---

## Activating the hotspot without a magnet

### Triple power-cycle method

If the magnet is not available:

1. Turn the device off (unplug power or use the Shutdown button if accessible).
2. Turn it back on.
3. Wait until the white LED has been blinking for a few seconds (the boot
   is counted once the device has started booting; you do not need to wait
   for the colour).
4. Turn it off again.
5. Turn it back on again.
6. Repeat once more (off → on) within 2 minutes total.

After the third boot within the time window, the hotspot starts and the LED
turns blue.

### SD card marker method (last resort)

If power-cycling is not practical:

1. Power off the device and remove the SD card.
2. Insert the SD card into a PC or Mac — it appears as a drive named `bootfs`
   or `boot`.
3. Create an empty file named exactly `IPR_SETUP` in the root of that drive.
4. Eject the card, reinsert it, and power on the device.
5. The hotspot starts on this boot and the marker file is deleted automatically.

---

## Switching the device off

The device is normally powered from a PC's USB port.  Pulling the plug while
it is writing to its memory card can corrupt it, so use the magnet:

1. Hold the magnet in place: the LED is dark, turns **blue** after 3 s, then **white** after 6 s (each change begins with a short dark blink).
2. Release.  The LED turns solid white while the device shuts down.
3. When the LED goes **off** (10–20 seconds), it is safe to unplug.

To start it again, disconnect and reconnect the power.  (The Shutdown button
on the dashboard's Settings page does the same thing.)

## Factory reset (WiFi only)

A factory reset deletes all saved WiFi profiles.  Use this when you are
moving the device to a completely different network and want a clean start.

**Hold the magnet in place for 15 seconds.**

- At 3 seconds the LED turns solid blue (hotspot), at 6 s solid white (shutdown), at 10 s solid purple (mode) — each change begins with a short dark gap.
- At 15 seconds the LED turns **solid red** — this is the reset threshold.
- Holding past 20 seconds turns the LED off and cancels: release does nothing.
- Release the magnet to confirm.

The device deletes all WiFi profiles and reboots.  After reboot, activate
the hotspot and configure the new network from the setup WiFi page.

> **Note:** Factory reset only removes WiFi profiles.  Application settings,
> users, and logs are not affected.

---

## Setup pages reference

| Page | What you can do |
|------|----------------|
| **Home** | See device name, hotspot credentials, IP addresses |
| **Status** | Check which services are running and Bluetooth connections |
| **WiFi** | Scan for networks and save WiFi credentials |
| **Logs** | View recent log output from device services |
| **System** | Renew the SSL certificate, reboot, or shut down |
