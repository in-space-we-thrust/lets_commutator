import json
import threading
import time
import paho.mqtt.client as mqtt
from communication import create_connection, SerialConnection
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
        
        # Initialize MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self._on_mqtt_connect
        self.mqtt_client.on_message = self._on_mqtt_message
        
        self._setup_devices()

    def _setup_devices(self):
        # Initialize sensors
        for sensor_config in self.config.get('sensors', []):
            sensor = Sensor.from_json(sensor_config)
            self.sensors[sensor.id] = sensor
            self._ensure_connection(sensor.connection)

        # Initialize valves
        for valve_config in self.config.get('valves', []):
            valve = Valve.from_json(valve_config)
            self.valves[valve.id] = valve
            self._ensure_connection(valve.connection)

    def _ensure_connection(self, connection_config):
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
            for sensor in self.sensors.values():
                try:
                    connection = self.connections[self._make_connection_key(sensor.connection)]
                    if isinstance(connection, SerialConnection):
                        data = connection.read_message()
                        if data:
                            try:
                                # Process and publish sensor data
                                # processed_value = sensor.process_signal(float(data))
                                self._publish_sensor_data(sensor.id, data)
                            except ValueError:
                                print(f"Invalid sensor data: {data}")
                except Exception as e:
                    print(f"Error polling sensor {sensor.id}: {e}")
            
            time.sleep(0.01)  # Small delay to prevent CPU overload

    def _publish_sensor_data(self, sensor_id, value):
        topic = f"{self.mqtt_config['base_topic']}/sensors/{sensor_id}"
        # payload = json.dumps({
        #     'id': sensor_id,
        #     'value': value,
        #     'timestamp': time.time()
        # })
        payload = value
        self.mqtt_client.publish(topic, payload)

    def _on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with code: {rc}")
        # Subscription is already correct: commutator/valves/+/command
        topic = f"{self.mqtt_config['base_topic']}/valves/+/command"
        client.subscribe(topic)

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            # Extract valve ID from topic
            parts = msg.topic.split('/')
            if len(parts) >= 4 and parts[1] == 'valves':
                valve_id = int(parts[2])
                command = json.loads(msg.payload)
                
                if valve_id in self.valves:
                    valve = self.valves[valve_id]
                    connection = self.connections[self._make_connection_key(valve.connection)]
                    
                    # Format and send command to the device
                    if isinstance(connection, SerialConnection):
                        command_str = json.dumps({
                            "type": 1,
                            "command": 17,
                            "valve_pin": valve.pin,
                            "status": command.get('status', False)
                        })
                        connection.send_message(command_str)
                        
                        # Update valve status and publish state
                        valve.status = command.get('state', False)
                        self._publish_valve_state(valve)
                        
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