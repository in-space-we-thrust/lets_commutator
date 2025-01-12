import json
import os

def load_config(file_path):
    """Load and validate configuration file"""
    try:
        if not os.path.exists(file_path):
            print(f"Config file not found: {file_path}")
            return None
            
        with open(file_path, 'r') as f:
            config = json.load(f)
            
        if 'mqtt' not in config:
            print("Missing MQTT configuration")
            return None
            
        return config
        
    except Exception as e:
        print(f"Error loading config: {e}")
        return None