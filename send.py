#!/usr/bin/env python3
"""
Fixed version of send.py with better MQTT handling and fallback options
"""

import json
import logging
import time
import threading
import signal
import sys
from collections import deque
from typing import Optional, Dict, Any

import coloredlogs
import requests

# Try to import paho.mqtt with fallback
MQTT_AVAILABLE = True
try:
    import paho.mqtt.client as mqtt
except ImportError:
    MQTT_AVAILABLE = False
    print("⚠️ paho-mqtt not available, using HTTP-only mode")

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
mqtt_enabled = MQTT_AVAILABLE and config.is_mqtt_enabled()

logger = logging.getLogger(__name__)
coloredlogs.install(level=logging.DEBUG, logger=logger, fmt="%(name)s - %(levelname)s - %(message)s")

# Graceful shutdown handling
shutdown_requested = False

def signal_handler(sig, frame):
    global shutdown_requested
    logger.info("🛑 Shutdown signal received")
    shutdown_requested = True

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# MQTT Event Callbacks (only if MQTT is available)
if MQTT_AVAILABLE:
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

def handle_mqtt_command(command: Dict[str, Any]):
    """Handle commands received via MQTT"""
    command_type = command.get("type")

    if command_type == "ping":
        logger.info("🏓 Received ping command")
    elif command_type == "restart":
        logger.warning("🔄 Received restart command")
    else:
        logger.warning(f"❓ Unknown command type: {command_type}")

def create_mqtt_client_safe() -> Optional[mqtt.Client]:
    """Safely create MQTT client with timeout protection"""
    if not MQTT_AVAILABLE:
        logger.info("📴 MQTT library not available")
        return None
        
    if not config.is_mqtt_enabled():
        logger.info("📴 MQTT is disabled in configuration")
        return None

    try:
        client_id = f"gomama_pi_{config.get_listing_id()}_{int(time.time())}"
        logger.info(f"🆔 Creating MQTT client: {client_id}")
        
        # Create client with timeout protection
        client_created = threading.Event()
        creation_error = None
        created_client = None
        
        def create_client():
            nonlocal creation_error, created_client
            try:
                logger.info("⏳ Calling mqtt.Client()...")
                created_client = mqtt.Client(client_id=client_id)
                logger.info("✅ MQTT client instance created")
                client_created.set()
            except Exception as e:
                creation_error = e
                logger.error(f"❌ MQTT client creation failed: {e}")
                client_created.set()
        
        # Run client creation in separate thread with timeout
        thread = threading.Thread(target=create_client, daemon=True)
        thread.start()
        
        # Wait for completion with timeout
        if not client_created.wait(timeout=10):
            logger.error("❌ MQTT client creation timed out after 10 seconds!")
            logger.error("💡 Falling back to HTTP-only mode")
            return None
        
        if creation_error:
            logger.error(f"❌ Client creation error: {creation_error}")
            return None
            
        if not created_client:
            logger.error("❌ Client creation failed - no client instance")
            return None

        # Set callbacks
        created_client.on_connect = on_mqtt_connect
        created_client.on_disconnect = on_mqtt_disconnect
        created_client.on_message = on_mqtt_message

        # Configure SSL if enabled
        if config.get_mqtt_use_ssl():
            try:
                created_client.tls_set()
                logger.info("🔒 MQTT SSL/TLS configured")
            except Exception as e:
                logger.error(f"❌ SSL configuration failed: {e}")
                return None

        logger.info(f"🚀 MQTT client created successfully: {client_id}")
        return created_client

    except Exception as e:
        logger.error(f"❌ Failed to create MQTT client: {e}")
        return None

