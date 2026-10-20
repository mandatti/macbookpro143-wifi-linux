# Third-party material

No Apple Boot Camp package, Windows `.sys`/`.exe`, firmware binary, or upstream NVRAM content is bundled in this repository or its release archives.

The installer retrieves the NVRAM text directly from MikeRatcliffe's public gist:

- Source: https://gist.github.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80
- Pinned raw file: https://gist.githubusercontent.com/MikeRatcliffe/9614c16a8ea09731a9d5e91685bd8c80/raw/bd7af7c6f01df3ccee1471d36cb8df15d618a6aa/brcmfmac43602-pcie.txt
- SHA-256: `b109f3e6663b0e888c2559e36f7e0109f2a3a6b9765786d11f849f16d4b32d06`
- The installer changes only `ccode`, `regrev`, and `macaddr` in that text.

The repository's MIT license covers only its original scripts and documentation. It does not assert a license for the external gist, hardware calibration data, or proprietary firmware. Those retain their own terms. Fetching a public file is not a grant to redistribute it; this project avoids bundling it. Review the upstream source and applicable terms before use or redistribution.

Ubuntu's existing `linux-firmware` files are used in place, under their own license terms.

Further technical references:

- https://github.com/Dunedan/mbp-2016-linux/issues/139
- https://wireless.docs.kernel.org/en/latest/en/users/drivers/brcm80211.html
- https://github.com/torvalds/linux/tree/master/drivers/net/wireless/broadcom/brcm80211/brcmfmac
