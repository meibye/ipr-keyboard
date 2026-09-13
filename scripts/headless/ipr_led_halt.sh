#!/usr/bin/env bash
#
# ipr_led_halt.sh — turn the status LED off at the very end of a shutdown
#
# Runs from ipr-led-halt.service (ExecStop, late in the shutdown sequence).
# The application leaves the LED cyan when it is stopped for a shutdown;
# once this has run the LED is dark and the device may be unplugged.
# Uses pinctrl (pokes the registers, nothing to keep alive) and falls back
# to gpioset with a short hold.
#
# category: Headless
# purpose: LED off as the "safe to unplug" signal at shutdown
# sudo: yes

set -u
LED_R=22; LED_G=23; LED_B=24
if [[ -r /etc/default/ipr-led ]]; then
  # shellcheck source=/dev/null
  source /etc/default/ipr-led
fi
if command -v pinctrl >/dev/null 2>&1; then
  pinctrl set "${LED_R},${LED_G},${LED_B}" op dl
elif command -v gpioset >/dev/null 2>&1; then
  gpioset --hold-period 200ms -c gpiochip0 "${LED_R}=0" "${LED_G}=0" "${LED_B}=0"
fi
exit 0
