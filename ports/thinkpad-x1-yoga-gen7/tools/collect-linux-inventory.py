#!/usr/bin/env python3
"""Collect a privacy-conscious, read-only hardware inventory on the target Kubuntu laptop.

The report goes to stdout by default. The optional --output path is created exclusively:
existing files are never overwritten and parent directories are never created.
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except (OSError, UnicodeError):
        return ""


def read_link(path: Path) -> str:
    try:
        return str(path.resolve(strict=False))
    except (OSError, RuntimeError):
        return ""


def section(lines: list[str], title: str, rows: list[str]) -> None:
    lines.extend(["", f"## {title}"])
    lines.extend(rows if rows else ["(no readable entries)"])


def collect_dmi() -> list[str]:
    base = Path("/sys/class/dmi/id")
    # Deliberately omit all serial numbers, UUIDs, asset tags, and product SKUs.
    fields = (
        ("System vendor", "sys_vendor"),
        ("Product name", "product_name"),
        ("Product version", "product_version"),
        ("Board name", "board_name"),
        ("BIOS vendor", "bios_vendor"),
        ("BIOS version", "bios_version"),
        ("BIOS date", "bios_date"),
    )
    return [f"{label}: {value}" for label, name in fields
            if (value := read_text(base / name))]


def collect_cpu() -> list[str]:
    text = read_text(Path("/proc/cpuinfo"))
    model = next((line.split(":", 1)[1].strip()
                  for line in text.splitlines()
                  if line.lower().startswith("model name")), "")
    logical = sum(line.lower().startswith("processor") and ":" in line
                  for line in text.splitlines())
    rows = [f"Model: {model}" if model else "Model: (not readable)"]
    rows.append(f"Logical CPUs: {logical}" if logical else "Logical CPUs: (not readable)")
    core_types: list[str] = []
    for cpu in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
        value = read_text(cpu / "topology" / "core_type")
        if value:
            core_types.append(f"{cpu.name}={value}")
    if core_types:
        rows.append("Linux core_type values (kernel-defined): " + ", ".join(core_types))
    return rows


def collect_pci() -> list[str]:
    rows: list[str] = []
    prefixes = ("0x02", "0x03", "0x04", "0x06", "0x0c")
    for device in sorted(Path("/sys/bus/pci/devices").glob("*")):
        cls = read_text(device / "class")
        if not cls.startswith(prefixes):
            continue
        vendor = read_text(device / "vendor")
        product = read_text(device / "device")
        subsystem_vendor = read_text(device / "subsystem_vendor")
        subsystem_device = read_text(device / "subsystem_device")
        driver = read_link(device / "driver")
        driver_name = Path(driver).name if driver else "none"
        firmware_node = read_link(device / "firmware_node")
        row = (f"{device.name}: class={cls} id={vendor}:{product} "
               f"subsystem={subsystem_vendor}:{subsystem_device} driver={driver_name}")
        if firmware_node:
            row += f" firmware_node={firmware_node}"
        rows.append(row)
    return rows


def collect_usb() -> list[str]:
    rows: list[str] = []
    for device in sorted(Path("/sys/bus/usb/devices").glob("*")):
        # USB interface directories contain a colon and are omitted.
        if ":" in device.name:
            continue
        vendor = read_text(device / "idVendor")
        product_id = read_text(device / "idProduct")
        if not vendor or not product_id:
            continue
        manufacturer = read_text(device / "manufacturer")
        product = read_text(device / "product")
        label = " ".join(part for part in (manufacturer, product) if part)
        bus = read_text(device / "busnum")
        devpath = read_text(device / "devpath")
        speed = read_text(device / "speed")
        rows.append(
            f"{device.name}: {vendor}:{product_id} {label} "
            f"bus={bus or '?'} port_path={devpath or '?'} speed={speed or '?'}"
        )
    return rows


def collect_acpi() -> list[str]:
    rows: list[str] = []
    wanted = ("syna8016", "wacf2200", "pnp0c50", "pnp0c09",
              "pnp0c14", "intc", "gpio", "i2c")
    for device in sorted(Path("/sys/bus/acpi/devices").glob("*")):
        hid = read_text(device / "hid")
        path = read_text(device / "path")
        match_text = " ".join((device.name, hid, path)).lower()
        if not any(token in match_text for token in wanted):
            continue
        status = read_text(device / "status")
        modalias = read_text(device / "modalias")
        fields = [f"hid={hid or '?'}", f"status={status or '?'}"]
        if path:
            fields.append(f"path={path}")
        if modalias:
            fields.append(f"modalias={modalias}")
        rows.append(f"{device.name}: " + " ".join(fields))
    return rows


def collect_i2c() -> list[str]:
    rows: list[str] = []
    for device in sorted(Path("/sys/bus/i2c/devices").glob("*")):
        if device.name.startswith("i2c-"):
            continue
        name = read_text(device / "name")
        modalias = read_text(device / "modalias")
        firmware_node = read_link(device / "firmware_node")
        fields = [f"name={name or '?'}"]
        if modalias:
            fields.append(f"modalias={modalias}")
        if firmware_node:
            fields.append(f"firmware_node={firmware_node}")
        rows.append(f"{device.name}: " + " ".join(fields))
    return rows


def collect_acpi_tables() -> list[str]:
    rows: list[str] = []
    roots = (Path("/sys/firmware/acpi/tables"),
             Path("/sys/firmware/acpi/tables/dynamic"))
    for root in roots:
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for table in entries:
            if not table.is_file():
                continue
            try:
                # Read only the 36-byte ACPI header, never dump table contents.
                with table.open("rb") as stream:
                    header = stream.read(36)
            except OSError:
                continue
            if len(header) < 36:
                continue
            signature = header[0:4].decode("ascii", errors="replace").strip("\x00 ")
            revision = header[8]
            oem_id = header[10:16].decode("ascii", errors="replace").strip("\x00 ")
            oem_table = header[16:24].decode("ascii", errors="replace").strip("\x00 ")
            rows.append(
                f"{table.name}: signature={signature} revision={revision} "
                f"oem_id={oem_id} oem_table_id={oem_table}"
            )
    return rows


def collect_displays() -> list[str]:
    rows: list[str] = []
    for connector in sorted(Path("/sys/class/drm").glob("card*-eDP-*")):
        status = read_text(connector / "status")
        modes = [line for line in read_text(connector / "modes").splitlines() if line]
        rows.append(
            f"{connector.name}: status={status or '?'} "
            f"modes={', '.join(modes) if modes else '(none readable)'}"
        )
    return rows


def collect_gpu_topology() -> list[str]:
    rows: list[str] = []
    for report in sorted(Path("/sys/kernel/debug/dri").glob("*/i915_sseu_status")):
        value = read_text(report)
        if value:
            rows.append(f"{report}:")
            rows.extend(f"  {line}" for line in value.splitlines())
    return rows


def build_report() -> str:
    lines = [
        "ThinkPad X1 Yoga Gen 7 read-only Linux inventory",
        f"Kernel: {platform.release()}",
        "",
        "Privacy/safety: serials, UUIDs, MAC addresses, storage devices, and partition tables are not collected.",
        "This script reads selected /proc and /sys data only; it does not invoke sudo, install packages, mount filesystems,",
        "change settings, or write a report unless --output is explicitly supplied.",
    ]
    section(lines, "System and BIOS", collect_dmi())
    section(lines, "Processor", collect_cpu())
    section(lines, "PCI devices (display, audio, network, bridges, and serial-bus controllers)", collect_pci())
    section(lines, "USB devices (no serial-number fields)", collect_usb())
    section(lines, "Relevant ACPI devices", collect_acpi())
    section(lines, "I2C adapters and clients", collect_i2c())
    section(lines, "ACPI table headers only", collect_acpi_tables())
    section(lines, "Internal eDP connectors", collect_displays())
    section(lines, "i915 EU topology (when debugfs already exposes it)", collect_gpu_topology())
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="create a new report at PATH (choose a removable USB path; never overwrites or creates directories)",
    )
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        parser.error("run this on the ThinkPad from Kubuntu; the main PC inventory would not describe the target")

    report = build_report()
    if args.output is None:
        sys.stdout.write(report)
        return 0

    try:
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(report)
    except FileExistsError:
        parser.error(f"refusing to overwrite existing report: {args.output}")
    except OSError as exc:
        parser.error(f"cannot create report at {args.output}: {exc}")
    print(f"Created report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
