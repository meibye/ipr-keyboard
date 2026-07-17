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

When the hotspot starts, the LED on the device turns **solid blue**.

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

**Step 5 — When done**

Hold the magnet near the reed switch for 3 seconds again to turn off the
hotspot.  The LED returns to its normal colour.  Alternatively, use the
Reboot button on the System page — the hotspot does not restart automatically.

---

### Option 2 — Via the main dashboard (requires home network)

If the device is already connected to your home network, you can reach the
setup pages directly from the main dashboard without activating the hotspot.

1. Open the main dashboard and sign in as an administrator.
2. Click **Setup** in the navigation bar.
3. You are taken directly to the setup home page — no second login required.
4. When done, click **← Dashboard** to return.

---

## LED status indicator

The small LED on the device shows the current state whenever you bring the
magnet near (or for 30 seconds after activating the hotspot).

| LED colour | Meaning |
|------------|---------|
| Off | Device running normally, no action needed |
| Green solid | WiFi connected and Bluetooth paired — all good |
| Amber solid | WiFi connected, waiting for Bluetooth |
| Red blinking | No WiFi connection — setup needed |
| Blue solid | Hotspot active — you can connect |
| White blinking | Device is starting up |

---

## Activating the hotspot without a magnet

### Triple power-cycle method

If the magnet is not available:

1. Turn the device off (unplug power or use the Shutdown button if accessible).
2. Turn it back on.
3. Wait for the startup blink (white LED) to finish — about 5 seconds.
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

## Factory reset (WiFi only)

A factory reset deletes all saved WiFi profiles.  Use this when you are
moving the device to a completely different network and want a clean start.

**Hold the magnet in place for 10 seconds.**

- At 3 seconds the LED turns blue fast-blink (hotspot arm threshold).
- At 10 seconds the LED turns **red fast-blink** — this is the reset threshold.
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
