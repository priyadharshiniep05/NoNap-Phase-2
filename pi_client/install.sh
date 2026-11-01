#!/bin/bash
# NoNap Pi client installer for Raspberry Pi OS (Legacy) Lite 32-bit.
# Run from the pi_client folder:   sudo ./install.sh
set -e

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo:  sudo ./install.sh"
  exit 1
fi

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-pi}"
BOOT_CONFIG=/boot/config.txt
[ -f /boot/firmware/config.txt ] && BOOT_CONFIG=/boot/firmware/config.txt

say() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }

say "Installing packages (python3-requests, alsa-utils, picamera if available)"
apt-get update -qq
apt-get install -y python3-requests alsa-utils
apt-get install -y python3-picamera || echo "   python3-picamera not available on this OS release; raspistill/rpicam-still will be used."

say "Enabling the legacy camera stack"
if raspi-config nonint get_legacy >/dev/null 2>&1; then
  raspi-config nonint do_legacy 0 || true          # Bullseye legacy
else
  raspi-config nonint do_camera 0 || true          # Buster and older
fi
grep -q '^start_x=1' "$BOOT_CONFIG" || echo 'start_x=1' >> "$BOOT_CONFIG"
if grep -q '^gpu_mem=' "$BOOT_CONFIG"; then
  sed -i 's/^gpu_mem=.*/gpu_mem=128/' "$BOOT_CONFIG"
else
  echo 'gpu_mem=128' >> "$BOOT_CONFIG"
fi

say "Routing audio to the 3.5 mm jack"
grep -q '^dtparam=audio=on' "$BOOT_CONFIG" || echo 'dtparam=audio=on' >> "$BOOT_CONFIG"
amixer -q cset numid=3 1 2>/dev/null || true       # 1 = analogue jack (legacy ALSA control)
raspi-config nonint do_audio 1 2>/dev/null || true # 1 = headphones on most releases
amixer -q sset PCM 90% 2>/dev/null || amixer -q sset Headphone 90% 2>/dev/null || true

say "Allowing the client to drive the green ACT LED without sudo"
getent group gpio >/dev/null || groupadd gpio
usermod -aG gpio,video,audio "$RUN_USER"
cat > /etc/udev/rules.d/99-nonap-led.rules <<'RULE'
SUBSYSTEM=="leds", ACTION=="add", RUN+="/bin/chgrp -R gpio /sys%p", RUN+="/bin/chmod -R g+w /sys%p"
RULE
udevadm control --reload-rules || true
for led in /sys/class/leds/led0 /sys/class/leds/ACT; do
  if [ -d "$led" ]; then chgrp -R gpio "$led"/ 2>/dev/null || true; chmod -R g+w "$led"/ 2>/dev/null || true; fi
done

say "Checking alert sounds"
if [ ! -f "$DIR/sounds/chime.wav" ] || [ ! -f "$DIR/sounds/alarm.wav" ]; then
  if [ -f "$DIR/../tools/make_sounds.py" ]; then
    sudo -u "$RUN_USER" python3 "$DIR/../tools/make_sounds.py"
  else
    echo "   sounds/ is missing. On the Mac run: python3 tools/make_sounds.py, then copy pi_client/ again."
  fi
fi

say "Installing the systemd service (auto-start on boot)"
sed -e "s#__USER__#$RUN_USER#g" -e "s#__DIR__#$DIR#g" "$DIR/nonap-pi.service" > /etc/systemd/system/nonap-pi.service
systemctl daemon-reload
systemctl enable nonap-pi.service

say "Done"
echo "   1. Edit $DIR/config.ini (server_url = your MacBook's IP)."
echo "   2. Reboot once so the camera and LED permissions apply:  sudo reboot"
echo "   3. After reboot it starts by itself. Watch it with:  journalctl -u nonap-pi -f"
echo "      Or stop the service and run it live:  sudo systemctl stop nonap-pi && python3 $DIR/nonap_pi.py"
