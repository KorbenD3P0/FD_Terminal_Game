# FD_Terminal_Game/main.py (Launcher Script)
import sys
import os
import logging
import pprint # Add this for readable printing
import shutil
import json
from kivy.uix.label import Label

print(f"--- Executing root main.py: {__file__} ---")
print(f"Initial os.getcwd(): {os.getcwd()}")

# --- Configure Logging Early ---
# Determine application path for bundled vs. source mode
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    application_path = os.path.dirname(sys.executable)
else:
    # Running in a normal Python environment
    application_path = os.path.dirname(os.path.abspath(__file__))

print(f"Calculated application_path: {application_path}")

# --- Path Setup for the fd_terminal package ---
if application_path not in sys.path:
    print(f"Adding {application_path} to sys.path[0]")
    sys.path.insert(0, application_path)
else:
    print(f"{application_path} is already in sys.path at index {sys.path.index(application_path)}")

# --- ENHANCED: Look for data directories and specific room data ---
possible_data_paths = [
    os.path.join(application_path, 'data'),
    os.path.join(application_path, 'assets'),
    os.path.join(application_path, 'fd_terminal', 'data'),
    os.path.join(application_path, 'fd_terminal', 'assets')
]

# Add PyInstaller _MEIPASS paths if applicable
if hasattr(sys, '_MEIPASS'):
    possible_data_paths.extend([
        os.path.join(sys._MEIPASS, 'data'),
        os.path.join(sys._MEIPASS, 'assets'),
        os.path.join(sys._MEIPASS, 'fd_terminal', 'data'),
        os.path.join(sys._MEIPASS, 'fd_terminal', 'assets')
    ])

# Function to recursively search for room data files
def find_room_data_files(base_path, max_depth=3, current_depth=0):
    found_files = []
    if current_depth > max_depth or not os.path.exists(base_path):
        return found_files
    
    try:
        for item in os.listdir(base_path):
            full_path = os.path.join(base_path, item)
            # Look for JSON files that might contain room data
            if os.path.isfile(full_path) and (
                'room' in item.lower() or 
                'level' in item.lower() or 
                'game_data' in item.lower()
            ) and item.endswith('.json'):
                found_files.append(full_path)
            # Recursively search directories
            elif os.path.isdir(full_path):
                found_files.extend(find_room_data_files(full_path, max_depth, current_depth + 1))
    except Exception as e:
        print(f"Error searching directory {base_path}: {e}")
    
    return found_files

print("--- Checking for game data directories ---")
data_path_found = None
room_data_files = []

for path in possible_data_paths:
    if os.path.exists(path):
        print(f"Found data directory: {path}")
        # First matching path becomes our default data path
        if data_path_found is None:
            data_path_found = path
        
        # List first few files to verify content
        try:
            files = os.listdir(path)[:5]  # Show up to 5 files
            print(f"  Contains: {files}")
            
            # Look for room data files
            room_files = find_room_data_files(path)
            if room_files:
                print(f"  Found potential room data files: {room_files}")
                room_data_files.extend(room_files)
                
                # Examine content of json files to verify they contain room data
                for file_path in room_files:
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                            if isinstance(data, dict) and ('rooms' in data or 'levels' in data):
                                print(f"  Verified room data in: {file_path}")
                                # Try to show room level ids if possible
                                if 'rooms' in data:
                                    room_ids = list(data['rooms'].keys()) if isinstance(data['rooms'], dict) else "Not a dictionary"
                                    print(f"  Room IDs: {room_ids[:5]}...")
                    except Exception as e:
                        print(f"  Error reading JSON file {file_path}: {e}")
        except Exception as e:
            print(f"  Error listing directory: {e}")
    else:
        print(f"Missing data directory: {path}")

print("--- sys.path before import of fd_terminal.main ---")
pprint.pprint(sys.path)

