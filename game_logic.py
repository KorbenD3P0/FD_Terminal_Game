import json
import random
import logging
import copy
import os
import datetime
import collections

# Color constants for UI rendering (though GameLogic primarily returns raw data)
from utils import color_text, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_ORANGE, COLOR_LIGHT_GREY, COLOR_BLUE, COLOR_PURPLE, COLOR_WHITE, COLOR_MAGENTA
from kivy.app import App # For user_data_dir path
import game_data
from hazard_engine import HazardEngine
# AchievementsSystem is passed in constructor

# ==================================
# Game Logic Class
# ==================================
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

        self.hazard_engine = None 
        self._setup_paths_and_logging() 
        logging.info("GameLogic instance created. Call start_new_game() or load_game() to begin play.")

    def _setup_paths_and_logging(self):
        """Sets up paths for saves and logging, dependent on Kivy App instance."""
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
            handler = logging.FileHandler(os.path.join(log_dir, "game_logic.log"))
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO) 
            self.logger.propagate = False 

        self.logger.info(f"GameLogic logging to: {os.path.join(self.user_data_dir, 'logs', 'game_logic.log')}")
        self.save_dir = os.path.join(self.user_data_dir, 'saves')
        os.makedirs(self.save_dir, exist_ok=True)
        self.logger.info(f"GameLogic save directory: {self.save_dir}")

    def start_new_game(self, character_class="Journalist"):
        """Initializes a completely new game session."""
        self.logger.info(f"Starting new game with character: {character_class}...")
        self.is_game_over = False
        self.game_won = False


        if hasattr(self.game_data, 'get_initial_player_state'):
            self.player = self.game_data.get_initial_player_state(character_class)
        else: 
            stats = self.game_data.CHARACTER_CLASSES.get(character_class, self.game_data.CHARACTER_CLASSES["Journalist"])
            self.player = {
                "location": self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"],
                "inventory": [],
                "hp": stats["max_hp"],
                "max_hp": stats["max_hp"],
                "perception": stats["perception"],
                "intuition": stats["intuition"],
                "status_effects": {},
                "score": 0,
                "turns_left": self.game_data.STARTING_TURNS,
                "actions_taken": 0,
                "visited_rooms": set(), 
                "current_level": 1,
                "qte_active": None,
                "qte_duration": 0,
                "qte_context": {},
                "last_hazard_type": None,
                "last_hazard_object_name": None, # Corrected key
                "character_class": character_class,
                "journal": {} 
            }
        self.player['current_level'] = 1
        self.player['location'] = self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"] 
        self.player['visited_rooms'] = {self.player['location']}
        self.player['mri_qte_failures'] = 0
        self.player['actions_taken_this_level'] = 0
        self.player['evidence_found_this_level'] = [] 
        self.player['evaded_hazards_current_level'] = [] 

        self._initialize_level_data(self.player['current_level'])
        
        if not self.hazard_engine:
            self.hazard_engine = HazardEngine(self)
        self.hazard_engine.initialize_for_level(self.player['current_level'])
        
        self.logger.info(f"New game started. Player at {self.player['location']}. Level {self.player['current_level']}.")
        self.interaction_counters.clear() # Clear for a new game
        pass

    def _initialize_level_data(self, level_id):
        """Sets up the game world (rooms, items, hazards) for the specified level."""
        self.logger.info(f"Initializing data for Level {level_id}...")

        self.revealed_items_in_rooms.clear()
        self.interaction_counters.clear()

        if not self.game_data or not hasattr(self.game_data, 'rooms'):
            self.logger.error(f"game_data.rooms not available. Cannot initialize level {level_id}.")
            self.current_level_rooms = {}
            self.current_level_items_master_copy = {}
            self.current_level_items_world_state = {}
            if self.hazard_engine:
                self.hazard_engine.active_hazards.clear()
            return

        level_rooms_master = self.game_data.rooms.get(level_id)
        if level_rooms_master is None:
            self.logger.error(f"Level {level_id} data not found in game_data.rooms.")
            self.current_level_rooms = {}
        else:
            self.current_level_rooms = copy.deepcopy(level_rooms_master)
            self.logger.info(f"Loaded {len(self.current_level_rooms)} rooms for level {level_id}.")

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
                if not isinstance(data, dict):
                    self.logger.warning(f"Skipping non-dict item entry in '{source_type}': {name} ({type(data)})")
                    continue

                item_level_id_from_data = data.get("level")
                is_eligible_for_current_level = False
                if item_level_id_from_data == level_id:
                    if level_id == 1 and source_type == "evidence":
                        allowed_evidence = getattr(self.game_data, "ALLOWED_EVIDENCE_LEVEL_1", [])
                        if name in allowed_evidence:
                            is_eligible_for_current_level = True
                        elif data.get("location") in ["Coroner's Office", "Morgue Autopsy Suite"]: # Specific Morgue rooms
                            is_eligible_for_current_level = True
                        else:
                            self.logger.debug(f"Evidence '{name}' is for Level 1 but not in ALLOWED_EVIDENCE_LEVEL_1 or fixed in Morgue. Excluding.")
                    else:
                        is_eligible_for_current_level = True
                elif item_level_id_from_data is None or str(item_level_id_from_data).lower() == "all":
                    is_eligible_for_current_level = True

                if is_eligible_for_current_level:
                    if name not in self.current_level_items_master_copy:
                        self.current_level_items_master_copy[name] = copy.deepcopy(data)
                    else:
                        self.logger.warning(f"Duplicate item name '{name}' found. Using first encountered definition from '{source_type}'.")

        self.current_level_items_world_state = copy.deepcopy(self.current_level_items_master_copy)
        self.logger.info(f"Initialized {len(self.current_level_items_world_state)} item types for level {level_id} world state.")

        for item_name, item_world_data in self.current_level_items_world_state.items():
            original_item_def = self.current_level_items_master_copy.get(item_name, {})
            is_fixed = (
                original_item_def.get("fixed_location")
                or (original_item_def.get("location") and original_item_def.get("revealed_by_action"))
                or item_name in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION
            )
            if not is_fixed:
                item_world_data.pop("location", None)
                item_world_data.pop("container", None)
                item_world_data["is_hidden"] = original_item_def.get("is_hidden", True)
            else:
                item_world_data["location"] = original_item_def.get("location")
                item_world_data["container"] = original_item_def.get("container")
                if original_item_def.get("revealed_by_action"):
                    item_world_data["is_hidden"] = True
                else:
                    item_world_data["is_hidden"] = original_item_def.get("is_hidden", False)

        self._place_dynamic_elements_for_level(level_id)

        if self.hazard_engine:
            self.hazard_engine.initialize_for_level(level_id)
        else:
            self.logger.warning("HazardEngine not yet initialized when _initialize_level_data was called.")
        self.logger.info(f"Level {level_id} data initialization complete.")

    def _get_available_container_slots_for_level(self):
        """Gets available UNLOCKED container slots from rooms in the current level."""
        slots = []
        if not self.current_level_rooms:
            self.logger.warning("_get_available_container_slots_for_level: No rooms loaded for current level.")
            return slots
        for room_name, room_data in self.current_level_rooms.items():
            if not isinstance(room_data, dict):
                self.logger.warning(f"Room data for '{room_name}' is not a dict. Skipping for container slots.")
                continue
            for furniture_dict in room_data.get("furniture", []):
                if isinstance(furniture_dict, dict) and \
                   furniture_dict.get("is_container") and \
                   not furniture_dict.get("locked"):
                    capacity = furniture_dict.get("capacity", 1)
                    for _ in range(capacity):
                        slots.append({"room": room_name, "container_name": furniture_dict["name"], "item_inside": None})
        random.shuffle(slots)
        self.logger.debug(f"Found {len(slots)} available unlocked container slots for level.")
        return slots

    def _place_dynamic_elements_for_level(self, level_id):
        """Places dynamic items and confirms fixed items for the current level."""
        self.logger.info(f"--- Placing Dynamic & Fixed Elements for Level {level_id} ---")
        items_for_dynamic_placement = {
            name: data for name, data in self.current_level_items_world_state.items()
            if name not in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION and \
               not self.current_level_items_master_copy.get(name, {}).get("fixed_location") and \
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
        self.logger.info(f"Dynamic placement: {len(keys_to_place_dynamically)} keys, {len(evidence_to_place_dynamically)} evidence, {len(other_items_to_place_dynamically)} other items. Slots: {len(available_slots)}.")

        if keys_to_place_dynamically:
            self._distribute_items_in_slots(list(keys_to_place_dynamically.keys()), available_slots, "Key")
        if evidence_to_place_dynamically:
            self._distribute_items_in_slots(list(evidence_to_place_dynamically.keys()), available_slots, "Evidence")
        if other_items_to_place_dynamically:
            items_to_place_as_other = list(other_items_to_place_dynamically.keys())
            if items_to_place_as_other:
                self._distribute_items_in_slots(items_to_place_as_other, available_slots, "Other Item")

        for item_name, item_world_data in self.current_level_items_world_state.items():
            master_data = self.current_level_items_master_copy.get(item_name, {})
            is_explicitly_fixed = item_name in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION or master_data.get("fixed_location")
            if is_explicitly_fixed and (master_data.get("level") == level_id or master_data.get("level") is None or str(master_data.get("level")).lower() == "all"):
                defined_loc = master_data.get("location")
                defined_container = master_data.get("container")
                if defined_loc and item_world_data.get("location") != defined_loc:
                    self.logger.warning(f"Fixed item '{item_name}' world location '{item_world_data.get('location')}' differs from master definition '{defined_loc}'. Correcting.")
                    item_world_data["location"] = defined_loc
                if defined_container and item_world_data.get("container") != defined_container:
                     item_world_data["container"] = defined_container
                elif not defined_container:
                     item_world_data.pop("container", None)
                if item_world_data.get("location"):
                    self.logger.info(f"Confirmed fixed item '{item_name}' at {item_world_data['location']}" +
                                     (f" in container '{item_world_data['container']}'." if item_world_data.get('container') else "."))
                else:
                    self.logger.warning(f"Fixed item '{item_name}' has no location in world state despite being fixed. Master def loc: {defined_loc}")
        self.logger.info("--- Dynamic and Fixed Element Placement Complete ---")

    def _distribute_items_in_slots(self, item_names_list, available_slots_list, item_category_log="Item"):
        """Distributes items into available container slots, respecting Level 1 item limits."""
        placed_count = 0
        random.shuffle(item_names_list)
        container_fill_count = {} 
        max_items_per_container_level_1 = 1 # Max non-essential items per container in Level 1

        for item_name in item_names_list:
            if not available_slots_list:
                self.logger.warning(f"Ran out of available slots for {item_category_log} '{item_name}'.")
                break
            item_data_world = self.current_level_items_world_state.get(item_name)
            if not item_data_world or item_data_world.get("location"): # Skip if no data or already placed
                continue
            
            slot_found_for_item = False
            temp_slots_to_retry = []
            original_slots_count = len(available_slots_list)
            processed_slots_count = 0

            while available_slots_list and not slot_found_for_item and processed_slots_count < original_slots_count * 2:
                slot = available_slots_list.pop(0)
                processed_slots_count += 1
                container_id = (slot["room"], slot["container_name"])
                
                is_level_1 = self.player.get("current_level") == 1
                # Stricter limit for "Other Item" category in Level 1
                is_restricted_category_for_level_1 = item_category_log == "Other Item" 

                if is_level_1 and is_restricted_category_for_level_1 and \
                   container_fill_count.get(container_id, 0) >= max_items_per_container_level_1:
                    temp_slots_to_retry.append(slot)
                    continue

                item_data_world["location"] = slot["room"]
                item_data_world["container"] = slot["container_name"]
                item_data_world["is_hidden"] = True
                container_fill_count[container_id] = container_fill_count.get(container_id, 0) + 1
                slot_found_for_item = True
                self.logger.info(f"Placed {item_category_log} '{item_name}' in '{slot['container_name']}' ({slot['room']}). Fill: {container_fill_count[container_id]}")
                placed_count += 1
            
            available_slots_list.extend(temp_slots_to_retry)
            if not slot_found_for_item:
                self.logger.warning(f"Could not find slot for {item_category_log} '{item_name}'.")
        if placed_count < len(item_names_list):
            self.logger.warning(f"Placed {placed_count}/{len(item_names_list)} {item_category_log}s due to slot/fill limits.")
        return placed_count

    def get_searchable_furniture_in_room(self):
        """
        Returns a list of furniture names in the current room that can be searched.
        """
        current_room = self.player.get('location')
        room_data = self.get_room_data(current_room)
        if not room_data:
            return []
        # Furniture is a list of dicts; filter for containers that are not locked or hidden
        return [
            furn.get("name") for furn in room_data.get("furniture", [])
            if furn.get("is_container", False) and not furn.get("locked", False) and not furn.get("is_hidden_container", False)
        ]

    def get_save_slot_info(self, slot_id):
        """Returns a dict with preview info for the given save slot, or None if not found or invalid."""
        save_path = os.path.join(self.save_dir, f"{slot_id}.json") # Use self.save_dir
        if not os.path.exists(save_path):
            return None
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                try:
                    content = f.read()
                    if not content.strip():
                        self.logger.warning(f"Save slot '{slot_id}' is empty. Skipping.")
                        return None
                    loaded = json.loads(content)
                except json.JSONDecodeError:
                    self.logger.warning(f"Save slot '{slot_id}' is empty or corrupted. Skipping.")
                    return None
            data = loaded.get("save_info", {})
            return {
                "location": data.get("location", "?"),
                "timestamp": data.get("timestamp", "Unknown"),
                "character_class": data.get("character_class", ""),
                "turns_left": data.get("turns_left", ""),
                "score": data.get("score", "")
            }
        except Exception as e:
            self.logger.error(f"Error reading save slot info for '{slot_id}': {e}")
            return None

    def process_player_input(self, command_str):
        """Processes the raw command string from the player."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.is_game_over and not self.player.get('qte_active'):
            return {"message": "The game is over. " + (color_text("You won!", "success") if self.game_won else color_text("You lost.", "error")), 
                    "death": not self.game_won, "turn_taken": False}

        if self.player.get('qte_active'):
            qte_response_data = self._handle_qte_response(self.player['qte_active'], command_str)
            # Merge QTE response directly into main response
            # The qte_response_data structure should match what process_player_input returns
            return qte_response_data


        command_str_original = command_str
        command_str = command_str.strip().lower()
        words = command_str.split()

        if not words:
            return {"message": "Please enter a command.", "death": False, "turn_taken": False}

        verb = words[0]
        target_str = " ".join(words[1:])

        verb_aliases = {
            "go": "move", "get": "take", "look": "examine", "inspect": "examine",
            "inv": "inventory", "i": "inventory", "bag": "inventory",
            "q": "quit", "exit": "quit", "restart": "newgame", "again": "newgame",
            "actions": "list", "commands": "list", "l": "examine",
            "force": "force", "break": "break", # Alias "force" to "break"
            self.game_data.ACTION_BREAK: self.game_data.ACTION_BREAK # Ensure "break" maps to itself
        }
        verb = verb_aliases.get(verb, verb)

        response = {
            "message": f"I don't know how to '{verb}'. Type 'list' for available actions.", 
            "death": False, "turn_taken": False, "found_items": None,
            "new_location": None, "item_taken": None, "item_dropped": None,
            "item_revealed": False, "qte_triggered": None
        }

        if verb == "quit":
            response["message"] = "Use the Exit button on the Title Screen or close the window to quit."
            return response
        if verb == "newgame":
            self.start_new_game(self.player.get("character_class", "Journalist"))
            response["message"] = f"{color_text('--- New Game Started ---', 'special')}\n{self.get_room_description()}"
            response["new_location"] = self.player['location']
            return response
        if verb == "save":
            save_response = self._command_save(target_str if target_str else "quicksave")
            response["message"] = save_response.get("message", "Save status unknown.")
            return response
        if verb == "load":
            load_response = self._command_load(target_str if target_str else "quicksave")
            response["message"] = load_response.get("message", "Load status unknown.")
            if load_response.get("success"):
                response["new_location"] = self.player['location']
                response["message"] += f"\n{self.get_room_description()}"
            return response
        if verb == "help" or verb == "list":
            response = self._command_list_actions()
            return response
        if verb == "inventory":
            response = self._command_inventory()
            return response
        if verb == "map":
            response = self._command_map()
            return response

        status_messages, action_prevented = self._handle_status_effects_pre_action()
        if status_messages:
            response["pre_action_status_message"] = "\n".join(status_messages)
        if action_prevented:
            response["message"] = response.get("pre_action_status_message", "") + \
                                  f"\n{color_text('You are unable to perform the action due to your condition.', 'warning')}"
            response["turn_taken"] = True
        else:
            command_methods = {
                "move": self._command_move, "examine": self._command_examine,
                "take": self._command_take, "search": self._command_search,
                "use": self._command_use, "drop": self._command_drop,
                "unlock": self._command_unlock, "force": self._command_force,
                self.game_data.ACTION_BREAK: self._command_break # Add break command
            }
            if verb in command_methods:
                command_func = command_methods[verb]
                if verb == "use":
                    action_response = command_func(words[1:])
                elif not target_str and verb not in ["examine"]:
                    action_response = {"message": f"{verb.capitalize()} what?", "turn_taken": False}
                elif verb == "examine" and not target_str:
                    action_response = command_func(self.player['location'])
                else:
                    action_response = command_func(target_str)
                response.update(action_response)
            else:
                response["turn_taken"] = False
        
        if response.get("pre_action_status_message"):
            response["message"] = response["pre_action_status_message"] + "\n" + response.get("message", "")
            del response["pre_action_status_message"]

        if response.get("death"):
            self.is_game_over = True
            self.game_won = False
            logger.info(f"Command '{command_str_original}' resulted in death. Player HP: {self.player.get('hp')}")
            if response.get("turn_taken", True):
                turn_progression_messages = self._handle_turn_progression_and_final_checks()
                if turn_progression_messages:
                    response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_progression_messages).strip()).strip()
            return response

        if not self.is_game_over and response.get("turn_taken"):
            turn_progression_messages = self._handle_turn_progression_and_final_checks()
            if turn_progression_messages:
                response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_progression_messages).strip()).strip()
            if self.is_game_over and not self.game_won:
                response["death"] = True
        
        if response.get("qte_triggered") and not self.player.get('qte_active'):
            qte_data = response["qte_triggered"]
            self.trigger_qte(qte_data.get("type"), qte_data.get("duration"), qte_data.get("context"))
            logger.info(f"QTE '{self.player['qte_active']}' triggered by command '{command_str}'.")
        
        # Handle level transition data if set by an action (e.g. successful level exit)
        if response.get("level_transition_data"):
            # This data will be picked up by GameScreen to navigate to InterLevelScreen
            # No further processing needed here for the transition itself.
            pass

        return response

    def get_gui_map_string(self, width=35, height=7):
        """Generates a Kivy-compatible map string with colors."""
        if not hasattr(self, 'player') or not self.player or \
           not hasattr(self, 'current_level_rooms') or not self.current_level_rooms:
            return "Map data not available."
        current_room_name = self.player.get('location')
        current_room_data = self.get_room_data(current_room_name)
        if not current_room_name or not current_room_data:
            return "Player location/room data unknown."

        exits = current_room_data.get('exits', {})
        location_line = f"[b]{color_text(current_room_name, 'room')}[/b]"

        def format_direction_cell(symbol_char, primary_key, alt_key, exits_dict):
            dest_room_name = exits_dict.get(primary_key)
            if not dest_room_name and alt_key:
                dest_room_name = exits_dict.get(alt_key)
            if dest_room_name:
                dest_room_data = self.get_room_data(dest_room_name)
                is_locked = dest_room_data.get('locked', False) if dest_room_data else False
                visited = dest_room_name in self.player.get('visited_rooms', set())
                text_color_name = "exit" if visited else "default" 
                base_symbol = color_text(symbol_char, text_color_name)
                lock_indicator = color_text("(L)", "error") if is_locked else ""
                return f"{base_symbol}{lock_indicator}"
            return " "
        u_cell = format_direction_cell("U", "upstairs", "up", exits)
        n_cell = format_direction_cell("N", "north", None, exits)
        w_cell = format_direction_cell("W", "west", None, exits)
        p_cell = color_text("P", "success")
        e_cell = format_direction_cell("E", "east", None, exits)
        s_cell = format_direction_cell("S", "south", None, exits)
        d_cell = format_direction_cell("D", "downstairs", "down", exits)
        map_lines = [f"{u_cell}", f"{n_cell}", f"{w_cell} - {p_cell} - {e_cell}", f"{s_cell}", f"{d_cell}"]
        final_map_string = location_line + "\n" + "\n".join(map_lines)
        return final_map_string
    
    def _command_force(self, target_name_str):
        """Handles the player attempting to force open a door or object."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        response_messages = []
        turn_taken = True
        death_triggered = False
        qte_triggered_by_action = None

        if not target_name_str:
            return {"message": "Force what?", "death": False, "turn_taken": False}

        target_lower = target_name_str.lower()

        # Specific interactions in the MRI Scan Room
        if current_room_name == "MRI Scan Room":
            # Case 1: Forcing the Morgue Door
            if target_lower == "morgue door":
                morgue_room_data = self.get_room_data("Morgue") # Check world state for Morgue
                mri_hazard = None
                mri_hazard_id = None
                if self.hazard_engine:
                    for h_id, h_instance in self.hazard_engine.active_hazards.items():
                        if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI:
                            mri_hazard = h_instance
                            mri_hazard_id = h_id
                            break
                
                if morgue_room_data and not morgue_room_data.get("locked", True): # Check if already unlocked
                    response_messages.append("The Morgue door is already open.")
                    turn_taken = False
                elif mri_hazard and mri_hazard_id:
                    response_messages.append(color_text("You brace yourself and heave against the heavy Morgue door...", "default"))
                    # Trigger the MRI hazard sequence
                    if self.hazard_engine:
                        self.player['mri_qte_failures'] = 0 # Reset counter for this sequence
                        self.hazard_engine._set_hazard_state(mri_hazard_id, "door_force_attempt_reaction", response_messages)
                        # The hazard state will then trigger the first QTE via its autonomous action
                        # The messages from _set_hazard_state will be added to response_messages
                else:
                    response_messages.append("You can't seem to force the Morgue door right now, or the MRI isn't responding.")
                    turn_taken = False
            
            # Case 2: Forcing the Stairwell Door
            elif target_lower == "stairwell door" or target_lower == "stairwell":
                stairwell_room_data_world = self.current_level_rooms.get("Stairwell")
                if stairwell_room_data_world and not stairwell_room_data_world.get("locked", True):
                    response_messages.append("The door to the Stairwell is already open.")
                    turn_taken = False
                elif stairwell_room_data_world: # It's locked, try to force
                    counter_key = f"{current_room_name}_Stairwell_force_attempts"
                    attempts = self.interaction_counters.get(counter_key, 0) + 1
                    self.interaction_counters[counter_key] = attempts

                    if attempts >= self.game_data.STAIRWELL_DOOR_FORCE_THRESHOLD:
                        stairwell_room_data_world["locked"] = False # Unlock in world state
                        response_messages.append(color_text("With a final, shuddering groan, the door to the Stairwell creaks open!", "success"))
                        logger.info(f"Stairwell door forced open after {attempts} attempts.")
                        # Optionally reset counter if you want it to be re-forceable (though unlikely for a door)
                        # self.interaction_counters.pop(counter_key, None) 
                    else:
                        remaining_attempts = self.game_data.STAIRWELL_DOOR_FORCE_THRESHOLD - attempts
                        feedback = "You slam your shoulder against the door. It groans but holds fast."
                        if remaining_attempts == 1:
                            feedback += " It feels like one more good push might do it!"
                        else:
                            feedback += f" It feels a little looser. Maybe {remaining_attempts} more tries?"
                        response_messages.append(color_text(feedback, "default"))
                        logger.info(f"Attempt {attempts} to force Stairwell door. {remaining_attempts} more needed.")
                else: # Should not happen if Stairwell room exists
                    response_messages.append(f"You try to force the '{target_name_str}', but something is wrong with its definition.")
                    turn_taken = False
            
            # Other targets in MRI room
            else:
                response_messages.append(f"You can't force '{target_name_str}' in this way here.")
                turn_taken = False
        
        # Generic force/break logic for other rooms (can be expanded or use existing _command_break)
        elif self.game_data.ACTION_BREAK and hasattr(self, '_command_break'): 
            return self._command_break(target_name_str) # Delegate to existing break
        else:
            response_messages.append(f"You can't force '{target_name_str}'.")
            turn_taken = False

        final_message = "\n".join(filter(None, response_messages))
        return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_action}

    def _command_break(self, target_name_str):
        """Handles the player attempting to break a piece of furniture."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        response_messages = []
        turn_taken = True # Attempting to break something takes a turn by default
        death_triggered = False

        if not target_name_str:
            return {"message": "Break what?", "death": False, "turn_taken": False}

        target_furniture_dict = self._get_furniture_piece(current_room_data, target_name_str)

        if not target_furniture_dict:
            return {"message": f"You don't see '{target_name_str}' here to break.", "death": False, "turn_taken": False}

        furniture_name = target_furniture_dict.get("name")
        if not target_furniture_dict.get("is_breakable"):
            response_messages.append(f"The {furniture_name} doesn't look like it can be forced open or broken easily.")
            # Still takes a turn for trying
        else:
            # Track break attempts or integrity
            integrity_key = f"{current_room_name}_{furniture_name}_integrity"
            # Get integrity from furniture definition, default to 1 if not specified
            initial_integrity = target_furniture_dict.get("break_integrity", 1)
            current_integrity = self.interaction_counters.get(integrity_key, initial_integrity)

            if current_integrity <= 0: # Already broken
                response_messages.append(f"The {furniture_name} is already broken.")
                turn_taken = False # Doesn't take a turn if already broken
            else:
                response_messages.append(f"You attempt to force the {furniture_name}...")
                
                # For now, assume each attempt reduces integrity by 1.
                # Could be modified by player strength, tools, etc.
                current_integrity -= 1
                self.interaction_counters[integrity_key] = current_integrity

                if current_integrity <= 0: # Successfully broken
                    response_messages.append(color_text(target_furniture_dict.get("on_break_success_message", f"The {furniture_name} splinters and breaks open!"), "success"))
                    
                    # Mark as no longer breakable (or set a "broken" state if furniture can have states)
                    # For simplicity, we rely on integrity_key counter.
                    # If you had a 'state' in furniture_dict in current_level_rooms, you'd update it here.

                    # Spill items
                    items_to_spill_defs = target_furniture_dict.get("on_break_spill_items", [])
                    if items_to_spill_defs:
                        spilled_item_names_for_msg = []
                        for spill_entry in items_to_spill_defs:
                            item_name_to_add = spill_entry.get("name")
                            quantity_str = spill_entry.get("quantity", "1")
                            num_to_add = 1
                            if item_name_to_add == "Dust Cloud Puff": # Handle Dust Cloud Puff specifically
                                if self.hazard_engine:
                                    dust_message = color_text("A cloud of dust erupts from the broken furniture, briefly obscuring your vision!", "warning")
                                    # Directly call HazardEngine to apply temporary effect
                                    temp_effect_msgs = self.hazard_engine.apply_temporary_room_effect(
                                        room_name=current_room_name,
                                        effect_key="visibility",
                                        temp_value="patchy_smoke", # Or "dim", "hazy"
                                        duration_turns=1,
                                        effect_message=dust_message # Pass the message to be included
                                    )
                                    response_messages.extend(temp_effect_msgs)
                                    logger.info(f"Dust cloud effect triggered in {current_room_name} from breaking {furniture_name}.")
                                # No item instance is created for Dust Cloud Puff
                                continue # Move to next spill_entry
                            if isinstance(quantity_str, str) and "d" in quantity_str: # e.g., "1d3"
                                try:
                                    parts = quantity_str.split('d')
                                    num_dice, dice_sides = int(parts[0]), int(parts[1])
                                    num_to_add = sum(random.randint(1, dice_sides) for _ in range(num_dice))
                                except:
                                    num_to_add = 1 # Fallback
                            elif isinstance(quantity_str, int):
                                num_to_add = quantity_str
                            
                            for _ in range(num_to_add):
                                if item_name_to_add:
                                    # Add item to the room (not in a container, visible)
                                    # Ensure the item definition exists if it's a new type
                                    if item_name_to_add not in self.current_level_items_world_state:
                                        master_spill_item_data = self._get_item_data(item_name_to_add)
                                        if master_spill_item_data:
                                            self.current_level_items_world_state[item_name_to_add] = copy.deepcopy(master_spill_item_data)
                                        else:
                                            self.current_level_items_world_state[item_name_to_add] = {
                                                "description": f"Some {item_name_to_add.lower()} from the broken {furniture_name}.",
                                                "takeable": False, 
                                                "level": self.player['current_level']
                                            }
                                            logger.info(f"Created temporary world state for spilled effect item '{item_name_to_add}'.")
                                    
                                    self.current_level_items_world_state[item_name_to_add].update({
                                        "location": current_room_name,
                                        "container": None, 
                                        "is_hidden": False 
                                    })
                                    self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name_to_add)
                                    if item_name_to_add != "Dust Cloud Puff": # Don't add "Dust Cloud Puff" to this message
                                        spilled_item_names_for_msg.append(item_name_to_add.capitalize())
                                    logger.info(f"Item '{item_name_to_add}' spilled from broken {furniture_name} in {current_room_name}.")
                                    # END Copied section
                        if spilled_item_names_for_msg: # Only add this message if there are actual items
                            response_messages.append(f"Contents spill out: {', '.join(spilled_item_names_for_msg)}.")
                    
                    # Trigger hazard
                    hazard_to_trigger_def = target_furniture_dict.get("on_break_trigger_hazard")
                    if hazard_to_trigger_def and isinstance(hazard_to_trigger_def, dict):
                        if random.random() < hazard_to_trigger_def.get("chance", 1.0): # Default 100% chance if defined
                            if self.hazard_engine:
                                new_haz_id = self.hazard_engine._add_active_hazard(
                                    hazard_type=hazard_to_trigger_def.get("type"),
                                    location=current_room_name,
                                    initial_state_override=hazard_to_trigger_def.get("initial_state"),
                                    target_object_override=hazard_to_trigger_def.get("object_name_override"),
                                    support_object_override=hazard_to_trigger_def.get("support_object_override")
                                )
                                if new_haz_id:
                                    response_messages.append(color_text(f"Your destructive action on the {furniture_name} seems to have caused a new problem!", "warning"))
                                    # Hazard engine will produce its own messages on its turn update
                            else:
                                self.logger.warning("Hazard engine not available to trigger hazard from break.")
                    
                    # Play sound (conceptual, UI would handle actual sound)
                    # if target_furniture_dict.get("on_break_sound"): self.play_sound_event(target_furniture_dict["on_break_sound"])

                else: # Failed to break it completely yet, but damaged it
                    response_messages.append(color_text(target_furniture_dict.get("break_failure_message", f"You damage the {furniture_name}, but it still holds."), "warning"))

        # Check for broader environmental reactions to the "break" action itself
        if self.hazard_engine:
            # Pass the canonical furniture name as the target of the break action
            hazard_resp = self.hazard_engine.check_action_hazard(self.game_data.ACTION_BREAK, furniture_name, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): response_messages.append(hazard_resp["message"])
                if hazard_resp.get("death"): death_triggered = True
        
        return {"message": "\n".join(filter(None, response_messages)), "death": death_triggered, "turn_taken": turn_taken}

    def _command_move(self, direction_str):
        """Handles moving the player to a new room."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        current_room_name = self.player.get('location')
        current_room_data = self.get_room_data(current_room_name)

        if not current_room_data:
            return {"message": color_text("Error: Current room data is missing.", "error"), "death": False, "turn_taken": False}

        exits = current_room_data.get('exits', {})
        normalized_direction = direction_str.lower()
        destination_room_name = None

        # Direction normalization and aliasing
        for exit_dir, dest_name in exits.items():
            if normalized_direction == exit_dir.lower() or \
            (normalized_direction == "n" and exit_dir.lower() == "north") or \
            (normalized_direction == "s" and exit_dir.lower() == "south") or \
            (normalized_direction == "e" and exit_dir.lower() == "east") or \
            (normalized_direction == "w" and exit_dir.lower() == "west") or \
            (normalized_direction == "u" and exit_dir.lower() in ["up", "upstairs"]) or \
            (normalized_direction == "d" and exit_dir.lower() in ["down", "downstairs"]):
                destination_room_name = dest_name
                break

        if not destination_room_name:
            valid_exits_str = ", ".join(exits.keys())
            return {"message": f"You can't go '{direction_str}'. Valid exits are: {valid_exits_str}", "death": False, "turn_taken": False}

        destination_room_data = self.get_room_data(destination_room_name)
        if not destination_room_data:
            logger.error(f"Data for destination room '{destination_room_name}' not found.")
            return {"message": color_text(f"Error: The path to '{destination_room_name}' seems to lead nowhere.", "error"), "death": False, "turn_taken": False}

        # Special case: Front Porch → Foyer locked door
        if current_room_name == "Front Porch" and destination_room_name == "Foyer" and destination_room_data.get('locked', False):
            return {
                "message": color_text("The front door is solidly locked. You'll need to unlock it first.", "warning"),
                "death": False,
                "turn_taken": False
            }

        unlock_message = ""
        if destination_room_data.get('locked', False):
            required_key_name = destination_room_data.get('unlocks_with')
            if required_key_name and required_key_name in self.player.get('inventory', []):
                self.current_level_rooms[destination_room_name]['locked'] = False
                unlock_message = color_text(f"You unlock the way to {destination_room_name} with the {required_key_name}.", "success")
            else:
                key_needed_msg = f"The way to {destination_room_name} is locked."
                if required_key_name:
                    key_needed_msg += f" You might need the {required_key_name}."
                return {"message": color_text(key_needed_msg, "warning"), "death": False, "turn_taken": False}

        # Level exit logic
        level_id = self.player.get("current_level", 1)
        level_req = self.game_data.LEVEL_REQUIREMENTS.get(level_id, {})
        is_level_exit_room = level_req.get("exit_room") == current_room_name
        is_attempting_level_exit = False
        if level_req.get("next_level_start_room") and destination_room_name == level_req.get("next_level_start_room"):
            is_attempting_level_exit = True

        if is_level_exit_room and is_attempting_level_exit:
            required_evidence_for_level = set(level_req.get("evidence_needed", []))
            player_evidence_inventory = {item for item in self.player.get("inventory", []) if self._get_item_data(item) and self._get_item_data(item).get("is_evidence")}
            if not required_evidence_for_level.issubset(player_evidence_inventory):
                missing_evidence_str = ", ".join(required_evidence_for_level - player_evidence_inventory)
                return {
                    "message": color_text(f"A sense of dread stops you. You feel there's crucial evidence still missing before you can leave this place. Perhaps you still need: {missing_evidence_str}.", "warning"),
                    "death": False,
                    "turn_taken": False
                }
            next_level_id_val = level_req.get("next_level_id")
            if next_level_id_val is not None:
                return {
                    "message": color_text(f"You've gathered what you need from {level_req.get('name', 'this area')}. You proceed towards {destination_room_name}...", "success"),
                    "death": False,
                    "turn_taken": True,
                    "level_transition_data": {
                        "next_level_id": next_level_id_val,
                        "next_level_start_room": destination_room_name,
                        "completed_level_id": level_id
                    }
                }
            else:
                self.game_won = True
                self.is_game_over = True
                return {
                    "message": color_text("You've gathered all you could and step out, a grim understanding dawning... You've survived the final ordeal.", "success"),
                    "death": False,
                    "turn_taken": True,
                    "new_location": destination_room_name
                }

        # Regular movement within the same level
        previous_location = self.player['location']
        self.player['location'] = destination_room_name
        self.player.setdefault('visited_rooms', set()).add(destination_room_name)

        move_message = f"You move from {previous_location} to {destination_room_name}."
        full_message = f"{unlock_message}\n{move_message}".strip()
        room_description = self.get_room_description(destination_room_name)
        full_message += f"\n\n{room_description}"

        hazard_on_entry_messages = []
        death_from_entry_hazard = False

        # Hazard checks: weak floorboards and additional floor hazards
        if self.hazard_engine:
            player_weight = self._calculate_player_inventory_weight()
            entry_hazard_result = self.hazard_engine.check_weak_floorboards_on_move(destination_room_name, player_weight)
            if entry_hazard_result and isinstance(entry_hazard_result, dict):
                if entry_hazard_result.get("message"):
                    hazard_on_entry_messages.append(entry_hazard_result["message"])
                if entry_hazard_result.get("death"):
                    death_from_entry_hazard = True
                if entry_hazard_result.get("room_transfer_to"):
                    self.player['location'] = entry_hazard_result["room_transfer_to"]
                    self.player['visited_rooms'].add(self.player['location'])
                    hazard_on_entry_messages.append(color_text(f"You are now in {self.player['location']}!", "warning"))
                    hazard_on_entry_messages.append(self.get_room_description(self.player['location']))
            # Additional floor hazard check after move (if not dead)
            if not death_from_entry_hazard:
                floor_hazard_msgs_list = []
                self.hazard_engine._check_floor_hazards_on_move(self.player['location'], floor_hazard_msgs_list)
                if floor_hazard_msgs_list:
                    hazard_on_entry_messages.extend(floor_hazard_msgs_list)
                if self.player['hp'] <= 0 and not death_from_entry_hazard:
                    death_from_entry_hazard = True

        if hazard_on_entry_messages:
            full_message += "\n" + "\n".join(hazard_on_entry_messages)

        return {
            "message": full_message,
            "death": death_from_entry_hazard,
            "turn_taken": True,
            "new_location": self.player['location']
        }

    def _command_examine(self, target_name_str):
        """Handles examining items, furniture, or the room itself."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        target_name_lower = target_name_str.lower()
        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        inventory = self.player.get('inventory', [])

        action_message_parts = []
        death_triggered = False
        turn_taken_by_examine = False # Examining usually doesn't take a turn unless a hazard is triggered
        item_revealed_or_transformed = False

        # 1. Examine item in inventory
        item_in_inventory = next((item for item in inventory if item.lower() == target_name_lower), None)
        if item_in_inventory:
            item_master_data = self._get_item_data(item_in_inventory)
            if item_master_data:
                description = item_master_data.get('examine_details', item_master_data.get('description', f"It's a {item_in_inventory}."))
                action_message_parts.append(description)
                transform_target = item_master_data.get('transforms_into_on_examine')
                if transform_target:
                    if self._transform_item_in_inventory(item_in_inventory, transform_target):
                        action_message_parts.append(color_text(f"Upon closer inspection, it's actually a {transform_target}!", "special"))
                        item_revealed_or_transformed = True
                        turn_taken_by_examine = True # Transforming an item might be considered a turn
                        new_item_info = self._get_item_data(transform_target)
                        if new_item_info and new_item_info.get("is_evidence"):
                            self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
            else:
                action_message_parts.append(f"You look at the {item_in_inventory}. Nothing new comes to mind.")
            return {
                "message": "\n".join(action_message_parts),
                "death": death_triggered,
                "turn_taken": turn_taken_by_examine,
                "item_revealed": item_revealed_or_transformed
            }

        # 2. Examine item/object/furniture in the room
        item_to_examine_in_room = None
        item_data_in_room = None

        for item_name_key, item_data_val in self.current_level_items_world_state.items():
            if item_name_key.lower() == target_name_lower and item_data_val.get('location') == current_room_name:
                is_visible = not item_data_val.get('container') and not item_data_val.get('is_hidden')
                is_revealed = item_name_key in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible or is_revealed:
                    item_to_examine_in_room = item_name_key
                    item_data_in_room = item_data_val
                    break
        
        if item_to_examine_in_room: # Examining an item in the room
            master_item_data = self._get_item_data(item_to_examine_in_room)
            description = master_item_data.get('examine_details', master_item_data.get('description', f"It's a {item_to_examine_in_room}."))
            action_message_parts.append(description)
            # Hazard check for examining this specific item
            if self.hazard_engine:
                hazard_result = self.hazard_engine.check_action_hazard('examine', item_to_examine_in_room, current_room_name)
                if hazard_result and isinstance(hazard_result, dict):
                    if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                    if hazard_result.get("death"): death_triggered = True
                    if hazard_result.get("message") or death_triggered: turn_taken_by_examine = True
        else: # Examine furniture, room object, or room itself
            feature_to_examine = None
            # feature_type = None # Not strictly needed for logic but good for debugging
            if current_room_data.get('furniture'):
                for furn_dict in current_room_data['furniture']:
                    if furn_dict.get('name', '').lower() == target_name_lower:
                        feature_to_examine = furn_dict['name']
                        # feature_type = 'furniture'
                        break
            if not feature_to_examine and current_room_data.get('objects'):
                for obj_name in current_room_data['objects']:
                    if obj_name.lower() == target_name_lower:
                        feature_to_examine = obj_name
                        # feature_type = 'object'
                        break

            if feature_to_examine:
                examine_detail_key = feature_to_examine # Use the cased name from room_data
                details = current_room_data.get('examine_details', {}).get(examine_detail_key)
                action_message_parts.append(details or f"You see nothing special about the {feature_to_examine}.")

                # Special logic for "fireplace" revealing "loose brick"
                if feature_to_examine.lower() == "fireplace" and current_room_name == "Living Room":
                    room_flags = self.current_level_rooms[current_room_name].get("interaction_flags", {})
                    loose_brick_taken = room_flags.get("loose_brick_taken", False)
                    cavity_revealed = room_flags.get("fireplace_cavity_revealed", False)
                    loose_brick_name = self.game_data.ITEM_LOOSE_BRICK
                    brick_world_data = self.current_level_items_world_state.get(loose_brick_name)

                    if not loose_brick_taken and brick_world_data and brick_world_data.get('location') == current_room_name:
                        if brick_world_data.get('is_hidden') or loose_brick_name not in self.revealed_items_in_rooms.get(current_room_name, set()):
                            brick_world_data['is_hidden'] = False
                            self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(loose_brick_name)
                            action_message_parts.append(color_text("One brick near the bottom looks loose and out of place.", "special"))
                            item_revealed_or_transformed = True
                        else:
                             action_message_parts.append(color_text("The loose brick is still there.", "default"))
                    elif loose_brick_taken and not cavity_revealed:
                        action_message_parts.append(color_text("Where the loose brick was, you now see a dark cavity within the fireplace.", "special"))
                        for furn_idx, furn_dict_iter in enumerate(self.current_level_rooms[current_room_name].get("furniture", [])):
                            if furn_dict_iter.get("name") == "fireplace cavity" and furn_dict_iter.get("is_hidden_container"):
                                self.current_level_rooms[current_room_name]["furniture"][furn_idx]["is_hidden_container"] = False
                                break
                        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add("fireplace cavity")
                        if "interaction_flags" in self.current_level_rooms[current_room_name]:
                             self.current_level_rooms[current_room_name]["interaction_flags"]["fireplace_cavity_revealed"] = True
                        item_revealed_or_transformed = True
                    elif loose_brick_taken and cavity_revealed:
                        action_message_parts.append(color_text("The cavity where the loose brick was is still there. It might be worth searching.", "default"))

                # Hazard check for examining this feature
                if self.hazard_engine:
                    hazard_result = self.hazard_engine.check_action_hazard('examine', feature_to_examine, current_room_name)
                    if hazard_result and isinstance(hazard_result, dict):
                        if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                        if hazard_result.get("death"): death_triggered = True
                        if hazard_result.get("message") or death_triggered: turn_taken_by_examine = True
            
            elif target_name_lower == current_room_name.lower() or target_name_str == "": # Examine current room
                action_message_parts.append(self.get_room_description(current_room_name))
                # Examining the room itself usually doesn't trigger hazards or take a turn unless defined
            else:
                action_message_parts.append(f"You don't see '{target_name_str}' here to examine.")

        return {
            "message": "\n".join(filter(None, action_message_parts)),
            "death": death_triggered,
            "turn_taken": turn_taken_by_examine,
            "item_revealed": item_revealed_or_transformed
        }
    
    def _command_take(self, item_name_str):
        """Handles taking an item from the room."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        item_name_lower = item_name_str.lower()
        current_room_name = self.player['location']
        action_message_parts = []
        death_triggered = False
        turn_taken = False
        item_taken_actual_name = None

        item_to_take_cased = None
        item_world_data = None

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
                    action_message_parts.append(f"You already have the {item_to_take_cased}.")
                else:
                    self.player['inventory'].append(item_to_take_cased)
                    item_taken_actual_name = item_to_take_cased
                    item_world_data['location'] = 'inventory'
                    item_world_data.pop('container', None)
                    item_world_data['is_hidden'] = False
                    if current_room_name in self.revealed_items_in_rooms:
                        self.revealed_items_in_rooms[current_room_name].discard(item_to_take_cased)
                    action_message_parts.append(f"You take the {item_to_take_cased}.")
                    turn_taken = True

                    if master_item_data.get("is_evidence"):
                        if self.achievements_system and not self.achievements_system.has_evidence(item_to_take_cased):
                            self.achievements_system.record_evidence(
                                item_to_take_cased, master_item_data.get('name', item_to_take_cased),
                                master_item_data.get('description', '')
                            )
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
                        self.player.setdefault("found_evidence_count", 0)
                        self.player["found_evidence_count"] += 1
                        self.player.setdefault("evidence_found_this_level", []).append(item_to_take_cased) # Track for interlevel

                        narrative_flag = master_item_data.get("narrative_flag_on_collect")
                        narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag: self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet: self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)

                    if item_to_take_cased.lower() == self.game_data.ITEM_LOOSE_BRICK.lower() and current_room_name == "Living Room":
                        if "interaction_flags" in self.current_level_rooms[current_room_name]:
                             self.current_level_rooms[current_room_name]["interaction_flags"]["loose_brick_taken"] = True
                        basement_key_name = self.game_data.ITEM_BASEMENT_KEY
                        key_world_data = self.current_level_items_world_state.get(basement_key_name)
                        if key_world_data and key_world_data.get('location') == "Living Room" and key_world_data.get('is_hidden'):
                            key_world_data['is_hidden'] = False
                            self.revealed_items_in_rooms.setdefault("Living Room", set()).add(basement_key_name)
                            action_message_parts.append(color_text("As you pull the brick free, something metallic clatters out - the Basement Key!", "special"))
                            logger.info("Basement Key revealed after taking loose brick.")
                    
                    if self.hazard_engine:
                        hazard_result = self.hazard_engine.check_action_hazard('take', item_to_take_cased, current_room_name)
                        if hazard_result and isinstance(hazard_result, dict):
                            if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                            if hazard_result.get("death"): death_triggered = True
            else:
                action_message_parts.append(f"You can't take the {item_to_take_cased}.")
        else:
            action_message_parts.append(f"You don't see '{item_name_str}' here to take.")

        return {"message": "\n".join(filter(None, action_message_parts)), "death": death_triggered,
                "turn_taken": turn_taken, "item_taken": item_taken_actual_name if not death_triggered and turn_taken else None}

    def _command_search(self, furniture_name_str):
        """Handles searching a piece of furniture."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        action_message_parts = []
        death_triggered = False
        turn_taken = False
        found_items_for_ui = []

        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        if not current_room_data:
            return {"message": color_text("Error: Room data missing.", "error"), "death": False, "turn_taken": False, "found_items": None}

        target_furniture_dict = self._get_furniture_piece(current_room_data, furniture_name_str)
        canonical_furniture_name = target_furniture_dict.get("name") if target_furniture_dict else None

        if not target_furniture_dict:
            action_message_parts.append(f"You don't see '{furniture_name_str}' to search here.")
        elif not target_furniture_dict.get("is_container"):
            action_message_parts.append(f"You can't search the {canonical_furniture_name}.")
        elif target_furniture_dict.get("is_hidden_container"): # Check if it's a hidden container that's not yet revealed
            action_message_parts.append(f"You don't see a searchable '{furniture_name_str}' here yet.") # Or more generic
        elif target_furniture_dict.get("locked"):
            lock_msg = f"The {canonical_furniture_name} is locked."
            required_key = target_furniture_dict.get("unlocks_with_item") # From furniture definition in room
            if not required_key: # Fallback to check key definitions if not on furniture
                required_key = next((k_name for k_name, k_data in self.current_level_items_master_copy.items()
                                    if k_data.get("is_key") and k_data.get("unlocks", "").lower() == canonical_furniture_name.lower()), None)
            if required_key: lock_msg += f" You might need the {required_key}."
            action_message_parts.append(lock_msg)
        else:
            turn_taken = True
            action_message_parts.append(f"You search the {canonical_furniture_name}...")
            items_newly_found_names = []
            for item_name, item_world_data in self.current_level_items_world_state.items():
                if item_world_data.get('location') == current_room_name and \
                   (item_world_data.get('container') or '').lower() == (canonical_furniture_name.lower() if canonical_furniture_name else "") and \
                   item_name not in self.player['inventory'] and \
                   item_world_data.get('is_hidden', False): # Only find items that were hidden in this container
                    items_newly_found_names.append(item_name)
                    found_items_for_ui.append(item_name) # For UI button generation
                    item_world_data['is_hidden'] = False # Reveal it
                    self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name)
                    logger.info(f"Item '{item_name}' revealed in {canonical_furniture_name} in {current_room_name}.")
                    master_item_data = self._get_item_data(item_name)
                    if master_item_data and master_item_data.get("is_evidence"):
                        if self.achievements_system and not self.achievements_system.has_evidence(item_name):
                            self.achievements_system.record_evidence(item_name, master_item_data.get('name', item_name), master_item_data.get('description', ''))
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
                        self.player.setdefault("evidence_found_this_level", []).append(item_name)
                        narrative_flag = master_item_data.get("narrative_flag_on_collect")
                        narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag: self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet: self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)
            if items_newly_found_names:
                action_message_parts.append(f"You find: {', '.join(item.capitalize() for item in items_newly_found_names)}.")
            else:
                action_message_parts.append("You find nothing new of interest.")
            if self.hazard_engine:
                hazard_result = self.hazard_engine.check_action_hazard('search', canonical_furniture_name, current_room_name)
                if hazard_result and isinstance(hazard_result, dict):
                    if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                    if hazard_result.get("death"): death_triggered = True
        return {
            "message": "\n".join(filter(None, action_message_parts)), "death": death_triggered,
            "turn_taken": turn_taken, "found_items": found_items_for_ui if not death_triggered and turn_taken and found_items_for_ui else None
        }
    
    def _command_use(self, words):
        """Handles using an item, potentially on a target."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        message_parts = []
        death_triggered = False
        turn_taken = True
        qte_triggered_by_use = None

        item_to_use_str = None
        target_object_str = None

        if not words:
            return {"message": "Use what?", "death": False, "turn_taken": False}

        if "on" in words:
            try:
                on_index = words.index("on")
                item_to_use_str = " ".join(words[:on_index])
                target_object_str = " ".join(words[on_index+1:])
            except ValueError: # "on" might be part of an item name
                item_to_use_str = " ".join(words)
        else:
            item_to_use_str = " ".join(words)

        item_in_inventory_cased = next((inv_item for inv_item in self.player['inventory'] if inv_item.lower() == item_to_use_str.lower()), None)
        if not item_in_inventory_cased:
            return {"message": f"You don't have '{item_to_use_str}'.", "death": False, "turn_taken": False}

        item_master_data = self._get_item_data(item_in_inventory_cased)
        if not item_master_data:
            logger.error(f"Item '{item_in_inventory_cased}' in inventory but no master data found.")
            return {"message": "Error with item data.", "death": False, "turn_taken": False}

        item_type = item_master_data.get("type") # For hazard interactions using item_used_type
        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        interaction_processed = False
        hazard_specific_interaction_occurred = False
        targeted_hazard_instance = None
        targeted_hazard_id = None

        # --- NEW: Furniture-Specific Item Interaction (e.g., Key Card on Control Desk) ---
        if target_object_str and current_room_data:
            targeted_furniture_dict = self._get_furniture_piece(current_room_data, target_object_str)
            if targeted_furniture_dict:
                furniture_name_cased = targeted_furniture_dict.get("name")
                interaction_rule = targeted_furniture_dict.get("use_item_interaction")
                
                if interaction_rule and isinstance(interaction_rule, dict):
                    required_item_names = interaction_rule.get("item_names_required", [])
                    if isinstance(required_item_names, str): required_item_names = [required_item_names] # Ensure list

                    if item_in_inventory_cased in required_item_names:
                        interaction_processed = True
                        action_effect = interaction_rule.get("action_effect")
                        success_msg_template = interaction_rule.get("message_success", "Using {item_name} on {target_name} works.")
                        message_parts.append(color_text(success_msg_template.format(item_name=item_in_inventory_cased, target_name=furniture_name_cased), "success"))

                        if action_effect == "activate_mri_hazard":
                            if self.hazard_engine:
                                mri_hazard_instance_id = None
                                # Find the MRI hazard (assuming its type is HAZARD_TYPE_MRI and it's unique or findable)
                                for h_id, h_instance in self.hazard_engine.active_hazards.items():
                                    if h_instance.get('type') == self.game_data.HAZARD_TYPE_MRI:
                                        mri_hazard_instance_id = h_id
                                        break
                                if mri_hazard_instance_id:
                                    # Set MRI to an active state, e.g., "power_surge"
                                    self.hazard_engine._set_hazard_state(mri_hazard_instance_id, "power_surge", message_parts)
                                    logger.info(f"MRI hazard {mri_hazard_instance_id} activated to 'power_surge' by using {item_in_inventory_cased} on {furniture_name_cased}.")
                                    # Check if state change caused death (e.g., if player was in MRI room with metal)
                                    if self.is_game_over: death_triggered = True
                                else:
                                    message_parts.append(color_text("Error: Could not find the MRI machine to activate.", "error"))
                            else:
                                message_parts.append(color_text("Error: Hazard system not available.", "error"))
                        
                        # Handle item consumption if defined for this furniture interaction
                        if item_master_data.get("consumable_on_use_for_target", {}).get(furniture_name_cased.lower(), item_master_data.get("consumable_on_use", False)):
                            self.player['inventory'].remove(item_in_inventory_cased)
                            message_parts.append(f"The {item_in_inventory_cased} is used up.")
                    else: # Item doesn't match required items for this furniture
                        interaction_processed = True # Still counts as an attempt to use on the furniture
                        fail_msg_template = interaction_rule.get("message_fail_item", "That item doesn't work with the {target_name}.")
                        message_parts.append(color_text(fail_msg_template.format(target_name=furniture_name_cased), "warning"))
                        turn_taken = True # Attempting to use an incorrect item still takes a turn

        # --- Existing Hazard-Specific Item Interaction (if not handled by furniture interaction) ---
        if not interaction_processed and target_object_str and self.hazard_engine:
            for h_id, h_instance in self.hazard_engine.active_hazards.items():
                if h_instance['location'] == current_room_name and (
                    h_instance.get('object_name', '').lower() == target_object_str.lower() or
                    h_instance.get('support_object', '').lower() == target_object_str.lower() or
                    h_instance.get('name', '').lower() == target_object_str.lower()):
                    targeted_hazard_instance = h_instance
                    targeted_hazard_id = h_id
                    break

            if targeted_hazard_instance and item_type:
                hazard_interaction_rules = targeted_hazard_instance['data'].get('player_interaction', {}).get('use', [])
                if not isinstance(hazard_interaction_rules, list):
                    hazard_interaction_rules = [hazard_interaction_rules] # Ensure list
                
                for rule in hazard_interaction_rules:
                    if isinstance(rule, dict) and rule.get('item_used_type') == item_type:
                        if random.random() < rule.get('chance_to_trigger', 1.0):
                            interaction_processed = True
                            hazard_specific_interaction_occurred = True
                            interaction_message = rule.get('message', f"Using {item_in_inventory_cased} on {targeted_hazard_instance['object_name']} has an effect.")
                            message_parts.append(color_text(interaction_message.format(object_name=targeted_hazard_instance['object_name']), "special"))
                            new_hazard_state = rule.get('target_state')
                            if new_hazard_state is not None:
                                self.hazard_engine._set_hazard_state(targeted_hazard_id, new_hazard_state, message_parts)
                                if self.is_game_over:
                                    death_triggered = True
                                    break
                            if rule.get("qte_type_to_trigger") and not death_triggered:
                                qte_context = rule.get("qte_context", {})
                                qte_context.update({
                                    "qte_source_hazard_id": targeted_hazard_id,
                                    "qte_source_hazard_state": targeted_hazard_instance['state'],
                                })
                                qte_triggered_by_use = {
                                    "type": rule["qte_type_to_trigger"],
                                    "duration": rule.get("qte_duration", self.game_data.QTE_DEFAULT_DURATION),
                                    "context": qte_context
                                }
                                message_parts.append(color_text(qte_context.get("initial_qte_message", "Quick! React!"), "hazard"))
                            if item_master_data.get("consumable_on_use_for_target", {}).get(target_object_str.lower(), item_master_data.get("consumable_on_use", False)):
                                self.player['inventory'].remove(item_in_inventory_cased)
                                message_parts.append(f"The {item_in_inventory_cased} is used up.")
                            break
                if death_triggered or hazard_specific_interaction_occurred:
                    final_message = "\n".join(filter(None, message_parts))
                    return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_use}

        # --- Existing Special Case: Bludworth's House Key on Front Door (if not handled above) ---
        if not interaction_processed and target_object_str and item_in_inventory_cased == "Bludworth's House Key" and \
        target_object_str.lower() == "front door" and current_room_name == "Front Porch":
            front_door_object_exists = any(obj.lower() == "front door" for obj in self._get_current_room_data().get("objects", []))
            if not front_door_object_exists:
                message_parts.append("There's no front door here to use the key on.")
                turn_taken = False
            else:
                interaction_processed = True # Mark as processed
                foyer_data_world = self.current_level_rooms.get("Foyer")
                if foyer_data_world and foyer_data_world.get("locked"):
                    foyer_data_world["locked"] = False 
                    msg_key_use = item_master_data.get("use_result", {}).get("front door", color_text("The front door is now unlocked.", "success"))
                    message_parts.append(msg_key_use)
                    logger.info("Front door unlocked using Bludworth's House Key via 'use' command.")
                elif foyer_data_world and not foyer_data_world.get("locked"):
                    message_parts.append("The front door is already unlocked.")
                    turn_taken = False
                else:
                    message_parts.append(color_text("Error with Foyer data or the door state.", "error"))
                    turn_taken = False

        # --- Existing Generic Item-on-Target and General Use (if not handled above) ---
        if not interaction_processed:
            if target_object_str:
                allowed_targets_for_item_def = item_master_data.get("use_on", [])
                actual_target_cased = None
                if isinstance(allowed_targets_for_item_def, list):
                    actual_target_cased = next((dt for dt in allowed_targets_for_item_def if dt.lower() == target_object_str.lower()), None)
                
                if actual_target_cased:
                    examinable_room_targets = self.get_examinable_targets_in_room()
                    target_is_present_and_interactable = any(ert.lower() == actual_target_cased.lower() for ert in examinable_room_targets)
                    if target_is_present_and_interactable:
                        use_results_dict = item_master_data.get("use_result", {})
                        result_msg_for_target = use_results_dict.get(actual_target_cased,
                            use_results_dict.get(actual_target_cased.lower(),
                                f"Using the {item_in_inventory_cased} on the {actual_target_cased} doesn't seem to do anything special."))
                        message_parts.append(result_msg_for_target)
                        if item_in_inventory_cased == self.game_data.ITEM_TOOLBELT and actual_target_cased == "fireplace cavity":
                            self.interaction_counters["fireplace_reinforced"] = True
                            logger.info("Fireplace cavity reinforced with toolbelt.")
                        consumable_rules = item_master_data.get("consumable_on_use_for_target", {})
                        if consumable_rules.get(actual_target_cased.lower(), item_master_data.get("consumable_on_use", False)):
                            self.player['inventory'].remove(item_in_inventory_cased)
                            message_parts.append(f"The {item_in_inventory_cased} is used up.")
                            logger.info(f"Item '{item_in_inventory_cased}' consumed after using on '{actual_target_cased}'.")
                    else:
                        message_parts.append(f"You don't see '{target_object_str}' here to use the {item_in_inventory_cased} on.")
                        turn_taken = False
                else:
                    message_parts.append(f"You can't use the {item_in_inventory_cased} on '{target_object_str}'.")
                    turn_taken = False # If no valid target or interaction rule
            elif not target_object_str: # General use (no target)
                general_use_effect_msg = item_master_data.get("general_use_effect_message")
                if general_use_effect_msg:
                    message_parts.append(general_use_effect_msg)
                    if item_master_data.get("heal_amount"):
                        heal_val = item_master_data["heal_amount"]
                        old_hp = self.player['hp']
                        self.player['hp'] = min(self.player['max_hp'], old_hp + heal_val)
                        message_parts.append(f" You heal for {self.player['hp'] - old_hp} HP.")
                        logger.info(f"Player used {item_in_inventory_cased}, healed to {self.player['hp']}.")
                    if item_master_data.get("consumable_on_use"):
                        self.player['inventory'].remove(item_in_inventory_cased)
                        message_parts.append(f"The {item_in_inventory_cased} is used up.")
                        logger.info(f"Item '{item_in_inventory_cased}' consumed (general use).")
                else:
                    message_parts.append(f"You fiddle with the {item_in_inventory_cased}, but nothing specific happens. Try using it 'on' something.")
                    turn_taken = False
        
        # --- Final Hazard Check for "use" action (indirect effects) ---
        if self.hazard_engine and not death_triggered and target_object_str and not hazard_specific_interaction_occurred:
            final_target_for_hazard_check = target_object_str
            if targeted_hazard_instance:
                final_target_for_hazard_check = targeted_hazard_instance.get('object_name', target_object_str)
            elif 'actual_target_cased' in locals() and actual_target_cased:
                final_target_for_hazard_check = actual_target_cased
            hazard_resp = self.hazard_engine.check_action_hazard(
                'use',
                final_target_for_hazard_check,
                current_room_name,
                item_used=item_in_inventory_cased
            )
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): message_parts.append(hazard_resp["message"])
                if hazard_resp.get("death"): death_triggered = True

        final_message = "\n".join(filter(None, message_parts))
        if not final_message and not death_triggered and not qte_triggered_by_use: # If no specific message was generated
            if turn_taken: # If a turn was taken but no clear outcome message
                final_message = "You use the item, but nothing remarkable happens."
            elif not turn_taken and not interaction_processed: # If no turn and not processed, it means it was a failed attempt
                final_message = f"You can't use the {item_in_inventory_cased} like that."

        return {"message": final_message, "death": death_triggered, "turn_taken": turn_taken, "qte_triggered": qte_triggered_by_use}

    def _command_drop(self, item_name_str):
        """Handles dropping an item from inventory."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name_str:
            return {"message": "Drop what?", "turn_taken": False}

        item_name_lower = item_name_str.lower()
        item_to_drop_cased = next((item for item in self.player['inventory'] if item.lower() == item_name_lower), None)

        if not item_to_drop_cased:
            return {"message": f"You don't have '{item_name_str}' to drop.", "turn_taken": False}

        current_room_name = self.player['location']
        self.player['inventory'].remove(item_to_drop_cased)

        item_world_data = self.current_level_items_world_state.get(item_to_drop_cased)
        if item_world_data:
            item_world_data['location'] = current_room_name
            item_world_data['container'] = None 
            item_world_data['is_hidden'] = False 
        else: 
            logger.error(f"Item '{item_to_drop_cased}' dropped from inventory, but no corresponding world state found to update.")
            master_data_for_dropped = self._get_item_data(item_to_drop_cased) # Get from master copy
            if master_data_for_dropped:
                self.current_level_items_world_state[item_to_drop_cased] = copy.deepcopy(master_data_for_dropped)
                self.current_level_items_world_state[item_to_drop_cased].update({
                    "location": current_room_name, "container": None, "is_hidden": False
                })
            else: # Should ideally not happen
                 self.current_level_items_world_state[item_to_drop_cased] = {
                    "location": current_room_name, "container": None, "is_hidden": False,
                    "description": "A dropped item.", "takeable": True
                }
        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_to_drop_cased)
        logger.info(f"Player dropped '{item_to_drop_cased}' in '{current_room_name}'.")
        return {"message": f"You drop the {item_to_drop_cased}.", "turn_taken": True, "item_dropped": item_to_drop_cased}
    
    def _command_unlock(self, target_name_str):
        """Handles unlocking doors or furniture."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        message = ""
        death_triggered = False
        turn_taken = True 
        unlocked_something = False

        target_name_lower = target_name_str.lower()
        current_room_name = self.player['location']
        current_room_data_world = self.current_level_rooms.get(current_room_name)
        inventory = self.player.get('inventory', [])
        
        if not current_room_data_world:
            return {"message": color_text("Error: Current room data missing.", "error"), "death": False, "turn_taken": False}

        available_keys_in_inv = {item_name for item_name in inventory 
                                 if self._get_item_data(item_name) and self._get_item_data(item_name).get("is_key")}
        if not available_keys_in_inv:
            return {"message": "You don't have any keys.", "death": False, "turn_taken": False}
            
        # --- Special case: Unlocking the front door from the Front Porch ---
        if target_name_lower == "front door" and current_room_name == "Front Porch":
            foyer_room_data_world = self.current_level_rooms.get("Foyer") # Check world state
            if "Bludworth's House Key" in available_keys_in_inv:
                if foyer_room_data_world and foyer_room_data_world.get("locked"):
                    foyer_room_data_world["locked"] = False # Unlock in world state
                    message = color_text("You use Bludworth's House Key and unlock the front door.", "success")
                    unlocked_something = True
                    logger.info("Front door unlocked with Bludworth's House Key.")
                elif foyer_room_data_world and not foyer_room_data_world.get("locked"):
                     message = "The front door is already unlocked."
                     turn_taken = False
                else:
                    message = color_text("Error: Foyer room data not found for unlocking.", "error")
                    turn_taken = False
            else:
                message = "You need a specific key for the front door."
                turn_taken = False # No key, no turn taken for just trying
            return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

        found_target_exit = False
        for direction, dest_room_name_master in current_room_data_world.get("exits", {}).items():
            # Check if target_name_str matches direction or destination room name
            if direction.lower() == target_name_lower or dest_room_name_master.lower() == target_name_lower:
                found_target_exit = True
                dest_room_world_data = self.current_level_rooms.get(dest_room_name_master)
                if dest_room_world_data and dest_room_world_data.get("locked"):
                    dest_room_master_data = self.game_data.rooms.get(self.player['current_level'], {}).get(dest_room_name_master, {})
                    required_key_name = dest_room_master_data.get('unlocks_with')
                    if required_key_name and required_key_name in available_keys_in_inv:
                        dest_room_world_data["locked"] = False # Unlock in world state
                        message = color_text(f"You unlock the way to {dest_room_name_master} with the {required_key_name}.", "success")
                        unlocked_something = True
                        logger.info(f"Unlocked exit to '{dest_room_name_master}' from '{current_room_name}' using '{required_key_name}'.")
                    elif required_key_name:
                        message = f"You need the {required_key_name} to unlock the way to {dest_room_name_master}."
                    else:
                        message = f"The way to {dest_room_name_master} is locked, and you're not sure how to open it."
                elif dest_room_world_data:
                    message = f"The way to {dest_room_name_master} is already unlocked."
                    turn_taken = False
                else: # Should not happen if exits are well-defined
                    message = f"The path '{target_name_str}' doesn't seem to lead anywhere valid."
                    turn_taken = False
                break
        if not found_target_exit:
            target_furniture_dict_world = None
            furn_idx_world = -1
            furniture_list_world = current_room_data_world.get("furniture", [])
            for i, furn_dict_world_iter in enumerate(furniture_list_world):
                if furn_dict_world_iter.get("name", "").lower() == target_name_lower:
                    target_furniture_dict_world = furn_dict_world_iter
                    furn_idx_world = i
                    break
            if target_furniture_dict_world and target_furniture_dict_world.get("locked"):
                furn_name_cased = target_furniture_dict_world["name"]
                furn_master_data = None
                for fm_dict_master in self.game_data.rooms.get(self.player['current_level'], {}).get(current_room_name, {}).get("furniture", []):
                    if fm_dict_master.get("name", "") == furn_name_cased:
                        furn_master_data = fm_dict_master
                        break
                required_key_name = furn_master_data.get("unlocks_with_item") if furn_master_data else None
                if required_key_name and required_key_name in available_keys_in_inv:
                    self.current_level_rooms[current_room_name]['furniture'][furn_idx_world]["locked"] = False # Unlock in world state
                    message = color_text(f"You unlock the {furn_name_cased} with the {required_key_name}.", "success")
                    unlocked_something = True
                    logger.info(f"Unlocked furniture '{furn_name_cased}' in '{current_room_name}' using '{required_key_name}'.")
                elif required_key_name:
                    message = f"You need the {required_key_name} to unlock the {furn_name_cased}."
                else:
                    message = f"The {furn_name_cased} is locked, and you're not sure how to open it."
            elif target_furniture_dict_world:
                message = f"The {target_furniture_dict_world['name']} is already unlocked."
                turn_taken = False
            else:
                message = f"You don't see '{target_name_str}' to unlock here."
                turn_taken = False

        if unlocked_something and self.hazard_engine:
            hazard_resp = self.hazard_engine.check_action_hazard('unlock', target_name_str, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): message += "\n" + hazard_resp["message"]
                if hazard_resp.get("death"): death_triggered = True
        return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

    def _command_inventory(self):
        """Displays the player's inventory."""
        inventory = self.player.get('inventory', [])
        if not inventory:
            return {"message": "Your inventory is empty.", "turn_taken": False}
        item_details = []
        for item_name in inventory:
            item_data = self._get_item_data(item_name)
            desc = item_name.capitalize()
            if item_data:
                desc = color_text(desc, "evidence" if item_data.get("is_evidence") else "item")
            item_details.append(desc)
        message = "You are carrying: " + ", ".join(item_details) + "."
        return {"message": message, "turn_taken": False}

    def _command_list_actions(self):
        """Generates a formatted string of possible actions."""
        message_parts = [color_text("Possible actions:", "info")]
        message_parts.append("  Move [direction] (e.g., 'move north', 'move n')")
        message_parts.append("  Examine [object/item/room] (e.g., 'examine table', 'examine')")
        message_parts.append(f"  {self.game_data.ACTION_BREAK.capitalize()} [furniture] (e.g., '{self.game_data.ACTION_BREAK} cupboard')") # Show break command
        message_parts.append("  Take [item]")
        message_parts.append("  Search [furniture]")
        message_parts.append("  Use [item] on [target] (e.g., 'use key on door')")
        message_parts.append("  Drop [item]")
        message_parts.append("  Unlock [door/furniture]")
        message_parts.append("  Inventory (or 'i')")
        message_parts.append("  Map")
        message_parts.append("  Save [slot_name] / Load [slot_name] (e.g., 'save game1', 'load quicksave')")
        message_parts.append("  Quit / Newgame")
        return {"message": "\n".join(message_parts), "turn_taken": False}

    def _command_map(self):
        """Displays a textual map of the current area."""
        map_string = self.get_gui_map_string() # Use the Kivy-compatible one
        return {"message": map_string, "turn_taken": False}
        
    def _get_item_data(self, item_name):
        """Gets master data for a specific item by its name (case-insensitive)."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name: return None
        target_name_lower = item_name.lower()
        for name, data in self.current_level_items_master_copy.items():
            if name.lower() == target_name_lower:
                return copy.deepcopy(data)
        # Fallback: check global game_data if not in current_level_items_master_copy (e.g. for dynamically created items like shards)
        for source_type in ["items", "evidence", "keys"]:
            source_dict = getattr(self.game_data, source_type, {})
            for name, data in source_dict.items():
                if name.lower() == target_name_lower:
                    logger.debug(f"Item '{item_name}' found in global game_data.{source_type}, not in current_level_items_master_copy.")
                    return copy.deepcopy(data) # Return a copy
        logger.debug(f"Item data for '{item_name}' not found.")
        return None

    def _get_current_room_data(self):
        """Get the data for the room the player is currently in."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("_get_current_room_data: Player or player location not set.")
            return None
        current_room_name = self.player['location']
        if not self.current_level_rooms:
            logger.warning(f"_get_current_room_data: current_level_rooms not initialized. Cannot get data for '{current_room_name}'.")
            return None
        room_data = self.current_level_rooms.get(current_room_name)
        if room_data is None:
             logger.warning(f"Room data for current location '{current_room_name}' not found in current_level_rooms.")
        return room_data

    def get_room_data(self, room_name):
        """Get data for a specific room by name from the current level's modifiable room data."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not room_name:
            logger.warning("get_room_data called with no room_name.")
            return None
        if not self.current_level_rooms:
            logger.warning(f"get_room_data: current_level_rooms not initialized. Cannot get data for '{room_name}'.")
            return None
        room_data = self.current_level_rooms.get(room_name)
        if room_data is None:
            logger.warning(f"Room data for '{room_name}' not found in current_level_rooms.")
        return room_data
        
    def get_room_description(self, room_name=None):
        """Generates the full, color-enhanced description for a room."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if room_name is None:
            if not self.player or 'location' not in self.player:
                logger.error("get_room_description: Player or location not set and no room_name provided.")
                return "You are in an indescribable void."
            room_name = self.player["location"]

        room_data = self._get_current_room_data() if room_name == self.player["location"] else self.get_room_data(room_name)
        if not room_data:
            logger.error(f"Room data for '{room_name}' not found in get_room_description.")
            return f"You sense an anomaly where '{room_name}' should be."

        description_parts = [color_text(f"\n--- {room_name.upper()} ---", 'room')]
        base_desc = room_data.get("description", "An empty space.")
        # Enhance keywords in the base description
        # This is a simple keyword highlighter, could be more sophisticated
        keywords_to_color = {
            "fireplace": "furniture", "cupboard": "furniture", "desk": "furniture",
            "wires": "hazard", "gas": "warning", "door": "furniture", "window": "furniture",
            "key": "item", "note": "evidence", "brick": "item", # Add more as needed
            "blood": "warning", "fire": "fire", "sparks": "hazard", "water": "default",
            "shadows": "default", "darkness": "default", "light": "default"
        }
        for kw, color_type in keywords_to_color.items():
            base_desc = base_desc.replace(kw, color_text(kw, color_type))
            base_desc = base_desc.replace(kw.capitalize(), color_text(kw.capitalize(), color_type))
        description_parts.append(base_desc)

        items_in_room_direct = []
        for item_key, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == room_name and \
               not item_world_data.get('container') and \
               not item_world_data.get('is_hidden'):
                item_master = self._get_item_data(item_key)
                color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                items_in_room_direct.append(color_text(item_key.capitalize(), color_type))
        if items_in_room_direct:
            description_parts.append("\n" + color_text("You see here: ", "default") + ", ".join(items_in_room_direct) + ".")

        revealed_items_in_room = []
        for item_key in self.revealed_items_in_rooms.get(room_name, set()):
            item_world_data = self.current_level_items_world_state.get(item_key)
            if item_world_data and item_world_data.get('location') == room_name and \
               not item_world_data.get('container') and \
               item_key not in self.player.get('inventory', []):
                item_master = self._get_item_data(item_key)
                color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                formatted_revealed_item = color_text(item_key.capitalize() + " (revealed)", color_type)
                if formatted_revealed_item not in items_in_room_direct :
                    revealed_items_in_room.append(formatted_revealed_item)
        if revealed_items_in_room:
            description_parts.append("\n" + color_text("You've also noticed: ", "default") + ", ".join(revealed_items_in_room) + ".")

        room_objects_list = room_data.get("objects", [])
        if room_objects_list:
            description_parts.append("\n" + color_text("Objects: ", "default") + ", ".join(color_text(obj.capitalize(), 'item') for obj in room_objects_list) + ".")
            
        furniture_list_data = room_data.get("furniture", [])
        if furniture_list_data:
            furniture_descs = []
            for f_dict in furniture_list_data:
                f_name = f_dict.get("name", "unknown furniture").capitalize()
                f_desc = color_text(f_name, 'furniture')
                if f_dict.get("locked"): f_desc += color_text(" (Locked)", "warning")
                if f_dict.get("is_hidden_container") and f_dict.get("name") not in self.revealed_items_in_rooms.get(room_name, set()):
                    continue # Don't list hidden containers unless revealed
                furniture_descs.append(f_desc)
            if furniture_descs:
                description_parts.append("\n" + color_text("Furniture: ", "default") + ", ".join(furniture_descs) + ".")

        if self.hazard_engine:
            env_state = self.hazard_engine.get_env_state(room_name)
            hazard_descs_from_engine = self.hazard_engine.get_room_hazards_descriptions(room_name)
            env_messages = []
            if env_state.get('gas_level', 0) >= self.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD:
                env_messages.append(color_text("The air is thick and heavy with gas!", "error"))
            elif env_state.get('gas_level', 0) >= 1:
                env_messages.append(color_text("You smell gas in the air.", "warning"))
            if env_state.get('is_on_fire'):
                env_messages.append(color_text("The room is on fire!", "fire"))
            elif env_state.get('is_sparking') and not any("spark" in hd.lower() for hd in hazard_descs_from_engine):
                env_messages.append(color_text("Electrical sparks crackle nearby!", "hazard"))
            if env_state.get('is_wet'):
                env_messages.append(color_text("The floor is wet here.", "default"))
            if env_state.get('visibility') != "normal":
                env_messages.append(color_text(f"Visibility is {env_state.get('visibility')}.", "warning"))
            if env_state.get('noise_level',0) >= 3:
                 env_messages.append(color_text("It's deafeningly noisy here.", "warning"))
            elif env_state.get('noise_level',0) >= 1:
                 env_messages.append(color_text("There's a noticeable background noise.", "default"))
            if env_messages: description_parts.append("\n" + "\n".join(env_messages))
            if hazard_descs_from_engine: description_parts.append("\n" + "\n".join(hazard_descs_from_engine))
        
        exits_data = room_data.get("exits", {})
        if exits_data:
            exit_parts = []
            for direction, dest_room_name in exits_data.items():
                dest_room_is_locked = self.current_level_rooms.get(dest_room_name, {}).get('locked', False)
                lock_indicator = color_text(" (Locked)", "warning") if dest_room_is_locked else ""
                exit_parts.append(f"{color_text(direction.capitalize(), 'exit')} to {color_text(dest_room_name.capitalize(), 'room')}{lock_indicator}")
            description_parts.append("\n\n" + color_text("Exits: ", "default") + "; ".join(exit_parts) + ".")
        else:
            description_parts.append("\n\n" + color_text("There are no obvious exits.", "default"))
        return "\n".join(filter(None, description_parts)).strip()

    def _enhance_description_keywords(self, description_text):
        """This is a placeholder. Keyword enhancement is now more integrated into get_room_description."""
        return description_text

    def _get_furniture_piece(self, room_data_dict, furniture_name_str):
        """Finds and returns the dictionary for a piece of furniture."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not room_data_dict or not isinstance(room_data_dict.get("furniture"), list):
            return None
        target_lower = furniture_name_str.lower()
        for furn_dict in room_data_dict["furniture"]:
            if isinstance(furn_dict, dict) and furn_dict.get("name", "").lower() == target_lower:
                return furn_dict
        return None

    def _handle_status_effects_pre_action(self):
        """Handles status effects that might prevent an action."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        messages = []
        action_prevented = False
        if not isinstance(self.player.get("status_effects"), dict):
            self.player["status_effects"] = {}
            return messages, action_prevented
        if "stunned" in self.player["status_effects"]:
            effect_def = self.game_data.status_effects_definitions.get("stunned", {})
            messages.append(color_text(effect_def.get("message_on_action_attempt", "You are stunned and cannot act!"), "warning"))
            action_prevented = True
            logger.info("Player action prevented by 'stunned' status.")
        return messages, action_prevented

    def _handle_status_effects_tick(self):
        """Processes active status effects at the end of a turn."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        tick_messages = []
        effects_to_remove = []
        if not isinstance(self.player.get("status_effects"), dict):
            self.player["status_effects"] = {}
            return tick_messages
        active_effects = copy.deepcopy(self.player["status_effects"])
        for effect_name, turns_left in active_effects.items():
            effect_def = self.game_data.status_effects_definitions.get(effect_name)
            if not effect_def:
                logger.warning(f"Status effect '{effect_name}' on player but not in definitions. Removing.")
                effects_to_remove.append(effect_name)
                continue
            msg_on_tick = effect_def.get("message_on_tick")
            if msg_on_tick: tick_messages.append(color_text(msg_on_tick, "warning"))
            hp_change = effect_def.get("hp_change_per_turn", 0)
            if hp_change != 0:
                self.apply_damage_to_player(-hp_change, f"status effect: {effect_name}")
                if hp_change < 0: tick_messages.append(color_text(f"You feel a bit better due to {effect_name}.", "success"))
            self.player["status_effects"][effect_name] -= 1
            if self.player["status_effects"][effect_name] <= 0:
                effects_to_remove.append(effect_name)
                msg_on_expire = effect_def.get("message_on_wear_off")
                if msg_on_expire: tick_messages.append(color_text(msg_on_expire, "info"))
                logger.info(f"Status effect '{effect_name}' expired.")
        for effect_name in effects_to_remove:
            if effect_name in self.player["status_effects"]:
                del self.player["status_effects"][effect_name]
        return tick_messages

    def _handle_turn_progression_and_final_checks(self):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        progression_messages = []
        if self.is_game_over:
            # If game ended mid-action (e.g. QTE failure), don't progress turn further
            return progression_messages

        if self.hazard_engine:
            hazard_update_msgs, death_from_hazards = self.hazard_engine.hazard_turn_update()
            if hazard_update_msgs:
                progression_messages.extend(hazard_update_msgs)
            if death_from_hazards and not self.is_game_over:  # Check if not already game over from player action
                self.is_game_over = True
                self.game_won = False
                # Hazard engine should set last_hazard_type and last_hazard_object_name on player
                # Or, we can formulate a generic message here if not set by hazard engine
                if not self.player.get('last_death_message'):
                    death_source = self.player.get('last_hazard_object_name', self.player.get('last_hazard_type', 'an environmental hazard'))
                    self.player['last_death_message'] = f"The environment proved deadly, overcome by {death_source}."
                logger.info(f"Game over triggered by HazardEngine update. Death message: {self.player.get('last_death_message')}")
                if not any("fatal" in msg.lower() or "die" in msg.lower() or "succumb" in msg.lower() for msg in progression_messages):
                    progression_messages.append(color_text(self.player['last_death_message'], "error"))

        status_tick_messages = self._handle_status_effects_tick()
        if status_tick_messages:
            progression_messages.extend(status_tick_messages)

        if self.player.get("hp", 0) <= 0 and not self.is_game_over:
            self.is_game_over = True
            self.game_won = False
            self.player['last_death_message'] = self.player.get('last_death_message', "Succumbed to afflictions.")  # Keep existing if more specific
            logger.info(f"Game over: Player HP <= 0 after status effect ticks. Death message: {self.player['last_death_message']}")
            if not any("fatal" in msg.lower() or "succumb" in msg.lower() for msg in progression_messages):
                progression_messages.append(color_text(self.player['last_death_message'], "error"))

        if not self.is_game_over:
            self.player["turns_left"] = self.player.get("turns_left", 0) - 1
            self.player["actions_taken"] = self.player.get("actions_taken", 0) + 1
            self.player["actions_taken_this_level"] = self.player.get("actions_taken_this_level", 0) + 1
            if self.player["turns_left"] <= 0:
                self.is_game_over = True
                self.game_won = False
                self.player['last_death_message'] = "Time ran out! Dawn breaks, and whatever malevolent force resides here claims you."
                logger.info("Game over: Turns ran out.")
                progression_messages.append(color_text(self.player['last_death_message'], "error"))
        return progression_messages

    def apply_damage_to_player(self, damage_amount, source="an unknown source"):
        """Applies damage to the player and checks for game over."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.is_game_over: return
        old_hp = self.player.get("hp", 0)
        new_hp = old_hp - damage_amount
        if damage_amount > 0:
            self.player["hp"] = max(0, new_hp)
            logger.info(f"Player took {damage_amount} damage from {source}. HP: {old_hp} -> {self.player['hp']}")
        elif damage_amount < 0:
            self.player["hp"] = min(self.player.get("max_hp", 10), new_hp)
            logger.info(f"Player healed {-damage_amount} from {source}. HP: {old_hp} -> {self.player['hp']}")
        if self.player["hp"] <= 0:
            self.is_game_over = True
            self.game_won = False
            self.player['last_hazard_type'] = source 
            self.player['last_death_message'] = f"Succumbed to injuries from {source}." # Store a more direct death message
            logger.info(f"Game Over: Player HP reached 0 from {source}.")

    def apply_status_effect(self, effect_name, duration_override=None, messages_list=None):
        """Applies a status effect to the player."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not hasattr(self.game_data, 'status_effects_definitions'):
            logger.warning("status_effects_definitions not found in game_data.")
            return False
        effect_def = self.game_data.status_effects_definitions.get(effect_name)
        if not effect_def:
            logger.warning(f"Attempted to apply unknown status effect: {effect_name}")
            return False
        duration = duration_override if duration_override is not None else effect_def.get("duration", 1)
        if not isinstance(self.player.get("status_effects"), dict): self.player["status_effects"] = {}
        self.player["status_effects"][effect_name] = duration
        apply_message = effect_def.get("message_on_apply", f"You are now {effect_name}.")
        if messages_list is not None: messages_list.append(color_text(apply_message, "warning"))
        else: logger.info(f"Applied status: {effect_name}. Message: {apply_message}")
        logger.info(f"Applied status effect: {effect_name} for {duration} turns.")
        return True

    def _handle_house_escape_sequence(self):
        """Handles the sequence when the player attempts to leave the house (Level 1 exit)."""
        # This logic is now more tied to the general _command_move and level exit checks.
        # The QTE for the wrecking ball would be triggered by HazardEngine or a special room script
        # when the player attempts to exit the "Front Porch" if certain conditions are met.
        # For now, this specific method might be deprecated or refactored into a more generic
        # "trigger_level_end_sequence" if needed.
        # The QTE triggering is now part of HazardEngine's _check_action_hazard or autonomous actions.
        self.logger.info("House escape sequence initiated (placeholder, actual QTE trigger moved).")
        # This would return data to signal a QTE to process_player_input if it were still primary.
        # For now, let's assume the move command to exit the house will lead to the QTE via hazard interactions.
        return {"message": "You approach the exit of the house...", "turn_taken": True}



    def get_valid_directions(self):
        """Returns a list of valid movement directions from the current room."""
        if not self.player or 'location' not in self.player:
            self.logger.warning("get_valid_directions: Player or location not set.")
            return []
        current_room_data = self._get_current_room_data()
        if not current_room_data or not isinstance(current_room_data.get("exits"), dict):
            self.logger.warning(f"get_valid_directions: No valid exits found for room '{self.player.get('location')}'.")
            return []
        return list(current_room_data["exits"].keys())

    def get_examinable_targets_in_room(self):
        """
        Returns a list of examinable targets (visible objects, furniture, items) in the current room.
        Does not include the room itself, as 'examine' with no target defaults to the current room.
        """
        if not self.player or 'location' not in self.player:
            self.logger.warning("get_examinable_targets_in_room: Player or location not set.")
            return []
            
        current_room_name = self.player['location']
        room_data = self.get_room_data(current_room_name) 
        
        if not room_data:
            self.logger.warning(f"get_examinable_targets_in_room: No room data for '{current_room_name}'.")
            return []
            
        targets = []

        # Add furniture names
        for furn_dict in room_data.get("furniture", []):
            furn_name = furn_dict.get("name")
            if not furn_name:
                continue
            # A hidden container itself isn't examinable until its presence is known.
            is_hidden_furn_container = furn_dict.get("is_hidden_container", False)
            
            if is_hidden_furn_container:
                # Only add if it has been revealed (e.g., "fireplace cavity")
                if furn_name in self.revealed_items_in_rooms.get(current_room_name, set()):
                    targets.append(furn_name)
            else:
                targets.append(furn_name)

        # Add object names from room_data.objects
        for obj_name_or_dict in room_data.get("objects", []):
            name_to_add = None
            if isinstance(obj_name_or_dict, dict):
                name_to_add = obj_name_or_dict.get("name")
            elif isinstance(obj_name_or_dict, str):
                name_to_add = obj_name_or_dict
            if name_to_add:
                 targets.append(name_to_add)

        # Add items physically present in the room (not in inventory, not in an unsearched hidden container)
        for item_name, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == current_room_name:
                # Item is directly in the room (not in a container) AND not hidden
                is_visible_on_floor = not item_world_data.get('container') and not item_world_data.get('is_hidden', False)
                # Item is in a container AND has been revealed by searching that container
                is_revealed_in_container = item_world_data.get('container') and \
                                           item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                
                if is_visible_on_floor or is_revealed_in_container:
                    targets.append(item_name)
        
        self.logger.debug(f"Examinable targets in '{current_room_name}': {list(set(filter(None, targets)))}")
        return list(set(filter(None, targets))) # Remove None and duplicates

    def get_takeable_items_in_room(self):
        """Returns a list of items in the current room that can be taken."""
        if not self.player or 'location' not in self.player:
            self.logger.warning("get_takeable_items_in_room: Player or location not set.")
            return []
        current_room_name = self.player['location']
        takeable_items = []

        for item_name, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == current_room_name:
                master_item_data = self._get_item_data(item_name) 
                if master_item_data and master_item_data.get('takeable', True):
                    is_visible_on_floor = not item_world_data.get('container') and not item_world_data.get('is_hidden', False)
                    is_revealed_in_container = item_world_data.get('container') and \
                                               item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                    
                    if is_visible_on_floor or is_revealed_in_container:
                        if item_name not in self.player.get('inventory', []):
                             takeable_items.append(item_name)
        
        self.logger.debug(f"Takeable items in '{current_room_name}': {list(set(takeable_items))}")
        return list(set(takeable_items))

    # get_searchable_furniture_in_room already exists in game_logic.py and is suitable.

    def get_usable_inventory_items(self):
        """Returns a list of items from player's inventory that have a defined use."""
        if not self.player or not isinstance(self.player.get('inventory'), list):
            self.logger.warning("get_usable_inventory_items: Player or inventory not available.")
            return []
        
        usable_items = []
        for item_name in self.player['inventory']:
            item_master_data = self._get_item_data(item_name)
            if item_master_data:
                if item_master_data.get('use_on') or \
                   item_master_data.get('general_use_effect_message') or \
                   item_master_data.get('heal_amount') or \
                   item_master_data.get('is_key'): 
                    usable_items.append(item_name)
        self.logger.debug(f"Usable inventory items: {list(set(usable_items))}")
        return list(set(usable_items))

    def get_inventory_items(self):
        """Returns a list of items currently in the player's inventory."""
        if not self.player or not isinstance(self.player.get('inventory'), list):
            self.logger.warning("get_inventory_items: Player or inventory not available.")
            return []
        return list(self.player['inventory']) 

    def get_unlockable_targets(self):
        """Returns a list of names of locked doors or furniture in the current room."""
        if not self.player or 'location' not in self.player:
            self.logger.warning("get_unlockable_targets: Player or location not set.")
            return []
        current_room_name = self.player['location']
        current_room_data_world = self.current_level_rooms.get(current_room_name)
        
        if not current_room_data_world:
            self.logger.warning(f"get_unlockable_targets: No world data for room '{current_room_name}'.")
            return []

        unlockable_targets = []

        # Check locked exits
        for direction, dest_room_name in current_room_data_world.get("exits", {}).items():
            dest_room_world_data = self.current_level_rooms.get(dest_room_name)
            if dest_room_world_data and dest_room_world_data.get("locked"):
                # For UI, it might be better to present the direction or a descriptive name
                # like "Door to [dest_room_name]" or just "Door" if it's the only one.
                # The command "unlock [target]" will try to match target to direction or room name.
                # Adding the destination room name is a common way for players to target.
                target_display_name = dest_room_name 
                # Special case for Front Porch -> Foyer for better UI
                if current_room_name == "Front Porch" and dest_room_name == "Foyer":
                    target_display_name = "Front Door" # This is more intuitive for the player
                
                if target_display_name not in unlockable_targets:
                    unlockable_targets.append(target_display_name)

        # Check locked furniture
        for furn_dict_world in current_room_data_world.get("furniture", []):
            furn_name = furn_dict_world.get("name")
            if furn_dict_world.get("locked") and furn_name:
                if furn_name not in unlockable_targets:
                    unlockable_targets.append(furn_name)
        
        self.logger.debug(f"Unlockable targets in '{current_room_name}': {list(set(unlockable_targets))}")
        return list(set(unlockable_targets))

    def trigger_qte(self, qte_type, duration, context):
        """Called by HazardEngine or other systems to initiate a QTE."""
        if self.player.get('qte_active'):
            self.logger.warning(f"Attempted to trigger QTE '{qte_type}' while QTE '{self.player['qte_active']}' is already active. Ignoring new QTE.")
            return
        self.player['qte_active'] = qte_type
        self.player['qte_duration'] = duration
        self.player['qte_context'] = context
        self.logger.info(f"QTE '{qte_type}' triggered by system. Duration: {duration}s. Context: {context}")

    def _handle_qte_response(self, qte_type_from_player_state, user_input_str):
        """Handles player's response to an active QTE, including special cases like MRI projectile sequence."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        qte_context = self.player.get('qte_context', {})
        self.player['qte_active'] = None
        self.player['qte_duration'] = 0
        response = {"message": "", "death": False, "turn_taken": True, "success": False, "level_transition_data": None}
        qte_master_definition = self.game_data.qte_definitions.get(qte_type_from_player_state, {})
        valid_responses = qte_master_definition.get("valid_responses", [self.game_data.QTE_RESPONSE_DODGE])

        # Special-case: MRI projectile QTE
        is_mri_sequence_qte = qte_context.get("is_mri_projectile_qte", False)
        is_success = user_input_str.lower() in [vr.lower() for vr in valid_responses]

        if is_success:
            response["success"] = True
            response["message"] = color_text(
                qte_context.get("success_message", qte_master_definition.get("success_message_default", "You succeed!")),
                "success"
            )
            self.player["score"] = self.player.get("score", 0) + qte_master_definition.get("score_on_success", 10)
            self.unlock_achievement(self.game_data.ACHIEVEMENT_QUICK_REFLEXES)

            source_hazard_id = qte_context.get('qte_source_hazard_id')
            # For MRI sequence, allow next state override
            next_hazard_state_on_success = qte_context.get('next_state_after_qte_success', qte_context.get('next_state_for_hazard'))

            if source_hazard_id and next_hazard_state_on_success and self.hazard_engine:
                hazard_progression_messages = []
                if source_hazard_id in self.hazard_engine.active_hazards:
                    self.hazard_engine._set_hazard_state(source_hazard_id, next_hazard_state_on_success, hazard_progression_messages)
                    if hazard_progression_messages:
                        response["message"] += "\n" + "\n".join(hazard_progression_messages)
                else:
                    logger.warning(f"QTE success: Source hazard {source_hazard_id} no longer active.")

            if qte_context.get("on_success_level_complete"):
                current_level_id = self.player.get("current_level", 1)
                level_reqs = self.game_data.LEVEL_REQUIREMENTS.get(current_level_id, {})
                next_level_id_val = level_reqs.get("next_level_id")
                next_level_start_room_val = level_reqs.get("next_level_start_room")
                if next_level_id_val is not None:
                    response["message"] += color_text(f"\nYou've survived Level {current_level_id}!", "special")
                    response["level_transition_data"] = {
                        "next_level_id": next_level_id_val,
                        "next_level_start_room": next_level_start_room_val,
                        "completed_level_id": current_level_id
                    }
                else:
                    self.game_won = True
                    self.is_game_over = True
                    response["message"] += color_text("\nIncredible! You've cheated Death and survived the final ordeal!", "success")

        else:
            response["success"] = False
            failure_message_template = qte_context.get("failure_message", qte_master_definition.get("failure_message_default", "You failed!"))
            projectile_name = qte_context.get("qte_projectile_name", "the flying object")
            # Use .format for MRI QTEs, otherwise just use the string
            if is_mri_sequence_qte:
                response["message"] = color_text(failure_message_template.format(projectile_name=projectile_name), "error")
            else:
                response["message"] = color_text(failure_message_template, "error")

            hp_damage = qte_context.get("hp_damage_on_failure", qte_master_definition.get("hp_damage_on_failure", 0))
            is_fatal_direct = qte_context.get("is_fatal_on_failure", False if is_mri_sequence_qte else True)

            if is_mri_sequence_qte:
                self.player['mri_qte_failures'] = self.player.get('mri_qte_failures', 0) + 1
                if hp_damage > 0:
                    self.apply_damage_to_player(hp_damage, f"hit by {projectile_name} during MRI event")
                    response["message"] += f" You take {hp_damage} damage."
                # MRI QTE: death if too many failures, fatal, or HP <= 0
                if self.player['mri_qte_failures'] >= self.game_data.MAX_MRI_QTE_FAILURES or is_fatal_direct or self.player['hp'] <= 0:
                    response["death"] = True
                    self.is_game_over = True
                    self.game_won = False
                    object_desc = qte_context.get("qte_projectile_name", "a piece of flying metal")
                    impact_res = "leaving you a mangled mess" if self.player['hp'] <= 0 else "fatally wounding you"
                    if is_fatal_direct:
                        impact_res = "instantly killing you"
                    self.player['last_death_message'] = self.game_data.GAME_OVER_MRI_DEATH.format(
                        object_description=object_desc,
                        impact_result=impact_res
                    )
                    response["message"] += f"\n{self.player['last_death_message']}"
                    logger.info(f"Game Over: Player killed by MRI projectiles. Failures: {self.player['mri_qte_failures']}. HP: {self.player['hp']}")
                else:
                    # Not dead yet, continue sequence
                    source_hazard_id = qte_context.get('qte_source_hazard_id')
                    next_hazard_state_on_failure = qte_context.get('next_state_after_qte_failure', qte_context.get('next_state_for_hazard'))
                    if source_hazard_id and next_hazard_state_on_failure and self.hazard_engine:
                        hazard_progression_messages = []
                        if source_hazard_id in self.hazard_engine.active_hazards:
                            self.hazard_engine._set_hazard_state(source_hazard_id, next_hazard_state_on_failure, hazard_progression_messages)
                            if hazard_progression_messages:
                                response["message"] += "\n" + "\n".join(hazard_progression_messages)
            else:
                # Generic QTE failure
                if is_fatal_direct:
                    response["death"] = True
                    self.is_game_over = True
                    self.game_won = False
                    self.player['last_hazard_type'] = f"Failed QTE: {qte_type_from_player_state}"
                    self.player['last_death_message'] = response["message"]
                elif hp_damage > 0:
                    self.apply_damage_to_player(hp_damage, f"failing QTE {qte_type_from_player_state}")
                    response["message"] += f" You take {hp_damage} damage."
                    if self.player['hp'] <= 0:
                        response["death"] = True
                        self.player['last_death_message'] = response["message"]
                if not self.is_game_over:
                    source_hazard_id = qte_context.get('qte_source_hazard_id')
                    next_hazard_state_on_failure = qte_context.get('next_state_for_hazard')
                    if source_hazard_id and next_hazard_state_on_failure and self.hazard_engine:
                        hazard_progression_messages = []
                        if source_hazard_id in self.hazard_engine.active_hazards:
                            self.hazard_engine._set_hazard_state(source_hazard_id, next_hazard_state_on_failure, hazard_progression_messages)
                            if hazard_progression_messages:
                                response["message"] += "\n" + "\n".join(hazard_progression_messages)
                        else:
                            logger.warning(f"QTE failure: Source hazard {source_hazard_id} no longer active.")

        self.player.pop('qte_context', None)
        logger.info(f"QTE '{qte_type_from_player_state}' response processed. Success: {is_success}. Player HP: {self.player.get('hp')}")
        if self.is_game_over and not response.get("death"):
            response["death"] = True
        return response

    def log_evaded_hazard(self, hazard_description_of_evasion):
        """Adds a description of an evaded hazard for the inter-level screen."""
        if self.player:
            self.player.setdefault('evaded_hazards_current_level', []).append(hazard_description_of_evasion)
            self.logger.info(f"Logged evaded hazard: {hazard_description_of_evasion}")

    def transition_to_new_level(self, new_level_id, start_room_override=None):
        """Handles the actual logic for transitioning the game state to a new level."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        completed_level_id = self.player['current_level']
        logger.info(f"Transitioning from Level {completed_level_id} to Level {new_level_id}...")

        self.player['current_level'] = new_level_id
        level_start_info = self.game_data.LEVEL_REQUIREMENTS.get(new_level_id, {})
        self.player['location'] = start_room_override or level_start_info.get('entry_room')
        if not self.player['location']:
             logger.error(f"Cannot transition: No entry room defined for level {new_level_id}.")
             # This should ideally not happen if LEVEL_REQUIREMENTS is correct
             # Fallback or error handling needed here. For now, log and potentially fail.
             return {"success": False, "message": color_text(f"Error: Misconfigured transition to level {new_level_id}.", "error")}

        self.player.setdefault('visited_rooms', set()).add(self.player['location'])
        self.player['actions_taken_this_level'] = 0
        self.player['evidence_found_this_level'] = []
        self.player['evaded_hazards_current_level'] = [] 
            
        self._initialize_level_data(new_level_id) 
        if self.hazard_engine:
            self.hazard_engine.initialize_for_level(new_level_id)
            
        logger.info(f"Player transitioned to Level {new_level_id}, starting in {self.player['location']}.")
        
        # Return data that might be useful for the UI or calling function
        return {
            "success": True,
            "message": f"Welcome to {level_start_info.get('name', 'the new area')}!\n\n{self.get_room_description()}",
            "new_location": self.player['location'] # For UI to update its display
        }

    def _calculate_player_inventory_weight(self):
        """Calculates the total weight of items in the player's inventory."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        total_weight = 0
        for item_name in self.player.get("inventory", []):
            item_data = self._get_item_data(item_name) 
            if item_data:
                total_weight += item_data.get("weight", self.game_data.DEFAULT_ITEM_WEIGHT)
            else:
                logger.warning(f"Could not find data for item '{item_name}' in inventory while calculating weight.")
        return total_weight

    def unlock_achievement(self, achievement_id):
        """Unlocks an achievement if the system is available."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.achievements_system:
            if self.achievements_system.unlock(achievement_id):
                 logger.info(f"Achievement '{achievement_id}' unlocked via GameLogic.")
                 return True
        else:
            logger.warning(f"Attempted to unlock achievement '{achievement_id}' but AchievementsSystem is not available.")
        return False

    def _get_save_filepath(self, slot_identifier="quicksave"):
        """Generates the full filepath for a given save slot identifier."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not hasattr(self, 'save_dir') or not self.save_dir:
            logger.error("_get_save_filepath: save_dir not initialized. Attempting to set up paths.")
            self._setup_paths_and_logging() 
            if not self.save_dir:
                logger.critical("_get_save_filepath: CRITICAL - save_dir could not be established.")
                return None
        filename = f"savegame_{slot_identifier}.json" 
        return os.path.join(self.save_dir, filename)

    def _convert_sets_to_lists(self, obj):
        """Recursively converts all sets in a dict/list structure to lists for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._convert_sets_to_lists(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_sets_to_lists(i) for i in obj]
        elif isinstance(obj, set):
            return list(obj)
        else:
            return obj

    def save_game(self, slot_identifier):
        try:
            if not hasattr(self, 'save_dir'):
                self.save_dir = os.path.join(os.path.dirname(__file__), "saves")
            os.makedirs(self.save_dir, exist_ok=True)
            save_path = os.path.join(self.save_dir, f"{slot_identifier}.json")
            # Prepare the data to save
            save_info = {
                "location": self.player.get("location", "?"),
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "character_class": self.player.get("character_class", ""),
                "turns_left": self.player.get("turns_left", ""),
                "score": self.player.get("score", "")
            }
            save_data = {
                "player": self._convert_sets_to_lists(self.player),
                "current_level": getattr(self, "current_level", None),
                "timestamp": save_info["timestamp"],
                "save_info": save_info  # <--- Add this line
                # Add more fields as needed
            }
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=2)
            return {"success": True, "message": f"Game saved to slot '{slot_identifier}'."}
        except Exception as e:
            return {"success": False, "message": f"Failed to save game: {e}"}

    def _command_save(self, slot_identifier="quicksave"):
        """Saves the current game state to the specified slot."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.player is None:
            logger.error("Cannot save game: Player state is not initialized.")
            return {"message": color_text("Error: No game active to save.", "error"), "success": False}

        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath:
             return {"message": color_text("Error: Could not determine save location.", "error"), "success": False}
        logger.info(f"Attempting to save game to slot '{slot_identifier}' at {save_filepath}...")
        hazard_engine_savable_state = self.hazard_engine.save_state() if self.hazard_engine and hasattr(self.hazard_engine, 'save_state') else None
        save_data = {
            'save_info': {
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'level': self.player.get('current_level', 1),
                'location': self.player.get('location', 'Unknown'),
                'character_class': self.player.get('character_class', 'Unknown'),
                'turns_left': self.player.get('turns_left', 0),
                'score': self.player.get('score', 0)
            },
            'player': self.player,
            'is_game_over': self.is_game_over, 'game_won': self.game_won,
            'revealed_items_in_rooms': {room: list(items) for room, items in self.revealed_items_in_rooms.items()},
            'interaction_counters': self.interaction_counters,
            'current_level_rooms': self.current_level_rooms,
            'current_level_items_world_state': self.current_level_items_world_state,
            'hazard_engine_state': hazard_engine_savable_state,
        }
        try:
            os.makedirs(os.path.dirname(save_filepath), exist_ok=True)
            with open(save_filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Game saved successfully to slot '{slot_identifier}'.")
            return {"message": color_text(f"Game saved to slot '{slot_identifier}'.", "success"), "success": True}
        except TypeError as te:
            logger.error(f"TypeError saving game to slot '{slot_identifier}': {te}. Check for non-serializable data types.", exc_info=True)
            return {"message": color_text(f"Error saving game: Non-serializable data encountered. {te}", "error"), "success": False}
        except Exception as e:
            logger.error(f"Error saving game to slot '{slot_identifier}': {e}", exc_info=True)
            return {"message": color_text(f"Error saving game: {e}", "error"), "success": False}


    def load_game(self, slot_identifier):
        """
        Loads the game state from a file named after the slot_identifier.
        Returns a dict with 'success' (bool) and 'message' (str).
        """
        try:
            if not hasattr(self, 'save_dir'):
                self.save_dir = os.path.join(os.path.dirname(__file__), "saves")
            save_path = os.path.join(self.save_dir, f"{slot_identifier}.json")
            if not os.path.exists(save_path):
                return {"success": False, "message": f"No save file found for slot '{slot_identifier}'."}
            with open(save_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Restore player and other state
            self.player = loaded.get("player", {})
            self.current_level = loaded.get("current_level", None)
            # Restore other fields as needed (rooms, items, hazards, etc.)
            # Example: self.rooms = loaded.get("rooms", {})
            # Example: self.current_level_items_world_state = loaded.get("current_level_items_world_state", {})
            return {"success": True, "message": f"Game loaded from slot '{slot_identifier}'."}
        except Exception as e:
            return {"success": False, "message": f"Failed to load game: {e}"}

    def _command_load(self, slot_identifier="quicksave"):
        """Loads a game state from the specified slot."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath or not os.path.exists(save_filepath):
            logger.warning(f"Save file for slot '{slot_identifier}' not found at {save_filepath}.")
            return {"message": color_text(f"No save data found for slot '{slot_identifier}'.", "warning"), "success": False}
        logger.info(f"Attempting to load game from slot '{slot_identifier}' from {save_filepath}...")
        try:
            with open(save_filepath, 'r', encoding='utf-8') as f: load_data = json.load(f)
            self.player = load_data.get('player')
            if not self.player:
                logger.error("Loaded save data is missing 'player' information.")
                return {"message": color_text("Error: Save data is corrupted (missing player info).", "error"), "success": False}
            self.is_game_over = load_data.get('is_game_over', False)
            self.game_won = load_data.get('game_won', False)
            loaded_revealed = load_data.get('revealed_items_in_rooms', {})
            self.revealed_items_in_rooms = {room: set(items) for room, items in loaded_revealed.items()}
            self.interaction_counters = load_data.get('interaction_counters', {})
            loaded_level_id = self.player.get('current_level', 1)
            self._initialize_level_data(loaded_level_id)
            self.current_level_rooms = load_data.get('current_level_rooms', self.current_level_rooms)
            self.current_level_items_world_state = load_data.get('current_level_items_world_state', self.current_level_items_world_state)
            hazard_engine_state_data = load_data.get('hazard_engine_state')
            if not self.hazard_engine: self.hazard_engine = HazardEngine(self)
            self.hazard_engine.initialize_for_level(loaded_level_id)
            if hazard_engine_state_data and hasattr(self.hazard_engine, 'load_state'):
                self.hazard_engine.load_state(hazard_engine_state_data)
                logger.info("HazardEngine state loaded successfully.")
            elif hazard_engine_state_data: logger.warning("HazardEngine state data found in save, but load_state method might be missing or failed.")
            else: logger.info("No specific HazardEngine state found in save file. Hazards will be default for the loaded level.")
            if isinstance(self.player.get("visited_rooms"), list): self.player["visited_rooms"] = set(self.player["visited_rooms"])
            if "journal" not in self.player: self.player["journal"] = {}
            logger.info(f"Game loaded successfully from slot '{slot_identifier}'. Player at {self.player.get('location')}, Level {loaded_level_id}.")
            return {"message": color_text(f"Game loaded from slot '{slot_identifier}'.", "success"), "success": True, "new_location": self.player.get('location')}
        except json.JSONDecodeError as jde:
            logger.error(f"JSONDecodeError loading game from slot '{slot_identifier}': {jde}", exc_info=True)
            return {"message": color_text(f"Error: Save file for slot '{slot_identifier}' is corrupted or not valid JSON.", "error"), "success": False}
        except Exception as e:
            logger.error(f"Error loading game from slot '{slot_identifier}': {e}", exc_info=True)
            return {"message": color_text(f"Error loading game: {e}", "error"), "success": False}
