import hashlib
import json
import logging
import time
from datetime import datetime

import coloredlogs
import pytz

logger = logging.getLogger('helper')
coloredlogs.install(level=logging.DEBUG, logger=logger,
                    fmt='%(name)s - %(levelname)s - %(message)s')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.ERROR)

# Get current date time


def get_current_date_time():
    now = datetime.now()
    return now.strftime("%d/%m/%Y %H:%M:%S")

# Get current time


def get_current_time():
    now = datetime.now()
    return now.strftime("%H:%M")

# Execute AT command


def AT(ser, cmd='AT', timeout=0.25):
    if cmd != 'AT':
        cmd = 'AT+' + cmd
    cmd += '\r\n'
    ser.write(cmd.encode('utf-8'))
    logger.debug(read_serial_output(ser, timeout))


def get_current_timestamp():
    now = time.time()
    date = datetime.fromtimestamp(now)
    date = pytz.timezone('Asia/Singapore').localize(date)
    return int(date.timestamp())

# Extract pi serial number from cpuinfo file


def get_pi_serial():
    cpuserial = '0000000000000000'
    try:
        f = open('/proc/cpuinfo', 'r')
        for line in f:
            if line[0:6] == 'Serial':
                cpuserial = line[10:26]
        f.close()
    except:
        cpuserial = 'ERROR000000000'

    return cpuserial


def generate_api_key_hashed(api_key, pi_id, timestamp):
    data = api_key + pi_id + str(timestamp)
    encoded = data.encode()
    sha256_hash = hashlib.sha256()
    sha256_hash.update(encoded)
    api_key_hashed = sha256_hash.hexdigest()
    return api_key_hashed


def read_disinfecting_occupied_data():
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json') as f:
        try:
            data = json.load(f)
            if 'is_disinfecting' in data:
                is_disinfecting = data['is_disinfecting']
            if 'is_occupied' in data:
                is_occupied = data['is_occupied']
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass
        return is_disinfecting, is_occupied

# Write data to config


def write_pi_config():
    pi_id = get_pi_serial()
    with open('/home/pi/Desktop/gomama-raspberrypi/config.json', 'r') as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass

    data['pi_id'] = pi_id

    with open('/home/pi/Desktop/gomama-raspberrypi/config.json', 'w') as f:
        json.dump(data, f, indent=4)

# Write is_send_data to data


def write_is_send_data(is_send_data=False, is_scheduled=False):
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json') as f:
        try:
            data = json.load(f)
            if 'is_send_data' in data:
                data['is_send_data'] = is_send_data
            if 'is_scheduled' in data:
                data['is_scheduled'] = is_scheduled
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass
        with open('/home/pi/Desktop/gomama-raspberrypi/data.json', 'w') as f:
            json.dump(data, f, indent=4)

# Write is_disinfecting to data


def write_is_disinfecting(is_disinfecting=False):
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json') as f:
        try:
            data = json.load(f)
            if 'is_disinfecting' in data:
                data['is_disinfecting'] = is_disinfecting
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass
        with open('/home/pi/Desktop/gomama-raspberrypi/data.json', 'w') as f:
            json.dump(data, f, indent=4)

# Write data to config


def write_data(data):
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json', 'w') as f:
        json.dump(data, f, indent=4)

# Read pi serial output


def read_serial_output(ser, timeout=0.25):
    ser.flushInput()
    last_received = ''
    while timeout > 0:
        time.sleep(0.2)
        count = ser.inWaiting()
        while count != 0:
            last_received += ser.read(count).decode('utf-8')
            time.sleep(0.2)
            count = ser.inWaiting()
        timeout = timeout-0.25
    return last_received

# Get local ip address


def get_local_ip(ser):
    ser.write('AT+CIFSR\r\n'.encode('utf-8'))
    logger.debug(read_serial_output(ser))

# MQTT Helper Functions

def validate_mqtt_payload(payload):
    """Validate MQTT payload structure"""
    required_fields = ['listing_id', 'timestamp', 'auth_hash', 'sensor_data']

    if not isinstance(payload, dict):
        return False, "Payload must be a dictionary"

    for field in required_fields:
        if field not in payload:
            return False, f"Missing required field: {field}"

    sensor_data = payload.get('sensor_data', {})
    if not isinstance(sensor_data, dict):
        return False, "sensor_data must be a dictionary"

    return True, "Valid payload"

def create_mqtt_sensor_payload(listing_id, pi_id, api_key, sensor_data):
    """Create standardized MQTT sensor data payload"""
    timestamp = int(time.time())
    auth_hash = generate_api_key_hashed(api_key, pi_id, timestamp)

    return {
        "listing_id": listing_id,
        "timestamp": timestamp,
        "auth_hash": auth_hash,
        "sensor_data": sensor_data
    }

def log_mqtt_status(connected, broker_host, broker_port):
    """Log MQTT connection status"""
    status = "✅ Connected" if connected else "❌ Disconnected"
    logger.info(f"MQTT Status: {status} to {broker_host}:{broker_port}")

def format_sensor_data_for_logging(sensor_data):
    """Format sensor data for readable logging"""
    if not isinstance(sensor_data, dict):
        return str(sensor_data)

    formatted = []
    for key, value in sensor_data.items():
        if isinstance(value, bool):
            formatted.append(f"{key}={'ON' if value else 'OFF'}")
        elif isinstance(value, (int, float)):
            if 'temp' in key.lower():
                formatted.append(f"{key}={value}°C")
            elif 'humid' in key.lower():
                formatted.append(f"{key}={value}%")
            else:
                formatted.append(f"{key}={value}")
        else:
            formatted.append(f"{key}={value}")

    return ", ".join(formatted)
