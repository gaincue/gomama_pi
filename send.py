#!/usr/bin/env python3
# -*- coding:utf-8 -*-

import json
import logging
import time
import threading
from collections import deque
from typing import Optional, Dict, Any

import coloredlogs
import requests
import paho.mqtt.client as mqtt

from helper import *
from mqtt_config import get_config

# Global configuration
config = get_config()

# Legacy variables (maintained for compatibility)
api_key = config.get_api_key()
pod_id = ""
pi_id = config.get_pi_id()
url = config.get_http_url()
timestamp = ""
loop_timestamp = time.time()
listing_data = {}
listing_id = config.get_listing_id()

# Sensor state variables
is_send_data = False
is_occupied = False
is_disinfecting = False
is_occupied_status_changed = False
start_disinfecting = False
is_scheduled = False
is_led_light_on = False
is_fan_on = False
is_uvc_lamp_on = False
is_door_opened = False

temperature = 0
humidity = 0

# MQTT client and connection state
mqtt_client: Optional[mqtt.Client] = None
mqtt_connected = False
mqtt_connection_attempts = 0
offline_message_queue = deque(maxlen=config.get_mqtt_offline_buffer_size())

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.DEBUG, logger=logger, fmt="%(name)s - %(levelname)s - %(message)s")
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.ERROR)


# MQTT Event Callbacks
def on_mqtt_connect(client, userdata, flags, rc):
    """Callback for when MQTT client connects"""
    global mqtt_connected, mqtt_connection_attempts

    if rc == 0:
        mqtt_connected = True
        mqtt_connection_attempts = 0
        logger.info("✅ MQTT connected successfully")

        # Subscribe to commands topic
        commands_topic = config.get_commands_topic()
        client.subscribe(commands_topic, qos=config.get_mqtt_qos())
        logger.info(f"📡 Subscribed to commands topic: {commands_topic}")

        # Process any queued offline messages
        process_offline_queue()

    else:
        mqtt_connected = False
        mqtt_connection_attempts += 1
        logger.error(f"❌ MQTT connection failed with code {rc}")


def on_mqtt_disconnect(client, userdata, rc):
    """Callback for when MQTT client disconnects"""
    global mqtt_connected
    mqtt_connected = False

    if rc != 0:
        logger.warning(f"⚠️ MQTT unexpected disconnection (code: {rc})")
    else:
        logger.info("🔌 MQTT disconnected gracefully")


def on_mqtt_message(client, userdata, msg):
    """Callback for when MQTT message is received"""
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        logger.info(f"📨 MQTT message received on {topic}: {payload}")

        # Handle commands from server
        if topic == config.get_commands_topic():
            handle_mqtt_command(payload)

    except json.JSONDecodeError:
        logger.error(f"❌ Invalid JSON in MQTT message: {msg.payload}")
    except Exception as e:
        logger.error(f"❌ Error processing MQTT message: {e}")


def on_mqtt_publish(client, userdata, mid):
    """Callback for when MQTT message is published"""
    logger.debug(f"📤 MQTT message published (mid: {mid})")


def handle_mqtt_command(command: Dict[str, Any]):
    """Handle commands received via MQTT"""
    command_type = command.get("type")

    if command_type == "ping":
        logger.info("🏓 Received ping command")
        # Could respond with pong if needed
    elif command_type == "restart":
        logger.warning("🔄 Received restart command")
        # Could implement restart logic
    else:
        logger.warning(f"❓ Unknown command type: {command_type}")


