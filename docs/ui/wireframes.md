# IPR Keyboard Web Dashboard Wireframes

This document provides low-fidelity wireframes and layout intent for the dashboard.

The wireframes are deliberately simple and should be treated as structural guidance rather than pixel-perfect design.

---

## Design principles

- status must be understandable at a glance
- top-level screens must use large cards and images
- technical detail is secondary
- action buttons must be obvious and safe
- layouts must work on small screens and desktop browsers

---

## Shared layout

### Desktop structure

```text
+----------------------------------------------------------------------------------+
| IPR Pen Bridge                                  READY                   [Settings]|
+----------------------------------------------------------------------------------+
| [Home] [Connections] [Activity] [Events] [Settings]                              |
+----------------------------------------------------------------------------------+
|                                                                                  |
|                               page-specific content                              |
|                                                                                  |
+----------------------------------------------------------------------------------+
```

### Mobile structure

```text
+---------------------------------------------+
| IPR Pen Bridge                 READY   [≡]  |
+---------------------------------------------+
|                                             |
|            page-specific content            |
|                                             |
+---------------------------------------------+
| [Home] [Connect] [Activity] [Events] [More]|
+---------------------------------------------+
```

## Home screen

### Purpose

The default screen for normal users.

### Layout
```text
+----------------------------------------------------------------------------------+
| IPR Pen Bridge                                  READY                   [⚙]      |
+----------------------------------------------------------------------------------+
|                                                                                  |
|              [ Pen ]  --->  [ Raspberry Pi ]  --->  [ PC ]                       |
|                                                                                  |
|                          Ready for use                                           |
|                                                                                  |
+----------------------------------+  +-------------------------------------------+
| [Bluetooth icon]                 |  | [Pen icon]                                |
| Bluetooth                        |  | Pen                                       |
| Connected                        |  | Ready                                     |
| Paired with Office-PC            |  | Scanner found                             |
+----------------------------------+  +-------------------------------------------+
| [Transfer icon]                  |  | [System icon]                             |
| Transmission                     |  | System                                    |
| Idle                             |  | Healthy                                   |
| No active send                   |  | Temperature normal                        |
+----------------------------------+  +-------------------------------------------+
| Last event: Pen connected 2 min ago                                              |
| [View Activity]                                           [Open Settings]        |
+----------------------------------------------------------------------------------+
```
### Notes
- The main hero area should contain a very simple visual flow from pen to Pi to PC.
- The four status cards are the core information objects.
- Each card should use icon + label + short explanation.
- The overall state badge in the header should reflect the worst active state.

## Connections screen

### Purpose

Focused view for Bluetooth and pen readiness.

### Layout
```text
+----------------------------------------------------------------------------------+
| Connections                                                                      |
+----------------------------------------------------------------------------------+
|                                                                                  |
|   +------------------+      +------------------+      +------------------+       |
|   | [PC image]       | ---> | [Pi image]       | ---> | [Pen image]      |       |
|   | PC / Bluetooth   |      | Bridge           |      | Pen / Scanner    |       |
|   | Connected        |      | Active           |      | Ready            |       |
|   | Office-PC        |      | Waiting for data |      | Device attached  |       |
|   +------------------+      +------------------+      +------------------+       |
|                                                                                  |
|   [Enter pairing mode]   [Reconnect Bluetooth]   [Rescan pen]                    |
|                                                                                  |
|   Details                                                                        |
|   - Bluetooth MAC / device name                                                  |
|   - Last connected time                                                          |
|   - Pen last detected time                                                       |
+----------------------------------------------------------------------------------+
```
### Notes
- The visual path is more important than raw technical fields.
- Details should be below the main visual area, not above it.
- If disconnected, the problematic block should be visually marked.

## Activity screen
### Purpose

Show whether data is moving right now or what happened recently.

### Layout
```text
+----------------------------------------------------------------------------------+
| Activity                                                                         |
+----------------------------------------------------------------------------------+
| Current state: SENDING                                                           |
|                                                                                  |
|               [PEN]   >>>>>>   [PI]   >>>>>>   [PC]                              |
|                                                                                  |
| Progress: 68%                                                                    |
| Items sent: 14                                                                   |
| Retries: 1                                                                       |
| Last success: 14:21:08                                                           |
|                                                                                  |
| Recent activity                                                                  |
| +------------------------------------------------------------------------------+ |
| | [✓] Transmission completed                                                   | |
| | [!] Retry needed                                                             | |
| | [✓] Pen read successful                                                      | |
| | [X] Previous send failed                                                     | |
| +------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------+
```
Notes
- Active transfer should include animation if inexpensive to render.
- If no live transfer is happening, show a calm idle state rather than empty space.
- The recent activity list should be short and scannable.

