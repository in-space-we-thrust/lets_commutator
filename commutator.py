import json
import threading
import time
import paho.mqtt.client as mqtt
from communication import create_connection, SerialConnection, DeviceDiscovery
from devices import Sensor, Valve

class Commutator:
    def __init__(self, config):
        self.config = config
        self.mqtt_config = config.get('mqtt', {
            'broker': 'localhost',
            'port': 1883,
            'base_topic': 'commutator'
        })
        
        self.connections = {}
        self.sensors = {}
        self.valves = {}
        self.running = False
        self.device_connections = {}  # uuid -> connection mapping
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        self._setup_devices()

    def _setup_devices(self):
        # Discover available devices
        discovered_devices = DeviceDiscovery.find_devices()
        
        # Store discovered ports to avoid using non-existent ones from config
        discovered_ports = {device['port'] for device in discovered_devices}
        
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
        
        # Initialize sensors only for discovered ports
        for sensor_config in self.config.get('sensors', []):
            port = sensor_config['connection'].get('port')
            if port in discovered_ports:
                sensor = Sensor.from_json(sensor_config)
                self.sensors[sensor.id] = sensor
        
        # Initialize valves only for discovered ports
        for valve_config in self.config.get('valves', []):
            port = valve_config['connection'].get('port')
            if port in discovered_ports:
                valve = Valve.from_json(valve_config)
                self.valves[valve.id] = valve

    def _ensure_connection(self, connection_config):
        # Skip if port doesn't exist
        if isinstance(connection_config, dict) and 'port' in connection_config:
            port = connection_config['port']
            if port not in self.connections:
                return

        key = self._make_connection_key(connection_config)
        if key not in self.connections:
            connection = create_connection(connection_config)
            if connection:
                self.connections[key] = connection

    def _make_connection_key(self, connection_config):
        if isinstance(connection_config, dict):
            return connection_config.get('port', str(connection_config))
        return str(connection_config)

    def start(self):
        self.running = True
        
        # Connect to MQTT broker
        self.mqtt_client.connect(
            self.mqtt_config['broker'],
            self.mqtt_config['port'],
            60
        )
        self.mqtt_client.loop_start()
        
        # Start device polling threads
        self.sensor_thread = threading.Thread(target=self._poll_sensors)
        self.sensor_thread.daemon = True
        self.sensor_thread.start()

    def stop(self):
        self.running = False
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        
        # Close all connections
        for connection in self.connections.values():
            connection.disconnect()

    def _poll_sensors(self):
        while self.running:
            # Poll all active connections
            for connection in self.connections.values():
                if isinstance(connection, SerialConnection):
                    try:
                        data = connection.read_message()
                        if data:
                            # Publish raw data to MQTT
                            self._publish_sensor_data(connection.get_uuid(), data)
                    except Exception as e:
                        print(f"Error polling connection: {e}")
            
            time.sleep(0.01)  # Small delay to prevent CPU overload

    def _publish_sensor_data(self, device_uuid, value):
        topic = f"{self.mqtt_config['base_topic']}/devices/{device_uuid}/data"
        self.mqtt_client.publish(topic, value)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with code: {rc}")
        # Subscription is already correct: commutator/valves/+/command
        topic = f"{self.mqtt_config['base_topic']}/valves/+/command"
        client.subscribe(topic)

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            command = json.loads(msg.payload)
            
            # Check for UUID in command
            device_uuid = command.get('uuid')
            if device_uuid and device_uuid in self.device_connections:
                connection = self.device_connections[device_uuid]
                
                # Format and send command to the device
                if isinstance(connection, SerialConnection):
                    command_str = json.dumps({
                        "uuid": device_uuid,
                        "type": command.get('type'),
                        "command": command.get('command'),
                        "valve_pin": command.get('pin'),
                        "status": command.get('status', False)
                    })
                    connection.send_message(command_str)
                    
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def _publish_valve_state(self, valve):
        # Change from 'state' to 'status' in topic name
        topic = f"{self.mqtt_config['base_topic']}/valves/{valve.id}/status"
        payload = json.dumps({
            'valve_id': valve.id,
            'state': valve.status,
            'timestamp': time.time()
        })
        self.mqtt_client.publish(topic, payload)