#!/usr/bin/env python3
"""Stage and validate a local-only X1 Yoga Gen 7 Recovery EFI candidate.

This does not create installer media or write to a USB/disk. The private
SMBIOS identity is generated into the staged config and is never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import plistlib
import secrets
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from pathlib import Path


OC_VERSION = "1.0.8"
OC_URL = (
    "https://github.com/acidanthera/OpenCorePkg/releases/download/1.0.8/"
    "OpenCore-1.0.8-RELEASE.zip"
)
OC_SHA256 = "2011e8b7216ecb2645d97ea710df965947edd406846e92050b9bc4190be6d27b"
MODEL = "MacBookPro16,2"

KEXTS = {
    "Lilu.kext": {
        "Lilu": "e3f00df5aca98c70363489292514f088ae3b667417c9c5afdd33799ff09390bd",
    },
    "VirtualSMC.kext": {
        "VirtualSMC": "bf91e9542b86c20acaf210353a93742291c49328e2d14b03fa0fa4fc52b3b5ce",
    },
    "WhateverGreen.kext": {
        "WhateverGreen": "059967ba94fba6cbf3c2cdf40fb4277e00a2a42bc1aa250e632103acbc3efdd0",
    },
    "AirportItlwm.kext": {
        "AirportItlwm": "259bac9432bffa8bf9c73411d8ac8f4a854552375e9f60ba0870ea3151ed973c",
    },
    "VoodooPS2Controller.kext": {
        "VoodooPS2Controller": "be6f3aa9dc88954462e422df78d8d7d129cb91b8fd03c4018ef04cc9f472e8f0",
        "Contents/PlugIns/VoodooPS2Keyboard.kext/VoodooPS2Keyboard":
            "a1e4903278b2028da9fea8feeb911026fb029ed8164d947bd7481245ae86193b",
        "Contents/PlugIns/VoodooPS2Mouse.kext/VoodooPS2Mouse":
            "075be10067839c38366da4f8864a87506e0c5d0305f98e540cd30e6da9adacab",
    },
}

EFI_FILES = {
    "X64/EFI/BOOT/BOOTx64.efi": "EFI/BOOT/BOOTx64.efi",
    "X64/EFI/OC/OpenCore.efi": "EFI/OC/OpenCore.efi",
    "X64/EFI/OC/Drivers/OpenRuntime.efi": "EFI/OC/Drivers/OpenRuntime.efi",
    "Utilities/ocvalidate/ocvalidate.linux": None,
    "Utilities/macserial/macserial.linux": None,
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bundle_executable(bundle: Path) -> tuple[Path, dict]:
    info_path = bundle / "Contents/Info.plist"
    info = plistlib.loads(info_path.read_bytes())
    rel = Path("Contents/MacOS") / info["CFBundleExecutable"]
    return bundle / rel, info


def generate_identity(macserial: Path) -> dict:
    result = subprocess.run(
        [str(macserial), "-m", MODEL, "-g", "-n", "1"],
        check=True,
        capture_output=True,
        text=True,
    )
    parts = [part.strip() for part in result.stdout.strip().split("|")]
    if len(parts) != 2 or not all(parts):
        raise RuntimeError("Pinned macserial returned an unexpected serial/MLB format")
    serial, mlb = parts
    return {
        "SystemProductName": MODEL,
        "SystemSerialNumber": serial,
        "MLB": mlb,
        "SystemUUID": str(uuid.uuid4()).upper(),
        "ROM": secrets.token_bytes(6),
    }


def read_identity(config_path: Path) -> dict:
    config = plistlib.loads(config_path.read_bytes())
    identity = config["PlatformInfo"]["Generic"]
    if identity.get("SystemProductName") != MODEL:
        raise ValueError(f"Identity source must use {MODEL}")
    fields = ("SystemSerialNumber", "MLB", "SystemUUID", "ROM")
    if any(not identity.get(field) for field in fields):
        raise ValueError("Identity source has incomplete SMBIOS values")
    if len(identity["ROM"]) != 6:
        raise ValueError("Identity source ROM must be exactly 6 bytes")
    uuid.UUID(identity["SystemUUID"])
    return {field: identity[field] for field in fields} | {"SystemProductName": MODEL}


def copy_release_file(archive: zipfile.ZipFile, source: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(archive.read(source))


def validate_payload(config: dict, staged: Path) -> None:
    oc = staged / "EFI/OC"
    for item in config["Kernel"]["Add"]:
        if not item["Enabled"]:
            continue
        bundle = oc / "Kexts" / item["BundlePath"]
        if not bundle.is_dir():
            raise RuntimeError(f"Enabled kext bundle is missing: {item['BundlePath']}")
        for key in ("ExecutablePath", "PlistPath"):
            if not (bundle / item[key]).is_file():
                raise RuntimeError(f"Missing {key} for enabled kext {item['BundlePath']}: {item[key]}")
    for item in config["UEFI"]["Drivers"]:
        if item["Enabled"] and not (oc / "Drivers" / item["Path"]).is_file():
            raise RuntimeError(f"Missing enabled UEFI driver: {item['Path']}")
    for item in config["ACPI"]["Add"]:
        if item["Enabled"] and not (oc / item["Path"]).is_file():
            raise RuntimeError(f"Missing enabled ACPI table: {item['Path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new local staging directory")
    parser.add_argument("--opencore-zip", type=Path, help="official OpenCore 1.0.8 release archive")
    parser.add_argument("--repo-root", type=Path, help="repository root (normally auto-detected)")
    parser.add_argument("--template", type=Path, help="recovery plist template (normally from the Yoga port)")
    parser.add_argument("--reuse-config", type=Path, help="reuse private SMBIOS values from a prior config")
    args = parser.parse_args()

    if not sys.platform.startswith("linux"):
        raise SystemExit("Run this staging helper on Linux; no USB or disk operations are performed.")

    script = Path(__file__).resolve()
    repo = args.repo_root.resolve() if args.repo_root else script.parents[3]
    port = repo / "ports/thinkpad-x1-yoga-gen7"
    template = args.template.expanduser().resolve() if args.template else port / "config-recovery-template.plist"
    kext_source = repo / "EFI/OC/Kexts"
    if not template.is_file() or not kext_source.is_dir():
        raise SystemExit("Could not locate the Yoga template and tracked kext source under repository root")

    output = args.output.expanduser().resolve()
    if output.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="x1yoga-recovery-", dir=output.parent) as tmp_name:
        tmp = Path(tmp_name)
        archive_path = args.opencore_zip.expanduser().resolve() if args.opencore_zip else tmp / "OpenCore.zip"
        if not args.opencore_zip:
            request = urllib.request.Request(OC_URL, headers={"User-Agent": "x1-yoga-recovery-stager"})
            with urllib.request.urlopen(request, timeout=60) as response, archive_path.open("wb") as out:
                shutil.copyfileobj(response, out)
        actual_hash = sha256(archive_path)
        if actual_hash != OC_SHA256:
            raise SystemExit(
                f"OpenCore archive SHA-256 mismatch ({actual_hash}); expected the pinned {OC_VERSION} release"
            )

        staged = tmp / "stage"
        (staged / "EFI/BOOT").mkdir(parents=True)
        (staged / "EFI/OC/Drivers").mkdir(parents=True)
        (staged / "EFI/OC/Kexts").mkdir(parents=True)
        with zipfile.ZipFile(archive_path) as archive:
            for source, relative in EFI_FILES.items():
                destination = tmp / Path(source).name if relative is None else staged / relative
                copy_release_file(archive, source, destination)

        macserial = tmp / "macserial.linux"
        ocvalidate = tmp / "ocvalidate.linux"
        macserial.chmod(0o755)
        ocvalidate.chmod(0o755)

        identity = read_identity(args.reuse_config) if args.reuse_config else generate_identity(macserial)
        config = plistlib.loads(template.read_bytes())
        generic = config["PlatformInfo"]["Generic"]
        generic.update(identity)
        config_path = staged / "EFI/OC/config.plist"
        config_path.write_bytes(plistlib.dumps(config, fmt=plistlib.FMT_XML, sort_keys=False))

        staged_kexts = staged / "EFI/OC/Kexts"
        kext_lines = []
        for name, expected_execs in KEXTS.items():
            source = kext_source / name
            if not source.is_dir():
                raise SystemExit(f"Missing tracked kext: {source}")
            destination = staged_kexts / name
            shutil.copytree(source, destination)
            for relative, expected in expected_execs.items():
                if relative == "Contents/PlugIns/VoodooPS2Keyboard.kext/VoodooPS2Keyboard":
                    plugin = destination / "Contents/PlugIns/VoodooPS2Keyboard.kext"
                    executable = plugin / "Contents/MacOS/VoodooPS2Keyboard"
                    info_path = plugin / "Contents/Info.plist"
                    info = plistlib.loads(info_path.read_bytes())
                elif relative == "Contents/PlugIns/VoodooPS2Mouse.kext/VoodooPS2Mouse":
                    plugin = destination / "Contents/PlugIns/VoodooPS2Mouse.kext"
                    executable = plugin / "Contents/MacOS/VoodooPS2Mouse"
                    info_path = plugin / "Contents/Info.plist"
                    info = plistlib.loads(info_path.read_bytes())
                else:
                    executable, info = bundle_executable(destination)
                actual = sha256(executable)
                if actual != expected:
                    raise SystemExit(f"Unexpected {name} binary for {info.get('CFBundleVersion')}: {actual}")
                kext_lines.append(f"{name} {info.get('CFBundleVersion')} {actual}")

        validate_payload(config, staged)
        check = subprocess.run([str(ocvalidate), str(config_path)], capture_output=True, text=True)
        if check.returncode != 0:
            raise SystemExit(check.stdout + check.stderr)
        print(check.stdout.strip())

        manifest = [
            "Local staging only; not a boot-tested EFI and not installer media.",
            f"OpenCore: {OC_VERSION}; archive SHA-256: {actual_hash}",
            f"SMBIOS model: {MODEL}; a local serial/MLB/UUID/ROM set is in config.plist.",
            "Do not commit or publish this generated config. Apple service acceptance is not verified.",
            "Kext executable SHA-256 values:",
            *kext_lines,
            f"config.plist SHA-256: {sha256(config_path)}",
            "No BaseSystem image, ACPI tables, USB map, GPU spoof, NootedGreen, Bluetooth, audio, or I2C kexts included.",
            "This helper did not touch a USB, internal drive, partition table, or firmware settings.",
        ]
        (staged / "STAGING-README.txt").write_text("\n".join(manifest) + "\n", encoding="utf-8")
        os.replace(staged, output)

    print(f"Staged and validated Recovery EFI at: {output}")
    print("SMBIOS values were not printed. Keep this generated config private and reuse it for future builds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
