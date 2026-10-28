# ADR: Derivation of the `uranus.bin` Firmware Restoration Image from `EX-V7.BIN`

## Status

Accepted

## Context

At an implementation stage during Casio Exilim EX-V7 firmware customization, a robust hardware-level recovery option was required to restore flash memory independently of the main operating system and standard `[MENU]` + Power updater UI.

Examination of the Casio Exilim EX-V7 Service Manual (`casio_ex-v7_sm.pdf`, Pages 8-9) identified an emergency firmware restoration procedure triggered by holding the `[SHUTTER]` button while inserting the battery. This procedure instructs the bootloader to load a restoration file named `uranus.bin` from the root directory of an SD card, signaling progress via the rear viewfinder LED (green/red blinking -> green blinking -> green steady). However, the proprietary `uranus.bin` file was nowhere to be found on the internet.

Reverse engineering of the bootloader partitions inside the retail `EX-V7.BIN` (V1.03) firmware update container revealed how the camera processes both retail updates and emergency restorations:

1. **Stage-1 Bootloader (`0x0480..0x0c80`)**:
   - Samples the `[SHUTTER]` button state via `0x0522` (`bsr 0x0808`).
   - When `[SHUTTER]` is depressed, loads and jumps to the Stage-2 Recovery Loader at virtual address `0x10000000` (file offset `0x04480..0x0b550`).
   - When `[SHUTTER]` is not depressed, validates the Main ROM header at `0x30030060` and jumps to `0x10030080`.

2. **Retail Updater (`0x10176e70` in Main ROM) vs. Stage-2 Recovery Loader (`0x10000000` in `rom825.lbn`)**:
   - The retail updater (`0x10176e70`) reads `\EX-V7.bin`, applies a bitwise NOT (`0x10176f02: not r2, r2`, equivalent to `byte ^ 0xFF`) across the entire buffer, reads the inner payload offset (`0x00000400`) from outer header offset `+0x18`, and advances the buffer pointer by `0x400` bytes (`0x10176f42`) to reach the `.\rom825.lbn` header.
   - By contrast, the Stage-2 Recovery Loader (`0x10000000`) reads `\uranus.bin` into DRAM at `0x30330000` (`r13`) via `0x1000094c` (blinking the LED green/red) **without** performing bitwise inversion and **without** skipping a `0x400`-byte outer header.
   - At `0x10000050`, the recovery loader inspects the 32-bit magic value at offset `+0x30` (`mov.l @(0x30, r13), r0`) of `uranus.bin`, supporting three distinct execution modes:
     - **Mode `0xa5a5a5a5` (Full Flash Recovery)**: Matches the `.\rom825.lbn` ("LoaderUpdater") header at offset `0x400` of de-inverted `EX-V7.BIN`. Verifies the 32-bit additive (`+0x28`) and XOR (`+0x2c`) checksums over `+0x24` (`0x00246250`) bytes starting at `+0x80` via `0x1000011e`, then invokes `0x10000340` to erase, program, and verify flash starting at block 0 (`r5 = 0x00`, blinking green) before setting the LED to steady green (`0x100003b6`) and halting (`0x100000ca`).
     - **Mode `0x00000001` (Main ROM Partition Recovery)**: Matches the `.\rom825.hbn` header at offset `0xc480` of de-inverted `EX-V7.BIN`. Verifies the checksums over `0x0023a1d0` bytes and flashes starting at Flash Block 3 (`r5 = 0x60`, shifted right by 5 at `0x100008d0` to block 3 = byte offset `0xc000`), preserving the bootloader blocks.
     - **Mode `0x00000004` (RAM-Only Live Boot)**: Copies `+0x24` bytes from `r13 + 0x80` directly into executable RAM at `0x30030080` (`0x10030080`) via `0x10000156` and jumps directly to `0x10030080` (`0x10000114`) without modifying flash memory.

## Options Considered

1. **Option 1: Directly Rename Raw `EX-V7.BIN` to `uranus.bin`**
   - *Pros:* Requires no file transformation.
   - *Cons:* Fails header validation at `0x10000050` because raw `EX-V7.BIN` is bitwise-inverted (`byte ^ 0xFF`) and prepended with a `0x400`-byte retail wrapper, placing `0xffffffff` at offset `+0x30` instead of `0xa5a5a5a5`.

2. **Option 2: Reconstruct `uranus.bin` by De-Inverting `EX-V7.BIN` and Stripping the `0x400`-Byte Retail Wrapper (Selected)**
   - *Pros:* Produces the exact `2,384,592`-byte (`0x2462d0`) `LoaderUpdater` image (`inv[0x400:0x2466d0]`) with `.\rom825.lbn` at `+0x00`, magic `0xa5a5a5a5` at `+0x30`, `"LoaderUpdater"` at `+0x40`, and valid additive (`0xc2103641`) and XOR (`0x9a4feb13`) checksums. Enables full hardware recovery on physical camera hardware without external flash programmers.
   - *Cons:* Requires a build step in `patcher.py` to emit `uranus.bin`.

## Decision

Option 2 was selected by TofuTofuMe. The factory `uranus.bin` restoration image is derived from `EX-V7.BIN` by:
1. Bitwise de-inverting all bytes (`inv[i] = raw[i] ^ 0xFF`).
2. Stripping the first `0x400` bytes (`uranus = inv[0x400:0x2466d0]`).
3. Supporting optional `uranus.bin` export in `patcher.py` (including full flash recovery mode `0xa5a5a5a5`, Main ROM recovery mode `0x00000001`, and RAM-only execution mode `0x00000004`).

## Consequences

- **Positive:**
  - Provides a verified, self-contained unbrick and recovery mechanism using only an SD card and the `[SHUTTER]` button.
  - Eliminates dependency on unobtainable external Casio factory files.
  - Enables risk-free RAM-only firmware testing via header mode `0x00000004`.
- **Negative / Trade-offs:**
  - Full flash restoration rewrites 2.38 MB of flash memory and requires a charged battery during the ~30-60 second green-blinking programming phase.
