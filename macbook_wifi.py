#!/usr/bin/env python3
"""Install the tested BCM43602 board configuration on MacBookPro14,3."""
import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.request

VERSION = "0.1.0"
UPSTREAM_URL = "https://gist.githubusercontent.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80/raw/bd7af7c6f01df3ccee1471d36cb8df15d618a6aa/brcmfmac43602-pcie.txt"
UPSTREAM_SHA256 = "b109f3e6663b0e888c2559e36f7e0109f2a3a6b9765786d11f849f16d4b32d06"
STATE_DIR = Path("/var/lib/macbookpro143-wifi")
STATE_FILE = STATE_DIR / "state.json"
MODEL = "MacBookPro14,3"


def run(args, check=True, timeout=45):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{args[0]} failed ({p.returncode}): {p.stdout.strip()}")
    return p


def read(path):
    return Path(path).read_text().strip()


def hardware():
    model = read("/sys/class/dmi/id/product_name")
    vendor = read("/sys/class/dmi/id/sys_vendor")
    if model != MODEL:
        raise ValueError(f"Supported model is {MODEL}; detected {model}.")
    if not re.fullmatch(r"[A-Za-z0-9 .,()_-]{1,80}", vendor):
        raise ValueError("Unsupported DMI vendor name.")
    matches = []
    for dev in Path("/sys/bus/pci/devices").iterdir():
        try:
            ids = tuple(read(dev / k) for k in
                        ("vendor", "device", "subsystem_vendor", "subsystem_device"))
        except OSError:
            continue
        if ids == ("0x14e4", "0x43ba", "0x106b", "0x0173"):
            matches.append(dev)
    if len(matches) != 1:
        raise ValueError("Expected exactly one BCM43602 with Apple subsystem 106b:0173.")
    dev = matches[0]
    ifaces = sorted(p.name for p in (dev / "net").glob("*") if (p / "wireless").exists())
    if len(ifaces) != 1:
        raise ValueError("The brcmfmac Wi-Fi interface must be available before installation.")
    iface = ifaces[0]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", iface):
        raise ValueError("Invalid interface name.")
    driver = (dev / "driver").resolve().name
    if driver != "brcmfmac":
        raise ValueError(f"Expected brcmfmac, detected {driver}.")
    return {"model": model, "vendor": vendor, "interface": iface}


def country_code(value):
    value = value.upper()
    table = Path("/usr/share/zoneinfo/iso3166.tab")
    if not table.is_file():
        raise ValueError("Install tzdata: /usr/share/zoneinfo/iso3166.tab is required.")
    valid = {line.split()[0] for line in table.read_text().splitlines()
             if line and not line.startswith("#")}
    if value not in valid or not re.fullmatch(r"[A-Z]{2}", value):
        raise ValueError("Use an ISO 3166-1 country code, e.g. DE for Germany.")
    return value


def source_data(local=None):
    if local:
        p = Path(local)
        if p.stat().st_size > 100_000:
            raise ValueError("NVRAM source is unexpectedly large.")
        data = p.read_bytes()
    else:
        req = urllib.request.Request(UPSTREAM_URL,
                                     headers={"User-Agent": f"macbookpro143-wifi/{VERSION}"})
        with urllib.request.urlopen(req, timeout=30) as response:
            data = response.read(100_001)
    if hashlib.sha256(data).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("NVRAM source SHA-256 mismatch; nothing will be installed.")
    return data.decode("ascii")


def usable_mac(value):
    if not re.fullmatch(r"(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", value.lower()):
        return False
    raw = bytes.fromhex(value.replace(":", ""))
    return not (raw[0] & 1) and value.lower() not in {
        "00:00:00:00:00:00", "00:90:4c:0d:f4:3e"}


def choose_mac(iface, state):
    # Reuse the per-installation value; never distribute the development machine's MAC.
    if state and usable_mac(state.get("mac", "")):
        return state["mac"]
    current = read(f"/sys/class/net/{iface}/address").lower()
    if usable_mac(current):
        return current
    raw = bytearray(secrets.token_bytes(6))
    raw[0] = (raw[0] | 2) & 0xfe
    return ":".join(f"{b:02x}" for b in raw)


def render_nvram(source, country, mac):
    settings = {"ccode": country, "regrev": "0", "macaddr": mac}
    lines = source.splitlines()
    for key, value in settings.items():
        indexes = [i for i, line in enumerate(lines) if line.startswith(key + "=")]
        if len(indexes) != 1:
            raise ValueError(f"Expected exactly one {key} in upstream NVRAM.")
        lines[indexes[0]] = f"{key}={value}"
    return ("\n".join(lines) + "\n").encode("ascii")