# MQTT Helper Functions
def init_mqtt_client() -> Optional[mqtt.Client]:
    """Initialize MQTT client with configuration"""
    global mqtt_client

    if not config.is_mqtt_enabled():
        logger.info("📴 MQTT is disabled in configuration")
        return None

    try:
        # Create MQTT client
        client_id = f"gomama_pi_{config.get_listing_id()}_{int(time.time())}"
        mqtt_client = mqtt.Client(client_id=client_id)

        # Set callbacks
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.on_message = on_mqtt_message
        mqtt_client.on_publish = on_mqtt_publish

        # Configure SSL if enabled
        if config.get_mqtt_use_ssl():
            ssl_config = config.get_mqtt_ssl_config()
            mqtt_client.tls_set(
                ca_certs=ssl_config["ca_cert"],
                certfile=ssl_config["cert_file"],
                keyfile=ssl_config["key_file"],
            )
            logger.info("🔒 MQTT SSL/TLS configured")

        # Set keepalive
        mqtt_client.keepalive = config.get_mqtt_keepalive()

        logger.info(f"🚀 MQTT client initialized: {client_id}")
        return mqtt_client

    except Exception as e:
        logger.error(f"❌ Failed to initialize MQTT client: {e}")
        return None


def connect_mqtt() -> bool:
    """Connect to MQTT broker"""
    global mqtt_client, mqtt_connection_attempts

    if not mqtt_client:
        mqtt_client = init_mqtt_client()
        if not mqtt_client:
            return False

    if mqtt_connected:
        return True

    if mqtt_connection_attempts >= config.get_mqtt_max_reconnect_attempts():
        logger.error("❌ Maximum MQTT reconnection attempts reached")
        return False

    try:
        # Set credentials (use simple credentials like Flutter app)
        username = "adonisjs_client"
        password = "adonisjs_pass"
        mqtt_client.username_pw_set(username, password)

        # Connect to broker
        logger.info(f"🔌 Connecting to MQTT broker: {config.get_mqtt_broker_host()}:{config.get_mqtt_broker_port()}")
        mqtt_client.connect(
            config.get_mqtt_broker_host(),
            config.get_mqtt_broker_port(),
            config.get_mqtt_keepalive(),
        )

        # Start network loop in background
        mqtt_client.loop_start()

        # Wait for connection with timeout
        timeout = config.get_mqtt_connect_timeout()
        start_time = time.time()

        while not mqtt_connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        return mqtt_connected

    except Exception as e:
        logger.error(f"❌ MQTT connection error: {e}")
        mqtt_connection_attempts += 1
        return False


def publish_mqtt_message(topic: str, payload: Dict[str, Any]) -> bool:
    """Publish message via MQTT"""
    global mqtt_client

    if not mqtt_connected or not mqtt_client:
        # Queue message for later if offline
        if len(offline_message_queue) < config.get_mqtt_offline_buffer_size():
            offline_message_queue.append((topic, payload, time.time()))
            logger.warning(f"📦 Queued MQTT message for offline delivery (queue size: {len(offline_message_queue)})")
        else:
            logger.error("❌ Offline message queue is full, dropping message")
        return False

    try:
        message_json = json.dumps(payload)
        result = mqtt_client.publish(
            topic,
            message_json,
            qos=config.get_mqtt_qos(),
            retain=config.get_mqtt_retain(),
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"📤 MQTT message published to {topic}")
            return True
        else:
            logger.error(f"❌ MQTT publish failed with code: {result.rc}")
            return False

    except Exception as e:
        logger.error(f"❌ MQTT publish error: {e}")
        return False


def process_offline_queue():
    """Process queued offline messages"""
    global offline_message_queue

    if not offline_message_queue:
        return

    logger.info(f"📦 Processing {len(offline_message_queue)} offline messages")

    while offline_message_queue:
        topic, payload, queued_time = offline_message_queue.popleft()

        # Check if message is too old (optional)
        if time.time() - queued_time > 300:  # 5 minutes
            logger.warning("⏰ Dropping old offline message")
            continue

        if not publish_mqtt_message(topic, payload):
            # Re-queue if still failing
            offline_message_queue.appendleft((topic, payload, queued_time))
            break


# Initialise config
def init_config():
    global api_key, apn, pod_id, pi_id, usb_port, baud_rate, url, timestamp
    with open("/home/pi/Desktop/gomama-raspberrypi/config.json") as f:
        try:
            data = json.load(f)
            if "api_key" in data:
                api_key = data["api_key"]
            if "pod_id" in data:
                pod_id = data["pod_id"]
            if "pi_id" in data:
                pi_id = data["pi_id"]
            else:
                write_pi_config()
            if "url" in data:
                url = data["url"]
            timestamp = get_current_timestamp()
            print(data)
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            pass


