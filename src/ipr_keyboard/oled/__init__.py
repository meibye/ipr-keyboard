"""OLED status display (SSD1306 128x64 over I2C).

See docs/architecture/oled-display-design.md.  ``manager.OledManager`` is the
only entry point main.py needs; ``screens`` is pure data, ``render`` needs
Pillow, ``ssd1306`` talks to /dev/i2c-N with the standard library.
"""
