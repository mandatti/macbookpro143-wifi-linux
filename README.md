# MacBookPro14,3 Wi-Fi on Linux

A reversible configuration tool for the **Broadcom BCM43602 in the 2017 15-inch MacBook Pro (MacBookPro14,3)**. It uses Ubuntu's existing `brcmfmac` driver and firmware, and adds a board configuration downloaded from a pinned community source.

[Português brasileiro](README.pt-BR.md) · [Technical notes](docs/technical-notes.md) · [Third-party source](THIRD_PARTY.md)

**Version 0.1.1 — experimental, tested on one machine.** This is a community project, unaffiliated with Apple or Broadcom. Other Mac models and PCI subsystem IDs are deliberately rejected. A successful connection is not a claim of support for every kernel, router, or country.

## Fix in v0.1.1

The DMI vendor on the tested Mac changed from `Acidanthera` to `Apple Inc.` after rebooting. Version 0.1.0 installed the board file under only the current vendor name, so the next boot could fall back to generic defaults. Version 0.1.1 installs both names and can upgrade or uninstall v0.1.0 backups even after that change.

To upgrade an existing tool-managed configuration, run the new installer with the same country. The first pre-installation backups are retained, including the original state of the newly managed alias.

## What was observed

On one MacBookPro14,3, Ubuntu 26.04.1 Live with persistence and kernel `7.0.0-30-generic`, in Germany:

| Observation | Minimal NVRAM configuration | Complete community board configuration |
|---|---|---|
| Band available/connected | 2.4 GHz | 5 GHz, channel 48, 40 MHz |
| Driver-reported signal | approximately −80 dBm | approximately −40 to −44 dBm |
| Reported link rate | 52–78 Mb/s | 300–400 Mb/s |

After the change, a 10 MB HTTPS sample download measured approximately 77.6 Mb/s. Twenty pings to the local router returned with no loss. Link rates are not internet speed; the download depends on the server and internet connection. No comparable before-change download was recorded. RSSI values also depend on the board configuration. A reboot confirmed that the files persist, but exposed a vendor-name change that prevented v0.1.0 from loading them. Version 0.1.1 installs both observed vendor names; reloading with the new name restored 5 GHz. A further reboot with this fix, long-term behavior, and suspend/resume remain unverified.

## Requirements

- MacBookPro14,3; PCI `14e4:43ba`, subsystem `106b:0173`.
- Ubuntu or a compatible Linux installation using `brcmfmac` and NetworkManager. Only the Ubuntu/kernel combination above was tested.
- Python 3.9+, `iw`, `kmod`, NetworkManager, `tzdata`, CA certificates and working BCM43602 firmware.
- Internet for the pinned NVRAM download, or an exact offline copy. USB tethering or Ethernet can provide the initial connection.

On Ubuntu, install missing tools with:

```bash
sudo apt install python3 iw kmod network-manager tzdata ca-certificates linux-firmware
```

## Install from the source archive

