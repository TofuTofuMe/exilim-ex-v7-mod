# Casio Exilim EX-V7 Firmware Reverse Engineering & Hacking

## 1. Project Overview

So I bought this neat wallet-sized camera. At first, it didn't allow shooting, erroring out with its "Camera stabilizer is not available" error. I updated my camera from V1.00 to V1.03 which allowed the camera to shoot regardless of the error, but it annoyingly still took seconds to allow shooting. I thought, why not let AI patch the firmware BIN?

Patching the firmware allowed me to bypass the startup error screen, and the camera boots up nearly instantly afterwards. Thanks, AI, lol.

At some point, I tried doing some additional mod like dumping internal assets for modifying menu icons and stuff, but the camera got bricked. I looked for a service manual that thankfully described a recovery method, but it required a `uranus.bin` that I couldn't find anywhere on the net. Fortunately, it's discovered that it's pretty much inside the firmware BIN, so technically, we just need the `EX-V7.BIN` firmware file.

I uploaded both `EX-V7.BIN` and `uranus.bin`, along with the service manual I found, on the Internet Archive:
https://archive.org/details/exilim-exv7

For the patched firmware for removing the annoying startup screen, that's what this project is for.

This repository reverse-engineers, customizes, and recovers the firmware of the **Casio Exilim EX-V7** (2007, Internal Model Code: `KX-825` / `0x0825`).

The 1.03 firmware of the camera is used as the base and modified to:

- Bypass the startup Image Stabilizer (`ISM`) fault error screen and sleep delay without triggering lens focus retry loops.
- Route the stabilizer error message (`#0x51`) to the stabilization settings menu as a quality-of-life reminder.
- Replace visual assets (such as the Best Shot mode icon) with custom icons.
- Provide a cable-free method for asset dumping and flashing via SD card triggers.
- Reverse-engineer, document, and generate the undocumented factory emergency recovery file `uranus.bin` for unbricking and safe RAM-only live testing.

The repository contains the source tooling (`patcher.py`), generated image artifacts (`EX-V7.BIN`, `EX-V7-PATCHED.BIN`, `uranus.bin`), extracted service documentation, and the associated architecture documents.

## 3. Usage

Run `patcher.py` to generate a patched firmware or to export the recovery image (`uranus.bin`):

```bash
# Generate patched retail update image
python3 patcher.py --input EX-V7.BIN --output EX-V7-PATCHED.BIN

# Also export a Stage-2 recovery image (full, hbn, or ram mode)
python3 patcher.py --input EX-V7.BIN --output EX-V7-PATCHED.BIN --export-uranus uranus.bin --uranus-mode full
```

## 4. Architecture

### Target Hardware & Firmware Specifications

- **Model**: Casio Exilim EX-V7 (2007, Internal Model Code: `KX-825` / `0x0825`)
- **CPU / SiP Architecture**: Renesas / Hitachi **SH-2A (`R8J30235EBGV`, 32-bit RISC, Big-Endian, Internal Platform Codename: `Uranus`)**
- **Operating Subsystem**: uITRON-based micro-kernel / RTOS with modular tasks (`SYSINI`, `MAIN`, `DISP MNG`, `CCDD`, `LEND`, `ISM`)
- **Firmware Container**: `EX-V7.BIN` (Version 1.03, `2,385,616` bytes / `0x2466d0` bytes)
- **Binary Encoding**: The retail `EX-V7.BIN` image is bitwise-inverted (`physical_byte ^ 0xFF == decoded_byte`) and prepended with a `0x400`-byte outer container header.

### Memory Map
| File Offset Range | Virtual Address (VA) | Component |
|---|---|---|
| `0x000000 - 0x000400` | N/A | Retail Container Header (`1.03.36.00`, inner offset `0x400`, size `0x2462d0`) |
| `0x000400 - 0x000480` | `0x30330000` | LoaderUpdater Header (`.\rom825.lbn`, magic `0xa5a5a5a5`) |
| `0x000480 - 0x000c80` | `0x10000480` | Stage-1 Hardware Bootloader |
| `0x004480 - 0x00b550` | `0x10000000` | Stage-2 Recovery Loader (`\uranus.bin` handler) |
| `0x00c480 - 0x00c500` | `0x10030000` | Main ROM Header (`.\rom825.hbn`, magic `0x00000001`) |
| `0x00c500 - 0x2466d0` | `0x10030080+` | Main System ROM & OS (`VA = file_offset + 0x10023b80`) |

### Stabilizer Subsystem Analysis
- **Image Stabilizer Micom (ISM)**:
  - Communicates with the hardware stabilizer voice coil actuator and gyro sensor.
  - Root status query runs via `is_stabilizer_faulty()` at `0x1003d204` (file offset `0x019684`).
  - When the hardware stabilizer is faulty, `0x1003d204` returns non-zero (`0x0001`), which triggers LCD dialog `#0x51` ("Camera stabilizer is not available"), a 5-second sleep delay at `0x10189544`, and caller retry loops at `0x1019810e`.
- **Root Fault Suppression (`0x1003d204`)**:
  - Patching `0x1003d204` to `mov #0x0, r2; rtv/n r2; nop; nop` (`e2 00 02 7b 00 09 00 09`) cleanly suppresses the fault across all tasks while keeping the physical stabilizer unpowered and quiescent.

### `uranus.bin` Emergency Firmware Restoration Architecture
When the `[SHUTTER]` button is held depressed while inserting the battery, the Stage-1 Bootloader (`0x0522`) invokes the Stage-2 Recovery Loader at `0x10000000` (file offset `0x04480`):
1. The recovery loader mounts the SD card (`FAT12` / `FAT16` / `FAT32`) and loads `\uranus.bin` into DRAM at `0x30330000` via `0x1000094c` while blinking the viewfinder LED **green/red**.
2. Unlike the retail updater (`0x10176e70`), the Stage-2 Recovery Loader expects `\uranus.bin` to be **un-inverted** (`byte ^ 0xFF` already applied) and **stripped of the `0x400`-byte outer retail header** (`inv[0x400:0x2466d0]`).
3. At `0x10000050`, the recovery loader inspects the 32-bit magic field at header offset `+0x30`:
   - **`0xa5a5a5a5` (`full` mode, `inv[0x400:0x2466d0]`)**: Verifies the 32-bit additive (`+0x28`) and XOR (`+0x2c`) checksums over `+0x24` (`0x00246250`) bytes via `0x1000011e`, then erases, programs, and verifies flash starting at block 0 (`0x10000340`) while blinking the LED **green**. Turns the LED **steady green** upon completion.
   - **`0x00000001` (`hbn` mode, `inv[0xc480:0x2466d0]`)**: Verifies checksums over `0x0023a1d0` bytes and flashes only the Main ROM partition starting at Flash Block 3 (`0x00c000`), leaving bootloader blocks 0-2 untouched.
   - **`0x00000004` (`ram` mode, `inv[0xc480:0x2466d0]`)**: Copies the Main ROM payload directly into executable RAM at `0x10030080` and boots it in memory without writing to flash.

### Checksum Verification Mechanism
Both updaters verify two sets of 32-bit checksums (each consisting of a 32-bit big-endian word additive sum and XOR sum):
1. **`rom825.hbn`** (header offset `0xc4a8 - 0xc4b0`):
   - Additive sum and XOR sum from file offset `0xc500` through `0x2466d0` (`0x23a1d0` bytes).
2. **`rom825.lbn`** (header offset `0x428 - 0x430`):
   - Additive sum and XOR sum from file offset `0x480` through `0x2466d0` (`0x246250` bytes).
