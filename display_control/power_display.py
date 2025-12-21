import time
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from utils import Display
import threading
from queue import Queue

# Load environment variables
load_dotenv()

# Home Assistant configuration
HA_URL = os.getenv('HA_URL', 'http://homeassistant.local:8123')
HA_TOKEN = os.getenv('HA_TOKEN')
HA_ENTITIES = {
    'solar_power': os.getenv('HA_SOLAR_ENTITY', 'sensor.balkonkraftwerk_power'),
    'grid_power': os.getenv('HA_GRID_ENTITY', 'sensor.main_power')
}

# Global variables for power values
solar_power = 0
home_power = 0
grid_power = 0

def get_power_values():
    """Fetch power values from Home Assistant"""
    headers = {
        'Authorization': f'Bearer {HA_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    try:
        # Fetch all entities in one request
        response = requests.get(
            f'{HA_URL}/api/states',
            headers=headers,
            verify=False,  # Disable SSL verification
            timeout=5  # Add timeout to prevent hanging
        )
        response.raise_for_status()
        states = response.json()
        
        # Extract values from states
        values = {}
        for entity_id in HA_ENTITIES.values():
            state = next((s for s in states if s['entity_id'] == entity_id), None)
            if state:
                try:
                    values[entity_id] = float(state['state'])
                except (ValueError, TypeError):
                    values[entity_id] = 0
            else:
                print(f"Warning: Entity {entity_id} not found")
                values[entity_id] = 0
        
        # Calculate home power as sum of grid and solar
        return (
            round(1000),#values[HA_ENTITIES['solar_power']]),
            round(-200),#values[HA_ENTITIES['grid_power']])
        )
    except Exception as e:
        print(f"Error fetching power values: {e}")
        return 0, 0

def update_power_values():
    """Background thread to update power values"""
    global solar_power, home_power, grid_power
    
    while True:
        try:
            new_solar, new_grid = get_power_values()
            solar_power = new_solar
            grid_power = new_grid
            home_power = round(grid_power + solar_power)
        except Exception as e:
            print(f"Error in update thread: {e}")
        time.sleep(5)  # Update every 5 seconds

def main():
    if not HA_TOKEN:
        print("Error: HA_TOKEN environment variable not set")
        return
        
    print("Starting power flow display...")
    display = Display(interval=0.02)
    
    # Start the background thread for updating power values
    update_thread = threading.Thread(target=update_power_values, daemon=True)
    update_thread.start()
    
    try:
        while True:
            # Update display with current values
            display.print_power_flow(
                solar_power=solar_power,
                home_power=home_power,
                grid_power=grid_power
            )
            time.sleep(0.02)  # Keep animation smooth
            
    except KeyboardInterrupt:
        print("\nStopping power flow display...")
    except Exception as e:
        print(f"Fatal error: {e}")

if __name__ == "__main__":
    main() 