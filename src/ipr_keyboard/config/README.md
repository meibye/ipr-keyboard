# src/ipr_keyboard/config/

Configuration management for the application.

## Files

- `manager.py`: `AppConfig` (dataclass) + thread-safe singleton `ConfigManager`
- `web.py`: Flask blueprint `bp_config` at `/config/` — `GET` returns the
  configuration as JSON, `POST` applies a partial update

## AppConfig

34 fields; the authoritative list, with defaults and comments, is the
dataclass in `manager.py`.  Grouped:

| Group | Fields |
|---|---|
| Pen | `IrisPenFolders`, `DeleteFiles`, `MaxFileSize` (1 MiB), `ReadTimeoutSeconds`, `PollIntervalSeconds` |
| Bluetooth | `PairingTimeoutSeconds`, `TypingDelayMs` |
| Web and TLS | `LogPort` (443), `TlsCertFile`, `TlsKeyFile`, `StatusIntervalSeconds` (SSE tick, 5 s) |
| Network | `NetworkMode` (`dhcp`/`static`), `StaticIP`, `StaticNetmask`, `StaticGateway` |
| LED and magnet | `GpioEnabled`, `GpioReedPin`, `GpioLedRPin`, `GpioLedGPin`, `GpioLedBPin`, `GpioLedIdleSeconds`, `MenuTimeoutSeconds`, `RecoveryRevealLimit` |
| Panel | `OledEnabled`, `OledI2cBus`, `OledI2cAddress`, `OledContrast`, `OledRotate`, `OledSendHoldSeconds`, `OledMarqueeFps`, `OledDisplayTimeoutMinutes` |
| Diagnostics | `Logging`, `LogLevel`, `MetricsEnabled` |

`TypingDelayMs` has no fixed default: it is the provisioned
`BT_KEY_DELAY_MS` from `/opt/ipr_common.env` (read once at import), so the
app and the BLE daemon agree on a fresh install.  A speed chosen in Settings
is saved to `config.json` and wins.

## Files on disk

- `config.default.json` — the factory defaults, shipped
- `config.json` — the live configuration, seeded from the defaults on first
  start and rewritten whole on every `update()`

Do not edit `config.json` while the service runs: the process holds the
configuration in memory and the next save overwrites a hand edit.

## Threading Model

- class-level lock protects singleton initialization
- instance-level `RLock` protects reads/writes/reload
