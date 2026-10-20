#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# SHADOWCOMM ground-comms node — Raspberry Pi 5 provisioning.
#
# Turns a fresh 64-bit Raspberry Pi OS install into a field node that can:
#   * key a radio's PTT over GPIO through an opto-isolator,
#   * play and record audio through a USB sound card,
#   * run the SHADOWCOMM messaging backend on port 5050,
#   * and listen for incoming radio traffic as an always-on service.
#
# Safe to re-run: every step is idempotent, and nothing is ever transmitted.
#
#   sudo ./scripts/rpi/deploy.sh                      # provision
#   sudo ./scripts/rpi/deploy.sh --with-listener      # + always-on RX service
#   sudo ./scripts/rpi/deploy.sh --with-gps           # + GPS time source
#   sudo ./scripts/rpi/deploy.sh --dry-run            # show, change nothing
#
# It ends by printing the exact commands for the (separately authorised) live
# radio test.
# ---------------------------------------------------------------------------
set -euo pipefail

# ------------------------------- configuration ------------------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NODE_USER="${SHADOWCOMM_USER:-${SUDO_USER:-pi}}"
NODE_HOME="$(getent passwd "$NODE_USER" 2>/dev/null | cut -d: -f6 || true)"
NODE_HOME="${NODE_HOME:-/home/$NODE_USER}"
INSTALL_DIR="${SHADOWCOMM_DIR:-$NODE_HOME/shadowcomm}"
VENV_DIR="$INSTALL_DIR/venv"
CONF_DIR="/etc/shadowcomm"
CONF_FILE="$CONF_DIR/motorola.env"
UDEV_FILE="/etc/udev/rules.d/60-shadowcomm-gpio.rules"

WITH_LISTENER=0
WITH_GPS=0
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-listener) WITH_LISTENER=1; shift ;;
    --with-gps)      WITH_GPS=1; shift ;;
    --dry-run)       DRY_RUN=1; shift ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

APT_PACKAGES=(
  python3-venv python3-dev python3-pip
  alsa-utils libportaudio2 portaudio19-dev
  sox libsox-fmt-all
  git curl rsync
  # liblgpio/python3-lgpio is the Pi 5 GPIO path: RPi.GPIO cannot drive the
  # RP1 southbridge pins, so lgpio is not optional on a Pi 5.
  liblgpio1 python3-lgpio
)
[[ $WITH_GPS -eq 1 ]] && APT_PACKAGES+=(gpsd gpsd-clients python3-gps chrony)

# ------------------------------- output helpers -----------------------------
# Colour is applied and reset per line. Anything less and a stray `DIM` leaves
# the operator's serial console dim for the rest of the session — which is
# exactly the kind of small wrongness that makes a tool feel untrustworthy.
if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'; C_RED=$'\033[31m'
  C_GRN=$'\033[32m'; C_YEL=$'\033[33m'; C_RST=$'\033[0m'
else
  C_BOLD=''; C_DIM=''; C_RED=''; C_GRN=''; C_YEL=''; C_RST=''
fi

step() { printf '\n%s%s%s\n' "$C_BOLD" "$*" "$C_RST"; }
ok()   { printf '  %s%s%s\n'   "$C_GRN"  "$*" "$C_RST"; }
warn() { printf '  %s%s%s\n'   "$C_YEL"  "$*" "$C_RST"; }
info() { printf '    %s%s%s\n' "$C_DIM"  "$*" "$C_RST"; }
die()  { printf '\n%s%s%s\n'   "$C_RED"  "$*" "$C_RST" >&2; exit 1; }

would() { printf '    %swould: %s%s\n' "$C_DIM" "$*" "$C_RST"; }

# ------------------------------- preflight ----------------------------------
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

printf '%sSHADOWCOMM ground-comms node — provisioning%s\n' "$C_BOLD" "$C_RST"
info "repo       : $REPO_DIR"
info "node user  : $NODE_USER (home $NODE_HOME)"
info "install to : $INSTALL_DIR"
info "listener   : $([[ $WITH_LISTENER -eq 1 ]] && echo yes || echo no)"
info "gps        : $([[ $WITH_GPS -eq 1 ]] && echo yes || echo no)"

if [[ $DRY_RUN -eq 1 ]]; then
  info "mode       : DRY RUN — nothing will be changed"
elif [[ $EUID -ne 0 ]]; then
  die "Run this with sudo (or pass --dry-run to preview)."
fi

MODEL="unknown"
[[ -r /proc/device-tree/model ]] && MODEL="$(tr -d '\0' < /proc/device-tree/model)"
ARCH="$(uname -m)"

step "Hardware"
info "model: $MODEL"
info "arch : $ARCH"
case "$MODEL" in
  *"Raspberry Pi 5"*) ok "Pi 5 recognised — GPIO will use the lgpio backend" ;;
  *"Raspberry Pi"*)   ok "Raspberry Pi recognised" ;;
  *) warn "Not a Raspberry Pi. GPIO/audio steps will fail harmlessly here." ;;
