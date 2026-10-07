#!/usr/bin/env bash
#
# ipr_led_boot.sh — blink the status LED white while the OS boots
#
# Runs from ipr-led-boot.service (early, as root) until ipr_keyboard.service
# starts and stops it via Conflicts=.  Pin numbers come from
# /etc/default/ipr-led (written by install_gpio_support.sh from config.json)
# and fall back to the documented defaults.
#
# Prefers `gpioset --toggle` from the gpiod package (one long-lived process,
# no polling).  Falls back to a shell loop over `pinctrl` (raspi-utils) when
# gpiod is missing.  Both are stopped cleanly by SIGTERM.
#
# category: Headless
# purpose: Early-boot white blink on the RGB status LED
# sudo: yes

set -u

LED_R=22
LED_G=23
LED_B=24
BLINK_MS=125          # 4 Hz
GPIOCHIP=gpiochip0

if [[ -r /etc/default/ipr-led ]]; then
  # shellcheck source=/dev/null
  source /etc/default/ipr-led
fi

# On a Pi Zero / Zero 2 the header GPIOs live on gpiochip0 with offset == BCM
# number.  Wait briefly for the device node if we were started very early.
for _ in $(seq 1 20); do
  [[ -e "/dev/${GPIOCHIP}" ]] && break
  sleep 0.25
done

if command -v gpioset >/dev/null 2>&1; then
  exec gpioset --toggle "${BLINK_MS}ms" --chip "${GPIOCHIP}" \
    "${LED_R}=1" "${LED_G}=1" "${LED_B}=1"
fi

if command -v pinctrl >/dev/null 2>&1; then
  trap 'pinctrl set "${LED_R},${LED_G},${LED_B}" op dl; exit 0' TERM INT
  while :; do
    pinctrl set "${LED_R},${LED_G},${LED_B}" op dh
    sleep "0.${BLINK_MS}"
    pinctrl set "${LED_R},${LED_G},${LED_B}" op dl
    sleep "0.${BLINK_MS}"
  done
fi

echo "ipr_led_boot: neither gpioset nor pinctrl found — no boot LED" >&2
exit 0
