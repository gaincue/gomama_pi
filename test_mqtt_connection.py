#!/usr/bin/env python3
"""
Simple MQTT connection test for mqtt.gomama.com.sg
"""

import paho.mqtt.client as mqtt
import time
import json

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker successfully!")
        print(f"Connection flags: {flags}")
        
        # Subscribe to a test topic
        test_topic = "gomama/test/connection"
        client.subscribe(test_topic, qos=1)
        print(f"📡 Subscribed to topic: {test_topic}")
        
        # Publish a test message
        test_message = {
            "timestamp": int(time.time()),
            "message": "Connection test from Python",
            "client": "python_test_client"
        }
        
        client.publish(test_topic, json.dumps(test_message), qos=1)
        print(f"📤 Published test message to {test_topic}")
        
    else:
        print(f"❌ Failed to connect to MQTT broker. Return code: {rc}")
        print("Return code meanings:")
        print("0: Connection successful")
        print("1: Connection refused - incorrect protocol version")
        print("2: Connection refused - invalid client identifier")
        print("3: Connection refused - server unavailable")
        print("4: Connection refused - bad username or password")
        print("5: Connection refused - not authorised")

def on_disconnect(client, userdata, rc):
    print(f"🔌 Disconnected from MQTT broker. Return code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        print(f"📥 Received message on topic '{topic}': {payload}")
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def on_publish(client, userdata, mid):
    print(f"✅ Message published successfully (mid: {mid})")

def test_mqtt_connection():
    """Test MQTT connection to mqtt.gomama.com.sg"""
    
    print("🚀 Testing MQTT connection to mqtt.gomama.com.sg:35883 (SSL)")
    print("=" * 50)
    
    # Create MQTT client
    client = mqtt.Client(client_id="python_test_client")
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.on_publish = on_publish
    
    # Set credentials (using the same as your Flutter app)
    client.username_pw_set("adonisjs_client", "adonisjs_pass")
    
    # Enable SSL/TLS
    client.tls_set()  # Use default SSL context
    
    try:
        # Connect to broker
        print("🔗 Attempting to connect with SSL...")
        result = client.connect("mqtt.gomama.com.sg", 35883, 60)
        
        if result == 0:
            print("🔄 Starting MQTT loop...")
            client.loop_start()
            
            # Wait for connection and test
            time.sleep(5)
            
            # Keep alive for a bit to see messages
            print("⏳ Waiting for messages (10 seconds)...")
            time.sleep(10)
            
            # Clean disconnect
            client.loop_stop()
            client.disconnect()
            print("👋 Test completed")
            
        else:
            print(f"❌ Connection failed with result code: {result}")
            
    except Exception as e:
        print(f"❌ Connection error: {e}")

if __name__ == "__main__":
    test_mqtt_connection()