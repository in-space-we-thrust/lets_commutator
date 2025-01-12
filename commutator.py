import json
import threading
import time
import paho.mqtt.client as mqtt
from communication import create_connection, SerialConnection, DeviceDiscovery

class Commutator:
    def __init__(self, mqtt_config=None):
        self.mqtt_config = mqtt_config or {
            'broker': 'localhost',
            'port': 1883,
            'base_topic': 'commutator'
        }
        
        self.connections = {}
        self.device_connections = {}  # uuid -> connection mapping
        self.running = False
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        self._discover_devices()

    def _discover_devices(self):
        discovered_devices = DeviceDiscovery.find_devices()
        
        for device in discovered_devices:
            connection_config = {
                'type': 'serial',
                'port': device['port'],
                'baudrate': 115200
            }
            connection = create_connection(connection_config)
            if connection:
                connection.connect()
                connection.set_uuid(device['uuid'])
                self.connections[device['port']] = connection
                self.device_connections[device['uuid']] = connection
                print(f"Connected to device {device['uuid']} on port {device['port']}")

    def start(self):
        self.running = True
        self.mqtt_client.connect(self.mqtt_config['broker'], self.mqtt_config['port'], 60)
        self.mqtt_client.loop_start()
        
        self.polling_thread = threading.Thread(target=self._poll_devices)
        self.polling_thread.daemon = True
        self.polling_thread.start()

    def stop(self):
        self.running = False
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        
        for connection in self.connections.values():
            connection.disconnect()

    def _poll_devices(self):
        while self.running:
            for connection in self.connections.values():
                if isinstance(connection, SerialConnection):
                    try:
                        data = connection.read_message()
                        if data:
                            self._publish_device_data(connection.get_uuid(), data)
                    except Exception as e:
                        print(f"Error polling connection: {e}")
            time.sleep(0.01)

    def _publish_device_data(self, device_uuid, data):
        topic = f"{self.mqtt_config['base_topic']}/devices/{device_uuid}/data"
        self.mqtt_client.publish(topic, data)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with code: {rc}")
        topic = f"{self.mqtt_config['base_topic']}/devices/+/command"
        client.subscribe(topic)

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            command = json.loads(msg.payload)
            device_uuid = command.get('device_uuid')
            if device_uuid and device_uuid in self.device_connections:
                connection = self.device_connections[device_uuid]
                if isinstance(connection, SerialConnection):
                    success = connection.send_message(msg.payload.decode())
                    # Send status message
                    status_topic = f"{self.mqtt_config['base_topic']}/devices/{device_uuid}/status"
                    status = {
                        "timestamp": time.time(),
                        "command": command,
                        "status": "delivered" if success else "failed"
                    }
                    self.mqtt_client.publish(status_topic, msg.payload)
        except Exception as e:
            print(f"Error processing MQTT message: {e}")