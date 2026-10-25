#!/usr/bin/env python3
"""
Casio Exilim EX-V7 Firmware Customizer & Patcher
-----------------------------------------------
"""

import sys
import os
import struct
import functools
import operator
import argparse

class ExV7Firmware:
    def __init__(self, filepath):
        with open(filepath, "rb") as f:
            self.raw = bytearray(f.read())
        # Hardware inversion: inverted with 0xFF
        self.inv = bytearray(b ^ 0xFF for b in self.raw)
        self.validate_original_header()

    def validate_original_header(self):
        # Check header
        if self.inv[0x400:0x40c] != b".\\rom825.lbn" or self.inv[0xc480:0xc48c] != b".\\rom825.hbn":
            raise ValueError("Invalid EX-V7.BIN: Header signatures do not match.")

    def va_to_offset(self, va):
        """Translate Virtual Address in Main ROM to file offset."""
        if 0x10030000 <= va < 0x10030000 + len(self.inv) - 0xc480:
            return va - 0x10023b80
        raise ValueError(f"VA {hex(va)} out of bounds.")

    def patch_startup_bypass(self):
        """
        Option A: Bypass the startup popup and freeze delay.
        At VA 0x101894fa (file offset 0x16597a):
        Original:
          101894fa: jsr/n @0x1003d204 (d5 45 45 4b)
        Replaced with:
          101894fa: bra   0x1018956c  (a0 37)
          101894fc: nop               (00 09)
        """
        off = self.va_to_offset(0x101894fa)
        self.inv[off:off+4] = b"\xa0\x37\x00\x09"
        print("[+] Applied Startup Stabilizer Check Bypass (Instant Startup, No Popup).")

    def patch_startup_delay(self, delay_ms=500):
        """
        Customise startup delay timer.
        At VA 0x10189544 (file offset 0x1659c4):
        Original:
          10189544: movi20 #0x1388, r4 (5000 ms) -> 04 00 13 88
        """
        if not (100 <= delay_ms <= 10000):
            raise ValueError("Delay must be between 100ms and 10000ms.")
        off = self.va_to_offset(0x10189544)
        w1 = 0x0400 | ((delay_ms >> 16) & 0x0F)
        w2 = delay_ms & 0xFFFF
        self.inv[off:off+4] = struct.pack(">HH", w1, w2)
        print(f"[+] Set Startup Delay Timer to {delay_ms} ms.")

    def patch_version_string(self, new_ver="1.31.36.00"):
        """
        Patch internal firmware version string.
        Stored at file offset 0xc4c0 (VA 0x10030040) and header offset 0x8.
        """
        ver_bytes = new_ver.encode("ascii")
        if len(ver_bytes) > 10:
            raise ValueError("Version string must be <= 10 characters.")
        ver_bytes = ver_bytes.ljust(11, b"\x00")

        # File header 0x8
        self.inv[0x8:0x8+len(ver_bytes)] = ver_bytes
        # Main ROM header 0xc4c0
        self.inv[0xc4c0:0xc4c0+len(ver_bytes)] = ver_bytes
        print(f"[+] Updated Firmware Version String to '{new_ver}'.")

    def patch_menu_reminder(self):
        """
        Show warning screen if user enters the Stabilizer / AntiShake menu while faulty.
        Hooks the menu option branch at VA 0x101a21d2 (file 0x17e652).
        Triggers dialog 0x51 when selected.
        """
        off = self.va_to_offset(0x101a21de)
        # 101a21de: mov #0x51, r4 (instead of 0x52)
        self.inv[off:off+2] = b"\xe4\x51"
        print("[+] Enabled Stabilizer Menu Fault Reminder (Message #0x51 on selection).")

    def recompute_checksums(self):
        """
        Recompute additive and XOR checksums for rom825.hbn and rom825.lbn.
        """
        # 1) rom825.hbn: covers 0xc500 .. 0x2466d0
        words_hbn = struct.unpack(f">{(0x2466d0-0xc500)//4}I", self.inv[0xc500:0x2466d0])
        sum_hbn = sum(words_hbn) & 0xFFFFFFFF
        xor_hbn = functools.reduce(operator.xor, words_hbn)
        self.inv[0xc4a8:0xc4ac] = struct.pack(">I", sum_hbn)
        self.inv[0xc4ac:0xc4b0] = struct.pack(">I", xor_hbn)
        print(f"[+] Computed rom825.hbn Checksum: Add={hex(sum_hbn)}, Xor={hex(xor_hbn)}")

        # 2) rom825.lbn: covers 0x460 .. 0x2466d0
        words_lbn = struct.unpack(f">{(0x2466d0-0x460)//4}I", self.inv[0x460:0x2466d0])
        sum_lbn = sum(words_lbn) & 0xFFFFFFFF
        xor_lbn = functools.reduce(operator.xor, words_lbn)
        self.inv[0x428:0x42c] = struct.pack(">I", sum_lbn)
        self.inv[0x42c:0x430] = struct.pack(">I", xor_lbn)
        print(f"[+] Computed rom825.lbn Checksum: Add={hex(sum_lbn)}, Xor={hex(xor_lbn)}")

    def save(self, output_path):
        self.recompute_checksums()
        # Invert back to physical flashed byte format
        out_bytes = bytes(b ^ 0xFF for b in self.inv)
        with open(output_path, "wb") as f:
            f.write(out_bytes)
        print(f"[+] Successfully wrote patched firmware to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Casio Exilim EX-V7 Firmware Customizer")
    parser.add_argument("--input", default="EX-V7.BIN", help="Source original firmware (default: EX-V7.BIN)")
    parser.add_argument("--output", default="EX-V7-PATCHED.BIN", help="Output firmware path (default: EX-V7-PATCHED.BIN)")
    parser.add_argument("--bypass-startup-error", action="store_true", default=True, help="Bypass stabilizer startup error popup & freeze")
    parser.add_argument("--enable-menu-reminder", action="store_true", default=True, help="Show warning popup if stabilizer menu is navigated to")
    parser.add_argument("--version-string", default="1.31.36.00", help="Firmware version tag (default: 1.31.36.00)")
    parser.add_argument("--custom-delay-ms", type=int, default=500, help="Startup delay in ms if error display is active (default: 500)")
    args = parser.parse_args()

    fw = ExV7Firmware(args.input)
    if args.bypass_startup_error:
        fw.patch_startup_bypass()
    if args.custom_delay_ms != 5000:
        fw.patch_startup_delay(args.custom_delay_ms)
    if args.version_string:
        fw.patch_version_string(args.version_string)
    if args.enable_menu_reminder:
        fw.patch_menu_reminder()

    fw.save(args.output)

if __name__ == "__main__":
    main()
