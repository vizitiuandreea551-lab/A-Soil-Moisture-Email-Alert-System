import os, threading, time, smtplib
from collections import deque
from datetime import datetime
from email.message import EmailMessage
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template
from gpiozero import DigitalInputDevice

load_dotenv()
app = Flask(__name__)
SENSOR_PIN = int(os.getenv('SENSOR_PIN', '17'))
DRY_SENSOR_VALUE = int(os.getenv('DRY_SENSOR_VALUE', '1'))  # Original code assumes 1=dry; verify sensor polarity.
POLL_INTERVAL = float(os.getenv('POLL_INTERVAL', '2'))
SMTP_SERVER, SMTP_PORT = 'smtp.gmail.com', 465
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS', '').strip()
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '').strip()
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', '').strip()

sensor = None
sensor_error = None
try:
    sensor = DigitalInputDevice(SENSOR_PIN)
except Exception as exc:
    sensor_error = str(exc)

lock = threading.Lock()
email_lock = threading.Lock()
activity = deque(maxlen=100)
monitoring = False
email_sending = False
email_sent_this_dry_period = False
soil_status = 'unknown'
last_checked = None
email_status = 'Not sent'
stop_event = threading.Event()


def log(message):
    with lock:
        activity.appendleft({'time': datetime.now().strftime('%H:%M:%S'), 'message': str(message)})


def email_configured():
    return bool(EMAIL_ADDRESS and EMAIL_PASSWORD and RECIPIENT_EMAIL)


def send_email(subject, body):
    global email_sending, email_status
    if not email_configured():
        with lock:
            email_status = 'Not configured: check .env'
        log('Email not sent: configure the three email values in .env.')
        return False
    with email_lock:
        with lock:
            email_sending, email_status = True, 'Sending'
        try:
            msg = EmailMessage()
            msg['Subject'], msg['From'], msg['To'] = subject, EMAIL_ADDRESS, RECIPIENT_EMAIL
            msg.set_content(body)
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.send_message(msg)
            with lock:
                email_status = 'Sent successfully'
            log('Email sent: ' + subject)
            return True
        except Exception as exc:
            with lock:
                email_status = 'Failed: ' + str(exc)
            log('Email failed: ' + str(exc))
            return False
        finally:
            with lock:
                email_sending = False


def monitor_loop():
    global soil_status, last_checked, email_sent_this_dry_period
    while not stop_event.is_set():
        if sensor is None:
            with lock:
                soil_status = 'error'
                last_checked = datetime.now().isoformat(timespec='seconds')
            stop_event.wait(POLL_INTERVAL)
            continue
        try:
            value = int(sensor.value)
            status = 'dry' if value == DRY_SENSOR_VALUE else 'wet'
            with lock:
                previous = soil_status
                soil_status = status
                last_checked = datetime.now().isoformat(timespec='seconds')
            if status == 'dry':
                if previous != 'dry': log('Sensor reports dry soil.')
                if not email_sent_this_dry_period:
                    email_sent_this_dry_period = True
                    threading.Thread(target=send_email, args=('Your plant needs water', 'The soil moisture sensor has detected dry soil.\n\nYour plant may need watering.'), daemon=True).start()
            else:
                if previous != 'wet': log('Sensor reports wet soil.')
                email_sent_this_dry_period = False
        except Exception as exc:
            with lock:
                soil_status = 'error'
                last_checked = datetime.now().isoformat(timespec='seconds')
            log('Sensor read failed: ' + str(exc))
        stop_event.wait(POLL_INTERVAL)


def snapshot():
    with lock:
        return {'monitoring': monitoring, 'status': soil_status, 'last_checked': last_checked,
                'email_status': email_status, 'email_sending': email_sending,
                'email_configured': email_configured(), 'sensor_ready': sensor is not None,
                'sensor_error': sensor_error, 'sensor_pin': SENSOR_PIN,
                'activity': list(activity)}


@app.get('/')
def dashboard():
    return render_template('index.html')


@app.get('/api/status')
def status_api():
    return jsonify(snapshot())


@app.post('/api/monitoring/start')
def start_monitoring():
    global monitoring
    if sensor is None:
        return jsonify(ok=False, message='Sensor unavailable: ' + (sensor_error or 'check wiring')), 503
    with lock:
        if monitoring:
            return jsonify(ok=True, message='Monitoring is already running.')
        monitoring = True
    stop_event.clear()
    threading.Thread(target=monitor_loop, daemon=True).start()
    log('Monitoring started from dashboard.')
    return jsonify(ok=True, message='Monitoring started.')


@app.post('/api/monitoring/stop')
def stop_monitoring():
    global monitoring
    with lock:
        was_running, monitoring = monitoring, False
    stop_event.set()
    if was_running: log('Monitoring stopped from dashboard.')
    return jsonify(ok=True, message='Monitoring stopped.')


@app.post('/api/email/test')
def test_email():
    if not email_configured():
        return jsonify(ok=False, message='Add EMAIL_ADDRESS, EMAIL_PASSWORD and RECIPIENT_EMAIL to .env.'), 400
    threading.Thread(target=send_email, args=('Smart Plant Monitor - Test Email', 'This is a test email from your Raspberry Pi Smart Plant Monitoring System.\n\nIf you received this, email alerts are working.'), daemon=True).start()
    log('Test email requested from dashboard.')
    return jsonify(ok=True, message='Test email started. Check email status and your inbox.')


if __name__ == '__main__':
    log('Web dashboard application started.')
    # Trusted local network only; do not port-forward this unauthenticated dashboard.
    app.run(host='0.0.0.0', port=int(os.getenv('WEB_PORT', '5000')), debug=False, threaded=True)
