# MATE3 UDP protocol references

## `mate3-radian-udp-stream.pdf`

OutBack Power's "PRELIMINARY" spec for the MATE3 serial/UDP data stream as
emitted by a Radian GS8048 inverter. This is the authoritative byte-layout
for the frames parsed in `outback_mate3_addon/src/parser.py`.

Key takeaways:

- Each status page starts with LF (`0x0A`) and ends with CR (`0x0D`) with a
  three-digit checksum immediately before the CR.
- Fields are comma-separated ASCII. The number of characters per field is
  fixed per-field (most currents are 2- or 3-digit, voltages 3-digit).
- **Battery voltage** on a Radian inverter is the 20th CSV field
  (`values[19]` in our parser), encoded as integer tenths of a volt — e.g.
  `532` means 53.2 V. Earlier 2.0 releases accidentally read `values[12]`
  (L2 sell current) and surfaced a stuck 0 V. Fixed in 2.0.1.
- Charge-controller battery voltage is `values[11]`, same tenths-of-a-volt
  encoding.
- Device type 6 = inverter (Radian GS / FX), type 3 = charge controller
  (FM / FlexMax).
- The MATE3 occasionally broadcasts non-telemetry lines on the same UDP
  port (filesystem log, outbound HTTP POST traces). The parser drops those
  by matching the `[MACHI-MACLO]<...>` envelope.

The PDF is labeled PRELIMINARY and the production MATE3 firmware deviates
from it in a few places (field widths, presence of some GS sub-fields).
Our fixtures in `tests/fixtures/mate3_frames/` are the ground truth for
what real hardware sends; the PDF is useful context, not gospel.
