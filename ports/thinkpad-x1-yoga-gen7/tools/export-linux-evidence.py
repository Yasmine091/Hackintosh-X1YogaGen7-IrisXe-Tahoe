#!/usr/bin/env python3
"""Copy ACPI and Intel i915 display evidence to a new folder on a mounted USB.

The files contain machine-specific firmware/configuration information. Keep them
private and out of Git. This script is for the Yoga running Kubuntu, not the main
PC. It does not mount, partition, format, or write outside the selected USB folder.
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

MAX_DEBUGFS_BYTES = 1024 * 1024
DEBUGFS_REPORTS = (
    "i915_display_info",
    "i915_sseu_status",
    "i915_dmc_info",
    "i915_edp_psr_status",
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(errors="replace").strip()
    except OSError:
        return ""


def decode_mount_field(value: str) -> str:
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match.group(1), 8)), value)


def open_usb_parent(path: Path) -> tuple[int, Path]:
    """Open and verify the destination parent; return its fd for anchored writes."""
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

        try:
            device_path = (Path("/sys/dev/block") / major_minor).resolve(strict=True)
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


def collect_acpi() -> tuple[list[tuple[str, bytes]], list[str]]:
    roots = (
        ("static", Path("/sys/firmware/acpi/tables")),
        ("dynamic", Path("/sys/firmware/acpi/tables/dynamic")),
    )
    files: list[tuple[str, bytes]] = []
    missing: list[str] = []
    for scope, root in roots:
        try:
            entries = sorted(root.iterdir())
        except FileNotFoundError:
            missing.append(f"ACPI {scope} table directory not found: {root}")
            continue
        except OSError as exc:
            missing.append(f"ACPI {scope} tables unreadable: {exc}")
            continue

        for entry in entries:
            if not entry.is_file():
                continue
            safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", entry.name)
            try:
                data = entry.read_bytes()
            except OSError as exc:
                missing.append(f"ACPI table {entry.name} unreadable: {exc}")
                continue
            if len(data) >= 36:
                files.append((f"{scope}-{safe_name}.bin", data))
            else:
                missing.append(f"ACPI table {entry.name} shorter than its 36-byte header")

    if not files:
        raise RuntimeError("no readable ACPI tables were found")
    return files, missing


def collect_i915_debugfs() -> tuple[list[tuple[str, bytes]], list[str]]:
    root = Path("/sys/kernel/debug/dri")
    files: list[tuple[str, bytes]] = []
    missing: list[str] = []
    if not root.is_dir():
        return files, ["i915 debugfs unavailable; debugfs may not be mounted"]

    for gpu in sorted(root.iterdir()):
        if not gpu.is_dir() or not gpu.name.isdecimal():
            continue
        if not (Path("/sys/class/drm") / f"card{gpu.name}").exists():
            continue
        for name in ("i915_vbt", *DEBUGFS_REPORTS):
            source = gpu / name
            output_name = f"i915-dri{gpu.name}-{name}.{'bin' if name == 'i915_vbt' else 'txt'}"
            if not source.is_file():
                missing.append(f"{source}: not exposed by this kernel")
                continue
            try:
                with source.open("rb") as stream:
                    data = stream.read(MAX_DEBUGFS_BYTES + 1)
            except OSError as exc:
                missing.append(f"{source}: unreadable ({exc})")
                continue
            if len(data) > MAX_DEBUGFS_BYTES:
                missing.append(f"{source}: exceeds {MAX_DEBUGFS_BYTES} byte capture limit")
                continue
            if name == "i915_vbt" and not data:
                missing.append(f"{source}: empty VBT")
            elif name == "i915_vbt" and not data.startswith(b"$VBT"):
                missing.append(f"{source}: captured bytes do not start with the expected $VBT signature")
            elif not data:
                missing.append(f"{source}: empty diagnostic report")
            else:
                files.append((output_name, data))

    if not any("i915_vbt" in name for name, _ in files):
        missing.append("No readable i915_vbt binary was captured; rerun with sufficient read access if needed")
    return files, missing


def write_file(directory_fd: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    file_fd = os.open(name, flags, 0o644, dir_fd=directory_fd)
    with os.fdopen(file_fd, "wb") as stream:
        stream.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-x1-yoga-gen7",
        action="store_true",
        help="confirm this is being run on the target ThinkPad, not the main PC",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        metavar="USB_PATH",
        help="new folder under an already-mounted USB filesystem; folder must not exist",
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
        acpi_files, missing = collect_acpi()
        i915_files, i915_missing = collect_i915_debugfs()
        files = acpi_files + i915_files
        missing.extend(i915_missing)
        os.mkdir(requested.name, mode=0o755, dir_fd=parent_fd)
        output_fd = os.open(
            requested.name,
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent_fd,
        )
        try:
            manifest = {
                "formatVersion": 2,
                "createdUtc": datetime.now(timezone.utc).isoformat(),
                "fileCount": len(files),
                "files": [],
                "notCaptured": missing,
                "privacy": "Machine-specific ACPI/VBT and display diagnostics. Keep private and out of Git.",
            }
            for filename, data in files:
                write_file(output_fd, filename, data)
                manifest["files"].append({
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

    print(f"Exported {len(files)} files to {parent / requested.name}")
    if missing:
        print(f"Some evidence could not be captured; see {parent / requested.name / 'manifest.json'}")
    print("Keep this machine-specific firmware data private and out of Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
