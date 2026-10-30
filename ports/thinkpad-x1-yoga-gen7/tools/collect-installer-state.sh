#!/bin/sh
# Read-only Tahoe Recovery diagnostics. The only write is the report beside
# this script, on the external USB volume that contains it.

set -u

script_dir=$(CDPATH= cd "$(dirname "$0")" 2>/dev/null && pwd -P) || {
    echo "Cannot locate the USB folder containing this script." >&2
    exit 1
}

if ! command -v diskutil >/dev/null 2>&1 || ! command -v plutil >/dev/null 2>&1; then
    echo "Run this from macOS Recovery Terminal." >&2
    exit 1
fi

disk_info=$(diskutil info -plist "$script_dir" 2>/dev/null) || {
    echo "Cannot identify the volume containing this script." >&2
    exit 1
}
device_location=$(printf '%s' "$disk_info" |
    plutil -extract DeviceLocation raw -o - - 2>/dev/null || true)
device_location=$(printf '%s' "$device_location" | tr '[:upper:]' '[:lower:]')
if [ "$device_location" != "external" ]; then
    echo "Refusing to write: this script is not on a volume identified as External." >&2
    exit 1
fi

stamp=$(date '+%Y%m%d-%H%M%S')
report="$script_dir/yoga-installer-state-$stamp.txt"
suffix=1
while [ -e "$report" ]; do
    report="$script_dir/yoga-installer-state-$stamp-$suffix.txt"
    suffix=$((suffix + 1))
done

umask 077
if ! : > "$report"; then
    echo "Cannot create the report on the USB volume." >&2
    exit 1
fi

section() {
    printf '\n===== %s =====\n' "$1" >> "$report"
}

run() {
    title=$1
    shift
    section "$title"
    if "$@" >> "$report" 2>&1; then
        :
    else
        result=$?
        printf 'Command exited with status %s.\n' "$result" >> "$report"
    fi
}

section "Capture information"
printf 'Captured: %s\n' "$(date)" >> "$report"
printf 'Recovery build:\n' >> "$report"
sw_vers >> "$report" 2>&1 || true

run "Kernel" uname -a
run "Disk layout" diskutil list
run "APFS containers and volumes" diskutil apfs list
run "Mounted volumes" mount
run "Volume space" df -h

for log_path in \
    /var/log/install.log \
    /var/log/osinstallersetup.log \
    /var/log/system.log
do
    if [ -f "$log_path" ]; then
        section "Tail of $log_path"
        tail -n 180 "$log_path" >> "$report" 2>&1 || true
    fi
done

for volume in /Volumes/*
do
    [ -d "$volume" ] || continue
    for log_path in \
        "$volume/private/var/log/install.log" \
        "$volume/var/log/install.log" \
        "$volume/private/var/log/osinstallersetup.log" \
        "$volume/var/log/osinstallersetup.log"
    do
        if [ -f "$log_path" ]; then
            section "Tail of $log_path"
            tail -n 180 "$log_path" >> "$report" 2>&1 || true
        fi
    done
    for metadata in \
        "$volume/macOS Install Data/InstallInfo.plist" \
        "$volume/System/Library/CoreServices/SystemVersion.plist"
    do
        if [ -f "$metadata" ]; then
            section "Metadata: $metadata"
            plutil -p "$metadata" >> "$report" 2>&1 || true
        fi
    done
done

if command -v log >/dev/null 2>&1; then
    section "Installer-related unified log (last two hours, up to 300 lines)"
    log show --last 2h --style compact \
        --predicate 'process == "OSInstaller" OR process == "osinstallersetupd" OR process == "InstallAssistant" OR process == "installer"' \
        2>&1 | tail -n 300 >> "$report"
fi

sync
printf 'Saved Recovery diagnostics to:\n%s\n' "$report"
