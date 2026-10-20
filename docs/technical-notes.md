# Technical notes

The tested machine reports DMI vendor `Acidanthera` (a customized boot environment) and model `MacBookPro14,3`. The installer also accepts a normal vendor such as `Apple Inc.` when the model and the exact Broadcom/Apple PCI identifiers match. Other vendor combinations and kernels remain untested even though the path is generated from their DMI data.

## Why a board text file?

The observed driver loaded Ubuntu's generic BCM43602 firmware binary but reported no NVRAM text file. A minimal country-only file allowed association, yet exposed only 2.4 GHz with poor performance. Adding antenna-chain fields alone did not expose 5 GHz. The complete community board text enabled both bands and improved the observed connection. We did not isolate each board field's contribution or extract this machine's OTP calibration.

The Windows Boot Camp driver was inspected separately. It includes firmware identification strings for BCM43602 with `bmac` architecture. We did not establish that those images could replace the FullMAC binary used by `brcmfmac`; no Windows binary is used by this tool.

## Driver and country settings

`roamoff=1` and `feature_disable=0x2000` disable firmware roaming and the firmware WPA supplicant. They were present in the successful configuration; their individual necessity was not established. The installer uses `regrev=0` with the user's actual ISO country. Only Germany (`DE`) was tested. Do not substitute another country to unlock channels or bandwidth. Both firmware country tables and Linux regulatory restrictions matter; setting the global domain alone is not proof of complete regulatory behavior inside the firmware.

The observed 5 GHz channel width was 40 MHz. The project does not promise 80 MHz, inject a different country table, or patch the kernel to bypass regulatory updates.

NetworkManager's power-saving configuration is a default scoped to the detected interface. If a Wi-Fi connection profile explicitly enables power saving, set that profile to use the default or disable it yourself; the tool does not rewrite stored connection profiles.

## Persistence and initramfs

The tool saves ordinary configuration files and does not rebuild an initramfs or change a Live ISO. If your distribution loads `brcmfmac` and firmware inside an initramfs, it may use an older copy at boot. Review your distribution's initramfs workflow before updating it; Live boot media differs from a regular disk installation. Diagnose again after reboot before concluding persistence works.

Existing modprobe files may declare conflicting options. Review `modprobe -c` and `/etc/modprobe.d/` if your country or options do not take effect. This tool does not overwrite unrelated files to resolve conflicts.

## Recovery

A root-owned private state file is stored at `/var/lib/macbookpro143-wifi/state.json` (mode 0600). It contains base64 snapshots of each pre-installation file, original permissions, the hashes of installed contents, country, and the per-installation MAC address. It is not encrypted. Never commit this private state or device-specific backups to a public repository.

`uninstall` verifies all managed files before restoring any. If you edited a file intentionally, copy your edit somewhere safe, then restore the installed content or manually restore the corresponding pre-installation backup. Do not delete state before preserving backups. Do not replace an existing file with a symbolic link: installation and uninstallation reject such links.

Filesystem write failures during installation restore the immediately preceding file contents and state. An `--apply` connection failure leaves the installed configuration and private backups available so that the user can choose the network or run `uninstall --apply` locally. Hardware/firmware failure or interruption can still require rebooting.

## Validation scope

Core tests cover first-install backup preservation across reinstall/uninstall, file-mode restoration, rollback on write failure, rejection of locally edited managed files, symbolic links, wrong hardware model, unexpected source hashes, invalid country codes, state path injection, address generation, and diagnostic redaction.

The tool's dry-run was performed on the working machine. Automated tests use temporary files and mocks; they do not prove hardware behavior. The working system was configured before packaging. The packaged live installer, a clean-system `.deb` install, reboot, suspend/resume, other routers, and other countries still require independent testing.
