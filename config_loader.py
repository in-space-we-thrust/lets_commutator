
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
            
        # Basic validation
        required_sections = ['mqtt', 'sensors', 'valves']
        for section in required_sections:
            if section not in config:
                print(f"Missing required section in config: {section}")
                return None
                
        return config
        
    except Exception as e:
        print(f"Error loading config: {e}")
        return None