def paths(hw):
    board = f"brcmfmac43602-pcie.{hw['vendor']}-{hw['model']}.txt"
    return [Path("/usr/lib/firmware/brcm") / board,
            Path("/etc/modprobe.d/macbookpro143-wifi.conf"),
            Path("/etc/NetworkManager/conf.d/80-macbookpro143-wifi.conf")]


def atomic_write(path, data, mode=0o644):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing symbolic link: {path}")
    fd, temp = tempfile.mkstemp(prefix=".mbp-wifi-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            os.fchmod(f.fileno(), mode)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def snapshot(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing symbolic link: {path}")
    if not path.exists():
        return None
    if not path.is_file():
        raise ValueError(f"Not a regular file: {path}")
    return {"data": base64.b64encode(path.read_bytes()).decode(),
            "mode": path.stat().st_mode & 0o777}


def restore(path, saved):
    if saved is None:
        if Path(path).is_symlink():
            raise ValueError(f"Refusing symbolic link: {path}")
        Path(path).unlink(missing_ok=True)
    else:
        atomic_write(Path(path), base64.b64decode(saved["data"], validate=True), saved["mode"])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def install_files(mapping, previous, metadata):
    # Preserve the first pre-installation snapshot across repeat installations.
    before = {str(p): snapshot(p) for p in mapping}
    original = previous["original"] if previous else before
    state_before = snapshot(STATE_FILE)
    state = dict(metadata, original=original,
                 installed={str(p): hashlib.sha256(data).hexdigest()
                            for p, data in mapping.items()})
    try:
        for path, data in mapping.items():
            atomic_write(path, data)
        atomic_write(STATE_FILE, (json.dumps(state, indent=2) + "\n").encode(), 0o600)
    except BaseException:
        for path, saved in before.items():
            restore(path, saved)
        restore(STATE_FILE, state_before)
        raise
    return state


def uninstall_files(state):
    # Preserve local edits: stop before restoring ANY file if one was changed.
    for name, expected in state["installed"].items():
        path = Path(name)
        if path.is_symlink() or not path.is_file() or digest(path) != expected:
            raise ValueError(f"Installed file was changed or removed: {path}. "
                             "Restore it to the installed version before uninstalling.")
    before = {name: snapshot(name) for name in state["installed"]}
    try:
        for name, saved in state["original"].items():
            restore(name, saved)
        STATE_FILE.unlink()
    except BaseException:
        for name, saved in before.items():
            restore(name, saved)
        raise


def validate_state(state, hw):
    expected = {str(p) for p in paths(hw)}
    if (state.get("model") != MODEL or set(state.get("original", {})) != expected
            or set(state.get("installed", {})) != expected):
        raise ValueError("Installed state does not match this machine and supported paths.")


@contextlib.contextmanager
def locked():
    if STATE_DIR.is_symlink():
        raise ValueError("State directory must not be a symbolic link.")
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    st = STATE_DIR.stat()
    if st.st_uid != 0 or st.st_mode & 0o022:
        raise ValueError("State directory must be root-owned and not group/world writable.")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(STATE_DIR / "lock", flags, 0o600)
    with os.fdopen(fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def apply(hw, country):
    iface = hw["interface"]
    print("Reloading brcmfmac: Wi-Fi will disconnect briefly.", flush=True)
    # modprobe removes dependents first if this kernel supplies the WCC module.
    if Path("/sys/module/brcmfmac_wcc").exists():
        run(["modprobe", "-r", "brcmfmac_wcc"])
    run(["modprobe", "-r", "brcmfmac"])
    # Existing local config may also declare options; pass the tested values explicitly.
    run(["modprobe", "brcmfmac", "roamoff=1", "feature_disable=0x2000"])
    for _ in range(40):
        if Path(f"/sys/class/net/{iface}/wireless").exists():
            break
        time.sleep(.5)
    else:
        raise RuntimeError("Wi-Fi interface did not return. Run uninstall --apply.")
    time.sleep(2)
    run(["iw", "reg", "set", country])
    run(["nmcli", "general", "reload", "conf"])
    run(["iw", "dev", iface, "set", "power_save", "off"], check=False)
    # Ask NM to auto-connect existing profiles; never request or print passwords.
    result = run(["nmcli", "--wait", "30", "device", "connect", iface], check=False)
    print(result.stdout.strip())
    if result.returncode:
        raise RuntimeError("Auto-connection failed. Use the desktop Wi-Fi menu; "
                           "files remain installed. Revert with uninstall --apply.")


def clean_output(value):
    value = re.sub(r"(?im)^(\s*(?:SSID|ssid):?).*$", "SSID: [redacted]", value)
    value = re.sub(r"(?i)(?:[0-9a-f]{2}:){5}[0-9a-f]{2}", "[MAC redacted]", value)
    value = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d+)?\b", "[IP redacted]", value)
    return value