def init_data():
    global listing_data, listing_id, timestamp, is_disinfecting, is_door_opened, is_occupied, is_led_light_on, is_fan_on, is_scheduled, is_uvc_lamp_on, temperature, humidity, is_send_data
    with open('/home/pi/Desktop/gomama-raspberrypi/data.json') as f:
        try:
            data = json.load(f)
            # listing_data = 1013995107100112091
            # listing_data = data
            # if '1013995107100112091' in data:
                # listing_id = data['listing_id']
            if 'timestamp' in data:
                timestamp = data['timestamp']
            if 'is_disinfecting' in data:
                is_disinfecting = data['is_disinfecting']
            if 'is_door_opened' in data:
                is_door_opened = data['is_door_opened']
            if 'is_occupied' in data:
                is_occupied = data['is_occupied']
            if 'is_led_light_on' in data:
                is_led_light_on = data['is_led_light_on']
            if 'is_fan_on' in data:
                is_fan_on = data['is_fan_on']
            if 'is_scheduled' in data:
                is_scheduled = data['is_scheduled']
            if 'is_uvc_lamp_on' in data:
                is_uvc_lamp_on = data['is_uvc_lamp_on']
            if 'temperature' in data:
                temperature = data['temperature']
            if 'humidity' in data:
                humidity = data['humidity']
            if 'is_send_data' in data:
                is_send_data = data['is_send_data']
        except json.decoder.JSONDecodeError as err:
            logger.error("JSON Decode Error", err)
            if listing_data:
                write_data(listing_data)


def post_https(pi_key_hashed):
    https_headers = {
        'Authorization': f'Bearer {pi_key_hashed}',
        'Content-Type': 'application/json',
    }
    data = json.dumps(listing_data)
    try:
        response = requests.post(url=url, data=data, headers=https_headers)
        logger.warning(f'{response}')
        logger.warning(f'* [E3372] server response: {response.text}')
    except requests.exceptions.RequestException as err:
        logger.error("Request Exception:", err)
        pass
    except requests.exceptions.HTTPError as errh:
        logger.error("Http Error:", errh)
        pass
    except requests.exceptions.ConnectionError as errc:
        logger.error("Connection Error:", errc)
        pass
    except requests.exceptions.Timeout as errt:
        logger.error("Timeout Error:", errt)
        pass
    except:
        logger.error("Error")
        pass


def send_data_mqtt() -> bool:
    """Send sensor data via MQTT"""
    try:
        # Prepare sensor data payload
        timestamp = int(time.time())
        auth_hash = generate_api_key_hashed(config.get_api_key(), config.get_pi_id(), timestamp)

        sensor_data_payload = {
            "listing_id": config.get_listing_id(),
            "timestamp": timestamp,
            "auth_hash": auth_hash,
            "sensor_data": {
                "is_disinfecting": is_disinfecting,
                "is_door_opened": is_door_opened,
                "is_occupied": is_occupied,
                "is_led_light_on": is_led_light_on,
                "is_fan_on": is_fan_on,
                "is_scheduled": is_scheduled,
                "is_uvc_lamp_on": is_uvc_lamp_on,
                "temperature": temperature,
                "humidity": humidity,
            },
        }

        # Publish to sensor data topic
        topic = config.get_sensor_data_topic()
        success = publish_mqtt_message(topic, sensor_data_payload)

        if success:
            logger.info(f"✅ Sensor data sent via MQTT to {topic}")
        else:
            logger.error("❌ Failed to send sensor data via MQTT")

        return success

    except Exception as e:
        logger.error(f"❌ Error sending MQTT data: {e}")
        return False


