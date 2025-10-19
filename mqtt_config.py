#!/usr/bin/env python3
"""
MQTT Configuration Module for GoMama Raspberry Pi
Handles loading and validation of MQTT configuration settings
"""

import json
import os
import logging
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MQTTConfig:
    """MQTT Configuration handler for GoMama Raspberry Pi"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialize MQTT configuration
        
        Args:
            config_file: Path to the configuration JSON file
        """
        self.config_file = config_file
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        try:
            if not os.path.exists(self.config_file):
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            logger.info(f"✅ Configuration loaded from {self.config_file}")
            return config
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading configuration: {e}")
            raise
    
    def _validate_config(self) -> None:
        """Validate required configuration fields"""
        required_fields = ['api_key', 'listing_id', 'pi_id']
        
        for field in required_fields:
            if field not in self.config or not self.config[field]:
                raise ValueError(f"Missing required configuration field: {field}")
        
        # Validate MQTT configuration if enabled
        if self.is_mqtt_enabled():
            mqtt_config = self.config.get('mqtt', {})
            required_mqtt_fields = ['broker_host', 'broker_port']
            
            for field in required_mqtt_fields:
                if field not in mqtt_config or mqtt_config[field] is None:
                    raise ValueError(f"Missing required MQTT configuration field: {field}")
        
        logger.info("✅ Configuration validation passed")
    
    def is_mqtt_enabled(self) -> bool:
        """Check if MQTT is enabled"""
        return self.config.get('mqtt', {}).get('enabled', False)
    
    def get_mqtt_broker_host(self) -> str:
        """Get MQTT broker host"""
        return self.config['mqtt']['broker_host']
    
    def get_mqtt_broker_port(self) -> int:
        """Get MQTT broker port"""
        return int(self.config['mqtt']['broker_port'])
    
    def get_mqtt_use_ssl(self) -> bool:
        """Check if SSL/TLS should be used"""
        return self.config['mqtt'].get('use_ssl', False)
    
    def get_mqtt_ssl_config(self) -> Dict[str, Optional[str]]:
        """Get SSL/TLS configuration"""
        mqtt_config = self.config['mqtt']
        return {
            'ca_cert': mqtt_config.get('ssl_ca_cert'),
            'cert_file': mqtt_config.get('ssl_cert_file'),
            'key_file': mqtt_config.get('ssl_key_file')
        }
    
    def get_mqtt_username(self) -> str:
        """Generate MQTT username based on format"""
        # username_format = self.config['mqtt'].get('username_format', 'pi_{listing_id}_{pi_id}')
        # return username_format.format(
        #     listing_id=self.config['listing_id'],
        #     pi_id=self.config['pi_id']
        # )
        return "adonisjs_client"
    
    def get_mqtt_password(self, timestamp: int, auth_hash: str) -> str:
        """Generate MQTT password based on format"""
        # password_format = self.config['mqtt'].get('password_format', '{timestamp}:{auth_hash}')
        # return password_format.format(
        #     timestamp=timestamp,
        #     auth_hash=auth_hash
        # )
        return "adonisjs_pass"
    
    def get_sensor_data_topic(self) -> str:
        """Get sensor data topic"""
        topic_format = self.config['mqtt'].get('sensor_data_topic', 'gomama/devices/{listing_id}/sensor_data')
        return topic_format.format(listing_id=self.config['listing_id'])
    
    def get_status_topic(self) -> str:
        """Get status topic"""
        topic_format = self.config['mqtt'].get('status_topic', 'gomama/devices/{listing_id}/status')
        return topic_format.format(listing_id=self.config['listing_id'])
    
    def get_commands_topic(self) -> str:
        """Get commands topic"""
        topic_format = self.config['mqtt'].get('commands_topic', 'gomama/devices/{listing_id}/commands')
        return topic_format.format(listing_id=self.config['listing_id'])
    
    def get_mqtt_qos(self) -> int:
        """Get MQTT QoS level"""
        return self.config['mqtt'].get('qos', 1)
    
    def get_mqtt_retain(self) -> bool:
        """Get MQTT retain flag"""
        return self.config['mqtt'].get('retain', False)
    
    def get_mqtt_keepalive(self) -> int:
        """Get MQTT keepalive interval"""
        return self.config['mqtt'].get('keepalive', 60)
    
    def get_mqtt_connect_timeout(self) -> int:
        """Get MQTT connection timeout"""
        return self.config['mqtt'].get('connect_timeout', 10)
    
    def get_mqtt_reconnect_delay(self) -> int:
        """Get MQTT reconnection delay"""
        return self.config['mqtt'].get('reconnect_delay', 5)
    
    def get_mqtt_max_reconnect_attempts(self) -> int:
        """Get maximum MQTT reconnection attempts"""
        return self.config['mqtt'].get('max_reconnect_attempts', 10)
    
    def get_mqtt_offline_buffer_size(self) -> int:
        """Get offline message buffer size"""
        return self.config['mqtt'].get('offline_buffer_size', 100)
    
    def should_fallback_to_http(self) -> bool:
        """Check if HTTP fallback is enabled"""
        return self.config.get('fallback_to_http', True)
    
    def get_send_interval(self) -> int:
        """Get data sending interval in seconds"""
        return self.config.get('send_interval_seconds', 1)
    
    def is_debug_mode(self) -> bool:
        """Check if debug mode is enabled"""
        return self.config.get('debug_mode', False)
    
    def get_api_key(self) -> str:
        """Get API key"""
        return self.config['api_key']
    
    def get_listing_id(self) -> str:
        """Get listing ID"""
        return self.config['listing_id']
    
    def get_pi_id(self) -> str:
        """Get Pi ID"""
        return self.config['pi_id']
    
    def get_http_url(self, use_dev: bool = False) -> str:
        """Get HTTP URL for fallback"""
        if use_dev:
            return self.config.get('url_dev', self.config['url'])
        return self.config['url']
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        logger.info("🔄 Reloading configuration...")
        self.config = self._load_config()
        self._validate_config()
    
    def print_config_summary(self) -> None:
        """Print configuration summary for debugging"""
        if not self.is_debug_mode():
            return
        
        print("\n=== GoMama Pi Configuration Summary ===")
        print(f"Listing ID: {self.get_listing_id()}")
        print(f"Pi ID: {self.get_pi_id()}")
        print(f"MQTT Enabled: {self.is_mqtt_enabled()}")
        
        if self.is_mqtt_enabled():
            print(f"MQTT Broker: {self.get_mqtt_broker_host()}:{self.get_mqtt_broker_port()}")
            print(f"MQTT Username: {self.get_mqtt_username()}")
            print(f"MQTT SSL: {self.get_mqtt_use_ssl()}")
            print(f"Sensor Data Topic: {self.get_sensor_data_topic()}")
            print(f"Status Topic: {self.get_status_topic()}")
            print(f"Commands Topic: {self.get_commands_topic()}")
        
        print(f"HTTP Fallback: {self.should_fallback_to_http()}")
        print(f"Send Interval: {self.get_send_interval()}s")
        print(f"Debug Mode: {self.is_debug_mode()}")
        print("=====================================\n")


# Global configuration instance
_config_instance: Optional[MQTTConfig] = None

def get_config(config_file: str = "config.json") -> MQTTConfig:
    """Get global configuration instance"""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = MQTTConfig(config_file)
    
    return _config_instance

def reload_config() -> None:
    """Reload global configuration"""
    global _config_instance
    
    if _config_instance is not None:
        _config_instance.reload_config()
    else:
        _config_instance = MQTTConfig()


if __name__ == "__main__":
    # Test configuration loading
    try:
        config = get_config()
        config.print_config_summary()
        print("✅ Configuration test passed")
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