Download an archive from [Releases](https://github.com/mandatti/macbookpro143-wifi-linux/releases), or clone the repository:

```bash
git clone https://github.com/mandatti/macbookpro143-wifi-linux.git
cd macbookpro143-wifi-linux
```

Extract the release archive and open a terminal inside its directory if using that method. Review the code and [third-party source information](THIRD_PARTY.md).

Use your **actual country**, not a country chosen to unlock channels. `DE` below means Germany. Only `DE` was tested.

```bash
./install.sh --country DE --dry-run
sudo ./install.sh --country DE
```

The second command backs up existing files and installs configuration without interrupting the running Wi-Fi. Reboot to activate it. On a persistent Live USB, the root filesystem must actually persist across boots. Some installations load Wi-Fi from an initramfs; see the technical notes if the change is absent after reboot.

To apply immediately instead of rebooting:

```bash
sudo ./install.sh --country DE --apply
```

**`--apply` disconnects Wi-Fi while the driver reloads. Run it locally, not through an SSH connection that depends on this Wi-Fi.** It tries existing NetworkManager profiles; use the desktop Wi-Fi menu if the network has not been configured. The tool never asks for a Wi-Fi password or GitHub credentials.

If reconnection fails, the original files remain backed up. Roll back using the uninstall command below. Live reconnection failure does **not** automatically uninstall: the desktop may simply need a network selection or password.

### Ubuntu/Debian tool package

The `.deb` installs the tool only. Installing the `.deb` itself does not download NVRAM, change Wi-Fi configuration, or reload the driver.

```bash
sudo apt install ./macbookpro143-wifi_0.1.1_all.deb
macbookpro143-wifi install --country DE --dry-run
sudo macbookpro143-wifi install --country DE --apply
```

### Offline source

Download the exact [pinned NVRAM source](https://gist.githubusercontent.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80/raw/bd7af7c6f01df3ccee1471d36cb8df15d618a6aa/brcmfmac43602-pcie.txt) on another connection. Transfer it locally and run:

```bash
sudo ./install.sh --country DE --nvram-source /path/to/brcmfmac43602-pcie.txt --apply
```

The SHA-256 is checked in both online and offline installation. Modified or unexpected input is rejected.

## Diagnose

```bash
python3 macbook_wifi.py diagnose
# Or, with the .deb installed:
macbookpro143-wifi diagnose
```

Diagnostics redact SSIDs, MAC addresses and IPv4 addresses. Review output before sharing it. They do not read passwords, connection profiles, serial numbers, or full system logs. Some `iw` operations may require `sudo`.

## Uninstall / rollback

Keep the tool or source archive until after rollback.

```bash
sudo ./uninstall.sh --apply
# Or, with the .deb installed:
sudo macbookpro143-wifi uninstall --apply
```

Without `--apply`, reboot after uninstalling. Files present before the first install are restored; files created by the tool are removed. Repeat installations preserve the first backup. If a managed file has been manually changed or removed, uninstall stops before touching any managed files, so local edits are not silently lost. See [recovery instructions](docs/technical-notes.md#recovery).

Removing the `.deb` does not roll back Wi-Fi settings automatically. Run the tool's `uninstall` command **before** removing the `.deb`. This avoids dropping an active network during a package-manager operation.

## What it changes

1. Two identical board-specific NVRAM text files under `/usr/lib/firmware/brcm/`, for `Apple Inc.-MacBookPro14,3` and `Acidanthera-MacBookPro14,3`. This covers the vendor change observed after rebooting through another boot path.
2. `/etc/modprobe.d/macbookpro143-wifi.conf`: disables firmware roaming and firmware WPA supplicant; sets the requested regulatory domain.
3. `/etc/NetworkManager/conf.d/80-macbookpro143-wifi.conf`: disables default power saving for the detected interface. An explicit power-saving setting in an existing profile can override this default.
4. Private backup/state under `/var/lib/macbookpro143-wifi/`.

The tool preserves a usable existing MAC address. If the driver reports the known default/sample MAC, it generates a local unicast address unique to that installation and reuses it on subsequent installs. Router MAC allowlists or reservations may need updating in that case.

It does not install a Windows driver, replace Ubuntu's firmware binary, modify EFI/macOS, or patch the kernel. The NVRAM includes community calibration values: it is **not** the factory calibration extracted from your particular machine.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 macbook_wifi.py --help
./build.sh
```

Tests run against temporary files and mock data; they do not reload hardware. There is no telemetry. Report the model, kernel, country, and redacted diagnostics in an issue. Avoid posting passwords, SSIDs, MAC addresses, or serial numbers.

## Credits and license

The original NVRAM configuration is attributed to [MikeRatcliffe's gist](https://gist.github.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80), and the [mbp-2016-linux community](https://github.com/Dunedan/mbp-2016-linux/issues/139) documented this family of issues. The [Linux Wireless documentation](https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html) describes `brcmfmac`.

The original scripts and documentation in this repository are MIT licensed. External configuration and firmware keep their respective terms; they are not relicensed or bundled here. See [THIRD_PARTY.md](THIRD_PARTY.md).
