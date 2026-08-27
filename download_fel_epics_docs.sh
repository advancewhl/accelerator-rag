#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${1:-$PWD/fel_epics_docs}"
mkdir -p "$BASE_DIR/EPICS" "$BASE_DIR/Hard_XFEL_SHINE" "$BASE_DIR/Hard_XFEL_European_XFEL"

fetch() {
  local url="$1"
  local out="$2"
  echo "[DOWNLOAD] $out"
  if command -v curl >/dev/null 2>&1; then
    curl -L --fail --retry 3 --connect-timeout 20 -o "$out" "$url"
  elif command -v wget >/dev/null 2>&1; then
    wget --tries=3 --timeout=20 -O "$out" "$url"
  else
    echo "Error: curl or wget is required." >&2
    exit 1
  fi
}

# ======================== EPICS official ========================
fetch 'https://docs.epics-controls.org/_/downloads/en/latest/pdf/' \
  "$BASE_DIR/EPICS/EPICS_Documentation_latest.pdf"

fetch 'https://epics.anl.gov/base/R3-16/2-docs/AppDevGuide.pdf' \
  "$BASE_DIR/EPICS/EPICS_Application_Developers_Guide_R3.16.2.pdf"

# ======================== SHINE / Hard X-ray FEL ========================
fetch 'https://proceedings.jacow.org/icalepcs2019/papers/WEPHA167.pdf' \
  "$BASE_DIR/Hard_XFEL_SHINE/Status_of_the_SHINE_Control_System_ICALEPCS2019.pdf"

fetch 'https://proceedings.jacow.org/pcapac2022/papers/fro21.pdf' \
  "$BASE_DIR/Hard_XFEL_SHINE/EPICS_IOC_and_PVs_Information_Management_System_for_SHINE_PCaPAC2022.pdf"

fetch 'https://epaper.kek.jp/ipac2022/papers/thiygd1.pdf' \
  "$BASE_DIR/Hard_XFEL_SHINE/White_Rabbit_Based_Beam_Synchronous_Timing_Systems_for_SHINE_IPAC2022.pdf"

fetch 'https://link.springer.com/content/pdf/10.1140/epjti/s40485-021-00066-7.pdf' \
  "$BASE_DIR/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf"

fetch 'https://www.researching.cn/ArticlePdf/m00117/2024/47/12/120203.pdf' \
  "$BASE_DIR/Hard_XFEL_SHINE/SHINE_Accelerator_Fast_Interlock_System_Design_and_Development_CN.pdf"

# ======================== European XFEL ========================
fetch 'https://docs.xfel.eu/alfresco/d/a/workspace/SpacesStore/466da93a-eeef-4a79-91b2-d539b7ff6534/european-xfeltdr.pdf' \
  "$BASE_DIR/Hard_XFEL_European_XFEL/European_XFEL_Full_Technical_Design_Report.pdf"

fetch 'https://docs.xfel.eu/alfresco/d/a/workspace/SpacesStore/3e02dc76-eb66-44c4-87ac-28539b5800e8/TR-2012-006_TDR_WP73.pdf' \
  "$BASE_DIR/Hard_XFEL_European_XFEL/European_XFEL_X-Ray_Optics_and_Beam_Transport_TDR.pdf"

fetch 'https://www.xfel.eu/sites/sites_custom/site_xfel/content/e35152/e35161/e166761/e63993/e74066/e74067/xfel_file74069/CDRK-Mono_maindocuments_eng.pdf' \
  "$BASE_DIR/Hard_XFEL_European_XFEL/European_XFEL_Undulator_Commissioning_Spectrometer_CDR.pdf"

fetch 'https://inspirehep.net/files/bf87493895017e0b48c538b9bfcacf00' \
  "$BASE_DIR/Hard_XFEL_European_XFEL/Standard_E-Beam_Diagnostics_for_European_XFEL.pdf"

cat <<MSG

Done. Files are under:
  $BASE_DIR

Suggested reading order:
  1. European_XFEL_Full_Technical_Design_Report.pdf
  2. European_XFEL_X-Ray_Optics_and_Beam_Transport_TDR.pdf
  3. Standard_E-Beam_Diagnostics_for_European_XFEL.pdf
  4. Status_of_the_SHINE_Control_System_ICALEPCS2019.pdf
  5. EPICS_Documentation_latest.pdf
  6. EPICS_Application_Developers_Guide_R3.16.2.pdf
  7. SHINE EPICS IOC/PV, timing, cryogenic, and fast-interlock papers
MSG