esac

# ------------------------------- 1. packages --------------------------------
step "[1/7] System packages"
if [[ $DRY_RUN -eq 1 ]]; then
  would "apt-get update"
  would "apt-get install -y ${APT_PACKAGES[*]}"
else
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends "${APT_PACKAGES[@]}" >/dev/null
  ok "installed ${#APT_PACKAGES[@]} packages"
fi

# ------------------------------- 2. permissions -----------------------------
step "[2/7] Device permissions"
if [[ $DRY_RUN -eq 1 ]]; then
  would "add $NODE_USER to gpio, spi, audio, dialout"
  would "write $UDEV_FILE"
else
  for grp in gpio spi audio dialout; do
    if getent group "$grp" >/dev/null 2>&1; then
      usermod -aG "$grp" "$NODE_USER" 2>/dev/null || true
      ok "$NODE_USER -> $grp"
    fi
  done
  cat > "$UDEV_FILE" <<'UDEV'
# SHADOWCOMM: let the gpio/audio groups reach the GPIO and sound devices.
SUBSYSTEM=="gpio", KERNEL=="gpiochip*", GROUP="gpio", MODE="0660"
SUBSYSTEM=="sound", KERNEL=="card*", GROUP="audio", MODE="0660"
UDEV
  ok "wrote $UDEV_FILE"
  info "group changes need a re-login or reboot to take effect"
fi

