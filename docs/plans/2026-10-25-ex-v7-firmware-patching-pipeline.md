# Plan: Casio Exilim EX-V7 Firmware Modification and Analysis Infrastructure

## Summary

Establish a formal reverse-engineering and firmware modification pipeline for the Casio Exilim EX-V7 digital camera. The plan documents the disassembly analysis of firmware version 1.03, the implementation of a reproducible patching script, and the maintenance of architectural records and project tracking.

## Goal

Provide TofuTofuMe with a reproducible, documented, and automated workflow to inspect, customize, and patch the Casio Exilim EX-V7 firmware, resolving hardware stabilization delays while preserving system integrity.

## Steps

1. Inspect firmware container `EX-V7.BIN` to identify encoding format, CPU architecture, memory layouts, and task dispatchers.
2. Locate stabilizer fault detection routines and startup error display handlers.
3. Determine the checksum algorithms protecting the firmware blocks.
4. Develop `patcher.py` to automate:
   - Byte de-inversion and re-inversion.
   - Bypassing startup stabilizer error screens and sleep delays.
   - Adding stabilizer fault reminder notifications upon menu selection.
   - Configuring customized delay timers and version strings.
   - Recomputing `rom825.hbn` and `rom825.lbn` checksums.
5. Generate `EX-V7-PATCHED.BIN` with verified valid checksums.
6. Write technical documentation in `README.md`.
7. Author Architecture Decision Record (ADR) and implementation plan under `docs/`.
8. Review plan and changes with TofuTofuMe.

## Relevant Files

- `casio-exilim-ex-v7/`
  - `EX-V7.BIN`
  - `EX-V7-PATCHED.BIN`
  - `patcher.py`
  - `README.md`
  - `docs/`
    - `adr/`
      - `2026-10-25-image-stabilizer-bypass-and-firmware-patching.md`
    - `plans/`
      - `2026-10-25-ex-v7-firmware-patching-pipeline.md`
