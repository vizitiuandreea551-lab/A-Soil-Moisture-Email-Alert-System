# Smart Plant Monitor — Web Dashboard

Flask dashboard for Raspberry Pi 5, LM393 digital soil moisture sensor and Gmail SMTP alerts.

## Hardware assumed
- Sensor DO -> GPIO 17 (physical pin 11)
- VCC -> 3.3 V (physical pin 1)
- GND -> GND (physical pin 6)
- AO unused

The existing project assumes `sensor.value == 1` means dry. Verify this with your sensor; set `DRY_SENSOR_VALUE=0` in `.env` if readings are reversed.

## Install on Raspberry Pi
```bash
sudo apt update
sudo apt install python3-venv
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure email
```bash
cp .env.example .env
nano .env
chmod 600 .env
```
Set `EMAIL_ADDRESS`, `EMAIL_PASSWORD` and `RECIPIENT_EMAIL`. Use your replacement Google App Password, not your normal Gmail password. Never share or commit `.env`.

## Run
```bash
source .venv/bin/activate
python app.py
```
On the Pi, open `http://127.0.0.1:5000`. To open from a phone/laptop on the same Wi-Fi, run `hostname -I` on the Pi and visit `http://PI_LOCAL_IP:5000` on the other device.

## Included features
- Responsive browser dashboard for phone/laptop
- Start/stop sensor monitoring; wet/dry status and watering recommendation
- Last reading time, sensor availability, email status, test-email button
- Recent activity log and auto-refresh every 2 seconds
- One email per dry period; can send another after the sensor reports wet and then dry again

## Security
The dashboard has no login. Use it only on a trusted private network; do not port-forward port 5000 or expose it directly to the internet. The app does not operate a watering pump.
