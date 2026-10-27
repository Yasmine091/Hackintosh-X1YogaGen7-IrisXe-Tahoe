#!/usr/bin/env python3
"""Export Linux ACPI tables to a new folder on an already-mounted USB device.

Raw ACPI tables are machine-specific firmware data. Keep them private and out of Git.
The exporter never mounts, partitions, formats, or writes by an unchecked path: it
opens the destination parent first, verifies that filesystem is USB-backed, and
performs all writes relative to that open directory handle.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def decode_mount_field(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def open_usb_parent(path: Path) -> tuple[int, Path]:
    """Open and verify the destination parent; return its fd for race-safe writes."""
    parent = path.parent.resolve(strict=True)
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        parent_fd = os.open(parent, flags)
    except OSError as exc:
        raise RuntimeError(f"cannot open output parent {parent}: {exc}") from exc

    try:
        opened_path = Path(os.path.realpath(f"/proc/self/fd/{parent_fd}"))
        device = os.fstat(parent_fd).st_dev
        opened_device = f"{os.major(device)}:{os.minor(device)}"
        try:
            mount_lines = Path("/proc/self/mountinfo").read_text().splitlines()
        except OSError as exc:
            raise RuntimeError(f"cannot read Linux mount information: {exc}") from exc

        matches: list[tuple[int, str, str]] = []
        for line in mount_lines:
            fields = line.split()
            if len(fields) < 7:
                continue
            mountpoint = decode_mount_field(fields[4])
            try:
                is_ancestor = os.path.commonpath((str(opened_path), mountpoint)) == mountpoint
            except ValueError:
                continue
            if is_ancestor and fields[2] == opened_device:
                matches.append((len(mountpoint), fields[2], mountpoint))

        if not matches:
            raise RuntimeError(f"no matching mounted filesystem found for output parent {opened_path}")
        _, major_minor, mountpoint = max(matches)
        if mountpoint == "/":
            raise RuntimeError("refusing to write to the root filesystem; select a mounted USB folder")

        device_link = Path("/sys/dev/block") / major_minor
        try:
            device_path = device_link.resolve(strict=True)
        except OSError as exc:
            raise RuntimeError(f"cannot verify output device {major_minor} through sysfs") from exc
        if not any(re.fullmatch(r"usb[0-9]+", part) for part in device_path.parts):
            raise RuntimeError(
                f"refusing output on non-USB device {major_minor}; selected mount is {mountpoint}"
            )
        return parent_fd, opened_path
    except Exception:
        os.close(parent_fd)
        raise


def collect_tables() -> list[tuple[str, bytes]]:
    roots = (
        ("static", Path("/sys/firmware/acpi/tables")),
        ("dynamic", Path("/sys/firmware/acpi/tables/dynamic")),
    )
    result: list[tuple[str, bytes]] = []
    for scope, root in roots:
        try:
            entries = sorted(root.iterdir())
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RuntimeError(f"cannot read ACPI table directory {root}: {exc}") from exc

        for entry in entries:
            if not entry.is_file():
                continue
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", entry.name)
            try:
                data = entry.read_bytes()
            except OSError as exc:
                raise RuntimeError(
                    f"cannot read {entry}; if Kubuntu denies access, rerun with sudo"
                ) from exc
            if len(data) >= 36:
                result.append((f"{scope}-{safe_name}.bin", data))

    if not result:
        raise RuntimeError("no readable ACPI tables were found under /sys/firmware/acpi/tables")
    return result


def write_file(directory_fd: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    file_fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
    with os.fdopen(file_fd, "wb") as stream:
        stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-x1-yoga-gen7",
        action="store_true",
        help="confirm this command is being run on the target ThinkPad, not the main PC",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        metavar="USB_PATH",
        help="new output folder under an already-mounted USB filesystem; the folder must not exist",
    )
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        parser.error("run this from Kubuntu on the target ThinkPad")
    if not args.confirm_x1_yoga_gen7:
        parser.error("refusing to run without --confirm-x1-yoga-gen7")
    if "lenovo" not in read_text(Path("/sys/class/dmi/id/sys_vendor")).casefold():
        parser.error("system vendor is not Lenovo; refusing to collect from this machine")

    requested = args.output_dir.expanduser()
    if not requested.is_absolute() or not requested.name or requested.name in (".", ".."):
        parser.error("--output-dir must be an absolute path naming a new folder")
    if requested.exists() or requested.is_symlink():
        parser.error(f"refusing to overwrite existing path: {requested}")

    parent_fd = -1
    try:
        parent_fd, parent = open_usb_parent(requested)
        tables = collect_tables()
        os.mkdir(requested.name, mode=0o700, dir_fd=parent_fd)
        output_fd = os.open(
            requested.name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        try:
            manifest = {
                "formatVersion": 1,
                "createdUtc": datetime.now(timezone.utc).isoformat(),
                "tableCount": len(tables),
                "tables": [],
                "privacy": "Raw machine-specific ACPI firmware data. Do not commit or share without review.",
            }
            for filename, data in tables:
                write_file(output_fd, filename, data)
                manifest["tables"].append({
                    "file": filename,
                    "sizeBytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "signature": data[:4].decode("ascii", errors="replace"),
                })
            write_file(
                output_fd,
                "manifest.json",
                (json.dumps(manifest, indent=2) + "\n").encode("utf-8"),
            )
        finally:
            os.close(output_fd)
    except (OSError, RuntimeError) as exc:
        parser.error(str(exc))
    finally:
        if parent_fd >= 0:
            os.close(parent_fd)

    print(f"Exported {len(tables)} ACPI tables to {parent / requested.name}")
    print("Keep these firmware files private and out of Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
