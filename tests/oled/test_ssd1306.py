"""SSD1306 driver — I2C traffic captured, no hardware."""

import os

import pytest

from ipr_keyboard.oled import ssd1306 as drv


class FakeBus:
    """Monkeypatches os.open/os.write/os.close and fcntl.ioctl."""

    def __init__(self, monkeypatch, exists=True):
        self.writes: list[bytes] = []
        self.slave = None
        self.opened = 0
        self.closed = 0
        self.exists = exists

        def fake_open(path, flags):
            if not self.exists:
                raise FileNotFoundError(path)
            self.opened += 1
            return 42

        def fake_write(fd, data):
            assert fd == 42
            self.writes.append(bytes(data))
            return len(data)

        def fake_close(fd):
            self.closed += 1

        def fake_ioctl(fd, req, arg):
            assert req == drv.I2C_SLAVE
            self.slave = arg

        monkeypatch.setattr(os, "open", fake_open)
        monkeypatch.setattr(os, "write", fake_write)
        monkeypatch.setattr(os, "close", fake_close)
        fake_fcntl = type("F", (), {"ioctl": staticmethod(fake_ioctl)})
        monkeypatch.setattr(drv, "_fcntl", fake_fcntl)


def test_probe_true_when_nop_is_acknowledged(monkeypatch):
    bus = FakeBus(monkeypatch)
    assert drv.probe(1, 0x3C)
    assert bus.slave == 0x3C
    assert bus.writes == [bytes([0x00, 0xE3])]
    assert bus.closed == 1


def test_probe_false_without_device_node(monkeypatch):
    FakeBus(monkeypatch, exists=False)
    assert not drv.probe(1, 0x3C)


def test_probe_false_when_nothing_answers(monkeypatch):
    bus = FakeBus(monkeypatch)

    def nack(fd, data):
        raise OSError(121, "Remote I/O error")

    monkeypatch.setattr(os, "write", nack)
    assert not drv.probe(1, 0x3C)
    assert bus.closed == 1


def test_setup_sends_init_sequence_then_clears_and_turns_on(monkeypatch):
    bus = FakeBus(monkeypatch)
    d = drv.Ssd1306(bus=1, address=0x3C, contrast=77)
    d.setup()
    init = bus.writes[0]
    assert init[0] == 0x00 and init[1] == 0xAE  # commands, display off first
    assert bytes([0x81, 77]) in init  # contrast
    assert bytes([0xA1, 0xC8]) in init  # rotate 0
    data_writes = [w for w in bus.writes if w[0] == 0x40]
    assert sum(len(w) - 1 for w in data_writes) == 1024  # full clear
    assert bus.writes[-1] == bytes([0x00, 0xAF])


def test_rotate_180_flips_scan_direction(monkeypatch):
    bus = FakeBus(monkeypatch)
    drv.Ssd1306(rotate=180).setup()
    assert bytes([0xA0, 0xC0]) in bus.writes[0]


def test_sleep_wake_contrast_and_close(monkeypatch):
    bus = FakeBus(monkeypatch)
    d = drv.Ssd1306()
    d.setup()
    bus.writes.clear()
    d.sleep()
    d.wake()
    d.contrast(300)
    assert bus.writes == [
        bytes([0x00, 0xAE]),
        bytes([0x00, 0xAF]),
        bytes([0x00, 0x81, 255]),
    ]
    d.close()
    assert bus.closed == 1
    with pytest.raises(RuntimeError):
        d.sleep()


def test_pack_framebuffer_page_order_and_bit_order():
    Image = pytest.importorskip("PIL.Image")
    img = Image.new("1", (128, 64), 0)
    img.putpixel((0, 0), 1)  # column 0, page 0, bit 0
    img.putpixel((5, 9), 1)  # column 5, page 1, bit 1
    img.putpixel((127, 63), 1)  # column 127, page 7, bit 7
    buf = drv.pack_framebuffer(img)
    assert len(buf) == 1024
    assert buf[0] == 0b00000001
    assert buf[128 * 1 + 5] == 0b00000010
    assert buf[128 * 7 + 127] == 0b10000000
    assert sum(buf) == 1 + 2 + 128


def test_show_writes_whole_frame_in_chunks(monkeypatch):
    Image = pytest.importorskip("PIL.Image")
    bus = FakeBus(monkeypatch)
    d = drv.Ssd1306()
    d.setup()
    bus.writes.clear()
    d.show(Image.new("1", (128, 64), 1))
    data = b"".join(w[1:] for w in bus.writes if w[0] == 0x40)
    assert data == b"\xff" * 1024
    assert all(len(w) - 1 <= drv._WRITE_CHUNK for w in bus.writes)
    with pytest.raises(ValueError):
        d.show(Image.new("1", (64, 32), 0))
