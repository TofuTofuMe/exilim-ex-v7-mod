# ADR: Casio Exilim EX-V7 Firmware Reverse Engineering and Image Stabilizer Bypass

## Status

Accepted

## Context

The Casio Exilim EX-V7 (released in 2007) is equipped with a hardware CCD-shift camera stabilization system controlled by an internal Image Stabilizer microcontroller (ISM). In units where the stabilizer actuator or sensors fail, firmware version 1.03 permits general camera operation but forces an error popup ("Camera stabilizer is not available") alongside an unskippable 5-second sleep timer delay during system boot.

Analysis of the firmware container `EX-V7.BIN` revealed:
- Architecture: Renesas / Hitachi SH-2A (32-bit RISC, Big-Endian).
- Byte Obfuscation: The binary image is byte-inverted using bitwise NOT (`byte ^ 0xFF`).
- Checksum Protection: Dual-level 32-bit additive and bitwise XOR checksums protect both `rom825.lbn` (loader) and `rom825.hbn` (main system ROM).

Modifications must suppress the startup popup and freeze delay while retaining normal camera functionality, keeping hardware quiescent, and allowing optional fault reminders inside the settings menu.

## Options Considered

1. **Option 1: Complete Handler Stubbing (`rts/n; nop`)**
   - *Pros:* Completely halts the execution of the error check routine on entry.
   - *Cons:* Skips setting internal completion state flags (e.g., at RAM address `0x10295f8c`), which may cause unexpected secondary checks or state inconsistencies.

2. **Option 2: Targeted Startup Bypass with Checksum Recalculation (Selected)**
   - *Pros:* Replaces the conditional fault branch at virtual address `0x101894fa` with an unconditional branch (`bra 0x1018956c; nop`), completely skipping the popup dialog and sleep delay while allowing normal state flag updates. Enables modular customization of delay timings, menu fault reminders, and version display.
   - *Cons:* Requires recomputing both `rom825.hbn` and `rom825.lbn` dual additive and XOR checksums.

3. **Option 3: Full Hardware Emulation in Software**
   - *Pros:* Simulates valid sensor returns.
   - *Cons:* Extremely high complexity with no practical gain over patching the caller check.

## Decision

Option 2 was selected by TofuTofuMe. An automated Python patcher (`patcher.py`) is used to:
1. De-obfuscate firmware bytes (`^ 0xFF`).
2. Apply the branch patch at virtual address `0x101894fa` (file offset `0x16597a`).
3. Route stabilizer error reporting to menu interactions.
4. Update firmware version metadata strings (`1.31.36.00`).
5. Recalculate 32-bit big-endian additive and XOR sums across `rom825.hbn` and `rom825.lbn`.
6. Re-invert and output the flashable binary (`EX-V7-PATCHED.BIN`).

## Consequences

- **Positive:**
  - Startup delay and error popup are removed.
  - Stabilizer actuator remains safely inactive without buzzing or drawing excess current.
  - Flash verification passes due to valid checksums.
  - Changes are fully reproducible and script-driven.
- **Negative / Trade-offs:**
  - Optical image stabilization remains non-operational due to physical hardware failure.
