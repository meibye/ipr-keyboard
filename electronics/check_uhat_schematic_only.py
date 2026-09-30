#!/usr/bin/env python3
"""Verify that the uHAT 2x20 header (J1) is schematic-only in the IprSense Module.

J1 exists in the schematic to document which Raspberry Pi GPIO pins the module
uses. It must never reach the PCB or the BOM. This script exports the netlist
with kicad-cli and checks:

1. J1 carries the exclude_from_board, exclude_from_bom and dnp attributes.
2. Every net that has on-board parts AND touches J1 also reaches a real
   on-board connector (J2/J3), so no signal depends on J1 physically existing.
   Nets that touch only J1 (unused GPIOs) are documentation and are skipped.
3. The PCB file contains no J1 footprint.

Usage: python check_uhat_schematic_only.py [--kicad-cli PATH]
Exit code 0 = all checks passed, 1 = a check failed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE / "IprSense Module"
SCHEMATIC = PROJECT / "IprSense Module.kicad_sch"
PCB = PROJECT / "IprSense Module.kicad_pcb"
DOC_ONLY_REF = "J1"
BOARD_CONNECTORS = {"J2", "J3"}
REQUIRED_FLAGS = {"exclude_from_board", "exclude_from_bom", "dnp"}
DEFAULT_CLI = r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe"


def export_netlist(kicad_cli: str, out: Path) -> ET.Element:
    subprocess.run(
        [kicad_cli, "sch", "export", "netlist", "--format", "kicadxml",
         "--output", str(out), str(SCHEMATIC)],
        check=True, capture_output=True,
    )
    return ET.parse(out).getroot()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kicad-cli", default=DEFAULT_CLI)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = export_netlist(args.kicad_cli, Path(tmp) / "net.xml")

    failures: list[str] = []

    # 1. J1 attributes
    comp = next((c for c in root.iter("comp") if c.get("ref") == DOC_ONLY_REF), None)
    if comp is None:
        failures.append(f"{DOC_ONLY_REF} not found in schematic")
        flags: set[str] = set()
    else:
        flags = {p.get("name") for p in comp.findall("property")}
    for flag in sorted(REQUIRED_FLAGS - flags):
        failures.append(f"{DOC_ONLY_REF} is missing the '{flag}' attribute")

    # 2. Every J1 net that also has on-board parts must hit a real connector
    print(f"{'net':22s} {'on-board parts':28s} {'connector':14s} {DOC_ONLY_REF} pins")
    for net in root.iter("net"):
        nodes = [(n.get("ref"), n.get("pin")) for n in net.findall("node")]
        j1_pins = [p for r, p in nodes if r == DOC_ONLY_REF]
        board = [f"{r}.{p}" for r, p in nodes if r != DOC_ONLY_REF]
        if not j1_pins or not board:
            continue
        conns = [f"{r}.{p}" for r, p in nodes if r in BOARD_CONNECTORS]
        print(f"{net.get('name'):22s} {', '.join(board):28s} {', '.join(conns) or '-':14s} {','.join(j1_pins)}")
        if not conns:
            failures.append(
                f"net {net.get('name')} reaches {DOC_ONLY_REF} but no on-board connector"
            )

    # 3. No J1 footprint on the PCB
    pcb = PCB.read_text(encoding="utf-8")
    if re.search(r'\(property "Reference" "J1"', pcb):
        failures.append(f"{DOC_ONLY_REF} footprint is placed on the PCB")

    print()
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"OK: {DOC_ONLY_REF} is schematic-only (flags {sorted(flags & REQUIRED_FLAGS)}), "
          f"all its nets reach {sorted(BOARD_CONNECTORS)}, no {DOC_ONLY_REF} on PCB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
