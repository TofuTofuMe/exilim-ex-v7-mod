# Plan: Derivation and Generation of the `uranus.bin` Firmware Restoration Image

## Summary

Reverse-engineer the Stage-1 and Stage-2 bootloaders (`rom825.lbn`) embedded within the Casio Exilim EX-V7 retail firmware update container (`EX-V7.BIN`) to determine the exact binary format, header structure, and checksum validation rules of the factory restoration image (`uranus.bin`), and integrate `uranus.bin` generation into the firmware tooling.

## Goal

Provide TofuTofuMe with a reliable, self-contained method to generate the proprietary `uranus.bin` emergency firmware restoration file directly from `EX-V7.BIN`, enabling low-level hardware recovery via the camera's Stage-2 bootloader (`[SHUTTER]` + battery insertion) without external programming hardware.

## Steps

1. Read the plan skill and create this plan file under `docs/plans/2026-10-27-uranus-firmware-recovery-image.md`.
2. Inspect the Casio Exilim EX-V7 Service Manual (`casio_ex-v7_sm.pdf`, Pages 8-9) to identify the hardware trigger sequence (`[SHUTTER]` depressed during power-on / battery insertion), LED status transitions (green/red blinking -> green blinking -> green steady), and target filename (`\uranus.bin`).
3. Disassemble the Stage-1 Bootloader (`0x0480..0x0c80`) in `EX-V7.BIN` to trace how the `[SHUTTER]` key press is detected at `0x0522` (`bsr 0x0808`) and how control transfers to the Stage-2 Recovery Loader at virtual address `0x10000000` (file offset `0x04480`).
4. Disassemble the Stage-2 Recovery Loader (`0x04480..0x0b550`, mapped to `0x10000000..0x100070d0`) and compare it against the Main ROM retail updater (`0x10176e70`):
   - Verify how `\uranus.bin` is loaded into DRAM at `0x30330000` via `0x1000094c` without bitwise inversion.
   - Analyze header magic validation at `0x10000050` (`@(0x30, r13)`) for `0xa5a5a5a5` (Full Flash Recovery), `0x00000001` (Main ROM Partition Recovery), and `0x00000004` (RAM-Only Execution).
   - Verify the 32-bit additive and XOR checksum routine at `0x1000011e` against header fields `+0x24` (size), `+0x28` (additive sum), and `+0x2c` (XOR sum).
5. Extract and verify `uranus.bin` by de-inverting `EX-V7.BIN` (`byte ^ 0xFF`) and stripping the `0x400`-byte retail container header (`inv[0x400:0x2466d0]`).
6. Update `patcher.py` and `README.md` to support generating `uranus.bin` while keeping experimental SD dumper routines stashed.
7. Author the corresponding Architecture Decision Record (ADR) in `docs/adr/2026-10-27-uranus-firmware-restoration-container.md`.
8. Review the plan and changes with TofuTofuMe.

## Relevant Files

- `casio-exilim-ex-v7/`
  - `casio_ex-v7_sm.pdf`
  - `EX-V7.BIN`
  - `uranus.bin`
  - `patcher.py`
  - `README.md`
  - `docs/`
    - `plans/`
      - `2026-10-27-uranus-firmware-recovery-image.md`
    - `adr/`
      - `2026-10-27-uranus-firmware-restoration-container.md`
