# IprSense Module – perfboard assembly sheet

Board: double-sided prototype board 30 x 64.8 mm, 10 x 24 pads on 2.54 mm
pitch. Every pad is a plated-through hole — a pre-tinned copper ring on **both**
faces, joined by the plating wall in the hole, and isolated from every other
pad. So the two rings of one pad are one electrical node: solder to whichever
ring is easier to reach. Rows A–J run bottom to top, columns 1–24 left to right,
as seen from the **top side** (the side that carries the OLED, reed switch and
LED dome). The corner pads A1, J1, A24, J24 are the M2.5 mounting holes.
Parts and wires only use columns 3–22. The same row/column labels are printed
on both sides, so a pad has one name no matter which side you look at.

The KiCad board (`IprSense Module.kicad_pcb`) is the drawing for this sheet:
footprints sit on the grid cells listed below and the wires are drawn as
0.6 mm tracks on B.Cu. One wire is drawn on F.Cu (the GND link, wire 8) purely
so DRC accepts it crossing the others — physically it is an insulated wire on
the back like all the rest. The uHAT 40-pin header J1 is schematic-only and is
not built.

**What the PCB editor does and does not fix.** The pad grid you see is `PB1`,
a drawing on F.Fab and B.Fab (both faces, because the real pads are on both
faces). It deliberately carries no copper in KiCad: the rings are made by the
board, not by this footprint, so component pads and tracks are free to sit on
them without KiCad calling it a short. The only real pads in the file are the
ones belonging to the footprints, and for the custom parts (LED, reed, OLED,
perfboard) those positions are choices recorded in `IprSense.pretty/*.kicad_mod`,
not properties of the board. Change how a part is mounted and the footprint has
to be edited to match.

## Soldering rules

The pads are plated through, so top ring, plating wall and bottom ring are one
node. That makes the choice of face purely mechanical — pick the ring you can
actually reach with the iron.

- A lead and a wire may share a **pad**, never the **hole**. The lead goes
  through the hole; the wire is soldered flat onto a ring beside it.
- Solder the lead where it protrudes. Where the opposite ring is also clear
  (resistors, LED leads, reed leads) put a little solder there too — it costs
  nothing and leaves a clean ring for the wire.
- The wire goes on whichever ring is **clear**:

  | Pads | Lead joint | Wire goes |
  |---|---|---|
  | J3 A7–A10, J2 A14–A18 | top, where the pin tail protrudes | **top**, against the pin tail — the seat covers the bottom ring (see below) |
  | R3/R4/R5, D1 leads, SW1 leads | where the lead protrudes | **other** face (the back), where the rest of the wiring runs |

- "bridge" = solder blob joining two adjacent pads (or a bare lead offcut);
  "wire" = insulated solid-core wire, 24–26 AWG. Use bridges only for the
  one-step joins listed; everything longer is wire.
- A wire that turns a corner (G15, H16, J14, D22) is one continuous wire, not two.
  Only **F16** and **H7** are real junctions of separate wires — twist the
  stripped ends together there before soldering.
- Every through-hole lead must be in its pad **before** a wire is soldered into
  the same pad: solder wicks into a plated hole and then no lead will go in.
  Parts first, wires second — see "Assembly order".

### Connector joints (J2, J3) — why they are made on the top

A 2.54 mm header's plastic seat is about 2.5 mm thick and sits flat across the
whole pad, so once J2 or J3 is seated against the bottom face the bottom rings
of A7–A10 and A14–A18 are **covered and cannot be soldered**. The layout shows
those wires arriving on the bottom; that is the electrical path, not a
buildable instruction.

The joint is therefore made on the **top**, where the pin tail protrudes
(≈ 1.4 mm through a 1.6 mm board):

1. Seat the connector against the bottom face and solder the pin to the top
   ring as usual.
2. Tin the pin tail, lay the pre-tinned wire end flat against it on the top
   ring, and reflow so pin, ring and wire become one joint. Do **not** try to
   get a second conductor into the hole.
3. Wires **1–4** and **5** have their far end on a ring that is only reachable
   from the back, so each leaves its top-side joint, runs one pad to
   **B7–B10** / **B14**, drops through that free hole to the back, and
   continues on the back. The wire itself is the feed-through; no via or link
   part is needed. Wires **6, 9, 11, 13** stay on the top for their whole
   length — their far ends are lead tails that protrude on the top anyway.

Two cautions:

- **Keep these four joints flat.** The OLED module sits only ~2.5 mm above the
  top face, directly over columns 3–13. Use 26 AWG here, keep the solder
  low-profile, and dress each wire straight toward its B-row hole so nothing
  stands proud.
- **They are buried afterwards.** Every joint in this group is under the OLED,
  so they must be complete and tested before step 13. They are still
  recoverable — the OLED lifts off by desoldering its four pins from the back
  — but not reachable in place.

## Placement

