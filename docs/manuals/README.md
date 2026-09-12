# End-user manuals (Danish)

Two customer-facing Word manuals and the scripts that generate them.

## Deliverables

| File | Audience | Contents |
|---|---|---|
| `Brugermanual_IPR_Pen_Bridge.docx` | End user | Purpose, connecting the IRIS scanner and PC, daily use, LED colours, magnet actions, error situations |
| `Administratormanual_IPR_Pen_Bridge.docx` | Administrator | Architecture, SD-card imaging, SSH access and file transfer, first-time provisioning, configuration, access/hotspot, accounts, security, updates (incl. offline devices), operations, troubleshooting (device and PC side), testing |

Both are Danish, A4, with a Word TOC field, numbered figures and tables,
and generated diagrams in `figures/`.

> The TOC is empty until Word updates it: open the document, press `Ctrl+A`, then `F9`
> (or right-click the TOC and choose *Opdatér felt*).

## Regenerating

No project dependency is added — the build runs on ephemeral tool environments:

```bash
uv run --with pillow --no-project python docs/manuals/_build/make_figures.py
cd docs/manuals/_build
uv run --with python-docx --no-project python build_user_manual.py
uv run --with python-docx --no-project python build_admin_manual.py
```

## Layout

```
docs/manuals/
  Brugermanual_IPR_Pen_Bridge.docx
  Administratormanual_IPR_Pen_Bridge.docx
  figures/            generated PNG diagrams (fig01…fig12)
  _build/
    make_figures.py       diagram generator (Pillow)
    docx_helpers.py       shared Word styling, tables, captions, notes
    build_user_manual.py  user manual content
    build_admin_manual.py administrator manual content
```

## Photos and screenshots

Diagrams are generated; photographs and screenshots are not — they must be shot or
produced with an image tool. **Appendix C of the administrator manual** lists the 11
required images (B1–B11) with a description detailed enough to hand to a photographer
or use as an image-generation prompt, plus the delivery requirements. Drop finished
files into `figures/` as `foto_B<n>_<name>.png` and reference them from the build
scripts.

## Versioning

Each manual's cover page shows a document id, a version and a date. They come from
the `VERSION` and `DATE` constants at the top of the build script, and `VERSION`
also appears in the page footer.

**Any change to a manual's content must bump both, in the same commit, followed by a
rebuild.** The manuals are handed out as files rather than read from the repository,
so the cover page is the only way a reader can tell which revision they are holding.

| Change | Bump |
|---|---|
| Typo, rewording, corrected command | patch — `1.1` → `1.1.1` |
| New section, new table, added procedure | minor — `1.1` → `1.2` |
| Renumbered chapters, reorganised structure | major — `1.1` → `2.0` |

Write `DATE` in Danish long form, matching the document language: `30. august 2026`.

```python
# docs/manuals/_build/build_admin_manual.py
VERSION = "1.1"
DATE = "30. august 2026"
```

| Manual | Build script | Document id |
|---|---|---|
| Brugermanual | `build_user_manual.py` | IPR-DOC-001 |
| Administratormanual | `build_admin_manual.py` | IPR-DOC-002 |

## Keeping the manuals current

Update these when behaviour changes, in line with the documentation policy in
`AGENTS.md`:

| Change | Update |
|---|---|
| `AppConfig` fields | Admin manual §4.1 table |
| systemd units, install sequence | Admin manual §2.3, §3.5 |
| `/api/` endpoints | Admin manual Appendix B |
| LED colours or reed thresholds | User manual ch. 5 + `make_figures.py` (fig03, fig04) |
| Hotspot triggers | Admin manual §5.2 |
| Deploy scripts | Admin manual ch. 8 |
| SD-card imaging parameters (hostname, user, SSID, SSH mode) | Admin manual §3.1 table |
| Supported device models (Zero 2 W / Zero W), OS architecture | Admin manual §1.1 model table, §3.1 image table, §8.5 wheel platform |
| SSH accounts, hostnames, transfer procedure | Admin manual §3.2, §3.3, §8.5, Appendix A |
| Transfer/bootstrap scripts in `scripts/deploy/` | Admin manual §3.3, §3.5 |
| KPIs recorded by `metrics.py`, perf scripts in `scripts/perf/` | Admin manual §4.1 (MetricsEnabled), §9.4; `docs/ui/api-contract.md` GET /api/metrics |
| GPIO pins or LED resistor values | Admin manual §2.x pin table + `docs/hardware/gpio-wiring.md` |