# Set up basic logging (adjust as needed)
# This will log to the directory where the script (or EXE) is run from.
# For packaged apps, consider Kivy App's user_data_dir for logs.
log_file = "fd_launcher.log"
logging.basicConfig(filename=log_file,
                    level=logging.DEBUG, # DEBUG for more info during troubleshooting
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s')

logging.info("Launcher main.py started.")
logging.info(f"sys.executable: {sys.executable}")
logging.info(f"sys.argv: {sys.argv}")
logging.info(f"os.getcwd(): {os.getcwd()}")
logging.info(f"application_path: {application_path}")
logging.info(f"sys.path: {sys.path}")
logging.info(f"Is frozen (bundled): {getattr(sys, 'frozen', False)}")
if hasattr(sys, '_MEIPASS'):
    logging.info(f"sys._MEIPASS: {sys._MEIPASS}")
    # For PyInstaller, ensure data directories from _MEIPASS are checked
    meipass_data = os.path.join(sys._MEIPASS, 'data')
    meipass_assets = os.path.join(sys._MEIPASS, 'fd_terminal', 'data')
    logging.info(f"_MEIPASS data exists: {os.path.exists(meipass_data)}")
    logging.info(f"_MEIPASS fd_terminal/data exists: {os.path.exists(meipass_assets)}")

# Now, import and run your Kivy app from the fd_terminal package
try:
    logging.info("Attempting to import FinalDestinationApp from fd_terminal.main")
    print("--- Attempting: from fd_terminal.main import FinalDestinationApp ---")
    from fd_terminal.main import FinalDestinationApp
    logging.info("Import successful.")
    
    # Set environment variables to help the app locate data files
    os.environ['FD_GAME_ROOT'] = application_path
    logging.info(f"Set FD_GAME_ROOT environment variable to: {application_path}")
    
    # If we found a specific data path, set that too
    if data_path_found:
        os.environ['FD_DATA_PATH'] = data_path_found
        logging.info(f"Set FD_DATA_PATH environment variable to: {data_path_found}")
    
    # If we found room data files, set that path too
    if room_data_files:
        room_data_dir = os.path.dirname(room_data_files[0])
        os.environ['FD_ROOM_DATA_PATH'] = room_data_dir
        logging.info(f"Set FD_ROOM_DATA_PATH environment variable to: {room_data_dir}")

    # --- RUN THE APP ---
    print("--- Running FinalDestinationApp ---")
    app = FinalDestinationApp()
    
    # Directly set data paths if available
    if hasattr(app, 'set_data_path') and data_path_found:
        print(f"Setting app data path to: {data_path_found}")
        app.set_data_path(data_path_found)
    
    # Directly set room data path if available
    if hasattr(app, 'set_room_data_path') and room_data_files:
        room_data_dir = os.path.dirname(room_data_files[0])
        print(f"Setting app room data path to: {room_data_dir}")
        app.set_room_data_path(room_data_dir)
    
    # Monkey patch the app's resource finding function if needed
    if hasattr(app, 'find_resource'):
        original_find_resource = app.find_resource
        def enhanced_find_resource(resource_path, *args, **kwargs):
            # Try original method first
            result = original_find_resource(resource_path, *args, **kwargs)
            if result and os.path.exists(result):
                return result
                
            # If original fails, try our known paths
            for base_path in possible_data_paths:
                test_path = os.path.join(base_path, resource_path)
                if os.path.exists(test_path):
                    print(f"Resource found at alternative path: {test_path}")
                    return test_path
            
            print(f"Resource not found: {resource_path}")
            return resource_path  # Return original path as fallback
            
        app.find_resource = enhanced_find_resource
        print("Enhanced resource finding function installed.")
    
    app.run()

except ImportError as e_import:
    logging.error(f"ImportError in launcher: {e_import}", exc_info=True)
    print(f"IMPORT ERROR: {e_import}")
    raise
except Exception as e_launcher:
    logging.error(f"General error in launcher: {e_launcher}", exc_info=True)
    print(f"ERROR: {e_launcher}")
    raise