def diagnose():
    try:
        hw = hardware()
        print(f"Version: {VERSION}\nModel: {hw['model']}\nDMI vendor: {hw['vendor']}")
    except (OSError, ValueError) as e:
        print(f"Hardware check: {e}")
        return 1
    iface = hw["interface"]
    for args in (["uname", "-r"], ["iw", "dev", iface, "link"],
                 ["iw", "dev", iface, "get", "power_save"], ["iw", "reg", "get"]):
        print("\n$ " + " ".join(args))
        print(clean_output(run(args, check=False).stdout).strip())
    print("\nManaged files:")
    for p in paths(hw):
        print(f"{p}: {'present' if p.is_file() else 'absent'}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    subs = parser.add_subparsers(dest="command", required=True)
    p = subs.add_parser("install", help="Install board config; reboot unless --apply is used")
    p.add_argument("--country", required=True, help="Your actual ISO country code; tested: DE")
    p.add_argument("--nvram-source", help="Offline copy of the exact pinned upstream NVRAM")
    p.add_argument("--dry-run", action="store_true", help="Validate and preview without root or writes")
    p.add_argument("--apply", action="store_true", help="Reload driver now; interrupts Wi-Fi")
    p = subs.add_parser("uninstall", help="Restore pre-installation files")
    p.add_argument("--apply", action="store_true", help="Reload the restored driver configuration")
    subs.add_parser("diagnose", help="Print diagnostics with SSID/MAC/IP redacted")
    args = parser.parse_args(argv)
    try:
        if args.command == "diagnose":
            return diagnose()
        hw = hardware()
        if args.command == "install":
            country = country_code(args.country)
            source = source_data(args.nvram_source)
            target_paths = paths(hw)
            if args.dry_run:
                print(f"Validated {MODEL}, BCM43602, country={country}; upstream SHA-256 OK.")
                for path in target_paths:
                    print(f"Would manage: {path}")
                print("Would disable default Wi-Fi power saving for this interface.")
                print("No system changes made; use --apply to reload after installation.")
                return 0
        if os.geteuid() != 0:
            raise ValueError("Run installation/uninstallation with sudo (diagnose and --dry-run do not need it).")
        with locked():
            previous = None
            if STATE_FILE.is_symlink():
                raise ValueError("State file must not be a symbolic link.")
            if STATE_FILE.exists():
                previous = json.loads(STATE_FILE.read_text())
                validate_state(previous, hw)
            if args.command == "uninstall":
                if not previous:
                    print("No managed installation found; nothing changed.")
                    return 0
                uninstall_files(previous)
                print("Original files restored.")
                if args.apply:
                    # Reload restored options without re-applying this package's overrides.
                    if Path("/sys/module/brcmfmac_wcc").exists():
                        run(["modprobe", "-r", "brcmfmac_wcc"])
                    run(["modprobe", "-r", "brcmfmac"])
                    run(["modprobe", "brcmfmac"])
                    run(["nmcli", "general", "reload", "conf"])
                    print("Driver reloaded; reconnect using the desktop Wi-Fi menu.")
                else:
                    print("Reboot to use the restored configuration.")
                return 0
            if previous:
                for name, expected in previous["installed"].items():
                    if Path(name).is_symlink() or not Path(name).is_file() or digest(name) != expected:
                        raise ValueError(f"Managed file changed: {name}; refusing to overwrite local edits.")
            mac = choose_mac(hw["interface"], previous)
            nvram = render_nvram(source, country, mac)
            modprobe = ("# Managed by macbookpro143-wifi\n"
                        "options brcmfmac roamoff=1 feature_disable=0x2000\n"
                        f"options cfg80211 ieee80211_regdom={country}\n").encode()
            nm = ("# Managed by macbookpro143-wifi\n[connection-macbookpro143-wifi]\n"
                  f"match-device=interface-name:{hw['interface']}\n"
                  "wifi.powersave=2\n").encode()
            install_files(dict(zip(target_paths, (nvram, modprobe, nm))), previous,
                          dict(version=VERSION, model=MODEL, vendor=hw["vendor"],
                               country=country, mac=mac, upstream_sha256=UPSTREAM_SHA256))
            print("Installed. Original files saved privately under " + str(STATE_DIR))
            if args.apply:
                apply(hw, country)
            else:
                print("Reboot to activate. No running network settings were changed.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
