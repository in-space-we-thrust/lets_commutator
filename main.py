import json
import os
import time
import threading
import paho.mqtt.client as mqtt
from commutator import Commutator
from config_loader import load_config

def main():
    # Load configuration
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    config = load_config(config_path)
    
    if not config:
        print("Failed to load configuration")
        return

    # Create and start commutator
    commutator = Commutator(config)
    
    try:
        commutator.start()
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nShutting down...")
        commutator.stop()

if __name__ == "__main__":
    main()
