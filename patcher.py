#!/usr/bin/env python3
"""
Casio Exilim EX-V7 Firmware Customizer and Recovery Builder.
"""

import argparse
import datetime
import functools
import json
import operator
import os
import struct


class ExV7Firmware:
    def __init__(self, filepath):
        # Read raw firmware file from disk.
        with open(filepath, "rb") as file_handle:
            self.raw = bytearray(file_handle.read())
        # Invert all bytes with 0xFF to decode the container.
        self.inv = bytearray(byte_val ^ 0xFF for byte_val in self.raw)
        self.validate_original_header()

    def validate_original_header(self):
        # Verify partition signatures for rom825.lbn and rom825.hbn.
        if (
            self.inv[0x400:0x40C] != b".\\rom825.lbn"
            or self.inv[0xC480:0xC48C] != b".\\rom825.hbn"
        ):
            raise ValueError("Invalid EX-V7.BIN: Header signatures do not match.")

    def va_to_offset(self, va):
        # Convert Main ROM virtual address to file offset.
        if 0x10030000 <= va < 0x10030000 + len(self.inv) - 0xC480:
            return va - 0x10023B80
        raise ValueError(f"Virtual address {hex(va)} is out of bounds.")

    def patch_stabilizer_status(self):
        # Patch is_stabilizer_faulty() at VA 0x1003d204 to return 0.
        off = self.va_to_offset(0x1003D204)
        self.inv[off : off + 8] = b"\xe2\x00\x02\x7b\x00\x09\x00\x09"
        print("[+] Applied Stabilizer Fault Suppression (0x1003d204 -> return 0).")

    def patch_version_string(self, new_ver="1.31.36.00"):
        # Write custom ASCII version string into outer and Main ROM headers.
        ver_bytes = new_ver.encode("ascii")
        if len(ver_bytes) > 10:
            raise ValueError("Version string must be 10 characters or fewer.")
        ver_bytes = ver_bytes.ljust(11, b"\x00")

        self.inv[0x8 : 0x8 + len(ver_bytes)] = ver_bytes
        self.inv[0xC4C0 : 0xC4C0 + len(ver_bytes)] = ver_bytes
        print(f"[+] Updated Firmware Version String to '{new_ver}'.")

    def apply_asset_overrides(self, patched_assets_dir="assets_patched"):
        # Apply declarative mode icon overrides from JSON configuration.
        if not os.path.exists(patched_assets_dir):
            return

        mode_icons_override = os.path.join(patched_assets_dir, "mode_icons.json")
        if os.path.exists(mode_icons_override):
            with open(mode_icons_override, "r") as file_handle:
                overrides = json.load(file_handle)

            named_icons = {
                "VIEW": 0x02820001,
                "INTERVAL": 0x02820002,
                "MOVIE": 0x02820003,
                "BEST_ALBUM": 0x02820004,
                "MANUAL": 0x02820005,
                "NIGHT": 0x02820006,
                "BEST_SHOT": 0x02820007,
                "AUTO": 0x02820008,
                "PLAY": 0x02820009,
                "MP3": 0x0282000A,
                "DIGITAL_FL": 0x0282000B,
                "STEREO": 0x0282000C,
                "TWO_SHOT": 0x02820011,
                "MACRO": 0x02820012,
                "APERTURE": 0x02820013,
                "SHUTTER": 0x0282000D,
            }

            mode_offsets = {
                "BEST_SHOT": 0x212A5C,
                "AUTO": 0x212A6C,
                "NIGHT": 0x212A4C,
                "MANUAL": 0x212A3C,
                "BEST_ALBUM": 0x212A2C,
                "MOVIE": 0x212A1C,
            }

            for mode_name, replacement in overrides.items():
                clean_name = mode_name.strip()
                if clean_name in mode_offsets:
                    off = mode_offsets[clean_name]
                    target_rid = None
                    if isinstance(replacement, int):
                        target_rid = replacement
                    elif isinstance(replacement, str):
                        if replacement.startswith("0x"):
                            target_rid = int(replacement, 16)
                        elif replacement.upper() in named_icons:
                            target_rid = named_icons[replacement.upper()]

                    if target_rid is not None:
                        self.inv[off + 12 : off + 16] = struct.pack(">I", target_rid)
                        print(
                            f"[+] Replaced {clean_name} mode icon with {replacement} "
                            f"({hex(target_rid)}) at offset {hex(off + 12)}."
                        )

    def recompute_checksums(self):
        # Compute 32-bit additive and XOR checksums for rom825.hbn.
        words_hbn = struct.unpack(
            f">{(0x2466D0 - 0xC500) // 4}I", self.inv[0xC500:0x2466D0]
        )
        sum_hbn = sum(words_hbn) & 0xFFFFFFFF
        xor_hbn = functools.reduce(operator.xor, words_hbn)
        self.inv[0xC4A8:0xC4AC] = struct.pack(">I", sum_hbn)
        self.inv[0xC4AC:0xC4B0] = struct.pack(">I", xor_hbn)
        print(
            f"[+] Computed rom825.hbn Checksum: Add={hex(sum_hbn)}, Xor={hex(xor_hbn)}"
        )

        # Compute 32-bit additive and XOR checksums for rom825.lbn.
        words_lbn = struct.unpack(
            f">{(0x2466D0 - 0x480) // 4}I", self.inv[0x480:0x2466D0]
        )
        sum_lbn = sum(words_lbn) & 0xFFFFFFFF
        xor_lbn = functools.reduce(operator.xor, words_lbn)
        self.inv[0x428:0x42C] = struct.pack(">I", sum_lbn)
        self.inv[0x42C:0x430] = struct.pack(">I", xor_lbn)
        print(
            f"[+] Computed rom825.lbn Checksum: Add={hex(sum_lbn)}, Xor={hex(xor_lbn)}"
        )

    def save(self, output_path):
        # Recalculate checksums and write inverted retail image to disk.
        self.recompute_checksums()
        out_bytes = bytes(byte_val ^ 0xFF for byte_val in self.inv)
        with open(output_path, "wb") as file_handle:
            file_handle.write(out_bytes)
        print(f"[+] Wrote retail firmware image to: {output_path}")

    def export_uranus(self, uranus_path, mode="full"):
        # Export un-inverted Stage-2 recovery image (uranus.bin).
        self.recompute_checksums()
        if mode == "full":
            # Full flash recovery (magic 0xa5a5a5a5 at +0x30, starts at 0x400).
            blob = bytearray(self.inv[0x400:0x2466D0])
            blob[0x30:0x34] = struct.pack(">I", 0xA5A5A5A5)
        elif mode == "hbn":
            # Main ROM partition recovery (magic 0x00000001 at +0x30, starts at 0xc480).
            blob = bytearray(self.inv[0xC480:0x2466D0])
            blob[0x30:0x34] = struct.pack(">I", 0x00000001)
        elif mode == "ram":
            # RAM-only live execution (magic 0x00000004 at +0x30, starts at 0xc480).
            blob = bytearray(self.inv[0xC480:0x2466D0])
            blob[0x30:0x34] = struct.pack(">I", 0x00000004)
        else:
            raise ValueError(f"Unsupported uranus mode: {mode}")

        with open(uranus_path, "wb") as file_handle:
            file_handle.write(blob)
        print(
            f"[+] Exported Stage-2 recovery image ({mode} mode, {len(blob)} bytes) "
            f"to: {uranus_path}"
        )


