#!/usr/bin/env python3
"""Read-only helper for mapping physical Yoga USB connectors to Linux port paths.

Run on the ThinkPad from Kubuntu. The tool prints newly attached USB devices
and asks for the physical connector label. It never reads USB serial numbers,
never writes a report, and does not need root access.
"""
from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import time
from pathlib import Path

USB_ROOT = Path("/sys/bus/usb/devices")
USB_DEVICE_NAME = re.compile(r"^[0-9]+-[0-9]+(?:\.[0-9]+)*$")
PCI_BDF = re.compile(r"[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]")


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def pci_chain(path: Path) -> str:
    try:
        resolved = str(path.resolve(strict=False))
    except (OSError, RuntimeError):
        return "unknown"
    matches = PCI_BDF.findall(resolved)
    return ",".join(matches) if matches else "unknown"


def connected_devices() -> dict[str, dict[str, str]]:
    devices: dict[str, dict[str, str]] = {}
    try:
        entries = sorted(USB_ROOT.iterdir())
    except OSError as exc:
        raise RuntimeError(f"cannot read {USB_ROOT}: {exc}") from exc

    for path in entries:
        if not USB_DEVICE_NAME.fullmatch(path.name):
            continue
        vendor = read_text(path / "idVendor")
        product = read_text(path / "idProduct")
        if not vendor or not product:
            continue
        bus = read_text(path / "busnum")
        route = read_text(path / "devpath")
        root_hub = USB_ROOT / f"usb{bus}"
        devices[path.name] = {
            "sysfs": path.name,
            "bus": bus or "unknown",
            "route": route or "unknown",
            "id": f"{vendor}:{product}",
            "speed_mbps": read_text(path / "speed") or "unknown",
            "class": read_text(path / "bDeviceClass") or "unknown",
            "pci_chain": pci_chain(root_hub),
        }
    return devices


def describe(device: dict[str, str]) -> str:
    return (
        f"id={device['id']} speed={device['speed_mbps']}M "
        f"bus={device['bus']} route={device['route']} "
        f"sysfs={device['sysfs']} pci_chain={device['pci_chain']} "
        f"class={device['class']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-x1-yoga-gen7",
        action="store_true",
        help="confirm this is being run on the target ThinkPad, not the main PC",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        metavar="SECONDS",
        help="USB change polling interval from 0.1 to 5 seconds (default: 0.5)",
    )
    args = parser.parse_args()

    if platform.system().lower() != "linux":
        parser.error("run this on the ThinkPad from Kubuntu")
    if not args.confirm_x1_yoga_gen7:
        parser.error("refusing to run without --confirm-x1-yoga-gen7")
    vendor = read_text(Path("/sys/class/dmi/id/sys_vendor"))
    if "lenovo" not in vendor.casefold():
        parser.error("system vendor is not Lenovo; refusing to collect from this machine")
    if not 0.1 <= args.interval <= 5.0:
        parser.error("--interval must be between 0.1 and 5 seconds")

    try:
        current = connected_devices()
    except RuntimeError as exc:
        parser.error(str(exc))

    print("Read-only USB connector mapping; USB serial numbers are not read.")
    print("Currently connected USB devices:")
    if current:
        for device in current.values():
            print(f"  {describe(device)}")
    else:
        print("  (none found)")
    print("Unplug the test device, then insert it into one physical connector at a time.")
    print("For each new device, enter a short label such as 'left USB-C' or 'right USB-A'.")
    print("Repeat for every connector and, if available, both USB 2 and USB 3 test devices.")
    print("Press Ctrl+C when finished. This captures USB paths, not Thunderbolt PCIe topology.")
    print("Watching for USB changes...")

    try:
        while True:
            time.sleep(args.interval)
            try:
                updated = connected_devices()
            except RuntimeError as exc:
                print(f"USB scan temporarily unavailable: {exc}", file=sys.stderr)
                continue

            added = [updated[name] for name in sorted(updated.keys() - current.keys())]
            removed = [current[name] for name in sorted(current.keys() - updated.keys())]
            current = updated

            for device in removed:
                print(f"REMOVED {describe(device)}", flush=True)
            for device in added:
                print(f"ATTACHED {describe(device)}", flush=True)
                try:
                    label = input("  Physical connector label (blank to skip): ").strip()
                except EOFError:
                    label = ""
                if label:
                    record = {"label": label[:80], **device}
                    print("MAP " + json.dumps(record, sort_keys=True), flush=True)
    except KeyboardInterrupt:
        print("Stopped; no files were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
