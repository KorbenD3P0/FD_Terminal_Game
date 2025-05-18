import json
import random
import logging
import copy
import os
import datetime
import collections

# Color constants for UI rendering (though GameLogic primarily returns raw data)
from .utils import color_text, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_ORANGE, COLOR_LIGHT_GREY, COLOR_BLUE, COLOR_PURPLE, COLOR_WHITE, COLOR_MAGENTA
from kivy.app import App # For user_data_dir path
from . import game_data
from .hazard_engine import HazardEngine
# AchievementsSystem is passed in constructor

class GameLogic:
    SAVE_FILENAME_TEMPLATE = "savegame_{}.json" # Adjusted template for clarity
    MAX_SAVE_SLOTS = 5
    
    def __init__(self, achievements_system=None):
        logging.info("GameLogic initialization started")
        try:
            self.game_data = game_data
            if not hasattr(self.game_data, 'rooms') or not hasattr(self.game_data, 'items'):
                logging.error("game_data module is missing critical attributes like 'rooms' or 'items'.")
            logging.info(f"game_data module loaded. Levels available: {list(self.game_data.rooms.keys()) if hasattr(self.game_data, 'rooms') else 'N/A'}")
        except ImportError:
            logging.error("Failed to import game_data module directly in GameLogic init.")
            self.game_data = None 
        except Exception as e:
            logging.error(f"Error accessing game_data during GameLogic init: {e}")
            self.game_data = None

        self.achievements_system = achievements_system 
        self.is_game_over = False
        self.game_won = False
        self.player = None 
        self.evaded_hazards_for_interlevel_screen = [] 

        self.revealed_items_in_rooms = {} 
        self.interaction_counters = {}    
        self.current_level_rooms = {}     
        self.current_level_items_master_copy = {} 
        self.current_level_items_world_state = {} 
        self.logger = logging.getLogger(__name__) # Ensure logger is initialized
        if not self.logger.handlers:
            # Basic setup if not already configured by main app
            log_dir = os.path.join(os.getcwd(), "logs") # Fallback log dir
            try:
                running_app = App.get_running_app()
                if running_app and hasattr(running_app, 'user_data_dir'):
                    log_dir = os.path.join(running_app.user_data_dir, "logs")
            except Exception:
                pass # Use CWD if Kivy app not running
            os.makedirs(log_dir, exist_ok=True)
            handler = logging.FileHandler(os.path.join(log_dir, "fd_gamelogic_alt.log"), mode='w')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False
        self.hazard_engine = None 
        self._setup_paths_and_logging() 
        logging.info("GameLogic instance created. Call start_new_game() or load_game() to begin play.")

    def _setup_paths_and_logging(self):
        self.user_data_dir = ""
        try:
            running_app = App.get_running_app()
            if running_app and hasattr(running_app, 'user_data_dir'):
                self.user_data_dir = running_app.user_data_dir
            else:
                self.user_data_dir = os.path.abspath(os.path.join(os.getcwd(), "user_data_fallback"))
                logging.warning(f"Kivy app not running or user_data_dir not found. Using fallback: {self.user_data_dir}")
            os.makedirs(self.user_data_dir, exist_ok=True)
        except Exception as e:
            self.user_data_dir = os.path.abspath(os.path.join(os.getcwd(), "user_data_fallback_exception"))
            logging.error(f"Error getting user_data_dir: {e}. Using exception fallback: {self.user_data_dir}", exc_info=True)
            os.makedirs(self.user_data_dir, exist_ok=True)

        self.logger = logging.getLogger(__name__) 
        if not self.logger.handlers: 
            log_dir = os.path.join(self.user_data_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            # Use a unique name for the GameLogic log file if App.py also logs
            handler = logging.FileHandler(os.path.join(log_dir, "fd_gamelogic.log"), mode='w') # Changed mode to 'w'
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO) 
            self.logger.propagate = False 

        self.logger.info(f"GameLogic logging to: {os.path.join(self.user_data_dir, 'logs', 'fd_gamelogic.log')}")
        self.save_dir = os.path.join(self.user_data_dir, 'saves')
        os.makedirs(self.save_dir, exist_ok=True)
        self.logger.info(f"GameLogic save directory: {self.save_dir}")

    def start_new_game(self, character_class="Journalist"):
        self.logger.info(f"Starting new game with character: {character_class}...")
        self.is_game_over = False; self.game_won = False
        if hasattr(self.game_data, 'get_initial_player_state'):
            self.player = self.game_data.get_initial_player_state(character_class)
        else: 
            stats = self.game_data.CHARACTER_CLASSES.get(character_class, self.game_data.CHARACTER_CLASSES["Journalist"])
            self.player = {
                "location": self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"], "inventory": [],
                "hp": stats["max_hp"], "max_hp": stats["max_hp"], "perception": stats["perception"], "intuition": stats["intuition"],
                "status_effects": {}, "score": 0, "turns_left": self.game_data.STARTING_TURNS,
                "actions_taken": 0, "visited_rooms": set(), "current_level": 1,
                "qte_active": None, "qte_duration": 0, "qte_context": {},
                "last_hazard_type": None, "last_hazard_object_name": None, 
                "character_class": character_class, "journal": {} 
            }
        self.player['current_level'] = 1
        self.player['location'] = self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"] 
        self.player['visited_rooms'] = {self.player['location']}
        self.player['mri_qte_failures'] = 0
        self.player['actions_taken_this_level'] = 0
        self.player['evidence_found_this_level'] = [] 
        self.player['evaded_hazards_current_level'] = [] 
        self._initialize_level_data(self.player['current_level'])
        if not self.hazard_engine: self.hazard_engine = HazardEngine(self)
        self.hazard_engine.initialize_for_level(self.player['current_level'])
        self.logger.info(f"New game started. Player at {self.player['location']}. Level {self.player['current_level']}.")
        self.interaction_counters.clear()

    def _initialize_level_data(self, level_id):
        self.logger.info(f"Initializing data for Level {level_id}...")
        self.revealed_items_in_rooms.clear()
        self.interaction_counters.clear()

        if not self.game_data or not hasattr(self.game_data, 'rooms'):
            self.logger.error(f"game_data.rooms not available. Cannot initialize level {level_id}.")
            # Initialize to empty structures to prevent crashes later
            self.current_level_rooms = {}
            self.current_level_items_master_copy = {}
            self.current_level_items_world_state = {}
            if self.hazard_engine: # Check if hazard_engine exists
                self.hazard_engine.active_hazards.clear() # Clear active hazards if engine exists
            return

        level_rooms_master = self.game_data.rooms.get(level_id)
        if level_rooms_master is None:
            self.logger.error(f"Level {level_id} data not found in game_data.rooms.")
            self.current_level_rooms = {}
        else:
            self.current_level_rooms = copy.deepcopy(level_rooms_master)
            self.logger.info(f"Loaded {len(self.current_level_rooms)} rooms for level {level_id}.")

        # Initialize current_level_items_master_copy by merging items, evidence, and keys
        self.current_level_items_master_copy.clear()
        all_item_sources = {
            "items": getattr(self.game_data, 'items', {}),
            "evidence": getattr(self.game_data, 'evidence', {}),
            "keys": getattr(self.game_data, 'keys', {})
        }

        for source_type, item_dict in all_item_sources.items():
            if not isinstance(item_dict, dict):
                self.logger.warning(f"Item source '{source_type}' in game_data is not a dictionary. Skipping.")
                continue
            for name, data in item_dict.items():
                if not isinstance(data, dict): # Ensure item data is a dictionary
                    self.logger.warning(f"Skipping non-dict item entry in '{source_type}': {name} ({type(data)})")
                    continue
                
                item_level_id_from_data = data.get("level")
                is_eligible_for_current_level = False

                # Check if item belongs to the current level or is global
                if item_level_id_from_data == level_id:
                    is_eligible_for_current_level = True
                elif item_level_id_from_data is None or str(item_level_id_from_data).lower() == "all":
                    is_eligible_for_current_level = True
                
                if is_eligible_for_current_level:
                    if name not in self.current_level_items_master_copy:
                        self.current_level_items_master_copy[name] = copy.deepcopy(data)
                    else:
                        # If item name is duplicated, log a warning. Could prioritize or merge.
                        self.logger.warning(f"Duplicate item name '{name}' found. Using first definition from '{source_type}'.")
        
        # Create the world state from the master copy for this level
        self.current_level_items_world_state = copy.deepcopy(self.current_level_items_master_copy)
        self.logger.info(f"Initialized {len(self.current_level_items_world_state)} item types for level {level_id} world state.")

        # Set initial world state for items (location, container, hidden status)
        # This ensures items not explicitly placed by _place_dynamic_elements_for_level
        # still have their defined locations if any.
        for item_name, item_world_data in self.current_level_items_world_state.items():
            original_item_def = self.current_level_items_master_copy.get(item_name, {})
            
            # Determine if item has a fixed placement
            is_fixed = (original_item_def.get("fixed_location") or 
                        (original_item_def.get("location") and original_item_def.get("container")) or # If location AND container are defined
                        (original_item_def.get("location") and not original_item_def.get("container") and not original_item_def.get("is_rare_random_hospital_spawn") and not original_item_def.get("spawn_locations")) or # On floor
                        item_name in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION)

            if not is_fixed and not original_item_def.get("spawn_locations") and not original_item_def.get("is_rare_random_hospital_spawn"):
                # Item is meant for dynamic placement or is not placed by default
                item_world_data.pop("location", None)
                item_world_data.pop("container", None)
                item_world_data["is_hidden"] = original_item_def.get("is_hidden", True) # Default to hidden if dynamic
            else: # Fixed or specific spawn logic will handle it
                item_world_data["location"] = original_item_def.get("location")
                item_world_data["container"] = original_item_def.get("container")
                # is_hidden true if it's in a container or explicitly hidden, false if on floor and not hidden
                item_world_data["is_hidden"] = original_item_def.get("is_hidden", bool(original_item_def.get("container")))


        self._place_dynamic_elements_for_level(level_id) # Place items that need dynamic placement

        if self.hazard_engine:
            self.hazard_engine.initialize_for_level(level_id)
        else:
            self.logger.warning("HazardEngine not initialized when _initialize_level_data called.")
        
        self.logger.info(f"Level {level_id} data initialization complete.")

    def _place_dynamic_elements_for_level(self, level_id):
        self.logger.info(f"--- Placing Dynamic & Fixed Elements for Level {level_id} ---")
        
        # Handle specific spawn logic first (like Radiology Key Card, Medical Director Key Card)
        # Radiology Key Card
        radiology_key_name = "Radiology Key Card"
        radiology_key_master_data = self.current_level_items_master_copy.get(radiology_key_name)
        if radiology_key_master_data and radiology_key_master_data.get("level") == level_id:
            spawn_options = radiology_key_master_data.get("spawn_locations", [])
            if spawn_options:
                chosen_spawn = random.choice(spawn_options)
                self.current_level_items_world_state[radiology_key_name]["location"] = chosen_spawn["room"]
                self.current_level_items_world_state[radiology_key_name]["container"] = chosen_spawn.get("container")
                self.current_level_items_world_state[radiology_key_name]["is_hidden"] = True # Always hidden initially
                self.logger.info(f"Placed '{radiology_key_name}' in {chosen_spawn.get('container', 'floor')} of {chosen_spawn['room']}.")
            else:
                self.logger.warning(f"'{radiology_key_name}' has no defined spawn_locations.")

        # Medical Director Key Card (Rare random hospital container)
        med_director_key_name = "Medical Director Key Card"
        med_director_key_master_data = self.current_level_items_master_copy.get(med_director_key_name)
        if med_director_key_master_data and med_director_key_master_data.get("level") == level_id and med_director_key_master_data.get("is_rare_random_hospital_spawn"):
            hospital_containers = []
            for room_name, room_data in self.current_level_rooms.items():
                # Simple check if room_name contains "hospital" or is part of a predefined hospital room list
                # For now, assuming all rooms in level 1 are hospital rooms.
                if level_id == 1: # Assuming level 1 is the hospital
                    for furn in room_data.get("furniture", []):
                        if furn.get("is_container") and not furn.get("locked"):
                            hospital_containers.append({"room": room_name, "container_name": furn["name"]})
            if hospital_containers:
                chosen_container_spawn = random.choice(hospital_containers)
                self.current_level_items_world_state[med_director_key_name]["location"] = chosen_container_spawn["room"]
                self.current_level_items_world_state[med_director_key_name]["container"] = chosen_container_spawn["container_name"]
                self.current_level_items_world_state[med_director_key_name]["is_hidden"] = True
                self.logger.info(f"Rare spawn: Placed '{med_director_key_name}' in {chosen_container_spawn['container_name']} of {chosen_container_spawn['room']}.")
            else:
                self.logger.warning(f"Could not place '{med_director_key_name}', no suitable hospital containers found.")
        
        # Filter items for general dynamic placement (not already placed by specific logic or fixed)
        items_for_dynamic_placement = {
            name: data for name, data in self.current_level_items_world_state.items()
            if name not in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION and \
            not self.current_level_items_master_copy.get(name, {}).get("fixed_location") and \
            not self.current_level_items_master_copy.get(name, {}).get("spawn_locations") and \
            not self.current_level_items_master_copy.get(name, {}).get("is_rare_random_hospital_spawn") and \
            data.get("location") is None and \
            (self.current_level_items_master_copy.get(name, {}).get("level") == level_id or \
                self.current_level_items_master_copy.get(name, {}).get("level") is None or \
                str(self.current_level_items_master_copy.get(name, {}).get("level")).lower() == "all")
        }
        
        keys_to_place_dynamically = {n: d for n, d in items_for_dynamic_placement.items() if d.get("is_key")}
        evidence_to_place_dynamically = {n: d for n, d in items_for_dynamic_placement.items() if d.get("is_evidence") and n not in keys_to_place_dynamically}
        other_items_to_place_dynamically_names = set(items_for_dynamic_placement.keys()) - set(keys_to_place_dynamically.keys()) - set(evidence_to_place_dynamically.keys())
        other_items_to_place_dynamically = {name: items_for_dynamic_placement[name] for name in other_items_to_place_dynamically_names}
        
        available_slots = self._get_available_container_slots_for_level()
        self.logger.info(f"Dynamic placement: {len(keys_to_place_dynamically)} keys, {len(evidence_to_place_dynamically)} evidence, {len(other_items_to_place_dynamically)} other. Slots: {len(available_slots)}.")
        
        if keys_to_place_dynamically: self._distribute_items_in_slots(list(keys_to_place_dynamically.keys()), available_slots, "Key")
        if evidence_to_place_dynamically: self._distribute_items_in_slots(list(evidence_to_place_dynamically.keys()), available_slots, "Evidence")
        if other_items_to_place_dynamically:
            items_to_place_as_other = list(other_items_to_place_dynamically.keys())
            if items_to_place_as_other: self._distribute_items_in_slots(items_to_place_as_other, available_slots, "Other Item")
        
        # Confirm fixed item placements (already set by _initialize_level_data logic for fixed items)
        for item_name, item_world_data in self.current_level_items_world_state.items():
            master_data = self.current_level_items_master_copy.get(item_name, {})
            is_explicitly_fixed = (item_name in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION or 
                                master_data.get("fixed_location") or
                                (master_data.get("location") and master_data.get("container")) or
                                (master_data.get("location") and not master_data.get("container") and 
                                    not master_data.get("is_rare_random_hospital_spawn") and 
                                    not master_data.get("spawn_locations")))
            
            if is_explicitly_fixed and (master_data.get("level") == level_id or master_data.get("level") is None or str(master_data.get("level")).lower() == "all"):
                defined_loc = master_data.get("location"); defined_container = master_data.get("container")
                if defined_loc and item_world_data.get("location") != defined_loc:
                    self.logger.warning(f"Fixed item '{item_name}' world loc diff. Correcting."); item_world_data["location"] = defined_loc
                if defined_container and item_world_data.get("container") != defined_container: item_world_data["container"] = defined_container
                elif not defined_container: item_world_data.pop("container", None)
                if item_world_data.get("location"): self.logger.info(f"Confirmed fixed item '{item_name}' at {item_world_data['location']}" + (f" in '{item_world_data['container']}'." if item_world_data.get('container') else "."))
                else: self.logger.warning(f"Fixed item '{item_name}' no location. Master: {defined_loc}")
        
        self.logger.info("--- Dynamic and Fixed Element Placement Complete ---")
        
    def _distribute_items_in_slots(self, item_names_list, available_slots_list, item_category_log="Item"):
        placed_count = 0; random.shuffle(item_names_list)
        container_fill_count = {}; max_items_per_container_level_1 = 1
        for item_name in item_names_list:
            if not available_slots_list: self.logger.warning(f"Ran out of slots for {item_category_log} '{item_name}'."); break
            item_data_world = self.current_level_items_world_state.get(item_name)
            if not item_data_world or item_data_world.get("location"): continue
            slot_found_for_item = False; temp_slots_to_retry = []
            original_slots_count = len(available_slots_list); processed_slots_count = 0
            while available_slots_list and not slot_found_for_item and processed_slots_count < original_slots_count * 2:
                slot = available_slots_list.pop(0); processed_slots_count += 1
                container_id = (slot["room"], slot["container_name"])
                is_level_1 = self.player.get("current_level") == 1
                is_restricted_category_for_level_1 = item_category_log == "Other Item" 
                if is_level_1 and is_restricted_category_for_level_1 and container_fill_count.get(container_id, 0) >= max_items_per_container_level_1:
                    temp_slots_to_retry.append(slot); continue
                item_data_world["location"] = slot["room"]; item_data_world["container"] = slot["container_name"]
                item_data_world["is_hidden"] = True
                container_fill_count[container_id] = container_fill_count.get(container_id, 0) + 1
                slot_found_for_item = True
                self.logger.info(f"Placed {item_category_log} '{item_name}' in '{slot['container_name']}' ({slot['room']}). Fill: {container_fill_count[container_id]}")
                placed_count += 1
            available_slots_list.extend(temp_slots_to_retry)
            if not slot_found_for_item: self.logger.warning(f"Could not find slot for {item_category_log} '{item_name}'.")
        if placed_count < len(item_names_list): self.logger.warning(f"Placed {placed_count}/{len(item_names_list)} {item_category_log}s.")
        return placed_count

    def get_searchable_furniture_in_room(self):
        current_room = self.player.get('location'); room_data = self.get_room_data(current_room)
        if not room_data: return []
        return [furn.get("name") for furn in room_data.get("furniture", [])
                if furn.get("is_container", False) and not furn.get("locked", False) and not furn.get("is_hidden_container", False)]

    def delete_save_game(self, slot_identifier):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath:
            logger.error(f"Could not determine save filepath for slot '{slot_identifier}' for deletion.")
            return {"message": color_text("Error: Could not find save path.", "error"), "success": False}

        if os.path.exists(save_filepath):
            try:
                os.remove(save_filepath)
                logger.info(f"Save file for slot '{slot_identifier}' deleted: {save_filepath}")
                # Also, try to delete the .corrupted backup if it exists
                corrupted_backup_path = save_filepath + ".corrupted"
                if os.path.exists(corrupted_backup_path):
                    os.remove(corrupted_backup_path)
                    logger.info(f"Corrupted backup for slot '{slot_identifier}' also deleted: {corrupted_backup_path}")
                return {"message": color_text(f"Save slot '{slot_identifier}' deleted.", "success"), "success": True}
            except Exception as e:
                logger.error(f"Error deleting save file for slot '{slot_identifier}': {e}", exc_info=True)
                return {"message": color_text(f"Error deleting save: {e}", "error"), "success": False}
        else:
            logger.warning(f"Attempted to delete non-existent save slot '{slot_identifier}'.")
            return {"message": color_text(f"Save slot '{slot_identifier}' not found.", "warning"), "success": False}

    def get_save_slot_info(self, slot_id):
        save_path = os.path.join(self.save_dir, f"savegame_{slot_id}.json")
        if not os.path.exists(save_path): return None
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                content = f.read()
                if not content.strip(): 
                    self.logger.warning(f"Save slot '{slot_id}' empty.")
                    return None
                
                # Try to parse the JSON
                try:
                    loaded = json.loads(content)
                except json.JSONDecodeError as jde:
                    self.logger.error(f"Corrupted save file '{slot_id}': {jde}")
                    # Return partial info for corrupted files
                    return {
                        "location": "Unknown (corrupted save)",
                        "timestamp": "Unknown",
                        "character_class": "Unknown",
                        "turns_left": "?",
                        "score": "?",
                        "corrupted": True
                    }
                
                data = loaded.get("save_info", {})
                return {
                    "location": data.get("location", "?"), 
                    "timestamp": data.get("timestamp", "Unknown"),
                    "character_class": data.get("character_class", ""), 
                    "turns_left": data.get("turns_left", ""),
                    "score": data.get("score", "")
                }
        except Exception as e: 
            self.logger.error(f"Error reading save slot '{slot_id}': {e}")
            return None

    def process_player_input(self, command_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.is_game_over and not self.player.get('qte_active'): # qte_active check is now less relevant here
            return {"message": "The game is over. " + (color_text("You won!", "success") if self.game_won else color_text("You lost.", "error")), 
                    "death": not self.game_won, "turn_taken": False}

        # QTE response is now handled by GameScreen calling _handle_qte_response directly.
        # This method focuses on non-QTE commands.
        
        command_str_original = command_str; command_str = command_str.strip().lower(); words = command_str.split()
        if not words: return {"message": "Please enter a command.", "death": False, "turn_taken": False}
        verb = words[0]; target_str = " ".join(words[1:])
        verb_aliases = {
            "go": "move", "get": "take", "look": "examine", "inspect": "examine", "inv": "inventory", "i": "inventory", 
            "bag": "inventory", "q": "quit", "exit": "quit", "restart": "newgame", "again": "newgame",
            "actions": "list", "commands": "list", "l": "examine", "force": "force", "break": "break",
            self.game_data.ACTION_BREAK: self.game_data.ACTION_BREAK
        }
        verb = verb_aliases.get(verb, verb)
        response = {"message": f"I don't know how to '{verb}'. Type 'list' for actions.", "death": False, "turn_taken": False, 
                    "found_items": None, "new_location": None, "item_taken": None, "item_dropped": None,
                    "item_revealed": False, "qte_triggered": None}

        if verb == "quit": response["message"] = "Use Exit button or close window."; return response
        if verb == "newgame":
            self.start_new_game(self.player.get("character_class", "Journalist"))
            response["message"] = f"{color_text('--- New Game Started ---', 'special')}\n{self.get_room_description()}"
            response["new_location"] = self.player['location']; return response
        if verb == "save": response["message"] = self._command_save(target_str if target_str else "quicksave").get("message", "Save status unknown."); return response
        if verb == "load":
            load_resp = self._command_load(target_str if target_str else "quicksave")
            response["message"] = load_resp.get("message", "Load status unknown.")
            if load_resp.get("success"): response["new_location"] = self.player['location']; response["message"] += f"\n{self.get_room_description()}"
            return response
        if verb == "help" or verb == "list": return self._command_list_actions()
        if verb == "inventory": return self._command_inventory()
        if verb == "map": return self._command_map()

        status_messages, action_prevented = self._handle_status_effects_pre_action()
        if status_messages: response["pre_action_status_message"] = "\n".join(status_messages)
        if action_prevented:
            response["message"] = response.get("pre_action_status_message", "") + f"\n{color_text('Unable to act due to condition.', 'warning')}"
            response["turn_taken"] = True
        else:
            command_methods = {"move": self._command_move, "examine": self._command_examine, "take": self._command_take, 
                               "search": self._command_search, "use": self._command_use, "drop": self._command_drop,
                               "unlock": self._command_unlock, "force": self._command_force, self.game_data.ACTION_BREAK: self._command_break}
            if verb in command_methods:
                command_func = command_methods[verb]
                if verb == "use": action_response = command_func(words[1:])
                elif not target_str and verb not in ["examine"]: action_response = {"message": f"{verb.capitalize()} what?", "turn_taken": False}
                elif verb == "examine" and not target_str: action_response = command_func(self.player['location'])
                else: action_response = command_func(target_str)
                response.update(action_response)
            else: response["turn_taken"] = False
        
        if response.get("pre_action_status_message"):
            response["message"] = response["pre_action_status_message"] + "\n" + response.get("message", "")
            del response["pre_action_status_message"]

        if response.get("death"):
            self.is_game_over = True; self.game_won = False
            logger.info(f"Cmd '{command_str_original}' resulted in death. HP: {self.player.get('hp')}")
            if response.get("turn_taken", True):
                turn_prog_msgs = self._handle_turn_progression_and_final_checks()
                if turn_prog_msgs: response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_prog_msgs).strip()).strip()
            return response

        if not self.is_game_over and response.get("turn_taken"):
            turn_prog_msgs = self._handle_turn_progression_and_final_checks()
            if turn_prog_msgs: response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_prog_msgs).strip()).strip()
            if self.is_game_over and not self.game_won: response["death"] = True
        
        # If a normal command triggers a QTE, set it up here.
        # The UI (GameScreen) will see "qte_triggered" and display the QTEPopup.
        if response.get("qte_triggered") and not self.player.get('qte_active'): # Ensure not already in one
            qte_data = response["qte_triggered"]
            self.trigger_qte(qte_data.get("type"), qte_data.get("duration"), qte_data.get("context", {}))
            logger.info(f"QTE '{self.player['qte_active']}' triggered by command '{command_str_original}'.")
        
        if response.get("level_transition_data"): pass # Handled by GameScreen
        return response

    # ... (Other _command_ methods like _command_move, _command_examine, etc. remain largely the same) ...
    # Ensure _command_force and _command_break are present and functional from previous merges.
    # Make sure any QTEs triggered from these commands provide the full context for QTEPopup.

    def _get_available_container_slots_for_level(self):
        """
        Returns a list of available container slots for item placement in the current level.
        Each slot is a dict with 'room' and 'container_name' keys.
        """
        available_slots = []
        
        for room_name, room_data in self.current_level_rooms.items():
            for furniture in room_data.get("furniture", []):
                # Check if it's a valid container for placement
                if (furniture.get("is_container", False) and 
                    not furniture.get("locked", False) and 
                    not furniture.get("is_hidden_container", False)):
                    
                    # Add this container as an available slot
                    available_slots.append({
                        "room": room_name,
                        "container_name": furniture.get("name")
                    })
        
        # Shuffle to ensure random placement
        random.shuffle(available_slots)
        return available_slots

    def get_gui_map_string(self, width=35, height=7):
        if not hasattr(self, 'player') or not self.player or not hasattr(self, 'current_level_rooms') or not self.current_level_rooms:
            return "Map data not available."
        current_room_name = self.player.get('location'); current_room_data = self.get_room_data(current_room_name)
        if not current_room_name or not current_room_data: return "Player location/room data unknown."
        exits = current_room_data.get('exits', {}); location_line = f"[b]{color_text(current_room_name, 'room')}[/b]"
        def format_direction_cell(symbol_char, primary_key, alt_key, exits_dict):
            dest_room_name = exits_dict.get(primary_key)
            if not dest_room_name and alt_key: dest_room_name = exits_dict.get(alt_key)
            if dest_room_name:
                dest_room_data = self.get_room_data(dest_room_name)
                is_locked = dest_room_data.get('locked', False) if dest_room_data else False
                visited = dest_room_name in self.player.get('visited_rooms', set())
                text_color_name = "exit" if visited else "default" 
                base_symbol = color_text(symbol_char, text_color_name)
                lock_indicator = color_text("(L)", "error") if is_locked else ""
                return f"{base_symbol}{lock_indicator}"
            return " "
        u_cell = format_direction_cell("U", "upstairs", "up", exits); n_cell = format_direction_cell("N", "north", None, exits)
        w_cell = format_direction_cell("W", "west", None, exits); p_cell = color_text("P", "success")
        e_cell = format_direction_cell("E", "east", None, exits); s_cell = format_direction_cell("S", "south", None, exits)
        d_cell = format_direction_cell("D", "downstairs", "down", exits)
        map_lines = [f"{u_cell}", f"{n_cell}", f"{w_cell} - {p_cell} - {e_cell}", f"{s_cell}", f"{d_cell}"]
        final_map_string = location_line + "\n" + "\n".join(map_lines)
        return final_map_string
    
    def _command_force(self, target_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); current_room_name = self.player['location']
        current_room_data = self._get_current_room_data(); response_messages = []; turn_taken = True; death_triggered = False
        qte_triggered_by_action = None; target_lower = target_name_str.lower()
        if not target_name_str: return {"message": "Force what?", "death": False, "turn_taken": False}
        if current_room_name == "MRI Scan Room":
            if target_lower == "morgue door":
                morgue_room_data = self.get_room_data("Morgue"); mri_hazard = None; mri_hazard_id = None
                if self.hazard_engine:
                    for h_id, h_instance in self.hazard_engine.active_hazards.items():
                        if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI: mri_hazard = h_instance; mri_hazard_id = h_id; break
                if morgue_room_data and not morgue_room_data.get("locked", True): response_messages.append("The Morgue door is already open."); turn_taken = False
                elif mri_hazard and mri_hazard_id:
                    response_messages.append(color_text("You brace yourself and heave against the heavy Morgue door...", "default"))
                    if self.hazard_engine:
                        self.player['mri_qte_failures'] = 0 
                        self.hazard_engine._set_hazard_state(mri_hazard_id, "door_force_attempt_reaction", response_messages)
                        # HazardEngine will now trigger QTEs via _mri_qte_projectile_action, which calls GameLogic.trigger_qte
                        # The response from _set_hazard_state might include the initial QTE prompt if defined there.
                        # We need to check if GameLogic's player state now has an active QTE.
                        if self.player.get('qte_active'):
                            qte_triggered_by_action = { # This structure is for GameScreen to pick up
                                "type": self.player['qte_active'],
                                "duration": self.player['qte_duration'],
                                "context": self.player['qte_context']
                            }
                else: response_messages.append("Can't force Morgue door / MRI not responding."); turn_taken = False
            elif target_lower == "stairwell door" or target_lower == "stairwell":
                stairwell_room_data_world = self.current_level_rooms.get("Stairwell")
                if stairwell_room_data_world and not stairwell_room_data_world.get("locked", True): response_messages.append("Stairwell door already open."); turn_taken = False
                elif stairwell_room_data_world:
                    counter_key = f"{current_room_name}_Stairwell_force_attempts"; attempts = self.interaction_counters.get(counter_key, 0) + 1
                    self.interaction_counters[counter_key] = attempts
                    if attempts >= self.game_data.STAIRWELL_DOOR_FORCE_THRESHOLD:
                        stairwell_room_data_world["locked"] = False
                        response_messages.append(color_text("Stairwell door creaks open!", "success")); logger.info(f"Stairwell door forced open.")
                    else:
                        remaining_attempts = self.game_data.STAIRWELL_DOOR_FORCE_THRESHOLD - attempts
                        feedback = f"Door groans. {remaining_attempts} more {'try' if remaining_attempts == 1 else 'tries'}?"
                        response_messages.append(color_text(feedback, "default"))
                else: response_messages.append(f"Can't force '{target_name_str}', definition issue."); turn_taken = False
            else: response_messages.append(f"Can't force '{target_name_str}' here."); turn_taken = False
        elif self.game_data.ACTION_BREAK and hasattr(self, '_command_break'): return self._command_break(target_name_str)
        else: response_messages.append(f"Can't force '{target_name_str}'."); turn_taken = False
        final_message = "\n".join(filter(None, response_messages))
        return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_action}

    def _command_break(self, target_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); current_room_name = self.player['location']
        current_room_data = self._get_current_room_data(); response_messages = []; turn_taken = True; death_triggered = False
        if not target_name_str: return {"message": "Break what?", "death": False, "turn_taken": False}
        target_furniture_dict = self._get_furniture_piece(current_room_data, target_name_str)
        if not target_furniture_dict: return {"message": f"Don't see '{target_name_str}' to break.", "death": False, "turn_taken": False}
        furniture_name = target_furniture_dict.get("name")
        if not target_furniture_dict.get("is_breakable"): response_messages.append(f"The {furniture_name} can't be broken easily.")
        else:
            integrity_key = f"{current_room_name}_{furniture_name}_integrity"
            initial_integrity = target_furniture_dict.get("break_integrity", 1)
            current_integrity = self.interaction_counters.get(integrity_key, initial_integrity)
            if current_integrity <= 0: response_messages.append(f"{furniture_name} already broken."); turn_taken = False
            else:
                response_messages.append(f"Attempting to force {furniture_name}...")
                current_integrity -= 1; self.interaction_counters[integrity_key] = current_integrity
                if current_integrity <= 0:
                    response_messages.append(color_text(target_furniture_dict.get("on_break_success_message", f"{furniture_name} breaks!"), "success"))
                    items_to_spill_defs = target_furniture_dict.get("on_break_spill_items", [])
                    if items_to_spill_defs:
                        spilled_item_names_for_msg = []
                        for spill_entry in items_to_spill_defs:
                            item_name_to_add = spill_entry.get("name"); quantity_str = spill_entry.get("quantity", "1"); num_to_add = 1
                            if item_name_to_add == "Dust Cloud Puff":
                                if self.hazard_engine:
                                    dust_message = color_text("Dust erupts!", "warning")
                                    temp_effect_msgs = self.hazard_engine.apply_temporary_room_effect(room_name=current_room_name, effect_key="visibility", temp_value="patchy_smoke", duration_turns=1, effect_message=dust_message)
                                    response_messages.extend(temp_effect_msgs); logger.info(f"Dust cloud from breaking {furniture_name}.")
                                continue
                            if isinstance(quantity_str, str) and "d" in quantity_str:
                                try: parts = quantity_str.split('d'); num_dice, dice_sides = int(parts[0]), int(parts[1]); num_to_add = sum(random.randint(1, dice_sides) for _ in range(num_dice))
                                except: num_to_add = 1
                            elif isinstance(quantity_str, int): num_to_add = quantity_str
                            for _ in range(num_to_add):
                                if item_name_to_add:
                                    if item_name_to_add not in self.current_level_items_world_state:
                                        master_spill_item_data = self._get_item_data(item_name_to_add)
                                        if master_spill_item_data: self.current_level_items_world_state[item_name_to_add] = copy.deepcopy(master_spill_item_data)
                                        else: self.current_level_items_world_state[item_name_to_add] = {"description": f"Some {item_name_to_add.lower()}.", "takeable": False, "level": self.player['current_level']}
                                    self.current_level_items_world_state[item_name_to_add].update({"location": current_room_name, "container": None, "is_hidden": False})
                                    self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name_to_add)
                                    if item_name_to_add != "Dust Cloud Puff": spilled_item_names_for_msg.append(item_name_to_add.capitalize())
                                    logger.info(f"Item '{item_name_to_add}' spilled from broken {furniture_name}.")
                        if spilled_item_names_for_msg: response_messages.append(f"Contents spill: {', '.join(spilled_item_names_for_msg)}.")
                    hazard_to_trigger_def = target_furniture_dict.get("on_break_trigger_hazard")
                    if hazard_to_trigger_def and isinstance(hazard_to_trigger_def, dict) and random.random() < hazard_to_trigger_def.get("chance", 1.0):
                        if self.hazard_engine:
                            new_haz_id = self.hazard_engine._add_active_hazard(hazard_type=hazard_to_trigger_def.get("type"), location=current_room_name, initial_state_override=hazard_to_trigger_def.get("initial_state"), target_object_override=hazard_to_trigger_def.get("object_name_override"), support_object_override=hazard_to_trigger_def.get("support_object_override"))
                            if new_haz_id: response_messages.append(color_text(f"Breaking {furniture_name} caused a new problem!", "warning"))
                        else: self.logger.warning("Hazard engine not available for break trigger.")
                else: response_messages.append(color_text(target_furniture_dict.get("break_failure_message", f"{furniture_name} damaged but holds."), "warning"))
        if self.hazard_engine:
            hazard_resp = self.hazard_engine.check_action_hazard(self.game_data.ACTION_BREAK, furniture_name, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): response_messages.append(hazard_resp["message"])
                if hazard_resp.get("death"): death_triggered = True
        return {"message": "\n".join(filter(None, response_messages)), "death": death_triggered, "turn_taken": turn_taken}

    def _command_move(self, direction_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); current_room_name = self.player.get('location')
        current_room_data = self.get_room_data(current_room_name)
        if not current_room_data: return {"message": color_text("Error: Current room data missing.", "error"), "death": False, "turn_taken": False}
        exits = current_room_data.get('exits', {}); normalized_direction = direction_str.lower(); destination_room_name = None
        for exit_dir, dest_name in exits.items():
            if normalized_direction == exit_dir.lower() or \
               (normalized_direction == "n" and exit_dir.lower() == "north") or \
               (normalized_direction == "s" and exit_dir.lower() == "south") or \
               (normalized_direction == "e" and exit_dir.lower() == "east") or \
               (normalized_direction == "w" and exit_dir.lower() == "west") or \
               (normalized_direction == "u" and exit_dir.lower() in ["up", "upstairs"]) or \
               (normalized_direction == "d" and exit_dir.lower() in ["down", "downstairs"]):
                destination_room_name = dest_name; break
        if not destination_room_name:
            valid_exits_str = ", ".join(exits.keys())
            return {"message": f"Can't go '{direction_str}'. Valid: {valid_exits_str}", "death": False, "turn_taken": False}
        destination_room_data = self.get_room_data(destination_room_name)
        if not destination_room_data:
            logger.error(f"Data for dest room '{destination_room_name}' not found.")
            return {"message": color_text(f"Error: Path to '{destination_room_name}' leads nowhere.", "error"), "death": False, "turn_taken": False}
        if current_room_name == "Front Porch" and destination_room_name == "Foyer" and destination_room_data.get('locked', False):
            return {"message": color_text("Front door locked. Unlock it first.", "warning"), "death": False, "turn_taken": False}
        unlock_message = ""
        if destination_room_data.get('locked', False):
            required_key_name = destination_room_data.get('unlocks_with')
            if required_key_name and required_key_name in self.player.get('inventory', []):
                self.current_level_rooms[destination_room_name]['locked'] = False
                unlock_message = color_text(f"Unlocked {destination_room_name} with {required_key_name}.", "success")
            else:
                key_needed_msg = f"{destination_room_name} is locked."
                if required_key_name: key_needed_msg += f" Need {required_key_name}."
                return {"message": color_text(key_needed_msg, "warning"), "death": False, "turn_taken": False}
        level_id = self.player.get("current_level", 1); level_req = self.game_data.LEVEL_REQUIREMENTS.get(level_id, {})
        is_level_exit_room = level_req.get("exit_room") == current_room_name; is_attempting_level_exit = False
        if level_req.get("next_level_start_room") and destination_room_name == level_req.get("next_level_start_room"): is_attempting_level_exit = True
        if is_level_exit_room and is_attempting_level_exit:
            required_evidence_for_level = set(level_req.get("evidence_needed", []))
            player_evidence_inventory = {item for item in self.player.get("inventory", []) if self._get_item_data(item) and self._get_item_data(item).get("is_evidence")}
            if not required_evidence_for_level.issubset(player_evidence_inventory):
                missing_evidence_str = ", ".join(required_evidence_for_level - player_evidence_inventory)
                return {"message": color_text(f"Dread stops you. Missing evidence: {missing_evidence_str}.", "warning"), "death": False, "turn_taken": False}
            next_level_id_val = level_req.get("next_level_id")
            if next_level_id_val is not None:
                return {"message": color_text(f"Gathered enough from {level_req.get('name', 'area')}. Proceeding...", "success"), "death": False, "turn_taken": True,
                        "level_transition_data": {"next_level_id": next_level_id_val, "next_level_start_room": destination_room_name, "completed_level_id": level_id}}
            else:
                self.game_won = True; self.is_game_over = True
                return {"message": color_text("Survived the final ordeal.", "success"), "death": False, "turn_taken": True, "new_location": destination_room_name}
        previous_location = self.player['location']; self.player['location'] = destination_room_name
        self.player.setdefault('visited_rooms', set()).add(destination_room_name)
        move_message = f"Moved from {previous_location} to {destination_room_name}."
        full_message = f"{unlock_message}\n{move_message}".strip() + f"\n\n{self.get_room_description(destination_room_name)}"
        hazard_on_entry_messages = []; death_from_entry_hazard = False
        if self.hazard_engine:
            player_weight = self._calculate_player_inventory_weight()
            entry_hazard_result = self.hazard_engine.check_weak_floorboards_on_move(destination_room_name, player_weight)
            if entry_hazard_result and isinstance(entry_hazard_result, dict):
                if entry_hazard_result.get("message"): hazard_on_entry_messages.append(entry_hazard_result["message"])
                if entry_hazard_result.get("death"): death_from_entry_hazard = True
                if entry_hazard_result.get("room_transfer_to"):
                    self.player['location'] = entry_hazard_result["room_transfer_to"]; self.player['visited_rooms'].add(self.player['location'])
                    hazard_on_entry_messages.append(color_text(f"Now in {self.player['location']}!", "warning") + "\n" + self.get_room_description(self.player['location']))
            if not death_from_entry_hazard:
                floor_hazard_msgs_list = []
                self.hazard_engine._check_floor_hazards_on_move(self.player['location'], floor_hazard_msgs_list)
                if floor_hazard_msgs_list: hazard_on_entry_messages.extend(floor_hazard_msgs_list)
                if self.player['hp'] <= 0 and not death_from_entry_hazard: death_from_entry_hazard = True
        if hazard_on_entry_messages: full_message += "\n" + "\n".join(hazard_on_entry_messages)
        return {"message": full_message, "death": death_from_entry_hazard, "turn_taken": True, "new_location": self.player['location']}

    def _command_examine(self, target_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); target_name_lower = target_name_str.lower()
        current_room_name = self.player['location']; current_room_data = self._get_current_room_data()
        inventory = self.player.get('inventory', []); action_message_parts = []; death_triggered = False
        turn_taken_by_examine = False; item_revealed_or_transformed = False
        item_in_inventory = next((item for item in inventory if item.lower() == target_name_lower), None)
        if item_in_inventory:
            item_master_data = self._get_item_data(item_in_inventory)
            if item_master_data:
                description = item_master_data.get('examine_details', item_master_data.get('description', f"It's a {item_in_inventory}."))
                action_message_parts.append(description)
                transform_target = item_master_data.get('transforms_into_on_examine')
                if transform_target and self._transform_item_in_inventory(item_in_inventory, transform_target):
                    action_message_parts.append(color_text(f"Closer inspection: it's a {transform_target}!", "special"))
                    item_revealed_or_transformed = True; turn_taken_by_examine = True
                    new_item_info = self._get_item_data(transform_target)
                    if new_item_info and new_item_info.get("is_evidence"): self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
            else: action_message_parts.append(f"Look at {item_in_inventory}. Nothing new.")
            return {"message": "\n".join(action_message_parts), "death": death_triggered, "turn_taken": turn_taken_by_examine, "item_revealed": item_revealed_or_transformed}
        item_to_examine_in_room = None; item_data_in_room = None
        for item_name_key, item_data_val in self.current_level_items_world_state.items():
            if item_name_key.lower() == target_name_lower and item_data_val.get('location') == current_room_name:
                is_visible = not item_data_val.get('container') and not item_data_val.get('is_hidden')
                is_revealed = item_name_key in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible or is_revealed: item_to_examine_in_room = item_name_key; item_data_in_room = item_data_val; break
        if item_to_examine_in_room:
            master_item_data = self._get_item_data(item_to_examine_in_room)
            description = master_item_data.get('examine_details', master_item_data.get('description', f"It's a {item_to_examine_in_room}."))
            action_message_parts.append(description)
            if self.hazard_engine:
                hazard_result = self.hazard_engine.check_action_hazard('examine', item_to_examine_in_room, current_room_name)
                if hazard_result and isinstance(hazard_result, dict):
                    if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                    if hazard_result.get("death"): death_triggered = True
                    if hazard_result.get("message") or death_triggered: turn_taken_by_examine = True
        else:
            feature_to_examine = None
            if current_room_data.get('furniture'):
                for furn_dict in current_room_data['furniture']:
                    if furn_dict.get('name', '').lower() == target_name_lower: feature_to_examine = furn_dict['name']; break
            if not feature_to_examine and current_room_data.get('objects'):
                for obj_name in current_room_data['objects']:
                    if obj_name.lower() == target_name_lower: feature_to_examine = obj_name; break
            if feature_to_examine:
                examine_detail_key = feature_to_examine
                details = current_room_data.get('examine_details', {}).get(examine_detail_key)
                action_message_parts.append(details or f"Nothing special about {feature_to_examine}.")
                if feature_to_examine.lower() == "fireplace" and current_room_name == "Living Room":
                    room_flags = self.current_level_rooms[current_room_name].get("interaction_flags", {})
                    loose_brick_taken = room_flags.get("loose_brick_taken", False)
                    cavity_revealed = room_flags.get("fireplace_cavity_revealed", False)
                    loose_brick_name = self.game_data.ITEM_LOOSE_BRICK; brick_world_data = self.current_level_items_world_state.get(loose_brick_name)
                    if not loose_brick_taken and brick_world_data and brick_world_data.get('location') == current_room_name:
                        if brick_world_data.get('is_hidden') or loose_brick_name not in self.revealed_items_in_rooms.get(current_room_name, set()):
                            brick_world_data['is_hidden'] = False; self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(loose_brick_name)
                            action_message_parts.append(color_text("One brick looks loose.", "special")); item_revealed_or_transformed = True
                        else: action_message_parts.append(color_text("Loose brick is still there.", "default"))
                    elif loose_brick_taken and not cavity_revealed:
                        action_message_parts.append(color_text("Where brick was, see dark cavity.", "special"))
                        for furn_idx, furn_dict_iter in enumerate(self.current_level_rooms[current_room_name].get("furniture", [])):
                            if furn_dict_iter.get("name") == "fireplace cavity" and furn_dict_iter.get("is_hidden_container"):
                                self.current_level_rooms[current_room_name]["furniture"][furn_idx]["is_hidden_container"] = False; break
                        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add("fireplace cavity")
                        if "interaction_flags" in self.current_level_rooms[current_room_name]: self.current_level_rooms[current_room_name]["interaction_flags"]["fireplace_cavity_revealed"] = True
                        item_revealed_or_transformed = True
                    elif loose_brick_taken and cavity_revealed: action_message_parts.append(color_text("Cavity still there. Search it?", "default"))
                if self.hazard_engine:
                    hazard_result = self.hazard_engine.check_action_hazard('examine', feature_to_examine, current_room_name)
                    if hazard_result and isinstance(hazard_result, dict):
                        if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                        if hazard_result.get("death"): death_triggered = True
                        if hazard_result.get("message") or death_triggered: turn_taken_by_examine = True
            elif target_name_lower == current_room_name.lower() or target_name_str == "": action_message_parts.append(self.get_room_description(current_room_name))
            else: action_message_parts.append(f"Don't see '{target_name_str}' to examine.")
        return {"message": "\n".join(filter(None, action_message_parts)), "death": death_triggered, "turn_taken": turn_taken_by_examine, "item_revealed": item_revealed_or_transformed}
    def _command_take(self, item_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        item_name_lower = item_name_str.lower()
        current_room_name = self.player['location']
        action_message_parts = []
        death_triggered = False
        turn_taken = False
        item_taken_actual_name = None
        item_to_take_cased = None
        item_world_data = None

        # Find the item in the current room (not in a container or revealed from one)
        for name_key, data_val in self.current_level_items_world_state.items():
            if name_key.lower() == item_name_lower and data_val.get('location') == current_room_name:
                is_visible = not data_val.get('container') and not data_val.get('is_hidden')
                is_revealed = name_key in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible or is_revealed:
                    item_to_take_cased = name_key
                    item_world_data = data_val
                    break
        
        if item_to_take_cased and item_world_data:
            master_item_data = self._get_item_data(item_to_take_cased)
            if master_item_data.get('takeable', True):
                if item_to_take_cased in self.player['inventory']:
                    action_message_parts.append(f"Already have {item_to_take_cased}.")
                else:
                    self.player['inventory'].append(item_to_take_cased)
                    item_taken_actual_name = item_to_take_cased
                    
                    # Update item's world state
                    item_world_data['location'] = 'inventory'
                    item_world_data.pop('container', None)
                    item_world_data['is_hidden'] = False # No longer hidden once in inventory
                    
                    # Remove from revealed items if it was there
                    if current_room_name in self.revealed_items_in_rooms:
                        self.revealed_items_in_rooms[current_room_name].discard(item_to_take_cased)
                        
                    action_message_parts.append(f"Took {item_to_take_cased}.")
                    turn_taken = True

                    # --- Coroner's Office Key MRI Interaction ---
                    if item_to_take_cased == self.game_data.ITEM_CORONERS_OFFICE_KEY and \
                    current_room_name == self.game_data.ROOM_MRI_SCAN_ROOM:
                        action_message_parts.append(color_text("As you grasp the key, a sudden, intense hum emanates from the MRI machine. A powerful magnetic force flares to life!", "hazard"))
                        if self.hazard_engine:
                            mri_hazard_id = None
                            for h_id, h_instance in self.hazard_engine.active_hazards.items():
                                if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI:
                                    mri_hazard_id = h_id
                                    break
                            if mri_hazard_id:
                                # This state change will handle removing key from inventory via on_state_entry_special_action
                                self.hazard_engine._set_hazard_state(mri_hazard_id, "coroners_key_qte_initiate_pull", action_message_parts)
                                # Check if the QTE was triggered by the state change (GameScreen will handle UI)
                                if self.player.get('qte_active'):
                                    # This response structure signals GameScreen to show QTE
                                    return {"message": "\n".join(filter(None, action_message_parts)), 
                                            "death": False, "turn_taken": True, "item_taken": item_taken_actual_name,
                                            "qte_triggered": {
                                                "type": self.player['qte_active'],
                                                "duration": self.player['qte_duration'],
                                                "context": self.player['qte_context']
                                            }}
                            else:
                                action_message_parts.append(color_text("The MRI machine remains inert, surprisingly.", "default"))
                        else:
                            action_message_parts.append(color_text("Hazard system offline, MRI interaction skipped.", "error"))
                    
                    # --- Morgue Key Card MRI Interaction ---
                    elif item_to_take_cased == "Morgue Key Card" and \
                        current_room_name == self.game_data.ROOM_MRI_SCAN_ROOM and \
                        master_item_data.get("triggers_mri_on_pickup_if_in_mri_room"):
                        action_message_parts.append(color_text("Finding the Morgue Key Card here feels ominous. The nearby MRI machine seems to react to its presence, a low thrumming sound starting up...", "warning"))
                        if self.hazard_engine:
                            mri_hazard_id = None
                            for h_id, h_instance in self.hazard_engine.active_hazards.items():
                                if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI:
                                    mri_hazard_id = h_id
                                    break
                            if mri_hazard_id:
                                # Check if Coroner's Key is also present to trigger its QTE sequence
                                coroner_key_present_in_room_or_cart = False
                                coroner_key_world_data = self.current_level_items_world_state.get(self.game_data.ITEM_CORONERS_OFFICE_KEY)
                                if coroner_key_world_data and coroner_key_world_data.get('location') == self.game_data.ROOM_MRI_SCAN_ROOM:
                                    coroner_key_present_in_room_or_cart = True

                                if coroner_key_present_in_room_or_cart:
                                    action_message_parts.append(color_text("The MRI's reaction intensifies, focusing on something else metallic in the room!", "hazard"))
                                    # Logic to handle if Coroner's key is in cart vs already pulled
                                    if coroner_key_world_data.get('container') == "equipment cart": # Still in cart
                                        # Remove from cart, make it "magnetized"
                                        coroner_key_world_data['location'] = self.game_data.ROOM_MRI_SCAN_ROOM
                                        coroner_key_world_data['container'] = None
                                        coroner_key_world_data['is_hidden'] = True # Becomes part of the QTE event
                                        self.hazard_engine.active_hazards[mri_hazard_id].magnetized_item = self.game_data.ITEM_CORONERS_OFFICE_KEY
                                        action_message_parts.append(color_text(f"The {self.game_data.ITEM_CORONERS_OFFICE_KEY} is ripped from the equipment cart!", "warning"))

                                    self.hazard_engine._set_hazard_state(mri_hazard_id, "coroners_key_qte_initiate_pull", action_message_parts) # Start Coroner's Key QTE
                                else:
                                    self.hazard_engine._set_hazard_state(mri_hazard_id, "power_surge", action_message_parts) # Generic MRI activation
                                # Check for QTE trigger
                                if self.player.get('qte_active'):
                                    return {"message": "\n".join(filter(None, action_message_parts)), 
                                            "death": False, "turn_taken": True, "item_taken": item_taken_actual_name,
                                            "qte_triggered": {
                                                "type": self.player['qte_active'],
                                                "duration": self.player['qte_duration'],
                                                "context": self.player['qte_context']
                                            }}
                            else:
                                action_message_parts.append(color_text("The MRI machine remains inert.", "default"))

                    # Handle evidence items
                    if master_item_data.get("is_evidence"):
                        if self.achievements_system and not self.achievements_system.has_evidence(item_to_take_cased):
                            self.achievements_system.record_evidence(item_to_take_cased, master_item_data.get('name', item_to_take_cased), master_item_data.get('description', ''))
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
                        self.player.setdefault("found_evidence_count", 0); self.player["found_evidence_count"] += 1
                        self.player.setdefault("evidence_found_this_level", []).append(item_to_take_cased)
                        narrative_flag = master_item_data.get("narrative_flag_on_collect")
                        narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag: 
                            self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet: 
                            self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)
                    
                    # Special case for loose brick
                    if item_to_take_cased.lower() == self.game_data.ITEM_LOOSE_BRICK.lower() and current_room_name == "Living Room":
                        if "interaction_flags" in self.current_level_rooms[current_room_name]: 
                            self.current_level_rooms[current_room_name]["interaction_flags"]["loose_brick_taken"] = True
                        basement_key_name = self.game_data.ITEM_BASEMENT_KEY
                        key_world_data = self.current_level_items_world_state.get(basement_key_name)
                        if key_world_data and key_world_data.get('location') == "Living Room" and key_world_data.get('is_hidden'):
                            key_world_data['is_hidden'] = False
                            self.revealed_items_in_rooms.setdefault("Living Room", set()).add(basement_key_name)
                            action_message_parts.append(color_text("Pulled brick free, Basement Key clatters out!", "special"))
                            logger.info("Basement Key revealed.")
                    
                    # Check for hazard interactions
                    if self.hazard_engine:
                        hazard_result = self.hazard_engine.check_action_hazard('take', item_to_take_cased, current_room_name)
                        if hazard_result and isinstance(hazard_result, dict):
                            if hazard_result.get("message"): 
                                action_message_parts.append(hazard_result["message"])
                            if hazard_result.get("death"): 
                                death_triggered = True
            else:
                action_message_parts.append(f"Can't take {item_to_take_cased}.")
        else:
            action_message_parts.append(f"Don't see '{item_name_str}' to take.")

        return {"message": "\n".join(filter(None, action_message_parts)), 
                "death": death_triggered, 
                "turn_taken": turn_taken, 
                "item_taken": item_taken_actual_name if not death_triggered and turn_taken else None}

    def _command_search(self, furniture_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); action_message_parts = []; death_triggered = False
        turn_taken = False; found_items_for_ui = []; current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        if not current_room_data: return {"message": color_text("Error: Room data missing.", "error"), "death": False, "turn_taken": False, "found_items": None}
        target_furniture_dict = self._get_furniture_piece(current_room_data, furniture_name_str)
        canonical_furniture_name = target_furniture_dict.get("name") if target_furniture_dict else None
        if not target_furniture_dict: action_message_parts.append(f"Don't see '{furniture_name_str}' to search.")
        elif not target_furniture_dict.get("is_container"): action_message_parts.append(f"Can't search {canonical_furniture_name}.")
        elif target_furniture_dict.get("is_hidden_container"): action_message_parts.append(f"Don't see searchable '{furniture_name_str}' yet.")
        elif target_furniture_dict.get("locked"):
            lock_msg = f"{canonical_furniture_name} is locked."
            required_key = target_furniture_dict.get("unlocks_with_item")
            if not required_key: required_key = next((k_name for k_name, k_data in self.current_level_items_master_copy.items() if k_data.get("is_key") and k_data.get("unlocks", "").lower() == (canonical_furniture_name.lower() if canonical_furniture_name else "")), None)
            if required_key: lock_msg += f" Need {required_key}."
            action_message_parts.append(lock_msg)
        else:
            turn_taken = True; action_message_parts.append(f"Searching {canonical_furniture_name}...")
            items_newly_found_names = []
            for item_name, item_world_data in self.current_level_items_world_state.items():
                if item_world_data.get('location') == current_room_name and \
                   (item_world_data.get('container') or '').lower() == (canonical_furniture_name.lower() if canonical_furniture_name else "") and \
                   item_name not in self.player['inventory'] and item_world_data.get('is_hidden', False):
                    items_newly_found_names.append(item_name); found_items_for_ui.append(item_name)
                    item_world_data['is_hidden'] = False; self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name)
                    logger.info(f"Item '{item_name}' revealed in {canonical_furniture_name} in {current_room_name}.")
                    master_item_data = self._get_item_data(item_name)
                    if master_item_data and master_item_data.get("is_evidence"):
                        if self.achievements_system and not self.achievements_system.has_evidence(item_name):
                            self.achievements_system.record_evidence(item_name, master_item_data.get('name', item_name), master_item_data.get('description', ''))
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
                        self.player.setdefault("evidence_found_this_level", []).append(item_name)
                        narrative_flag = master_item_data.get("narrative_flag_on_collect"); narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag: self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet: self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)
            if items_newly_found_names: action_message_parts.append(f"Found: {', '.join(item.capitalize() for item in items_newly_found_names)}.")
            else: action_message_parts.append("Found nothing new.")
            if self.hazard_engine:
                hazard_result = self.hazard_engine.check_action_hazard('search', canonical_furniture_name, current_room_name)
                if hazard_result and isinstance(hazard_result, dict):
                    if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                    if hazard_result.get("death"): death_triggered = True
        return {"message": "\n".join(filter(None, action_message_parts)), "death": death_triggered, "turn_taken": turn_taken, "found_items": found_items_for_ui if not death_triggered and turn_taken and found_items_for_ui else None}
    
    def _command_use(self, words):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); message_parts = []; death_triggered = False
        turn_taken = True; qte_triggered_by_use = None; item_to_use_str = None; target_object_str = None
        if not words: return {"message": "Use what?", "death": False, "turn_taken": False}
        if "on" in words:
            try: on_index = words.index("on"); item_to_use_str = " ".join(words[:on_index]); target_object_str = " ".join(words[on_index+1:])
            except ValueError: item_to_use_str = " ".join(words)
        else: item_to_use_str = " ".join(words)
        item_in_inventory_cased = next((inv_item for inv_item in self.player['inventory'] if inv_item.lower() == item_to_use_str.lower()), None)
        if not item_in_inventory_cased: return {"message": f"Don't have '{item_to_use_str}'.", "death": False, "turn_taken": False}
        item_master_data = self._get_item_data(item_in_inventory_cased)
        if not item_master_data: logger.error(f"Item '{item_in_inventory_cased}' in inv, no master data."); return {"message": "Error with item data.", "death": False, "turn_taken": False}
        item_type = item_master_data.get("type"); current_room_name = self.player['location']
        current_room_data = self._get_current_room_data(); interaction_processed = False
        hazard_specific_interaction_occurred = False; targeted_hazard_instance = None; targeted_hazard_id = None
        
        # Standard furniture interactions
        if target_object_str and current_room_data:
            targeted_furniture_dict = self._get_furniture_piece(current_room_data, target_object_str)
            if targeted_furniture_dict:
                furniture_name_cased = targeted_furniture_dict.get("name"); interaction_rule = targeted_furniture_dict.get("use_item_interaction")
                if interaction_rule and isinstance(interaction_rule, dict):
                    required_item_names = interaction_rule.get("item_names_required", [])
                    if isinstance(required_item_names, str): required_item_names = [required_item_names]
                    if item_in_inventory_cased in required_item_names:
                        interaction_processed = True; action_effect = interaction_rule.get("action_effect")
                        success_msg_template = interaction_rule.get("message_success", "Using {item_name} on {target_name} works.")
                        message_parts.append(color_text(success_msg_template.format(item_name=item_in_inventory_cased, target_name=furniture_name_cased), "success"))
                        if action_effect == "activate_mri_hazard":
                            if self.hazard_engine:
                                mri_hazard_instance_id = None
                                for h_id, h_instance in self.hazard_engine.active_hazards.items():
                                    if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI: mri_hazard_instance_id = h_id; break
                                if mri_hazard_instance_id:
                                    self.hazard_engine._set_hazard_state(mri_hazard_instance_id, "power_surge", message_parts)
                                    logger.info(f"MRI activated by {item_in_inventory_cased} on {furniture_name_cased}.")
                                    if self.is_game_over: death_triggered = True
                                else: message_parts.append(color_text("Error: MRI not found.", "error"))
                            else: message_parts.append(color_text("Error: Hazard system unavailable.", "error"))
                        if item_master_data.get("consumable_on_use_for_target", {}).get(furniture_name_cased.lower(), item_master_data.get("consumable_on_use", False)):
                            self.player['inventory'].remove(item_in_inventory_cased); message_parts.append(f"{item_in_inventory_cased} used up.")
                    else:
                        interaction_processed = True; fail_msg_template = interaction_rule.get("message_fail_item", "That item doesn't work with {target_name}.")
                        message_parts.append(color_text(fail_msg_template.format(target_name=furniture_name_cased), "warning")); turn_taken = True
        
        # NEW: Special MRI Control Room key card interaction
        if not interaction_processed and target_object_str and \
        (item_in_inventory_cased == "Radiology Key Card" or item_master_data.get("is_master_key") or item_in_inventory_cased == "Medical Director Key Card") and \
        target_object_str.lower() == "control desk" and \
        current_room_name == self.game_data.ROOM_MRI_CONTROL_ROOM:
            
            interaction_processed = True
            targeted_furniture_dict = self._get_furniture_piece(current_room_data, target_object_str)
            
            if targeted_furniture_dict:
                interaction_rule = targeted_furniture_dict.get("use_item_interaction")
                if interaction_rule and interaction_rule.get("action_effect") == "activate_mri_hazard":
                    if item_in_inventory_cased in interaction_rule.get("item_names_required", []) or item_master_data.get("is_master_key") or item_master_data.get("activates_mri_via_control_panel"):
                        message_parts.append(color_text(interaction_rule.get("message_success", "MRI activated!").format(item_name=item_in_inventory_cased, target_name=target_object_str), "success"))
                        if self.hazard_engine:
                            mri_hazard_id = None
                            for h_id, h_instance in self.hazard_engine.active_hazards.items():
                                if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI:
                                    mri_hazard_id = h_id
                                    break
                            if mri_hazard_id:
                                # Check if Coroner's Key is in MRI Scan Room to trigger its QTE sequence
                                coroner_key_world_data = self.current_level_items_world_state.get(self.game_data.ITEM_CORONERS_OFFICE_KEY)
                                if coroner_key_world_data and coroner_key_world_data.get('location') == self.game_data.ROOM_MRI_SCAN_ROOM:
                                    message_parts.append(color_text("The MRI's activation seems to have a violent reaction with something metallic in the scan room!", "hazard"))
                                    # Logic to handle if Coroner's key is in cart vs already pulled
                                    if coroner_key_world_data.get('container') == "equipment cart": # Still in cart
                                        coroner_key_world_data['location'] = self.game_data.ROOM_MRI_SCAN_ROOM
                                        coroner_key_world_data['container'] = None
                                        coroner_key_world_data['is_hidden'] = True 
                                        self.hazard_engine.active_hazards[mri_hazard_id]["magnetized_item"] = self.game_data.ITEM_CORONERS_OFFICE_KEY
                                        message_parts.append(color_text(f"The {self.game_data.ITEM_CORONERS_OFFICE_KEY} is ripped from the equipment cart by the sudden magnetic force!", "warning"))
                                    
                                    self.hazard_engine._set_hazard_state(mri_hazard_id, "coroners_key_qte_initiate_pull", message_parts)
                                else:
                                    self.hazard_engine._set_hazard_state(mri_hazard_id, "power_surge", message_parts)
                                
                                if self.player.get('qte_active'):
                                    qte_triggered_by_use = {
                                        "type": self.player['qte_active'],
                                        "duration": self.player['qte_duration'],
                                        "context": self.player['qte_context']
                                    }
                                if self.is_game_over: death_triggered = True
                            else:
                                message_parts.append(color_text("Error: MRI hazard not found in scan room.", "error"))
                        else:
                            message_parts.append(color_text("Error: Hazard system unavailable.", "error"))
                    else:
                        message_parts.append(color_text(interaction_rule.get("message_fail_item", "That key doesn't work here."), "warning"))
                else:
                    message_parts.append(f"Using {item_in_inventory_cased} on {target_object_str} has no special effect here.")
            else:
                message_parts.append(f"You don't see a {target_object_str} here.")
        
        # Hazard-specific interactions
        if not interaction_processed and target_object_str and self.hazard_engine:
            for h_id, h_instance in self.hazard_engine.active_hazards.items():
                if h_instance['location'] == current_room_name and (h_instance.get('object_name', '').lower() == target_object_str.lower() or h_instance.get('support_object', '').lower() == target_object_str.lower() or h_instance.get('name', '').lower() == target_object_str.lower()):
                    targeted_hazard_instance = h_instance; targeted_hazard_id = h_id; break
            if targeted_hazard_instance and item_type:
                hazard_interaction_rules = targeted_hazard_instance['data'].get('player_interaction', {}).get('use', [])
                if not isinstance(hazard_interaction_rules, list): hazard_interaction_rules = [hazard_interaction_rules]
                for rule in hazard_interaction_rules:
                    if isinstance(rule, dict) and rule.get('item_used_type') == item_type:
                        if random.random() < rule.get('chance_to_trigger', 1.0):
                            interaction_processed = True; hazard_specific_interaction_occurred = True
                            interaction_message = rule.get('message', f"Using {item_in_inventory_cased} on {targeted_hazard_instance['object_name']} has an effect.")
                            message_parts.append(color_text(interaction_message.format(object_name=targeted_hazard_instance['object_name']), "special"))
                            new_hazard_state = rule.get('target_state')
                            if new_hazard_state is not None: self.hazard_engine._set_hazard_state(targeted_hazard_id, new_hazard_state, message_parts)
                            if self.is_game_over: death_triggered = True; break
                            if rule.get("qte_type_to_trigger") and not death_triggered:
                                qte_context = rule.get("qte_context", {})
                                qte_context.update({"qte_source_hazard_id": targeted_hazard_id, "qte_source_hazard_state": targeted_hazard_instance['state']})
                                # Ensure QTE context for UI is populated
                                qte_context.setdefault("ui_prompt_message", f"Quick! {rule['qte_type_to_trigger'].replace('_',' ').title()}!")
                                qte_context.setdefault("expected_input_word", rule.get("qte_expected_response", "dodge")) # Default expected
                                qte_context.setdefault("input_type", rule.get("qte_input_method", "word")) # Default method
                                qte_triggered_by_use = {"type": rule["qte_type_to_trigger"], "duration": rule.get("qte_duration", self.game_data.QTE_DEFAULT_DURATION), "context": qte_context}
                                message_parts.append(color_text(qte_context.get("initial_qte_message", "Quick! React!"), "hazard")) # This message might be redundant if ui_prompt_message is used by popup
                            if item_master_data.get("consumable_on_use_for_target", {}).get(target_object_str.lower(), item_master_data.get("consumable_on_use", False)):
                                self.player['inventory'].remove(item_in_inventory_cased); message_parts.append(f"{item_in_inventory_cased} used up.")
                            break
                if death_triggered or hazard_specific_interaction_occurred:
                    final_message = "\n".join(filter(None, message_parts))
                    return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_use}
        
        # Special case: Bludworth's House Key on front door
        if not interaction_processed and target_object_str and item_in_inventory_cased == "Bludworth's House Key" and target_object_str.lower() == "front door" and current_room_name == "Front Porch":
            front_door_object_exists = any(obj.lower() == "front door" for obj in self._get_current_room_data().get("objects", []))
            if not front_door_object_exists: message_parts.append("No front door here."); turn_taken = False
            else:
                interaction_processed = True; foyer_data_world = self.current_level_rooms.get("Foyer")
                if foyer_data_world and foyer_data_world.get("locked"):
                    foyer_data_world["locked"] = False; msg_key_use = item_master_data.get("use_result", {}).get("front door", color_text("Front door unlocked.", "success"))
                    message_parts.append(msg_key_use); logger.info("Front door unlocked by 'use' command.")
                elif foyer_data_world and not foyer_data_world.get("locked"): message_parts.append("Front door already unlocked."); turn_taken = False
                else: message_parts.append(color_text("Error with Foyer data.", "error")); turn_taken = False
        
        # Generic item-target interactions
        if not interaction_processed:
            if target_object_str:
                allowed_targets_for_item_def = item_master_data.get("use_on", []); actual_target_cased = None
                if isinstance(allowed_targets_for_item_def, list): actual_target_cased = next((dt for dt in allowed_targets_for_item_def if dt.lower() == target_object_str.lower()), None)
                if actual_target_cased:
                    examinable_room_targets = self.get_examinable_targets_in_room()
                    target_is_present_and_interactable = any(ert.lower() == actual_target_cased.lower() for ert in examinable_room_targets)
                    if target_is_present_and_interactable:
                        use_results_dict = item_master_data.get("use_result", {})
                        result_msg_for_target = use_results_dict.get(actual_target_cased, use_results_dict.get(actual_target_cased.lower(), f"Using {item_in_inventory_cased} on {actual_target_cased} does nothing special."))
                        message_parts.append(result_msg_for_target)
                        if item_in_inventory_cased == self.game_data.ITEM_TOOLBELT and actual_target_cased == "fireplace cavity": self.interaction_counters["fireplace_reinforced"] = True; logger.info("Fireplace reinforced.")
                        consumable_rules = item_master_data.get("consumable_on_use_for_target", {})
                        if consumable_rules.get(actual_target_cased.lower(), item_master_data.get("consumable_on_use", False)):
                            self.player['inventory'].remove(item_in_inventory_cased); message_parts.append(f"{item_in_inventory_cased} used up."); logger.info(f"'{item_in_inventory_cased}' consumed on '{actual_target_cased}'.")
                    else: message_parts.append(f"Don't see '{target_object_str}' to use {item_in_inventory_cased} on."); turn_taken = False
                else: message_parts.append(f"Can't use {item_in_inventory_cased} on '{target_object_str}'."); turn_taken = False
            elif not target_object_str:
                general_use_effect_msg = item_master_data.get("general_use_effect_message")
                if general_use_effect_msg:
                    message_parts.append(general_use_effect_msg)
                    if item_master_data.get("heal_amount"):
                        heal_val = item_master_data["heal_amount"]; old_hp = self.player['hp']
                        self.player['hp'] = min(self.player['max_hp'], old_hp + heal_val)
                        message_parts.append(f" Healed {self.player['hp'] - old_hp} HP."); logger.info(f"Player used {item_in_inventory_cased}, healed to {self.player['hp']}.")
                    if item_master_data.get("consumable_on_use"):
                        self.player['inventory'].remove(item_in_inventory_cased); message_parts.append(f"{item_in_inventory_cased} used up."); logger.info(f"'{item_in_inventory_cased}' consumed (general use).")
                else: message_parts.append(f"Fiddle with {item_in_inventory_cased}, nothing specific. Use 'on' something?"); turn_taken = False
        
        # Final hazard check
        if self.hazard_engine and not death_triggered and target_object_str and not hazard_specific_interaction_occurred:
            final_target_for_hazard_check = target_object_str
            if targeted_hazard_instance: final_target_for_hazard_check = targeted_hazard_instance.get('object_name', target_object_str)
            elif 'actual_target_cased' in locals() and actual_target_cased: final_target_for_hazard_check = actual_target_cased
            hazard_resp = self.hazard_engine.check_action_hazard('use', final_target_for_hazard_check, current_room_name, item_used=item_in_inventory_cased)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): message_parts.append(hazard_resp["message"])
                if hazard_resp.get("death"): death_triggered = True
        
        # Create final response
        final_message = "\n".join(filter(None, message_parts))
        if not final_message and not death_triggered and not qte_triggered_by_use:
            if turn_taken: final_message = "Used item, nothing remarkable."
            elif not turn_taken and not interaction_processed: final_message = f"Can't use {item_in_inventory_cased} like that."
        
        return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_use}

    def _command_drop(self, item_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name_str: return {"message": "Drop what?", "turn_taken": False}
        item_name_lower = item_name_str.lower()
        item_to_drop_cased = next((item for item in self.player['inventory'] if item.lower() == item_name_lower), None)
        if not item_to_drop_cased: return {"message": f"Don't have '{item_name_str}' to drop.", "turn_taken": False}
        current_room_name = self.player['location']; self.player['inventory'].remove(item_to_drop_cased)
        item_world_data = self.current_level_items_world_state.get(item_to_drop_cased)
        if item_world_data:
            item_world_data['location'] = current_room_name; item_world_data['container'] = None; item_world_data['is_hidden'] = False 
        else: 
            logger.error(f"Item '{item_to_drop_cased}' dropped, no world state found.")
            master_data_for_dropped = self._get_item_data(item_to_drop_cased)
            if master_data_for_dropped:
                self.current_level_items_world_state[item_to_drop_cased] = copy.deepcopy(master_data_for_dropped)
                self.current_level_items_world_state[item_to_drop_cased].update({"location": current_room_name, "container": None, "is_hidden": False})
            else: self.current_level_items_world_state[item_to_drop_cased] = {"location": current_room_name, "container": None, "is_hidden": False, "description": "Dropped item.", "takeable": True}
        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_to_drop_cased)
        logger.info(f"Player dropped '{item_to_drop_cased}' in '{current_room_name}'.")
        return {"message": f"Dropped {item_to_drop_cased}.", "turn_taken": True, "item_dropped": item_to_drop_cased}
    
    def _command_unlock(self, target_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); message = ""; death_triggered = False
        turn_taken = True; unlocked_something = False; target_name_lower = target_name_str.lower()
        current_room_name = self.player['location']; current_room_data_world = self.current_level_rooms.get(current_room_name)
        inventory = self.player.get('inventory', [])
        
        if not current_room_data_world: return {"message": color_text("Error: Room data missing.", "error"), "death": False, "turn_taken": False}
        
        # Get available keys and check for master key
        available_keys_in_inv_data = {item_name: self._get_item_data(item_name) for item_name in inventory 
                                    if self._get_item_data(item_name) and self._get_item_data(item_name).get("is_key")}
        available_keys_in_inv = set(available_keys_in_inv_data.keys())
        has_master_key = any(data.get("is_master_key") for data in available_keys_in_inv_data.values() if data)
        
        if not available_keys_in_inv: return {"message": "No keys.", "death": False, "turn_taken": False}
        
        # Special case: Front door on Front Porch
        if target_name_lower == "front door" and current_room_name == "Front Porch":
            foyer_room_data_world = self.current_level_rooms.get("Foyer")
            if "Bludworth's House Key" in available_keys_in_inv:
                if foyer_room_data_world and foyer_room_data_world.get("locked"):
                    foyer_room_data_world["locked"] = False; message = color_text("Used Bludworth's House Key, front door unlocked.", "success")
                    unlocked_something = True; logger.info("Front door unlocked.")
                elif foyer_room_data_world and not foyer_room_data_world.get("locked"): message = "Front door already unlocked."; turn_taken = False
                else: message = color_text("Error: Foyer data not found.", "error"); turn_taken = False
            else: message = "Need specific key for front door."; turn_taken = False
            return {"message": message, "death": death_triggered, "turn_taken": turn_taken}
        
        # Try to unlock an exit
        found_target_exit = False
        for direction, dest_room_name_master in current_room_data_world.get("exits", {}).items():
            if direction.lower() == target_name_lower or dest_room_name_master.lower() == target_name_lower:
                found_target_exit = True; dest_room_world_data = self.current_level_rooms.get(dest_room_name_master)
                if dest_room_world_data and dest_room_world_data.get("locked"):
                    dest_room_master_data = self.game_data.rooms.get(self.player['current_level'], {}).get(dest_room_name_master, {})
                    required_keys_for_exit = dest_room_master_data.get('unlocks_with', [])
                    if not isinstance(required_keys_for_exit, list): required_keys_for_exit = [required_keys_for_exit]  # Ensure it's a list
                    
                    key_used_to_unlock = None
                    for req_key in required_keys_for_exit:
                        if req_key in available_keys_in_inv:
                            key_used_to_unlock = req_key
                            break
                    
                    can_use_master = has_master_key and dest_room_master_data.get("level", self.player['current_level']) == 1  # Master key for hospital level
                    
                    if key_used_to_unlock or can_use_master:
                        dest_room_world_data["locked"] = False
                        used_key_display = key_used_to_unlock if key_used_to_unlock else "Medical Director Key Card"
                        message = color_text(f"Unlocked way to {dest_room_name_master} with {used_key_display}.", "success")
                        unlocked_something = True
                        logger.info(f"Unlocked exit to '{dest_room_name_master}' using '{used_key_display}'.")
                    elif required_keys_for_exit:
                        message = f"Need {required_keys_for_exit[0]} for {dest_room_name_master}."
                        if len(required_keys_for_exit) > 1:
                            message = f"Need one of these keys for {dest_room_name_master}: {', '.join(required_keys_for_exit)}."
                    else: message = f"{dest_room_name_master} locked, unsure how."
                elif dest_room_world_data: message = f"{dest_room_name_master} already unlocked."; turn_taken = False
                else: message = f"Path '{target_name_str}' invalid."; turn_taken = False
                break
        
        # If not an exit, try to unlock furniture
        if not found_target_exit:
            target_furniture_dict_world = None; furn_idx_world = -1
            furniture_list_world = current_room_data_world.get("furniture", [])
            for i, furn_dict_world_iter in enumerate(furniture_list_world):
                if furn_dict_world_iter.get("name", "").lower() == target_name_lower: target_furniture_dict_world = furn_dict_world_iter; furn_idx_world = i; break
            
            if target_furniture_dict_world and target_furniture_dict_world.get("locked"):
                furn_name_cased = target_furniture_dict_world["name"]; furn_master_data = None
                # Find master data for this furniture to get its unlocks_with_item
                for fm_dict_master in self.game_data.rooms.get(self.player['current_level'], {}).get(current_room_name, {}).get("furniture", []):
                    if fm_dict_master.get("name", "") == furn_name_cased: furn_master_data = fm_dict_master; break
                
                required_key_name = furn_master_data.get("unlocks_with_item") if furn_master_data else None
                can_use_master_furn = has_master_key and furn_master_data.get("level", self.player['current_level']) == 1  # Master key for hospital furniture
                
                if (required_key_name and required_key_name in available_keys_in_inv) or can_use_master_furn:
                    self.current_level_rooms[current_room_name]['furniture'][furn_idx_world]["locked"] = False
                    used_key_display = required_key_name if (required_key_name and required_key_name in available_keys_in_inv) else "Medical Director Key Card"
                    message = color_text(f"Unlocked {furn_name_cased} with {used_key_display}.", "success"); unlocked_something = True
                    logger.info(f"Unlocked furniture '{furn_name_cased}' using '{used_key_display}'.")
                elif required_key_name: message = f"Need {required_key_name} for {furn_name_cased}."
                else: message = f"{furn_name_cased} locked, unsure how."
            elif target_furniture_dict_world: message = f"{target_furniture_dict_world['name']} already unlocked."; turn_taken = False
            else: message = f"Don't see '{target_name_str}' to unlock."; turn_taken = False
        
        # Check for hazards if something was unlocked
        if unlocked_something and self.hazard_engine:
            hazard_resp = self.hazard_engine.check_action_hazard('unlock', target_name_str, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): message += "\n" + hazard_resp["message"]
                if hazard_resp.get("death"): death_triggered = True
        
        return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

    def _command_inventory(self):
        inventory = self.player.get('inventory', [])
        if not inventory: return {"message": "Inventory empty.", "turn_taken": False}
        item_details = []
        for item_name in inventory:
            item_data = self._get_item_data(item_name); desc = item_name.capitalize()
            if item_data: desc = color_text(desc, "evidence" if item_data.get("is_evidence") else "item")
            item_details.append(desc)
        message = "Carrying: " + ", ".join(item_details) + "."
        return {"message": message, "turn_taken": False}

    def _command_list_actions(self):
        message_parts = [color_text("Possible actions:", "info"), "  Move [direction]", "  Examine [object/item/room]",
                         f"  {self.game_data.ACTION_BREAK.capitalize()} [furniture]", "  Take [item]", "  Search [furniture]",
                         "  Use [item] on [target]", "  Drop [item]", "  Unlock [door/furniture]", "  Inventory (or 'i')",
                         "  Map", "  Save [slot] / Load [slot]", "  Quit / Newgame"]
        return {"message": "\n".join(message_parts), "turn_taken": False}

    def _command_map(self): return {"message": self.get_gui_map_string(), "turn_taken": False}
        
    def _get_item_data(self, item_name):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name: return None
        target_name_lower = item_name.lower()
        for name, data in self.current_level_items_master_copy.items():
            if name.lower() == target_name_lower: return copy.deepcopy(data)
        for source_type in ["items", "evidence", "keys"]:
            source_dict = getattr(self.game_data, source_type, {})
            for name, data in source_dict.items():
                if name.lower() == target_name_lower:
                    logger.debug(f"Item '{item_name}' found in global game_data.{source_type}.")
                    return copy.deepcopy(data)
        logger.debug(f"Item data for '{item_name}' not found.")
        return None

    def _get_current_room_data(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player: logger.warning("Player/location not set."); return None
        current_room_name = self.player['location']
        if not self.current_level_rooms: logger.warning(f"current_level_rooms not initialized."); return None
        room_data = self.current_level_rooms.get(current_room_name)
        if room_data is None: logger.warning(f"Room data for '{current_room_name}' not found.")
        return room_data

    def get_room_data(self, room_name):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not room_name: logger.warning("get_room_data no room_name."); return None
        if not self.current_level_rooms: logger.warning(f"current_level_rooms not initialized."); return None
        room_data = self.current_level_rooms.get(room_name)
        if room_data is None: logger.warning(f"Room data for '{room_name}' not found.")
        return room_data
        
    def get_room_description(self, room_name=None):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if room_name is None:
            if not self.player or 'location' not in self.player: logger.error("Player/location not set."); return "Indescribable void."
            room_name = self.player["location"]
        room_data = self._get_current_room_data() if room_name == self.player["location"] else self.get_room_data(room_name)
        if not room_data: logger.error(f"Room data for '{room_name}' not found."); return f"Anomaly where '{room_name}' should be."
        description_parts = [color_text(f"\n--- {room_name.upper()} ---", 'room')]
        base_desc = room_data.get("description", "Empty space.")
        keywords_to_color = {"fireplace": "furniture", "cupboard": "furniture", "desk": "furniture", "wires": "hazard", "gas": "warning", "door": "furniture", "window": "furniture", "key": "item", "note": "evidence", "brick": "item", "blood": "warning", "fire": "fire", "sparks": "hazard", "water": "default", "shadows": "default", "darkness": "default", "light": "default"}
        for kw, color_type in keywords_to_color.items(): base_desc = base_desc.replace(kw, color_text(kw, color_type)); base_desc = base_desc.replace(kw.capitalize(), color_text(kw.capitalize(), color_type))
        description_parts.append(base_desc)
        items_in_room_direct = []
        for item_key, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == room_name and not item_world_data.get('container') and not item_world_data.get('is_hidden'):
                item_master = self._get_item_data(item_key); color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                items_in_room_direct.append(color_text(item_key.capitalize(), color_type))
        if items_in_room_direct: description_parts.append("\n" + color_text("See here: ", "default") + ", ".join(items_in_room_direct) + ".")
        revealed_items_in_room = []
        for item_key in self.revealed_items_in_rooms.get(room_name, set()):
            item_world_data = self.current_level_items_world_state.get(item_key)
            if item_world_data and item_world_data.get('location') == room_name and not item_world_data.get('container') and item_key not in self.player.get('inventory', []):
                item_master = self._get_item_data(item_key); color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                formatted_revealed_item = color_text(item_key.capitalize() + " (revealed)", color_type)
                if formatted_revealed_item not in items_in_room_direct : revealed_items_in_room.append(formatted_revealed_item)
        if revealed_items_in_room: description_parts.append("\n" + color_text("Also noticed: ", "default") + ", ".join(revealed_items_in_room) + ".")
        room_objects_list = room_data.get("objects", [])
        if room_objects_list: description_parts.append("\n" + color_text("Objects: ", "default") + ", ".join(color_text(obj.capitalize(), 'item') for obj in room_objects_list) + ".")
        furniture_list_data = room_data.get("furniture", [])
        if furniture_list_data:
            furniture_descs = []
            for f_dict in furniture_list_data:
                f_name = f_dict.get("name", "unknown furniture").capitalize(); f_desc = color_text(f_name, 'furniture')
                if f_dict.get("locked"): f_desc += color_text(" (Locked)", "warning")
                if f_dict.get("is_hidden_container") and f_dict.get("name") not in self.revealed_items_in_rooms.get(room_name, set()): continue
                furniture_descs.append(f_desc)
            if furniture_descs: description_parts.append("\n" + color_text("Furniture: ", "default") + ", ".join(furniture_descs) + ".")
        if self.hazard_engine:
            env_state = self.hazard_engine.get_env_state(room_name); hazard_descs_from_engine = self.hazard_engine.get_room_hazards_descriptions(room_name)
            env_messages = []
            if env_state.get('gas_level', 0) >= self.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD: env_messages.append(color_text("Air thick with gas!", "error"))
            elif env_state.get('gas_level', 0) >= 1: env_messages.append(color_text("Smell gas.", "warning"))
            if env_state.get('is_on_fire'): env_messages.append(color_text("Room on fire!", "fire"))
            elif env_state.get('is_sparking') and not any("spark" in hd.lower() for hd in hazard_descs_from_engine): env_messages.append(color_text("Sparks crackle!", "hazard"))
            if env_state.get('is_wet'): env_messages.append(color_text("Floor wet.", "default"))
            if env_state.get('visibility') != "normal": env_messages.append(color_text(f"Visibility {env_state.get('visibility')}.", "warning"))
            if env_state.get('noise_level',0) >= 3: env_messages.append(color_text("Deafeningly noisy.", "warning"))
            elif env_state.get('noise_level',0) >= 1: env_messages.append(color_text("Noticeable background noise.", "default"))
            if env_messages: description_parts.append("\n" + "\n".join(env_messages))
            if hazard_descs_from_engine: description_parts.append("\n" + "\n".join(hazard_descs_from_engine))
        exits_data = room_data.get("exits", {})
        if exits_data:
            exit_parts = []
            for direction, dest_room_name in exits_data.items():
                dest_room_is_locked = self.current_level_rooms.get(dest_room_name, {}).get('locked', False)
                lock_indicator = color_text(" (Locked)", "warning") if dest_room_is_locked else ""
                exit_parts.append(f"{color_text(direction.capitalize(), 'exit')} to {color_text(str(dest_room_name).capitalize(), 'room')}{lock_indicator}")
                description_parts.append("\n\n" + color_text("Exits: ", "default") + "; ".join(exit_parts) + ".")
        else: description_parts.append("\n\n" + color_text("No obvious exits.", "default"))
        return "\n".join(filter(None, description_parts)).strip()

    def _enhance_description_keywords(self, description_text): return description_text

    def _get_furniture_piece(self, room_data_dict, furniture_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not room_data_dict or not isinstance(room_data_dict.get("furniture"), list): return None
        target_lower = furniture_name_str.lower()
        for furn_dict in room_data_dict["furniture"]:
            if isinstance(furn_dict, dict) and furn_dict.get("name", "").lower() == target_lower: return furn_dict
        return None

    def _handle_status_effects_pre_action(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); messages = []; action_prevented = False
        if not isinstance(self.player.get("status_effects"), dict): self.player["status_effects"] = {}; return messages, action_prevented
        if "stunned" in self.player["status_effects"]:
            effect_def = self.game_data.status_effects_definitions.get("stunned", {})
            messages.append(color_text(effect_def.get("message_on_action_attempt", "Stunned, cannot act!"), "warning"))
            action_prevented = True; logger.info("Action prevented by 'stunned'.")
        return messages, action_prevented

    def _handle_status_effects_tick(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); tick_messages = []; effects_to_remove = []
        if not isinstance(self.player.get("status_effects"), dict): self.player["status_effects"] = {}; return tick_messages
        active_effects = copy.deepcopy(self.player["status_effects"])
        for effect_name, turns_left in active_effects.items():
            effect_def = self.game_data.status_effects_definitions.get(effect_name)
            if not effect_def: logger.warning(f"Effect '{effect_name}' not in defs. Removing."); effects_to_remove.append(effect_name); continue
            msg_on_tick = effect_def.get("message_on_tick"); hp_change = effect_def.get("hp_change_per_turn", 0)
            if msg_on_tick: tick_messages.append(color_text(msg_on_tick, "warning"))
            if hp_change != 0:
                self.apply_damage_to_player(-hp_change, f"status effect: {effect_name}")
                if hp_change < 0: tick_messages.append(color_text(f"Feel better due to {effect_name}.", "success"))
            self.player["status_effects"][effect_name] -= 1
            if self.player["status_effects"][effect_name] <= 0:
                effects_to_remove.append(effect_name); msg_on_expire = effect_def.get("message_on_wear_off")
                if msg_on_expire: tick_messages.append(color_text(msg_on_expire, "info"))
                logger.info(f"Effect '{effect_name}' expired.")
        for effect_name in effects_to_remove:
            if effect_name in self.player["status_effects"]: del self.player["status_effects"][effect_name]
        return tick_messages

    def _handle_turn_progression_and_final_checks(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); progression_messages = []
        if self.is_game_over: return progression_messages
        if self.hazard_engine:
            hazard_update_msgs, death_from_hazards = self.hazard_engine.hazard_turn_update()
            if hazard_update_msgs: progression_messages.extend(hazard_update_msgs)
            if death_from_hazards and not self.is_game_over:
                self.is_game_over = True; self.game_won = False
                if not self.player.get('last_death_message'):
                    death_source = self.player.get('last_hazard_object_name', self.player.get('last_hazard_type', 'environmental hazard'))
                    self.player['last_death_message'] = f"Overcome by {death_source}."
                logger.info(f"Game over by HazardEngine. Death: {self.player.get('last_death_message')}")
                if not any("fatal" in msg.lower() or "die" in msg.lower() for msg in progression_messages):
                    progression_messages.append(color_text(self.player['last_death_message'], "error"))
        status_tick_messages = self._handle_status_effects_tick()
        if status_tick_messages: progression_messages.extend(status_tick_messages)
        if self.player.get("hp", 0) <= 0 and not self.is_game_over:
            self.is_game_over = True; self.game_won = False
            self.player['last_death_message'] = self.player.get('last_death_message', "Succumbed to afflictions.")
            logger.info(f"Game over: HP <= 0. Death: {self.player['last_death_message']}")
            if not any("fatal" in msg.lower() or "succumb" in msg.lower() for msg in progression_messages):
                progression_messages.append(color_text(self.player['last_death_message'], "error"))
        if not self.is_game_over:
            self.player["turns_left"] = self.player.get("turns_left", 0) - 1
            self.player["actions_taken"] = self.player.get("actions_taken", 0) + 1
            self.player["actions_taken_this_level"] = self.player.get("actions_taken_this_level", 0) + 1
            if self.player["turns_left"] <= 0:
                self.is_game_over = True; self.game_won = False
                self.player['last_death_message'] = "Time ran out! Dawn breaks, claiming you."
                logger.info("Game over: Turns ran out.")
                progression_messages.append(color_text(self.player['last_death_message'], "error"))
        return progression_messages

    def apply_damage_to_player(self, damage_amount, source="an unknown source"):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.is_game_over: return
        old_hp = self.player.get("hp", 0); new_hp = old_hp - damage_amount
        if damage_amount > 0: self.player["hp"] = max(0, new_hp); logger.info(f"Player took {damage_amount} from {source}. HP: {old_hp} -> {self.player['hp']}")
        elif damage_amount < 0: self.player["hp"] = min(self.player.get("max_hp", 10), new_hp); logger.info(f"Player healed {-damage_amount} from {source}. HP: {old_hp} -> {self.player['hp']}")
        if self.player["hp"] <= 0:
            self.is_game_over = True; self.game_won = False
            self.player['last_hazard_type'] = source 
            self.player['last_death_message'] = f"Succumbed to injuries from {source}."
            logger.info(f"Game Over: Player HP 0 from {source}.")

    def apply_status_effect(self, effect_name, duration_override=None, messages_list=None):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not hasattr(self.game_data, 'status_effects_definitions'): logger.warning("status_effects_definitions not found."); return False
        effect_def = self.game_data.status_effects_definitions.get(effect_name)
        if not effect_def: logger.warning(f"Unknown status effect: {effect_name}"); return False
        duration = duration_override if duration_override is not None else effect_def.get("duration", 1)
        if not isinstance(self.player.get("status_effects"), dict): self.player["status_effects"] = {}
        self.player["status_effects"][effect_name] = duration
        apply_message = effect_def.get("message_on_apply", f"Now {effect_name}.")
        if messages_list is not None: messages_list.append(color_text(apply_message, "warning"))
        else: logger.info(f"Applied status: {effect_name}. Message: {apply_message}")
        logger.info(f"Applied status effect: {effect_name} for {duration} turns.")
        return True

    def get_valid_directions(self):
        if not self.player or 'location' not in self.player: self.logger.warning("Player/location not set."); return []
        current_room_data = self._get_current_room_data()
        if not current_room_data or not isinstance(current_room_data.get("exits"), dict): self.logger.warning(f"No valid exits for room '{self.player.get('location')}'."); return []
        return list(current_room_data["exits"].keys())

    def get_examinable_targets_in_room(self):
        if not self.player or 'location' not in self.player: self.logger.warning("Player/location not set."); return []
        current_room_name = self.player['location']; room_data = self.get_room_data(current_room_name) 
        if not room_data: self.logger.warning(f"No room data for '{current_room_name}'."); return []
        targets = []
        for furn_dict in room_data.get("furniture", []):
            furn_name = furn_dict.get("name")
            if not furn_name: continue
            is_hidden_furn_container = furn_dict.get("is_hidden_container", False)
            if is_hidden_furn_container:
                if furn_name in self.revealed_items_in_rooms.get(current_room_name, set()): targets.append(furn_name)
            else: targets.append(furn_name)
        for obj_name_or_dict in room_data.get("objects", []):
            name_to_add = obj_name_or_dict.get("name") if isinstance(obj_name_or_dict, dict) else obj_name_or_dict
            if name_to_add: targets.append(name_to_add)
        for item_name, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == current_room_name:
                is_visible_on_floor = not item_world_data.get('container') and not item_world_data.get('is_hidden', False)
                is_revealed_in_container = item_world_data.get('container') and item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible_on_floor or is_revealed_in_container: targets.append(item_name)
        self.logger.debug(f"Examinable targets in '{current_room_name}': {list(set(filter(None, targets)))}")
        return list(set(filter(None, targets)))

    def get_takeable_items_in_room(self):
        if not self.player or 'location' not in self.player: self.logger.warning("Player/location not set."); return []
        current_room_name = self.player['location']; takeable_items = []
        for item_name, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == current_room_name:
                master_item_data = self._get_item_data(item_name) 
                if master_item_data and master_item_data.get('takeable', True):
                    is_visible_on_floor = not item_world_data.get('container') and not item_world_data.get('is_hidden', False)
                    is_revealed_in_container = item_world_data.get('container') and item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                    if (is_visible_on_floor or is_revealed_in_container) and item_name not in self.player.get('inventory', []):
                         takeable_items.append(item_name)
        self.logger.debug(f"Takeable items in '{current_room_name}': {list(set(takeable_items))}")
        return list(set(takeable_items))

    def get_usable_inventory_items(self):
        if not self.player or not isinstance(self.player.get('inventory'), list): self.logger.warning("Player/inventory not available."); return []
        usable_items = []
        for item_name in self.player['inventory']:
            item_master_data = self._get_item_data(item_name)
            if item_master_data and (item_master_data.get('use_on') or item_master_data.get('general_use_effect_message') or item_master_data.get('heal_amount') or item_master_data.get('is_key')): 
                usable_items.append(item_name)
        self.logger.debug(f"Usable inventory items: {list(set(usable_items))}")
        return list(set(usable_items))

    def get_inventory_items(self):
        if not self.player or not isinstance(self.player.get('inventory'), list): self.logger.warning("Player/inventory not available."); return []
        return list(self.player['inventory']) 

    def get_unlockable_targets(self):
        if not self.player or 'location' not in self.player: self.logger.warning("Player/location not set."); return []
        current_room_name = self.player['location']; current_room_data_world = self.current_level_rooms.get(current_room_name)
        if not current_room_data_world: self.logger.warning(f"No world data for room '{current_room_name}'."); return []
        unlockable_targets = []
        for direction, dest_room_name in current_room_data_world.get("exits", {}).items():
            dest_room_world_data = self.current_level_rooms.get(dest_room_name)
            if dest_room_world_data and dest_room_world_data.get("locked"):
                target_display_name = "Front Door" if current_room_name == "Front Porch" and dest_room_name == "Foyer" else dest_room_name
                if target_display_name not in unlockable_targets: unlockable_targets.append(target_display_name)
        for furn_dict_world in current_room_data_world.get("furniture", []):
            furn_name = furn_dict_world.get("name")
            if furn_dict_world.get("locked") and furn_name and furn_name not in unlockable_targets: unlockable_targets.append(furn_name)
        self.logger.debug(f"Unlockable targets in '{current_room_name}': {list(set(unlockable_targets))}")
        return list(set(unlockable_targets))

    def mri_lock_doors_and_initiate_qtes(self, hazard_id, hazard_instance, messages_list):
        """
        Called by HazardEngine when MRI enters 'mri_qte_sequence_start_and_lock_doors' state.
        Locks relevant doors and can add a message.
        The HazardEngine will then proceed to the next state which triggers the first QTE.
        """
        self.logger.info(f"GameLogic: MRI sequence started by hazard {hazard_id}. Locking doors.")
        mri_room_name = self.game_data.ROOM_MRI_SCAN_ROOM # "MRI Scan Room"
        
        doors_to_lock_map = { # exit_direction: target_room_name
            "south": self.game_data.ROOM_MORGUE, # "Morgue Autopsy Suite"
            "east": self.game_data.ROOM_STAIRWELL # "Stairwell"
        }

        locked_any_door = False
        if mri_room_name in self.current_level_rooms:
            room_data = self.current_level_rooms[mri_room_name]
            for exit_dir, target_room_key in doors_to_lock_map.items():
                if exit_dir in room_data.get("exits", {}):
                    actual_target_room_name = room_data["exits"][exit_dir]
                    if actual_target_room_name == target_room_key: # Ensure it's the correct target
                        if actual_target_room_name in self.current_level_rooms:
                            self.current_level_rooms[actual_target_room_name]["original_lock_state_mri"] = self.current_level_rooms[actual_target_room_name].get("locked", False)
                            self.current_level_rooms[actual_target_room_name]["locked"] = True
                            self.current_level_rooms[actual_target_room_name]["locked_by_mri"] = True # Custom flag
                            messages_list.append(color_text(f"The door to {actual_target_room_name} slams shut and locks!", "warning"))
                            locked_any_door = True
                            self.logger.info(f"MRI locked door to {actual_target_room_name}.")
                        else:
                            self.logger.warning(f"Target room {actual_target_room_name} for MRI door lock not found in current_level_rooms.")
                    else:
                         self.logger.warning(f"MRI door lock: Mismatch for exit '{exit_dir}'. Expected target '{target_room_key}', got '{actual_target_room_name}'.")
                else:
                    self.logger.warning(f"MRI door lock: Exit direction '{exit_dir}' not found in {mri_room_name} exits.")
        
        if not locked_any_door:
            messages_list.append(color_text("The MRI hums menacingly, but the doors seem unaffected by this specific surge.", "default"))

        # The HazardEngine will handle transitioning to the next state which actually calls _trigger_mri_qte_stage.
        # This function just sets up the door state.

    def mri_unlock_doors_and_breakdown(self, hazard_id, hazard_instance, messages_list):
        """
        Called by HazardEngine when MRI enters 'mri_field_collapsing_qte_success' state.
        Unlocks doors and confirms MRI breakdown.
        """
        self.logger.info(f"GameLogic: MRI QTE sequence success for hazard {hazard_id}. Unlocking doors.")
        
        doors_to_unlock_map = {
            "south": self.game_data.ROOM_MORGUE,
            "east": self.game_data.ROOM_STAIRWELL
        }

        unlocked_any_door = False
        mri_room_name = self.game_data.ROOM_MRI_SCAN_ROOM
        if mri_room_name in self.current_level_rooms:
            room_data = self.current_level_rooms[mri_room_name]
            for exit_dir, target_room_key in doors_to_unlock_map.items():
                if exit_dir in room_data.get("exits", {}):
                    actual_target_room_name = room_data["exits"][exit_dir]
                    if actual_target_room_name == target_room_key:
                        if actual_target_room_name in self.current_level_rooms:
                            # Restore original lock state or ensure unlocked
                            original_state = self.current_level_rooms[actual_target_room_name].get("original_lock_state_mri", False)
                            self.current_level_rooms[actual_target_room_name]["locked"] = original_state
                            self.current_level_rooms[actual_target_room_name].pop("locked_by_mri", None)
                            self.current_level_rooms[actual_target_room_name].pop("original_lock_state_mri", None)
                            messages_list.append(color_text(f"The lock on the door to {actual_target_room_name} disengages with a click.", "success"))
                            unlocked_any_door = True
                            self.logger.info(f"MRI unlocked door to {actual_target_room_name}.")
        
        if not unlocked_any_door:
            messages_list.append(color_text("The MRI is broken, but the doors remain stubbornly sealed by other means.", "warning"))
            
        messages_list.append(color_text("The MRI machine is now a smoking wreck.", "info"))

    def trigger_qte(self, qte_type, duration, context):
        """
        Sets up QTE data on the player object. UI (GameScreen) will detect this and show the QTEPopup.
        
        Args:
            qte_type (str): The type of QTE to trigger (dodge_projectile, etc.)
            duration (float): Time limit in seconds for the QTE
            context (dict): Context data for the QTE including prompts and result handling
        """
        if self.player.get('qte_active'):
            self.logger.warning(f"GameLogic: Attempted to trigger QTE '{qte_type}' while QTE '{self.player['qte_active']}' is already active. Ignoring.")
            return

        # Ensure the context has the fields needed by QTEPopup
        context.setdefault("ui_prompt_message", f"Quick! {qte_type.replace('_', ' ').title()}!")
        context.setdefault("expected_input_word", "dodge")  # Default, should be overridden by specific QTE def
        context.setdefault("input_type", "word")  # "word" or "button"
            
        self.player['qte_active'] = qte_type
        self.player['qte_duration'] = float(duration)  # Ensure it's a float
        self.player['qte_context'] = context  # Store the full context
        self.logger.info(f"GameLogic: QTE '{qte_type}' triggered. Duration: {duration}s. Context: {context}")
        # GameScreen.on_game_session_ready or its update loop will see player.qte_active and launch the QTEPopup

    def _handle_qte_response(self, qte_type_resolved, player_response_str):
        """
        Handles player's response to an active QTE.
        Called by GameScreen.resolve_qte_from_popup.
        
        Args:
            qte_type_resolved (str): The type of QTE being resolved
            player_response_str (str): The player's input response
            
        Returns:
            dict: Response payload with message, death flag, turn taken flag, and success status
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        
        qte_context = self.player.get('qte_context', {})
        qte_master_definition = self.game_data.qte_definitions.get(qte_type_resolved, {})
        
        # Clear QTE state from player object as it's being resolved
        self.player['qte_active'] = None
        self.player['qte_duration'] = 0
        
        response_payload = {"message": "", "death": False, "turn_taken": True, "success": False, "level_transition_data": None}
        
        expected_input_word = qte_context.get("expected_input_word", "action").lower()  # Default if not specified
        qte_input_method = qte_context.get("input_type", "word")
        target_mash_count = qte_context.get("target_mash_count", 10)  # For button_mash

        # Determine if player succeeded
        is_success = False
        if player_response_str == self.game_data.SIGNAL_QTE_TIMEOUT:
            is_success = False
            response_payload["message"] = color_text(qte_context.get("timeout_message", "Too slow!"), "error")
        elif qte_input_method == "word" or qte_input_method == "sequence_input_qte":  # Sequence input treated as a single "word"
            is_success = player_response_str.lower() == expected_input_word
        elif qte_input_method == "button_mash":
            # Assuming player_response_str for mash is "mash_success" if UI determines success
            is_success = player_response_str.lower() == "mash_success" 
        elif qte_input_method == "button":  # Generic button
            is_success = player_response_str.lower() == expected_input_word

        source_hazard_id = qte_context.get('qte_source_hazard_id')
        
        # Handle success case
        if is_success:
            response_payload["success"] = True
            response_payload["message"] = color_text(
                qte_context.get("success_message", qte_master_definition.get("success_message_default", "Success!")), "success")
            self.player["score"] = self.player.get("score", 0) + qte_master_definition.get("score_on_success", 10)
            self.unlock_achievement(self.game_data.ACHIEVEMENT_QUICK_REFLEXES)
            
            # Find the appropriate next state for the hazard on success
            next_state_success = qte_context.get('next_state_after_qte_success', 
                                                qte_context.get('next_state_for_hazard',
                                                qte_context.get('next_state_after_qte')))
            
            # Update the hazard state if applicable
            if source_hazard_id and next_state_success and self.hazard_engine:
                prog_msgs = []
                if self.hazard_engine._set_hazard_state(source_hazard_id, next_state_success, prog_msgs):
                    if prog_msgs:
                        response_payload["message"] += "\n" + "\n".join(prog_msgs)
                else:
                    logger.warning(f"QTE success: Hazard {source_hazard_id} could not be set to state {next_state_success}.")
            
            # Handle level completion if triggered by QTE success
            if qte_context.get("on_success_level_complete"):
                current_level_id = self.player.get("current_level", 1)
                level_reqs = self.game_data.LEVEL_REQUIREMENTS.get(current_level_id, {})
                next_level_id_val = level_reqs.get("next_level_id")
                next_level_start_room_val = level_reqs.get("next_level_start_room")
                
                if next_level_id_val is not None:
                    response_payload["message"] += color_text(f"\nSurvived Level {current_level_id}!", "special")
                    response_payload["level_transition_data"] = {
                        "next_level_id": next_level_id_val, 
                        "next_level_start_room": next_level_start_room_val, 
                        "completed_level_id": current_level_id
                    }
                else:
                    self.game_won = True
                    self.is_game_over = True
                    response_payload["message"] += color_text("\nIncredible! Cheated Death and survived final ordeal!", "success")
        
        else:  # Handle failure case
            response_payload["success"] = False
            if player_response_str != self.game_data.SIGNAL_QTE_TIMEOUT:  # Wrong input vs timeout
                response_payload["message"] = color_text(
                    qte_context.get("failure_message_wrong_input", qte_context.get("failure_message", "That's not right!")), 
                    "error"
                )
            
            hp_damage = qte_context.get("hp_damage_on_failure", qte_master_definition.get("hp_damage_on_failure", 0))
            is_fatal_direct = qte_context.get("is_fatal_on_failure", qte_master_definition.get("fatal_on_failure", False))
            
            # Special handling for MRI QTE failures
            if qte_context.get("is_mri_projectile_qte", False):
                self.player['mri_qte_failures'] = self.player.get('mri_qte_failures', 0) + 1
                
                if hp_damage > 0:
                    self.apply_damage_to_player(hp_damage, f"hit by {qte_context.get('qte_projectile_name', 'MRI projectile')}")
                    response_payload["message"] += f" You take {hp_damage} damage."
                    
                # Check if this failure is fatal (direct fatal flag, max failures reached, or HP depleted)
                if self.player['mri_qte_failures'] >= self.game_data.MAX_MRI_QTE_FAILURES or is_fatal_direct or self.player['hp'] <= 0:
                    response_payload["death"] = True
                    self.is_game_over = True
                    self.game_won = False
                    
                    obj_desc = qte_context.get("qte_projectile_name", "flying metal")
                    impact_res = "fatally wounding you"
                    if is_fatal_direct:
                        impact_res = "instantly killing you"
                    elif self.player['hp'] <= 0:
                        impact_res = "leaving you a mangled mess"
                    
                    self.player['last_death_message'] = self.game_data.GAME_OVER_MRI_DEATH.format(
                        object_description=obj_desc, 
                        impact_result=impact_res
                    )
                    response_payload["message"] += f"\n{self.player['last_death_message']}"
                    logger.info(f"Game Over: MRI QTE failure. Fails: {self.player['mri_qte_failures']}. HP: {self.player['hp']}")
                else:
                    # Not dead yet, progress to next hazard state
                    next_state_failure = qte_context.get('next_state_after_qte_failure', 
                                                    qte_context.get('next_state_for_hazard',
                                                    qte_context.get('next_state_after_qte')))
                    
                    if source_hazard_id and next_state_failure and self.hazard_engine:
                        hazard_prog_msgs = []
                        if source_hazard_id in self.hazard_engine.active_hazards:
                            self.hazard_engine._set_hazard_state(source_hazard_id, next_state_failure, hazard_prog_msgs)
                            if hazard_prog_msgs:
                                response_payload["message"] += "\n" + "\n".join(hazard_prog_msgs)
            
            else:  # Generic QTE failure handling
                if is_fatal_direct:
                    response_payload["death"] = True
                    self.is_game_over = True
                    self.game_won = False
                    self.player['last_hazard_type'] = f"Failed QTE: {qte_type_resolved}"
                    self.player['last_death_message'] = response_payload["message"]
                elif hp_damage > 0:
                    self.apply_damage_to_player(hp_damage, f"failing QTE {qte_type_resolved}")
                    response_payload["message"] += f" You take {hp_damage} damage."
                    if self.player['hp'] <= 0:
                        response_payload["death"] = True
                        self.player['last_death_message'] = response_payload["message"] + " You succumb to your injuries."
                
                # Handle hazard state transition on failure if player is still alive
                if not self.is_game_over:
                    next_state_failure = qte_context.get('next_state_after_qte_failure', 
                                                    qte_context.get('next_state_for_hazard',
                                                    qte_context.get('next_state_after_qte')))
                    
                    if source_hazard_id and next_state_failure and self.hazard_engine:
                        hazard_prog_msgs = []
                        if source_hazard_id in self.hazard_engine.active_hazards:
                            self.hazard_engine._set_hazard_state(source_hazard_id, next_state_failure, hazard_prog_msgs)
                            if hazard_prog_msgs:
                                response_payload["message"] += "\n" + "\n".join(hazard_prog_msgs)
                        else:
                            logger.warning(f"QTE failure: Hazard {source_hazard_id} could not be set to state {next_state_failure}.")
                elif self.is_game_over and source_hazard_id and next_state_failure and self.hazard_engine:
                    # If game over due to QTE, still try to set the hazard to its "aftermath" state
                    if source_hazard_id in self.hazard_engine.active_hazards:
                        self.hazard_engine._set_hazard_state(source_hazard_id, next_state_failure, [])
        
        # Clean up and return result
        self.player.pop('qte_context', None)
        logger.info(f"GameLogic: QTE '{qte_type_resolved}' response processed. Success: {is_success}. Player HP: {self.player.get('hp')}")
        
        if self.is_game_over and not response_payload.get("death"):
            response_payload["death"] = True  # Ensure death flag is set if game over
            
        return response_payload

    def log_evaded_hazard(self, hazard_description_of_evasion):
        if self.player:
            self.player.setdefault('evaded_hazards_current_level', []).append(hazard_description_of_evasion)
            self.logger.info(f"Logged evaded hazard: {hazard_description_of_evasion}")

    def transition_to_new_level(self, new_level_id, start_room_override=None):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); completed_level_id = self.player['current_level']
        logger.info(f"Transitioning from Level {completed_level_id} to Level {new_level_id}...")
        self.player['current_level'] = new_level_id
        level_start_info = self.game_data.LEVEL_REQUIREMENTS.get(new_level_id, {})
        self.player['location'] = start_room_override or level_start_info.get('entry_room')
        if not self.player['location']: logger.error(f"No entry room for level {new_level_id}."); return {"success": False, "message": color_text(f"Error: Misconfigured transition to level {new_level_id}.", "error")}
        self.player.setdefault('visited_rooms', set()).add(self.player['location'])
        self.player['actions_taken_this_level'] = 0; self.player['evidence_found_this_level'] = []
        self.player['evaded_hazards_current_level'] = [] 
        self._initialize_level_data(new_level_id) 
        if self.hazard_engine: self.hazard_engine.initialize_for_level(new_level_id)
        logger.info(f"Player transitioned to Level {new_level_id}, starting in {self.player['location']}.")
        return {"success": True, "message": f"Welcome to {level_start_info.get('name', 'new area')}!\n\n{self.get_room_description()}", "new_location": self.player['location']}

    def _calculate_player_inventory_weight(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__)); total_weight = 0
        for item_name in self.player.get("inventory", []):
            item_data = self._get_item_data(item_name) 
            if item_data: total_weight += item_data.get("weight", self.game_data.DEFAULT_ITEM_WEIGHT)
            else: logger.warning(f"No data for item '{item_name}' in inv for weight calc.")
        return total_weight

    def unlock_achievement(self, achievement_id):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.achievements_system and self.achievements_system.unlock(achievement_id):
            logger.info(f"Achievement '{achievement_id}' unlocked via GameLogic."); return True
        elif not self.achievements_system: logger.warning(f"Tried to unlock '{achievement_id}' but AchievementsSystem missing.")
        return False

    def _get_save_filepath(self, slot_identifier="quicksave"):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not hasattr(self, 'save_dir') or not self.save_dir:
            logger.error("save_dir not initialized. Setting up paths."); self._setup_paths_and_logging() 
            if not self.save_dir: logger.critical("CRITICAL - save_dir could not be established."); return None
        filename = f"savegame_{slot_identifier}.json" # Using underscore for consistency
        return os.path.join(self.save_dir, filename)

    def _convert_sets_to_lists(self, obj):
        if isinstance(obj, dict): return {k: self._convert_sets_to_lists(v) for k, v in obj.items()}
        elif isinstance(obj, list): return [self._convert_sets_to_lists(i) for i in obj]
        elif isinstance(obj, set): return list(obj)
        else: return obj

    def save_game(self, slot_identifier): # This is the public method called by UI/command
        return self._command_save(slot_identifier)

    def _command_save(self, slot_identifier="quicksave"):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.player is None: logger.error("No game active to save."); return {"message": color_text("Error: No game active.", "error"), "success": False}
        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath: return {"message": color_text("Error: Save location issue.", "error"), "success": False}
        logger.info(f"Saving game to slot '{slot_identifier}' at {save_filepath}...")
        hazard_engine_savable_state = self.hazard_engine.save_state() if self.hazard_engine and hasattr(self.hazard_engine, 'save_state') else None
        
        # Create the save data dictionary
        raw_save_data = {
            'save_info': {'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'level': self.player.get('current_level', 1),
                        'location': self.player.get('location', 'Unknown'), 'character_class': self.player.get('character_class', 'Unknown'),
                        'turns_left': self.player.get('turns_left', 0), 'score': self.player.get('score', 0)},
            'player': self.player,
            'is_game_over': self.is_game_over, 'game_won': self.game_won,
            'revealed_items_in_rooms': self.revealed_items_in_rooms,
            'interaction_counters': self.interaction_counters,
            'current_level_rooms': self.current_level_rooms,
            'current_level_items_world_state': self.current_level_items_world_state,
            'hazard_engine_state': hazard_engine_savable_state,
        }
        
        # Convert ALL nested data structures to JSON-serializable types
        save_data = self._convert_sets_to_lists(raw_save_data)
        
        # Add this validation check before attempting to write the file
        try:
            # Test if the data is actually serializable to JSON
            json_test = json.dumps(save_data)
        except TypeError as te:
            logger.error(f"Save data not serializable: {te}")
            return {"message": color_text("Error: Save data contains invalid types.", "error"), "success": False}
        
        try:
            os.makedirs(os.path.dirname(save_filepath), exist_ok=True)
            with open(save_filepath, 'w', encoding='utf-8') as f: json.dump(save_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Game saved to slot '{slot_identifier}'.")
            return {"message": color_text(f"Game saved to slot '{slot_identifier}'.", "success"), "success": True}
        except TypeError as te: 
            logger.error(f"TypeError saving game: {te}. Check data.", exc_info=True)
            return {"message": color_text(f"Error saving: Non-serializable data. {te}", "error"), "success": False}
        except Exception as e: 
            logger.error(f"Error saving game: {e}", exc_info=True)
            return {"message": color_text(f"Error saving game: {e}", "error"), "success": False}

    def load_game(self, slot_identifier): # This is the public method called by UI/command
        return self._command_load(slot_identifier)

    def _command_load(self, slot_identifier="quicksave"):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath or not os.path.exists(save_filepath):
            logger.warning(f"Save file for '{slot_identifier}' not found at {save_filepath}.")
            return {"message": color_text(f"No save data for '{slot_identifier}'.", "warning"), "success": False}
        logger.info(f"Loading game from slot '{slot_identifier}' from {save_filepath}...")
        try:
            with open(save_filepath, 'r', encoding='utf-8') as f: load_data = json.load(f)
            self.player = load_data.get('player')
            if not self.player: logger.error("Loaded save missing 'player'."); return {"message": color_text("Error: Save corrupted (no player info).", "error"), "success": False}
            self.is_game_over = load_data.get('is_game_over', False); self.game_won = load_data.get('game_won', False)
            loaded_revealed = load_data.get('revealed_items_in_rooms', {})
            self.revealed_items_in_rooms = {room: set(items) for room, items in loaded_revealed.items()}
            self.interaction_counters = load_data.get('interaction_counters', {})
            loaded_level_id = self.player.get('current_level', 1) # Use player's current_level
            self._initialize_level_data(loaded_level_id) # Re-init base level data
            self.current_level_rooms = load_data.get('current_level_rooms', self.current_level_rooms) # Then overlay saved room states
            self.current_level_items_world_state = load_data.get('current_level_items_world_state', self.current_level_items_world_state) # And item states
            hazard_engine_state_data = load_data.get('hazard_engine_state')
            if not self.hazard_engine: self.hazard_engine = HazardEngine(self)
            self.hazard_engine.initialize_for_level(loaded_level_id) # Re-init hazard engine for level
            if hazard_engine_state_data and hasattr(self.hazard_engine, 'load_state'):
                self.hazard_engine.load_state(hazard_engine_state_data); logger.info("HazardEngine state loaded.")
            elif hazard_engine_state_data: logger.warning("HazardEngine state data found, but load_state failed/missing.")
            else: logger.info("No HazardEngine state in save. Hazards default for level.")
            if isinstance(self.player.get("visited_rooms"), list): self.player["visited_rooms"] = set(self.player["visited_rooms"])
            if "journal" not in self.player: self.player["journal"] = {}
            logger.info(f"Game loaded from '{slot_identifier}'. Player at {self.player.get('location')}, Level {loaded_level_id}.")
            return {"message": color_text(f"Game loaded from slot '{slot_identifier}'.", "success"), "success": True, "new_location": self.player.get('location')}
        except json.JSONDecodeError as jde: logger.error(f"JSONDecodeError loading '{slot_identifier}': {jde}", exc_info=True); return {"message": color_text(f"Error: Save file '{slot_identifier}' corrupted.", "error"), "success": False}
        except Exception as e: logger.error(f"Error loading '{slot_identifier}': {e}", exc_info=True); return {"message": color_text(f"Error loading game: {e}", "error"), "success": False}

