#!/bin/sh
# NileGlass FHD - online installer / updater
#   wget -q -O - https://raw.githubusercontent.com/Saadmelshepiny/NileGlass-FHD/main/installer.sh | /bin/sh
# Installs the package only: it does not change the active skin or any receiver setting.
URL="https://raw.githubusercontent.com/Saadmelshepiny/NileGlass-FHD/main"
TMP=/tmp/nileglass_install.ipk

get() {  # get URL FILE
	wget -q -O "$2" "$1" 2>/dev/null || wget -q --no-check-certificate -O "$2" "$1"
}

echo "NileGlass FHD installer"
get "$URL/version.json" /tmp/nileglass_version.json || { echo "Cannot reach GitHub"; exit 1; }
VER=$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' /tmp/nileglass_version.json)
SHA=$(sed -n 's/.*"sha256": *"\([0-9a-f]*\)".*/\1/p' /tmp/nileglass_version.json)
rm -f /tmp/nileglass_version.json
[ -n "$VER" ] || { echo "Bad version file"; exit 1; }
echo "Downloading version $VER ..."
get "$URL/releases/enigma2-plugin-skins-nileglass-fhd_${VER}_all.ipk" "$TMP" || { echo "Download failed"; exit 1; }
if [ -n "$SHA" ] && command -v sha256sum >/dev/null 2>&1; then
	echo "$SHA  $TMP" | sha256sum -c - >/dev/null 2>&1 || { echo "Checksum mismatch"; rm -f "$TMP"; exit 1; }
fi
opkg install --force-reinstall "$TMP"
RC=$?
rm -f "$TMP"
if [ $RC -eq 0 ]; then
	echo ""
	echo "Done. Select NileGlass_FHD in Menu > Setup > User Interface > Skin and restart the GUI."
	echo "Settings: Plugins > NileGlass FHD (add your free TMDB key for posters)."
fi
exit $RC