def log_patch_history(args_list, log_path="patch_history.log"):
    # Append patch execution record using ISO 8601 UTC timestamp format.
    timestamp = datetime.datetime.now(datetime.UTC).strftime(
        "[%Y-%m-%dT%H:%M:%SZ]"
    )
    formatted_args = "; ".join(args_list)
    log_entry = f"{timestamp}: {formatted_args}\n"
    with open(log_path, "a") as file_handle:
        file_handle.write(log_entry)
    print(f"[+] Logged patch execution to {log_path} using ISO 8601 timestamp.")


def main():
    parser = argparse.ArgumentParser(
        description="Casio Exilim EX-V7 Firmware Customizer and Recovery Builder"
    )
    parser.add_argument(
        "--input",
        default="EX-V7.BIN",
        help="Source original firmware (default: EX-V7.BIN)",
    )
    parser.add_argument(
        "--output",
        default="EX-V7-PATCHED.BIN",
        help="Output firmware path (default: EX-V7-PATCHED.BIN)",
    )
    parser.add_argument(
        "--bypass-stabilizer",
        action="store_true",
        default=True,
        help="Suppress stabilizer fault at 0x1003d204 (default: True)",
    )
    parser.add_argument(
        "--version-string",
        default="1.31.36.00",
        help="Firmware version tag (default: 1.31.36.00)",
    )
    parser.add_argument(
        "--assets-patched-dir",
        default="assets_patched",
        help="Directory containing asset overrides (default: assets_patched)",
    )
    parser.add_argument(
        "--export-uranus",
        default=None,
        help="Optional output path for Stage-2 recovery image (uranus.bin)",
    )
    parser.add_argument(
        "--uranus-mode",
        choices=["full", "hbn", "ram"],
        default="full",
        help="Header mode for uranus.bin: full (0xa5a5a5a5), hbn (0x1), or ram (0x4)",
    )
    parser.add_argument(
        "--log-file",
        default="patch_history.log",
        help="Path to patch history log file (default: patch_history.log)",
    )
    args = parser.parse_args()

    applied_actions = []

    fw = ExV7Firmware(args.input)
    if args.bypass_stabilizer:
        fw.patch_stabilizer_status()
        applied_actions.append("--bypass-stabilizer")
    if args.version_string:
        fw.patch_version_string(args.version_string)
        applied_actions.append(f"--version-string {args.version_string}")
    if args.assets_patched_dir:
        fw.apply_asset_overrides(args.assets_patched_dir)
        applied_actions.append(f"--assets-patched-dir {args.assets_patched_dir}")

    fw.save(args.output)

    if args.export_uranus:
        fw.export_uranus(args.export_uranus, mode=args.uranus_mode)
        applied_actions.append(
            f"--export-uranus {args.export_uranus} --uranus-mode {args.uranus_mode}"
        )

    log_patch_history(applied_actions, args.log_file)


if __name__ == "__main__":
    main()
