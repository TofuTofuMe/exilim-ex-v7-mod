# Casio Exilim EX-V7 Firmware Reverse Engineering & Hacking

## 1. Target Hardware & Firmware Specifications
- **Model**: Casio Exilim EX-V7 (2007)
- **CPU Architecture**: Renesas / Hitachi **SH-2A (SH-4 / SH-2A 32-bit RISC, Big-Endian)**
- **Operating Subsystem**: Micro-kernel / RTOS with modular tasks (`SYSINI`, `MAIN`, `DISP MNG`, `CCDD`, `LEND`, `ISM`)
- **Firmware Container**: `EX-V7.BIN` (Version 1.03)
- **Binary Encoding**: The complete flash image is byte-inverted with `0xFF` (`physical_byte ^ 0xFF == decoded_byte`).

## 2. Memory Map
| File Offset Range | Virtual Address (VA) | Component |
|---|---|---|
| `0x000000 - 0x000400` | N/A | File Container Header (`1.03.36.00`) |
| `0x000400 - 0x000480` | `0x30030000` | Loader Header (`.\rom825.lbn`) |
| `0x004480 - 0x00c480` | `0x10001000` | LoaderUpdater execution code |
| `0x00c480 - 0x00c500` | `0x10030000` | Main ROM Header (`.\rom825.hbn`) |
| `0x00c500 - 0x2466d0` | `0x10030080+` | Main System ROM & OS |

## 3. Stabilizer Subsystem Analysis
- **Image Stabilizer Micom (ISM)**:
  - Communicates with the hardware stabilizer voice coil actuator and gyro sensor.
  - Status queries run via `0x1003d204` / `0x1003d0e4` (checking internal status registers at `0x10033290` / `0x10033294`).
  - When the hardware stabilizer is jammed or faulty, `0x1003d204` returns `0x0001` (fault).
- **Startup Error & Delay Trigger (`0x101894e6`, file `0x165966`)**:
  - Checks stabilizer status with `jsr/n @0x1003d204`.
  - On error, triggers LCD dialog `#0x51` ("Camera stabilizer is not available") via `0x10191790`.
  - Sets warning icon via `0x10191644`.
  - Deliberately executes a 5-second / 5000-tick delay via `movi20 #0x1388, r4; jsr/n @0x1003815e`.
  - Marks status flag `0x10295f8c` as handled and resumes camera operation.

## 4. Checksum Verification Mechanism
The firmware updater checks two sets of 32-bit checksums (each consisting of an additive sum and an XOR sum over 32-bit big-endian words):
1. **`rom825.hbn`** (header offset `0xc4a8 - 0xc4b0`):
   - Additive sum and XOR sum from file offset `0xc500` through `0x2466d0`.
2. **`rom825.lbn`** (header offset `0x428 - 0x430`):
   - Additive sum and XOR sum from file offset `0x460` through `0x2466d0`.

## 5. Automated Patcher Tool (`patcher.py`)
Run the Python patcher to apply configurations and recompute all checksums automatically:
```bash
python3 patcher.py --input EX-V7.BIN --output EX-V7-PATCHED.BIN
```

### Configurable Options
- `--bypass-startup-error`: Bypasses the startup error popup and removes the boot delay (enabled by default).
- `--enable-menu-reminder`: Re-routes warning dialog `#0x51` to show when opening the AntiShake menu option.
- `--custom-delay-ms`: Configures delay timer in milliseconds (default: 500ms).
- `--version-string`: Configures internal version string (e.g. `1.31.36.00`).
