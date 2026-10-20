#!/bin/sh
set -eu
cd -- "$(dirname -- "$0")"
version=$(python3 macbook_wifi.py --version)
outdir="$(pwd)/dist"
mkdir -p "$outdir"
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT HUP INT TERM
name="macbookpro143-wifi-linux-$version"
mkdir -p "$stage/$name"
for item in macbook_wifi.py install.sh uninstall.sh build.sh README.md README.pt-BR.md LICENSE THIRD_PARTY.md docs tests .github .gitignore; do
    cp -R -- "$item" "$stage/$name/"
done
# Never include local caches or device-specific state in release archives.
find "$stage/$name" -type d -name __pycache__ -prune -exec rm -rf -- {} +
tar -czf "$outdir/$name.tar.gz" -C "$stage" "$name"
python3 - "$stage" "$name" "$outdir" <<'PY'
from pathlib import Path
import sys, zipfile
root, name, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
with zipfile.ZipFile(out / (name + '.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted((root / name).rglob('*')):
        if p.is_file():
            z.write(p, str(p.relative_to(root)))
PY
if command -v dpkg-deb >/dev/null 2>&1; then
    deb="$stage/deb"
    mkdir -p "$deb/DEBIAN" "$deb/usr/lib/macbookpro143-wifi" "$deb/usr/bin" "$deb/usr/share/doc/macbookpro143-wifi"
    cp macbook_wifi.py "$deb/usr/lib/macbookpro143-wifi/"
    chmod 755 "$deb/usr/lib/macbookpro143-wifi/macbook_wifi.py"
    ln -s ../lib/macbookpro143-wifi/macbook_wifi.py "$deb/usr/bin/macbookpro143-wifi"
    cp README.md THIRD_PARTY.md "$deb/usr/share/doc/macbookpro143-wifi/"
    cp LICENSE "$deb/usr/share/doc/macbookpro143-wifi/copyright"
    cat > "$deb/DEBIAN/control" <<EOF_CONTROL
Package: macbookpro143-wifi
Version: $version
Architecture: all
Maintainer: Gabriel Mandatti <7130257+mandatti@users.noreply.github.com>
Depends: python3 (>= 3.9), iw, kmod, network-manager, tzdata, ca-certificates
Recommends: linux-firmware
Section: net
Priority: optional
Description: Reversible BCM43602 configuration tool for MacBookPro14,3
 Installs the tool only; run macbookpro143-wifi install explicitly to
 configure Wi-Fi. Board data is fetched from a pinned community source.
EOF_CONTROL
    find "$deb" -type d -exec chmod 755 {} +
    find "$deb/usr/share/doc" -type f -exec chmod 644 {} +
    chmod 644 "$deb/DEBIAN/control"
    dpkg-deb --root-owner-group --build "$deb" "$outdir/macbookpro143-wifi_${version}_all.deb"
fi
python3 - "$outdir" "$version" <<'PY_SUM'
from pathlib import Path
import hashlib, sys
out = Path(sys.argv[1])
version = sys.argv[2]
names = [f'macbookpro143-wifi-linux-{version}.tar.gz', f'macbookpro143-wifi-linux-{version}.zip', f'macbookpro143-wifi_{version}_all.deb']
artifacts = [out / name for name in names if (out / name).is_file()]
(out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in artifacts))
PY_SUM
printf 'Artifacts: %s\n' "$outdir"