def send_data_http() -> bool:
    """Send sensor data via HTTP (fallback)"""
    try:
        # Prepare data in legacy format
        listing_data["listing_id"] = config.get_listing_id()
        listing_data["timestamp"] = loop_timestamp
        listing_data["is_disinfecting"] = is_disinfecting
        listing_data["is_door_opened"] = is_door_opened
        listing_data["is_occupied"] = is_occupied
        listing_data["is_led_light_on"] = is_led_light_on
        listing_data["is_fan_on"] = is_fan_on
        listing_data["is_scheduled"] = is_scheduled
        listing_data["is_uvc_lamp_on"] = is_uvc_lamp_on
        listing_data["temperature"] = temperature
        listing_data["humidity"] = humidity
        listing_data["is_send_data"] = False

        # Generate authentication hash
        pi_key_hashed = generate_api_key_hashed(config.get_api_key(), config.get_pi_id(), loop_timestamp)

        # Send via HTTP
        logger.info("📡 Sending data via HTTP fallback...")
        post_https(pi_key_hashed)
        return True

    except Exception as e:
        logger.error(f"❌ Error sending HTTP data: {e}")
        return False


def update_and_send_data():
    """Main data sending function with MQTT and HTTP fallback"""
    global is_scheduled, is_send_data

    logger.info("📊 Updating and sending sensor data...")
    init_data()

    # Log current sensor readings
    if config.is_debug_mode():
        logger.debug(
            f"Sensor readings: occupied={is_occupied}, disinfecting={is_disinfecting}, "
            f"temp={temperature}°C, humidity={humidity}%, door={is_door_opened}"
        )

    success = False

    # Try MQTT first if enabled
    if config.is_mqtt_enabled():
        if not mqtt_connected:
            logger.info("🔌 Attempting to connect to MQTT broker...")
            connect_mqtt()

        if mqtt_connected:
            success = send_data_mqtt()
        else:
            logger.warning("⚠️ MQTT not connected, will try HTTP fallback")

    # Fallback to HTTP if MQTT failed or disabled
    if not success and config.should_fallback_to_http():
        logger.info("🔄 Using HTTP fallback...")
        success = send_data_http()

    if success:
        logger.info("✅ Sensor data sent successfully")
    else:
        logger.error("❌ Failed to send sensor data via all methods")

    return success


def start_send_module():
    """Main application loop with MQTT and HTTP support"""
    global is_send_data, loop_timestamp, mqtt_client

    logger.info("🚀 Starting GoMama Pi sensor data module...")

    # Print configuration summary
    config.print_config_summary()

    # Initialize configuration
    init_config()

    # Initialize MQTT if enabled
    if config.is_mqtt_enabled():
        logger.info("📡 Initializing MQTT client...")
        mqtt_client = init_mqtt_client()
        if mqtt_client:
            connect_mqtt()
        else:
            logger.error("❌ Failed to initialize MQTT client")
    else:
        logger.info("📴 MQTT disabled, using HTTP only")

    # Main loop
    loop_timestamp = time.time()
    send_interval = config.get_send_interval()

    logger.info(f"🔄 Starting main loop (interval: {send_interval}s)")

    try:
        while True:
            time.sleep(0.2)  # Short sleep for responsiveness

            current_time = time.time()
            if current_time >= loop_timestamp + send_interval:
                logger.debug(f"[LOOP] Starting data cycle at {current_time:.2f}...")

                # Send sensor data
                update_and_send_data()

                # Update loop timestamp
                loop_timestamp = current_time

                logger.debug(f"[LOOP] Data cycle completed at {time.time():.2f}")

                if config.is_debug_mode():
                    print("\n" + "=" * 60 + "\n")

            # Small sleep to prevent excessive CPU usage
            time.sleep(0.2)

    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal, shutting down...")
        shutdown_gracefully()
    except Exception as e:
        logger.error(f"❌ Unexpected error in main loop: {e}")
        shutdown_gracefully()


def shutdown_gracefully():
    """Graceful shutdown procedure"""
    global mqtt_client

    logger.info("🔄 Shutting down gracefully...")

    # Disconnect MQTT client
    if mqtt_client and mqtt_connected:
        logger.info("🔌 Disconnecting MQTT client...")
        mqtt_client.loop_stop()
        mqtt_client.disconnect()

    logger.info("✅ Shutdown complete")


if __name__ == "__main__":
    start_send_module()