## Events screen
### Purpose

Default troubleshooting screen.

### Layout
```text
+----------------------------------------------------------------------------------+
| Events                                                                           |
+----------------------------------------------------------------------------------+
| [All] [Bluetooth] [Pen] [Transfer] [Errors] [System]                             |
|                                                                                  |
| +------------------------------------------------------------------------------+ |
| | [✓] 14:21 Pen connected                                                      | |
| | [✓] 14:21 Bluetooth connected to Office-PC                                   | |
| | [✓] 14:22 Transmission started                                               | |
| | [!] 14:22 Transmission retry                                                 | |
| | [✓] 14:22 Transmission completed                                             | |
| +------------------------------------------------------------------------------+ |
|                                                                                  |
| [Show raw logs]                                                                  |
|                                                                                  |
| Raw logs panel (collapsed by default)                                            |
+----------------------------------------------------------------------------------+
```

### Notes
- Use translated events as the default view.
- Raw logs must be collapsible and secondary.
- Severity icons should be consistent across the UI.

## Settings screen
### Purpose

Configuration and protected actions.

### Layout
```text
+----------------------------------------------------------------------------------+
| Settings                                                                         |
+----------------------------------------------------------------------------------+
| Device                                                                           |
| +------------------------------------------------------------------------------+ |
| | Device name: IPR Pen Bridge                                                  | |
| | UI title: IPR Pen Bridge                                                     | |
| +------------------------------------------------------------------------------+ |
|                                                                                  |
| Bluetooth                                                                        |
| +------------------------------------------------------------------------------+ |
| | Pairing mode timeout                                                         | |
| | Auto reconnect                                                               | |
| | Allowed host / last host                                                     | |
| +------------------------------------------------------------------------------+ |
|                                                                                  |
| Pen / Scanner                                                                    |
| +------------------------------------------------------------------------------+ |
| | Auto detect                                                                   | |
| | Read timeout                                                                  | |
| +------------------------------------------------------------------------------+ |
|                                                                                  |
| Diagnostics                                                                      |
| +------------------------------------------------------------------------------+ |
| | Log level                                                                     | |
| | Export diagnostics                                                            | |
| +------------------------------------------------------------------------------+ |
|                                                                                  |
| Power                                                                            |
| +------------------------------------------------------------------------------+ |
| | [ Reboot device ]                                                            | |
| | [ Shutdown device ]                                                          | |
| +------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------+
```

### Notes
- Put power actions in a clearly separated danger section.
- Confirm dialogs are mandatory for reboot and shutdown.
- Keep configuration focused and minimal.

## Error state examples
### Bluetooth disconnected
```text
Bluetooth
Not connected
Waiting for paired PC
[Enter pairing mode]
```

### Pen missing
```text
Pen
Not detected
Attach the pen / scanner
[Rescan]
```

### Transmission failed
```text
Transmission
Failed
Open Activity for details
[View Activity]
```

### System warning
```text
System
Warning
Check events for details
[Open Events]
```

## Component inventory
### Core components
- TopBar
- NavBar
- StateBadge
- StatusCard
- DeviceFlowGraphic
- EventTimeline
- FilterChips
- ConfirmDialog
- PowerActions
- DetailsPanel

### Page components
- HomePage
- ConnectionsPage
- ActivityPage
- EventsPage
- SettingsPage

## Responsive behavior
### Small screens
- stack cards vertically
- keep cards large and tappable
- move less important detail below the fold
- preserve a strong top-level summary

### Larger screens
- two-column status card layout
- more visible event list
- keep whitespace generous

## Visual priority order

The user should visually notice, in this order:

1. overall device readiness
2. Bluetooth readiness
3. pen readiness
4. transfer state
5. last important event
6. navigation to details

## Implementation note

These wireframes are intentionally low-fidelity.
If a frontend implementation chooses slightly different visual arrangements while preserving the same information hierarchy and simplicity, that is acceptable.

SVG assets (device illustrations, state icons) should be stored in `src/ipr_keyboard/web/static/`.
The existing Flask templates in `src/ipr_keyboard/web/templates/` are the baseline to evolve from.