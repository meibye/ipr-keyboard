# GPIO Wiring — Reed Switch and RGB LED

Hardware guide for the Pi Zero 2 W in a Flirc aluminium case.
The onboard ACT LED is not visible through the case; the external RGB LED
is the sole visual indicator.

---

## Components

| Component | Value / type | Notes |
|-----------|-------------|-------|
| Reed switch | Normally-Open (NO), any voltage rating | SMD or THT; 3 × 1.5 mm SMD or 14 × 2 mm THT glass tube |
| Small neodymium magnet | 5–10 mm disc or bar | Stored near the device; brought close to trigger |
| RGB LED | 5 mm common-cathode | R/G/B on separate anodes, one shared GND leg |
| Resistor — R leg | 150 Ω | Limits current on red element |
| Resistor — G leg | 150 Ω | Limits current on green element |
| Resistor — B leg | 22 Ω | Blue element has higher Vf, needs lower resistance |

**Temporary test rig** (use until RGB LED arrives):
three separate LEDs — red, yellow (green substitute), blue — each with its
own cathode wire to GND.  The blue resistor is still 22 Ω; red and yellow
use 150 Ω.  Software behaviour is identical; yellow maps to the "green" states.

---

## Pin assignments (BCM numbering)

| Signal | BCM | Physical pin | Notes |
|--------|-----|-------------|-------|
| Reed switch | **GPIO 27** | Pin 13 | Pull-up enabled in software |
| RGB LED — Red | **GPIO 22** | Pin 15 | 150 Ω series |
| RGB LED — Green | **GPIO 23** | Pin 16 | 150 Ω series |
| RGB LED — Blue | **GPIO 24** | Pin 18 | 22 Ω series |
| Factory reset (existing) | GPIO 17 | Pin 11 | Do not reuse |

All five signals are in the safe zone — no conflicts with I²C (GPIO 2/3),
UART (GPIO 14/15), or SPI (GPIO 7–11).

---

## Schematic

```
3.3 V supply
    │
    └─ internal pull-up (software)
             │
          GPIO 27 ──────────[Reed Switch]────── GND
             (Pin 13)         (NO type)

GPIO 22 ──[150 Ω]──┬── R anode   ┐
(Pin 15)            │             │
GPIO 23 ──[150 Ω]──┼── G anode   ├── Common cathode ── GND
(Pin 16)            │             │
GPIO 24 ──[ 22 Ω]──┴── B anode   ┘
(Pin 18)
```

For the **test rig** (three separate LEDs):

```
GPIO 22 ──[150 Ω]── Red LED   (+) ── Red LED   (−) ──┐
GPIO 23 ──[150 Ω]── Yellow LED(+) ── Yellow LED(−) ──┼── GND
GPIO 24 ──[ 22 Ω]── Blue LED  (+) ── Blue LED  (−) ──┘
```

---

## Resistor value rationale

| LED | Typical Vf | Supply | Formula | Result | Use |
|-----|-----------|--------|---------|--------|-----|
| Red | 2.0 V | 3.3 V | (3.3 − 2.0) / 0.009 | 144 Ω | 150 Ω |
| Green | 2.1 V | 3.3 V | (3.3 − 2.1) / 0.008 | 150 Ω | 150 Ω |
| Yellow | 2.1 V | 3.3 V | (3.3 − 2.1) / 0.008 | 150 Ω | 150 Ω |
| Blue | 3.0 V | 3.3 V | (3.3 − 3.0) / 0.0136 | 22 Ω | 22 Ω |

GPIO pins on Pi Zero 2 W are rated for a maximum of 16 mA per pin.
Red and green run at 8–9 mA; blue runs at about 13.6 mA at typical Vf.
All three stay within the limit.

**Blue is the marginal channel.** Only about 0.3 V is left across its
resistor after the LED's forward drop, so part-to-part Vf spread moves the
current more than the resistor value does:

| Blue Vf | Voltage across 22 Ω | Current |
|---------|---------------------|---------|
| 2.9 V | 0.4 V | 18.2 mA — **over the 16 mA limit** |
| 3.0 V (typical) | 0.3 V | 13.6 mA |
| 3.1 V | 0.2 V | 9.1 mA |
| 3.2 V | 0.1 V | 4.5 mA — safe but dim |

Do not fit a resistor below 22 Ω: on a unit with below-typical Vf the pin
would already exceed its 16 mA rating.  If blue still looks dim, measure the
actual Vf before changing the resistor, and prefer trimming the other two
channels' PWM duty cycle to rebalance the composite colours instead.

---

## Physical placement in the Flirc case

The Flirc Pi Zero 2 W case is a sealed aluminium shell; the GPIO header
protrudes from one end.  Recommended approach:

1. Mount the reed switch inside the case or along the GPIO breakout PCB,
   positioned close to one edge of the aluminium shell so the external
   magnet can activate it through the thin wall (≤ 3 mm aluminium passes
   the field of a 6–10 mm neodymium magnet).
2. Mount the LED(s) on a small breakout PCB connected via a short ribbon to
   the GPIO header, visible through a small hole (3 mm drill) in the top or
   side of the case.
3. Store the trigger magnet on a small adhesive patch on the back of the
   case or on the cable management area.

---

## LED colour map

| Colour | Pattern | Meaning |
|--------|---------|---------|
| White | Fast blink (4 Hz, 3 s) | Device starting up |
| Green | Solid | All OK — WiFi connected and Bluetooth paired |
| Amber / Yellow | Solid | WiFi connected, Bluetooth not yet connected |
| Red | Slow blink (1 Hz) | No WiFi / no home network configured |
| Blue | Solid | Management hotspot is active (setup mode) |
| Blue | Fast blink | Hotspot arming — reed held ≥ 3 s |
| Red | Fast blink | Factory reset arming — reed held ≥ 10 s |
| Off | — | Idle — no power draw |

---

## Reed switch interaction

| Action | Duration | Result |
|--------|----------|--------|
| Bring magnet near (tap) | < 3 s | LED wakes and shows status for 30 s |
| Hold magnet in place | ≥ 3 s | LED turns blue fast-blink; release to toggle hotspot |
| Hold magnet in place | ≥ 10 s | LED turns red fast-blink; release to factory-reset |

The LED changes colour at the 3 s and 10 s thresholds so the user knows
exactly which action will fire before releasing the magnet.

---

## Software configuration

GPIO pin assignments and LED idle timeout are stored in `config.json`:

```json
{
  "GpioEnabled": true,
  "GpioReedPin": 27,
  "GpioLedRPin": 22,
  "GpioLedGPin": 23,
  "GpioLedBPin": 24,
  "GpioLedIdleSeconds": 30
}
```

Set `GpioEnabled: false` to disable GPIO monitoring on development machines
that lack RPi.GPIO.  The module also silently disables itself when RPi.GPIO
cannot be imported, so no code change is needed for non-Pi hosts.

---

## Migrating from test rig to final RGB LED

When the common-cathode RGB LED arrives:

1. Desolder the three individual LEDs.
2. Wire the new RGB LED: anode R → GPIO 22 via 150 Ω, anode G → GPIO 23 via
   150 Ω, anode B → GPIO 24 via 22 Ω, common cathode → GND.
3. No software change required — GPIO pin assignments are identical.
