from commutator import Commutator
from config_loader import load_config
import os
import time

def main():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    config = load_config(config_path)
    
    if not config:
        print("Failed to load configuration")
        return
    
    commutator = Commutator(config['mqtt'])
    
    try:
        commutator.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        commutator.stop()

if __name__ == "__main__":
    main()