| Ref | Part | Side | Pads (grid) | Notes |
|---|---|---|---|---|
| U2 | 0.96" 128x64 I2C OLED module | top | header pins J7 GND, J8 VCC, J9 SCL, J10 SDA | module covers columns 3–13 over the full board width; header edge (display top) at row J. Held by the soldered header; optional standoffs need 2.5 mm holes drilled between A4/A5, A12/A13, J4/J5, J12/J13 (off-grid) |
| SW1 | reed switch, 14 x 2 mm glass | top | J16 (GPIO27), B16 (GND) | lies along column 16, leads bent 3 mm outside the glass, 20.32 mm pitch |
| D1 | 5 mm RGB LED (4 leads in a row) | inserted from the back, dome on top | R → G20, K → F19, G → E19, B → D21 | a proposal, not a constraint — see "LED hole choice and lead bending" |
| J3 | 1x04 pin header (I2C + power to Pi) | back | A7 GND, A8 3V3, A9 SCL, A10 SDA | pin 1 at A7 |
| J2 | 1x05 pin socket (GPIO to Pi) | back | A14 GPIO27, A15 GPIO22, A16 GND, A17 GPIO23, A18 GPIO24 | pin 1 at A14 |
| R3 | 150 Ω (red), 7.62 mm horizontal | back | C15 (GPIO22 side) – F15 (LED side) | lies along column 15 |
| R4 | 150 Ω (green), 7.62 mm horizontal | back | B17 (GPIO23 side) – E17 (LED side) | lies along column 17 |
| R5 | 22 Ω (blue), 7.62 mm horizontal | back | C19 (GPIO24 side) – C22 (LED side) | lies along row C |

### LED hole choice and lead bending

Nothing on the board fixes which pads the LED leads use. The 5.2 mm hole is an
NPTH in the custom footprint — **you drill it**, it is not a grid hole, and it
destroys pads E20, E21, F20, F21. The four lead pads are likewise offsets I
chose in that footprint, picked so no two leads bend toward each other. Any set
of pads the leads reach without shorting is equally valid.

**If you bend the leads into different pads, edit the footprint to match** —
pad offsets in
`IprSense.pretty/LED_D5.0mm-4_RGB_ReverseMount_Perfboard.kicad_mod`, then
*Update Footprints from Library* and re-route the affected wires. Otherwise the
KiCad drawing stops describing the hardware.

**Check your LED's lead order before bending.** The footprint assumes the four
leads read R, K, G, B along the row, with R at the row-G end and B at the
row-D end, and the flat on the rim identifying that end. Confirm it against the
part (and against `Device:LED_RKGB`: pin 1 = R, 2 = K, 3 = G, 4 = B) with a
meter or a 3 V coin cell and a 1 kΩ resistor before committing to the bends.

Bending, done on the back with the flange against the board:

1. **R** (outer lead, row-G end): bend 2 mm from the flange straight outward
   toward row G, then into pad G20.
2. **B** (outer lead, row-D end): same, outward toward row D, into pad D21.
3. **K** (inner): bend 2 mm from the flange sideways toward column 19, into
   pad F19.
4. **G** (inner): slip a 5 mm sleeve (heat-shrink / PTFE) on it, bend 4 mm
   from the flange sideways toward column 19, clearing K, into pad E19.

Trim each lead so ~2 mm protrudes on the top side and solder it there; add a
fillet on the back ring too where the ring is clear.

## Assembly order

Two things make the order matter, and neither is obvious from the drawing:

- A connector's plastic body sits flat on its pads, so it **covers the ring on
  its own face**. J2 and J3 sit on the back, so once they are fitted the back
  rings of A7–A10 and A14–A18 are gone; those joints can then only be made on
  the top.
- The OLED module covers the whole top face over columns 3–13, rows A–J. It
  therefore hides J3's pin joints (A7–A10) and the top-side part of wires 1–4.
  **The OLED is always the last part fitted.**

### 0. Bare board

1. Mark the row letters A–J and column numbers 1–24 along two edges with a fine
   marker, on both faces. The stock perfboard has no printing — the labels exist
   only in the KiCad drawing, and every instruction below depends on them.
2. Meter between the top and bottom ring of one pad to confirm the plating
   (< 1 Ω). Everything here assumes the two rings are one node.
3. Confirm the LED's lead order (see "LED hole choice and lead bending").
4. Drill the 5.2 mm LED hole centred between E20/E21/F20/F21, and the optional
   OLED standoff holes. Drill now, while the board is bare and can be clamped.

### 1. Parts whose joints are on the top face

5. **R3, R4, R5** — bodies flat on the back, leads bent down into C15/F15,
   B17/E17, C19/C22. Solder the protruding tails on the top.
6. **D1** — from the back through the 5.2 mm hole, leads bent as described
   below into G20, F19, E19, D21. Solder the tails on the top.

### 2. Part whose joints are on the back face