def connect_mqtt_safe() -> bool:
    """Safely connect to MQTT broker with timeout protection"""
    global mqtt_client, mqtt_connection_attempts, mqtt_connected

    if not MQTT_AVAILABLE or not config.is_mqtt_enabled():
        return False

    if not mqtt_client:
        mqtt_client = create_mqtt_client_safe()
        if not mqtt_client:
            return False

    if mqtt_connected:
        return True

    if mqtt_connection_attempts >= config.get_mqtt_max_reconnect_attempts():
        logger.error("❌ Maximum MQTT reconnection attempts reached")
        return False

    try:
        # Set credentials
        username = "adonisjs_client"
        password = "adonisjs_pass"
        mqtt_client.username_pw_set(username, password)

        logger.info(f"🔌 Connecting to MQTT broker: {config.get_mqtt_broker_host()}:{config.get_mqtt_broker_port()}")
        
        # Connect with timeout protection
        connection_done = threading.Event()
        connect_error = None
        
        def connect():
            nonlocal connect_error
            try:
                result = mqtt_client.connect(
                    config.get_mqtt_broker_host(),
                    config.get_mqtt_broker_port(),
                    config.get_mqtt_keepalive(),
                )
                if result == 0:
                    logger.info("✅ MQTT connect() call successful")
                    mqtt_client.loop_start()
                else:
                    connect_error = f"Connect returned error code: {result}"
                connection_done.set()
            except Exception as e:
                connect_error = str(e)
                connection_done.set()
        
        # Run connection in separate thread with timeout
        thread = threading.Thread(target=connect, daemon=True)
        thread.start()
        
        # Wait for connection attempt with timeout
        if not connection_done.wait(timeout=15):
            logger.error("❌ MQTT connection attempt timed out after 15 seconds!")
            mqtt_connection_attempts += 1
            return False
        
        if connect_error:
            logger.error(f"❌ MQTT connection error: {connect_error}")
            mqtt_connection_attempts += 1
            return False

        # Wait for connection callback with timeout
        timeout = config.get_mqtt_connect_timeout()
        start_time = time.time()

        while not mqtt_connected and (time.time() - start_time) < timeout:
            if shutdown_requested:
                return False
            time.sleep(0.1)

        if not mqtt_connected:
            logger.error(f"❌ MQTT connection callback timeout after {timeout}s")
            mqtt_connection_attempts += 1
            return False

        return mqtt_connected

    except Exception as e:
        logger.error(f"❌ MQTT connection error: {e}")
        mqtt_connection_attempts += 1
        return False

def publish_mqtt_message(topic: str, payload: Dict[str, Any]) -> bool:
    """Publish message via MQTT"""
    global mqtt_client

    if not MQTT_AVAILABLE or not mqtt_connected or not mqtt_client:
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

# Data handling functions (same as original)
def init_config():
    global api_key, apn, pod_id, pi_id, usb_port, baud_rate, url, timestamp
    with open("/Users/kkcy/development/gomama/gomama2.0/gomama_pi/config.json") as f:
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
    with open('/Users/kkcy/development/gomama/gomama2.0/gomama_pi/data.json') as f:
        try:
            data = json.load(f)
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
    if not MQTT_AVAILABLE:
        return False
        
    try:
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

        pi_key_hashed = generate_api_key_hashed(config.get_api_key(), config.get_pi_id(), loop_timestamp)

        logger.info("📡 Sending data via HTTP...")
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

    if config.is_debug_mode():
        logger.debug(
            f"Sensor readings: occupied={is_occupied}, disinfecting={is_disinfecting}, "
            f"temp={temperature}°C, humidity={humidity}%, door={is_door_opened}"
        )

    success = False

    # Try MQTT first if enabled and available
    if mqtt_enabled:
        if not mqtt_connected:
            logger.info("🔌 Attempting to connect to MQTT broker...")
            connect_mqtt_safe()

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
    """Main application loop with improved error handling"""
    global is_send_data, loop_timestamp, mqtt_client, shutdown_requested

    logger.info("🚀 Starting GoMama Pi sensor data module...")

    # Print configuration summary
    config.print_config_summary()

    # Initialize configuration
    init_config()

    # Initialize MQTT if enabled and available
    if mqtt_enabled:
        logger.info("📡 Initializing MQTT client...")
        mqtt_client = create_mqtt_client_safe()
        if mqtt_client:
            connect_mqtt_safe()
        else:
            logger.warning("⚠️ MQTT initialization failed, using HTTP-only mode")
    else:
        if not MQTT_AVAILABLE:
            logger.info("📴 MQTT library not available, using HTTP-only mode")
        else:
            logger.info("📴 MQTT disabled, using HTTP-only mode")

    # Main loop
    loop_timestamp = time.time()
    send_interval = config.get_send_interval()

    logger.info(f"🔄 Starting main loop (interval: {send_interval}s)")

    try:
        while not shutdown_requested:
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
    except Exception as e:
        logger.error(f"❌ Unexpected error in main loop: {e}")
    finally:
        shutdown_gracefully()

def shutdown_gracefully():
    """Graceful shutdown procedure"""
    global mqtt_client, shutdown_requested

    shutdown_requested = True
    logger.info("🔄 Shutting down gracefully...")

    # Disconnect MQTT client
    if MQTT_AVAILABLE and mqtt_client and mqtt_connected:
        logger.info("🔌 Disconnecting MQTT client...")
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"❌ Error during MQTT disconnect: {e}")

    logger.info("✅ Shutdown complete")

if __name__ == "__main__":
    start_send_module()