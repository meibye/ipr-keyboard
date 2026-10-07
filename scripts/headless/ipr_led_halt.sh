#!/usr/bin/env bash
#
# ipr_led_halt.sh — turn the status LED off at the very end of a shutdown
#
# Runs from ipr-led-halt.service (ExecStop, late in the shutdown sequence).
# The application leaves the LED white when it is stopped for a shutdown;
# once this has run the LED is dark and the device may be unplugged.
# Uses pinctrl (pokes the registers, nothing to keep alive) and falls back
# to gpioset with a short hold.  Also blanks the OLED status display
# (SSD1306 DISPLAYOFF, 0xAE) so the panel is dark when power is cut.
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

# OLED off (install_oled_support.sh writes /etc/default/ipr-oled).
OLED_BUS=1; OLED_ADDR=0x3c
if [[ -r /etc/default/ipr-oled ]]; then
  # shellcheck source=/dev/null
  source /etc/default/ipr-oled
fi
if [[ -c "/dev/i2c-${OLED_BUS}" && -x /usr/sbin/i2cset ]]; then
  /usr/sbin/i2cset -y "${OLED_BUS}" "${OLED_ADDR}" 0x00 0xAE 2>/dev/null || true
fi
exit 0