# ------------------------------- 3. repo ------------------------------------
step "[3/7] Repository"
if [[ "$REPO_DIR" != "$INSTALL_DIR" ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    would "install the repo tree into $INSTALL_DIR"
  else
    mkdir -p "$INSTALL_DIR"
    rsync -a --delete --exclude '.git' --exclude 'venv' --exclude '__pycache__' \
          --exclude 'node_modules' --exclude 'dist' \
          "$REPO_DIR"/ "$INSTALL_DIR"/
    chown -R "$NODE_USER:$NODE_USER" "$INSTALL_DIR"
    ok "copied to $INSTALL_DIR"
  fi
else
  ok "repo already lives at $INSTALL_DIR"
fi

# ------------------------------- 4. python env ------------------------------
step "[4/7] Python environment"
if [[ $DRY_RUN -eq 1 ]]; then
  would "python3 -m venv $VENV_DIR"
  would "pip install -r requirements.txt sounddevice rpi-lgpio lgpio"
else
  if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    sudo -u "$NODE_USER" python3 -m venv "$VENV_DIR"
  fi
  sudo -u "$NODE_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip wheel
  if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    sudo -u "$NODE_USER" "$VENV_DIR/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
  fi
  # sounddevice = the audio path; rpi-lgpio + lgpio = the PTT pin on a Pi 5.
  sudo -u "$NODE_USER" "$VENV_DIR/bin/pip" install --quiet sounddevice rpi-lgpio lgpio
  ok "venv ready at $VENV_DIR"
fi

# ------------------------------- 5. configuration ---------------------------
step "[5/7] Configuration"
if [[ $DRY_RUN -eq 1 ]]; then
  would "write $CONF_FILE (only if it does not already exist)"
else
  mkdir -p "$CONF_DIR"
  if [[ -f "$CONF_FILE" ]]; then
    ok "kept existing $CONF_FILE"
  else
    cat > "$CONF_FILE" <<'CONF'
# SHADOWCOMM ground-comms node configuration, read by the systemd units.
# Edit, then: sudo systemctl restart shadowcomm-motorola-rx

# --- Radio transport --------------------------------------------------------
# soundcard = transparent audio modem (works with any radio, recommended)
# mnis_udp  = MOTOTRBO Network Interface Service (needs MOTOTRBO CPS)
# gpio_ptt  = GPIO PTT with the burst on a serial port
MOTOROLA_BACKEND=soundcard

# --- PTT wiring -------------------------------------------------------------
MOTOROLA_PTT_GPIO=17
MOTOROLA_PTT_LEAD_MS=250
MOTOROLA_PTT_TAIL_MS=150

# --- Audio ------------------------------------------------------------------
MOTOROLA_AUDIO_OUT=default
MOTOROLA_AUDIO_IN=default
MOTOROLA_AUDIO_FS=48000

# --- Transmission gate ------------------------------------------------------
# Leave false until you hold a licence AND the receiving operator is listening.
# The field-test tool also refuses to transmit while this is false.
MOTOROLA_RADIO_APPROVED=false
CONF
    chmod 640 "$CONF_FILE"
    chown "root:$NODE_USER" "$CONF_FILE" 2>/dev/null || true
    ok "wrote $CONF_FILE"
    info "MOTOROLA_RADIO_APPROVED=false — nothing can transmit yet"
  fi
fi

# ------------------------------- 6. services --------------------------------
step "[6/7] systemd units"
if [[ $DRY_RUN -eq 1 ]]; then
  would "install shadowcomm-node.service"
  [[ $WITH_LISTENER -eq 1 ]] && would "install shadowcomm-motorola-rx.service"
else
  sed -e "s|%i|$NODE_USER|g" \
      -e "s|/home/$NODE_USER/shadowcomm|$INSTALL_DIR|g" \
      "$INSTALL_DIR/scripts/rpi/shadowcomm-node.service" \
      > /etc/systemd/system/shadowcomm-node.service
  ok "shadowcomm-node.service (messaging backend on :5050)"

  if [[ $WITH_LISTENER -eq 1 ]]; then
    sed -e "s|@USER@|$NODE_USER|g" \
        -e "s|@DIR@|$INSTALL_DIR|g" \
        -e "s|@VENV@|$VENV_DIR|g" \
        "$INSTALL_DIR/scripts/rpi/shadowcomm-motorola-rx.service" \
        > /etc/systemd/system/shadowcomm-motorola-rx.service
    ok "shadowcomm-motorola-rx.service (always-listening radio RX)"
  fi

  systemctl daemon-reload
  systemctl enable shadowcomm-node.service >/dev/null 2>&1 || true
  if [[ $WITH_LISTENER -eq 1 ]]; then
    systemctl enable shadowcomm-motorola-rx.service >/dev/null 2>&1 || true
  fi
  ok "enabled at boot"
fi

# ------------------------------- 7. verify ----------------------------------
step "[7/7] Verification (no RF)"
if [[ $DRY_RUN -eq 1 ]]; then
  would "run the modem self-test and the hardware probe"
else
  info "the modem is verified before any radio is touched"
  if sudo -u "$NODE_USER" env MOTOROLA_BACKEND=soundcard \
       "$VENV_DIR/bin/python" "$INSTALL_DIR/scripts/motorola_field_test.py" \
       selftest --frames 8 --snr 12; then
    ok "modem self-test PASSED"
  else
    warn "modem self-test reported a problem — read the output above"
  fi
  echo
  sudo -u "$NODE_USER" env MOTOROLA_BACKEND=soundcard \
    "$VENV_DIR/bin/python" "$INSTALL_DIR/scripts/motorola_field_test.py" probe || true
fi

cat <<EOF

${C_BOLD}Provisioning complete.${C_RST}

${C_BOLD}Nothing has been transmitted.${C_RST} $CONF_FILE still has
MOTOROLA_RADIO_APPROVED=false, so the transmit path is closed.

Next, in this order:

  ${C_DIM}# 1. Apply the gpio/audio group changes${C_RST}
  sudo reboot

  ${C_DIM}# 2. Hardware inventory — no RF${C_RST}
  cd $INSTALL_DIR
  $VENV_DIR/bin/python scripts/motorola_field_test.py probe

  ${C_DIM}# 3. Modem through a simulated channel — no RF${C_RST}
  $VENV_DIR/bin/python scripts/motorola_field_test.py selftest --frames 12 --snr 12

  ${C_DIM}# 4. Whole chain in software — no RF${C_RST}
  $VENV_DIR/bin/python scripts/motorola_field_test.py loopback

  ${C_DIM}# 5. Only now, with a licence and a second operator listening${C_RST}
  $VENV_DIR/bin/python scripts/motorola_field_test.py run --role rx --count 6   ${C_DIM}# RX terminal${C_RST}
  $VENV_DIR/bin/python scripts/motorola_field_test.py run --role tx --approve   ${C_DIM}# TX terminal${C_RST}

Full runbook: docs/GROUND_COMMS_DEPLOYMENT.md
EOF
