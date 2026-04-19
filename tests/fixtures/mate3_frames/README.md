# MATE3 UDP capture fixtures

Captured from hass-4 (MATE3 at 192.168.200.9), 94 frames over ~90s.

## Telemetry frames (263 bytes, full streaming output)
- System MAC: `AAAAAA-BBBBBB` (real device serial obfuscated throughout)
- 2 inverters (type 6, device IDs 01 and 02)
- 2 charge controllers (type 3, device IDs 04 and 05)

### Files
- `telemetry_00.bin` — first frame in capture
- `telemetry_01.bin` — ~25% through capture
- `telemetry_02.bin` — midpoint
- `telemetry_03.bin` — ~75% through capture
- `telemetry_04.bin` — last frame in capture

## Noise frames (should be ignored by parser)
- `noise_fsop.bin` (42 bytes) — MATE3 internal filesystem log
- `noise_httpost.bin` (73 bytes) — MATE3 outbound HTTP POST log

## Full capture
- `all_frames.jsonl` — every frame, timestamped, base64-encoded payload (for replay tests)
- `mate3_capture.pcap` — original pcap