7. **SW1** — glass body on the top along column 16, leads into J16 and B16.
   Solder its tails on the back. Fit it now: its pads are wire endpoints, and a
   pad already full of solder will not take a lead.

### 3. Back-side wiring

8. Wires **7, 8, 10, 12, 14** and the back-side runs of **1–4** (columns 7–10
   from row B up to row J). All of these land on pads that stay accessible, so
   they can be done in any order.

### 4. Connectors and the joints they will block

9. **J3** — body on the back at A7–A10, pins protruding on the top. Solder the
   pins on the top.
10. **J2** — body on the back at A14–A18, pins protruding on the top. Solder the
    pins on the top.
11. Now make every top-side joint at row A, against the pins: wires **1–4** at
    A7–A10, **5** at A14, **9** at A15, **6** at A16, **11** at A17, **13** at
    A18. After this step nothing on the top of columns
     3–13 can be reached
    again.

### 5. Test before closing up

12. Buzz out each net against the wiring table — J3 pin to OLED pad, J2 pin to
    resistor and reed, and every pad in the GND group. Check for shorts between
    neighbouring row-A pins. This is the last moment the whole board is open.

### 6. Display

13. **U2** — module on the top, its header pins down into J7–J10. Solder the
    pins on the back. Fit the standoffs if used.

## Wiring

The **Side** column is the face the wire lies on and is soldered to. Most of it
is the bottom; the exception is every joint landing on a J2 or J3 pad, because
the connector body covers the bottom ring there, so that joint is made on the
top against the pin. Wires 1–5 therefore start (or end) on the top and cross to
the bottom through the free hole one row up; wires 6, 9, 11 and 13 are top-side
for their whole length.

The KiCad board draws this literally: **every track is on the layer the wire is
actually built on** — top-side runs on F.Cu, bottom-side runs on B.Cu, and a
via wherever a wire passes through a free hole. So the layout can be read
directly as the wiring drawing, per side.

Because wire 8 crosses four other bottom-side wires, KiCad reports two
`tracks crossing` errors. On a hand-wired board that is expected — the wires
are insulated and simply lie over one another. Set *Board Setup → Design Rules
→ Violation Severity → Tracks crossing* to **Ignore** to keep DRC useful for
the checks that do matter (unconnected items, clearance, courtyards).


| # | Net | Side | From → to | How |
|---|---|---|---|---|
| 1 | GND | **top**, then **bottom** | A7 → B7 → J7 | top ring at A7 against the J3 pin, down through the free hole at **B7**, then on the bottom up column 7 to the bottom ring at J7 |
| 2 | +3V3 | **top**, then **bottom** | A8 → B8 → J8 | as wire 1, crossing to the bottom through **B8**, up column 8 |
| 3 | SCL | **top**, then **bottom** | A9 → B9 → J9 | as wire 1, crossing to the bottom through **B9**, up column 9 |
| 4 | SDA | **top**, then **bottom** | A10 → B10 → J10 | as wire 1, crossing to the bottom through **B10**, up column 10 |
| 5 | GPIO27 (reed) | **bottom**, then **top** | J16 → J14 → B14 → A14 | on the bottom from J16 along row J, then down column 14 to **B14**; through that free hole to the top and onto the J2 pin-1 pad at A14 |
| 6 | GND (reed) | **top** | A16 → B16 | short link, J2's GND pin to the reed's lower lead |
| 7 | GND (LED cathode) | **bottom** | F19 → F16 → B16 | along row F, then down column 16 |
| 8 | GND link (jumper) | **bottom** (insulated) | H7 → H16 → F16 | crosses wires 2, 3, 4 and 5 along row H and wire 10 at G16, so it must be insulated — solder only at H7 (tapped onto wire 1's column-7 run) and F16. **Bottom only**: the reed's glass body lies over H16, G16 and F16 on the top face, so there is no top-side route |
| 9 | GPIO22 → R3 | **top** | A15 → C15 | over B15: J2 pin 2 to R3's protruding lead |
| 10 | R3 → LED R | **bottom** | F15 → G15 → G20 | up one pad, then along row G |
| 11 | GPIO23 → R4 | **top** | A17 → B17 | short link, J2 pin 4 to R4's protruding lead |
| 12 | R4 → LED G | **bottom** | E17 → E19 | along row E |
| 13 | GPIO24 → R5 | **top** | A18 → C19 | diagonal over B18/B19, to R5's protruding lead |
| 14 | R5 → LED B | **bottom** | C22 → D22 → D21 | two bridges |

Each row is **one continuous wire**. A pad in the middle of a path is a corner
(H16, J14, G15, D22) or a feed-through hole (B7–B10, B14), not a second wire
and not necessarily a solder point — solder only where the "How" column says.
H16 in wire 8 is just the turn from row H into column 16.

Pads under the OLED (columns 3–13) are free on the back; the module sits
~2.5 mm above the top side on its header spacer. The LED dome is ~14 mm from
the OLED glass edge, at the far end of the board.
