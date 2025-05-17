import json
import random
import logging
import copy
import os
import datetime
import collections

# Color constants for UI rendering
COLOR_CYAN = "#00FFFF"
COLOR_LIGHT_GREY = "#CCCCCC" 
COLOR_GREEN = "#00FF00"
COLOR_RED = "#FF0000"
from .utils import color_text # Assuming utils.py is in the same package
from kivy.app import App
from . import game_data # Assuming game_data.py is in the same package
from .hazard_engine import HazardEngine # Assuming hazard_engine.py is in the same package
# AchievementsSystem is passed in, so no direct import needed here if following that pattern.

# ==================================
# Game Logic Class
# ==================================
class GameLogic:
    # Class constants
    SAVE_FILENAME_TEMPLATE = "savegame{}.json"
    MAX_SAVE_SLOTS = 5
    
    def __init__(self, achievements_system=None):
        logging.info("GameLogic initialization started")
        # Ensure game_data is accessible
        try:
            self.game_data = game_data
            if not hasattr(self.game_data, 'rooms') or not hasattr(self.game_data, 'items'):
                logging.error("game_data module is missing critical attributes like 'rooms' or 'items'.")
                # Potentially raise an error or handle this more gracefully
                # For now, we'll let it proceed and fail later if these are accessed.
            logging.info(f"game_data module loaded. Levels available: {list(self.game_data.rooms.keys()) if hasattr(self.game_data, 'rooms') else 'N/A'}")
        except ImportError:
            logging.error("Failed to import game_data module directly in GameLogic init.")
            # This is a critical failure. The game cannot run without game_data.
            # Consider raising an exception or setting a flag that prevents game start.
            self.game_data = None # Ensure it's None if import fails
            # return # Or raise an error
        except Exception as e:
            logging.error(f"Error accessing game_data during GameLogic init: {e}")
            self.game_data = None
            # return

        self.achievements_system = achievements_system # Can be None
        self.is_game_over = False
        self.game_won = False
        self.player = None # Initialized in start_new_game or load_game
        self.evaded_hazards_for_interlevel_screen = [] 
        # World state, re-initialized per level or loaded from save
        self.revealed_items_in_rooms = {} # Items revealed by searching containers
        self.interaction_counters = {}    # For tracking interactions with specific objects (e.g., fireplace)
        self.current_level_rooms = {}     # Deep copy of room data for the current level
        self.current_level_items_master_copy = {} # Master definitions of items for the current level
        self.current_level_items_world_state = {} # Live state of items in the current level

        self.hazard_engine = None # Initialized in start_new_game or when a level loads

        # Path setup for save/load functionality (depends on Kivy App instance)
        self._setup_paths_and_logging() # Sets up self.save_dir

        # Initial game setup is typically done by calling start_new_game() externally
        # or load_game() after GameLogic object is created.
        # For example, in your UI, after creating GameLogic, you'd call game_logic.start_new_game().
        # We won't call it here to allow for flexibility (e.g. loading a game right after init).
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

        # Logging setup (can be more sophisticated, this is basic)
        log_dir = os.path.join(self.user_data_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        # Note: This might conflict if logging is already configured globally.
        # Consider using a named logger specific to GameLogic.
        # logging.basicConfig(filename=os.path.join(log_dir, "game_logic.log"), level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        # Using a named logger is better:
        self.logger = logging.getLogger(__name__) # or 'GameLogic'
        if not self.logger.handlers: # Avoid adding multiple handlers if already configured
            handler = logging.FileHandler(os.path.join(log_dir, "game_logic.log"))
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO) # Or DEBUG
            self.logger.propagate = False # Optional: stop messages going to root logger

        self.logger.info(f"GameLogic logging to: {os.path.join(log_dir, 'game_logic.log')}")

        self.save_dir = os.path.join(self.user_data_dir, 'saves')
        os.makedirs(self.save_dir, exist_ok=True)
        self.logger.info(f"GameLogic save directory: {self.save_dir}")

    def start_new_game(self, character_class="Journalist"): # Added character_class parameter
        """Initializes a completely new game session."""
        self.logger.info(f"Starting new game with character: {character_class}...")
        self.is_game_over = False
        self.game_won = False


        # Initialize player state based on character class
        # This assumes get_initial_player_state is now part of game_data or this class
        if hasattr(self.game_data, 'get_initial_player_state'):
            self.player = self.game_data.get_initial_player_state(character_class)
        else: # Fallback if not in game_data
            stats = self.game_data.CHARACTER_CLASSES.get(character_class, self.game_data.CHARACTER_CLASSES["Journalist"])
            self.player = {
                "location": self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"], # Default to level 1 start
                "inventory": [],
                "hp": stats["max_hp"],
                "max_hp": stats["max_hp"],
                "perception": stats["perception"],
                "intuition": stats["intuition"],
                "status_effects": {},
                "score": 0,
                "turns_left": self.game_data.STARTING_TURNS,
                "actions_taken": 0,
                "visited_rooms": set(), # Initialize as set
                "current_level": 1,
                "qte_active": None,
                "qte_duration": 0,
                "qte_context": {},
                "last_hazard_type": None,
                "last_hazard_target_name_str.lower()": None,
                "character_class": character_class,
                "journal": {} # Initialize journal
            }
        self.player['current_level'] = 1
        self.player['location'] = self.game_data.LEVEL_REQUIREMENTS[1]["entry_room"] # Hospital
        self.player['visited_rooms'] = {self.player['location']}
        
        # Initialize/reset per-level stats
        self.player['actions_taken_this_level'] = 0
        self.player['evidence_found_this_level'] = [] # Store names/IDs of evidence found this level
        self.player['evaded_hazards_current_level'] = [] # Already present

        self._initialize_level_data(self.player['current_level'])
        
        if not self.hazard_engine:
            self.hazard_engine = HazardEngine(self)
        self.hazard_engine.initialize_for_level(self.player['current_level'])
        
        self.logger.info(f"New game started. Player at {self.player['location']}. Level {self.player['current_level']}.")
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

        # Deepcopy rooms for the current level to allow in-game modifications (e.g., locked status)
        level_rooms_master = self.game_data.rooms.get(level_id)
        if level_rooms_master is None:
            self.logger.error(f"Level {level_id} data not found in game_data.rooms.")
            self.current_level_rooms = {}
        else:
            self.current_level_rooms = copy.deepcopy(level_rooms_master)
            self.logger.info(f"Loaded {len(self.current_level_rooms)} rooms for level {level_id}.")

        # Prepare master list of all items (items, evidence, keys) for the current level
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

                # --- Level 1 Evidence Control ---
                is_eligible_for_current_level = False
                if item_level_id_from_data == level_id:
                    if level_id == 1 and source_type == "evidence":
                        # For Level 1, only allow evidence from a specific list or with specific fixed locations
                        allowed_evidence = getattr(self.game_data, "ALLOWED_EVIDENCE_LEVEL_1", [])
                        if name in allowed_evidence:
                            is_eligible_for_current_level = True
                        elif data.get("location") in ["Coroner's Office", "Morgue Autopsy Suite"]:
                            is_eligible_for_current_level = True
                        else:
                            self.logger.debug(
                                f"Evidence '{name}' is for Level 1 but not in ALLOWED_EVIDENCE_LEVEL_1 or fixed in Morgue. Excluding."
                            )
                    else:
                        is_eligible_for_current_level = True
                elif item_level_id_from_data is None or str(item_level_id_from_data).lower() == "all":
                    is_eligible_for_current_level = True

                if is_eligible_for_current_level:
                    if name not in self.current_level_items_master_copy:
                        self.current_level_items_master_copy[name] = copy.deepcopy(data)
                    else:
                        self.logger.warning(
                            f"Duplicate item name '{name}' found. Using first encountered definition from '{source_type}'."
                        )

        # Create the live world state of items for this level
        self.current_level_items_world_state = copy.deepcopy(self.current_level_items_master_copy)
        self.logger.info(
            f"Initialized {len(self.current_level_items_world_state)} item types for level {level_id} world state."
        )

        # Reset dynamic placement flags for items (location, container, is_hidden)
        # This ensures that when a new level starts (not loaded from save), items are placed fresh.
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
                # Default to hidden for dynamically placed items unless explicitly set to not hidden
                item_world_data["is_hidden"] = original_item_def.get("is_hidden", True)
            else:  # For fixed items, ensure their defined properties are set
                item_world_data["location"] = original_item_def.get("location")
                item_world_data["container"] = original_item_def.get("container")
                # If fixed and revealed_by_action, it starts hidden.
                # If fixed and NOT revealed_by_action, is_hidden comes from definition (default False).
                if original_item_def.get("revealed_by_action"):
                    item_world_data["is_hidden"] = True
                else:
                    item_world_data["is_hidden"] = original_item_def.get("is_hidden", False)

        # Place dynamic and fixed items
        self._place_dynamic_elements_for_level(level_id)

        # Initialize HazardEngine for the level (if it exists)
        # This is often done in start_new_game or load_game, but if _initialize_level_data
        # is called independently (e.g. on level transition), ensure HE is also re-initialized.
        if self.hazard_engine:
            self.hazard_engine.initialize_for_level(level_id)
        else:
            # This case might occur if _initialize_level_data is called before start_new_game fully sets up HE.
            # Consider if HE should always be created here if None.
            self.logger.warning(
                "HazardEngine not yet initialized when _initialize_level_data was called. It will be set up by start_new_game/load_game."
            )

    self.logger.info(f"Level {level_id} data initialization complete.")

    def _get_available_container_slots_for_level(self):
        """
        Gets available UNLOCKED container slots from rooms in the current level.
        A slot is a dictionary: {"room": room_name, "container_name": furniture_name, "item": None}
        """
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
                   not furniture_dict.get("locked"): # Only unlocked containers
                    # Consider capacity if furniture has it
                    capacity = furniture_dict.get("capacity", 1) # Default capacity 1
                    for _ in range(capacity):
                        slots.append({"room": room_name, "container_name": furniture_dict["name"], "item_inside": None})
        random.shuffle(slots)
        self.logger.debug(f"Found {len(slots)} available unlocked container slots for level.")
        return slots

    def _place_dynamic_elements_for_level(self, level_id):
        """Places dynamic items (keys, evidence, other items) and confirms fixed items for the current level."""
        self.logger.info(f"--- Placing Dynamic & Fixed Elements for Level {level_id} ---")

        # 1. Identify items that need dynamic placement
        # These are items NOT in FIXED_ITEMS_DYNAMIC_EXCLUSION, NOT having "fixed_location",
        # AND their current "location" in world_state is None (meaning they haven't been placed yet).
        items_for_dynamic_placement = {
            name: data for name, data in self.current_level_items_world_state.items()
            if name not in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION and \
               not self.current_level_items_master_copy.get(name, {}).get("fixed_location") and \
               data.get("location") is None and \
               (self.current_level_items_master_copy.get(name, {}).get("level") == level_id or \
                self.current_level_items_master_copy.get(name, {}).get("level") is None or \
                str(self.current_level_items_master_copy.get(name, {}).get("level")).lower() == "all")
        }
        
        # Separate into categories for prioritized placement
        keys_to_place_dynamically = {n: d for n, d in items_for_dynamic_placement.items() if d.get("is_key")}
        evidence_to_place_dynamically = {n: d for n, d in items_for_dynamic_placement.items() if d.get("is_evidence") and n not in keys_to_place_dynamically}
        other_items_to_place_dynamically_names = set(items_for_dynamic_placement.keys()) - set(keys_to_place_dynamically.keys()) - set(evidence_to_place_dynamically.keys())
        other_items_to_place_dynamically = {name: items_for_dynamic_placement[name] for name in other_items_to_place_dynamically_names}

        available_slots = self._get_available_container_slots_for_level()
        
        self.logger.info(f"Dynamic placement: {len(keys_to_place_dynamically)} keys, {len(evidence_to_place_dynamically)} evidence, {len(other_items_to_place_dynamically)} other items. Slots: {len(available_slots)}.")

        # Placement Order: Keys > Evidence > Other
        if keys_to_place_dynamically:
            self._distribute_items_in_slots(list(keys_to_place_dynamically.keys()), available_slots, "Key")
        if evidence_to_place_dynamically:
            self._distribute_items_in_slots(list(evidence_to_place_dynamically.keys()), available_slots, "Evidence")
        if other_items_to_place_dynamically:
            # Decide how many "other" items to place, e.g., all of them or a random subset
            num_other_to_place = len(other_items_to_place_dynamically) 
            items_to_place_as_other = list(other_items_to_place_dynamically.keys()) # Place all for now
            if items_to_place_as_other:
                self._distribute_items_in_slots(items_to_place_as_other, available_slots, "Other Item")

        # 2. Confirm placement of FIXED items (those in FIXED_ITEMS_DYNAMIC_EXCLUSION or with "fixed_location")
        # These should have had their location/container set during _initialize_level_data based on their master definition.
        # This loop primarily serves as a log/confirmation or final check.
        for item_name, item_world_data in self.current_level_items_world_state.items():
            master_data = self.current_level_items_master_copy.get(item_name, {})
            is_explicitly_fixed = item_name in self.game_data.FIXED_ITEMS_DYNAMIC_EXCLUSION or master_data.get("fixed_location")
            
            if is_explicitly_fixed and (master_data.get("level") == level_id or master_data.get("level") is None or str(master_data.get("level")).lower() == "all"):
                # Ensure its location in world_state matches master_data if it was defined
                defined_loc = master_data.get("location")
                defined_container = master_data.get("container")

                if defined_loc and item_world_data.get("location") != defined_loc:
                    self.logger.warning(f"Fixed item '{item_name}' world location '{item_world_data.get('location')}' differs from master definition '{defined_loc}'. Correcting.")
                    item_world_data["location"] = defined_loc
                
                if defined_container and item_world_data.get("container") != defined_container:
                     item_world_data["container"] = defined_container
                elif not defined_container: # Ensure no container if not defined for a fixed item
                     item_world_data.pop("container", None)
                
                if item_world_data.get("location"): # If it has a location (should for fixed items)
                    self.logger.info(f"Confirmed fixed item '{item_name}' at {item_world_data['location']}" +
                                     (f" in container '{item_world_data['container']}'." if item_world_data.get('container') else "."))
                else:
                    self.logger.warning(f"Fixed item '{item_name}' has no location in world state despite being fixed. Master def loc: {defined_loc}")
        self.logger.info("--- Dynamic and Fixed Element Placement Complete ---")

    def _distribute_items_in_slots(self, item_names_list, available_slots_list, item_category_log="Item"):
        """
        Helper to place a list of item names into available container slots.
        Modifies self.current_level_items_world_state and available_slots_list.
        """
        placed_count = 0
        random.shuffle(item_names_list)

        # --- START MODIFICATION ---
        # Keep track of items placed in each container to respect a lower perceived capacity for Level 1
        container_fill_count = {}
        # For Level 1, limit non-essential items per container
        # This is a simple limit; could be more complex (e.g., based on item type or container type)
        # For this example, let's say max 1 non-key/non-crucial-evidence item per container in Level 1.
        # This specific logic might be better placed in _place_dynamic_elements_for_level
        # by limiting the `items_to_place_as_other` list if current_level is 1.
        # For now, let's assume _distribute_items_in_slots handles respecting a general "don't overfill"
        # This can be made more nuanced if needed. A simple hard cap:
        max_items_per_container_for_level_1 = 1 # If self.player.get('current_level') == 1 else some_other_value
        # --- END MODIFICATION ---


        for item_name in item_names_list:
            if not available_slots_list:
                self.logger.warning(f"Ran out of available slots while trying to place {item_category_log} '{item_name}'.")
                break

            item_data_world = self.current_level_items_world_state.get(item_name)
            if not item_data_world:
                self.logger.warning(f"Item data for '{item_name}' not found in world state during distribution. Skipping.")
                continue
            
            if item_data_world.get("location"):
                self.logger.debug(f"{item_category_log} '{item_name}' already has a location. Skipping dynamic slot placement.")
                continue

            # --- START MODIFICATION for container fill limit ---
            slot_found_for_item = False
            temp_slots_to_retry = [] # Slots skipped due to fill limit

            original_slots_count = len(available_slots_list)
            processed_slots_count = 0

            while available_slots_list and not slot_found_for_item and processed_slots_count < original_slots_count * 2 : # Safety break
                slot = available_slots_list.pop(0) # Take the next available slot
                processed_slots_count += 1
                container_id = (slot["room"], slot["container_name"])

                # Apply stricter capacity for Level 1 for 'Other Item' types
                is_level_1 = self.player.get("current_level") == 1
                is_other_item = item_category_log == "Other Item"

                if is_level_1 and is_other_item and container_fill_count.get(container_id, 0) >= max_items_per_container_for_level_1:
                    temp_slots_to_retry.append(slot) # Put slot back for other items/categories if possible
                    continue # Try next slot for this item

                # Place the item
                item_data_world["location"] = slot["room"]
                item_data_world["container"] = slot["container_name"]
                item_data_world["is_hidden"] = True 
                
                container_fill_count[container_id] = container_fill_count.get(container_id, 0) + 1
                slot_found_for_item = True
                
                self.logger.info(f"Placed {item_category_log} '{item_name}' in container '{slot['container_name']}' in room '{slot['room']}'. Container fill: {container_fill_count[container_id]}")
                placed_count += 1
            
            available_slots_list.extend(temp_slots_to_retry) # Add skipped slots back to the end

            if not slot_found_for_item:
                self.logger.warning(f"Could not find a suitable slot for {item_category_log} '{item_name}' due to fill limits or no slots.")
            # --- END MODIFICATION ---
            
        if placed_count < len(item_names_list):
            self.logger.warning(f"Could not place all {item_category_log}s. Placed {placed_count}/{len(item_names_list)} due to slot limitations or fill counts.")
        return placed_count

    def get_save_slot_info(self, slot_id):
        """
        Returns a dict with preview info for the given save slot, or None if not found.
        """
        save_path = os.path.join(self.SAVE_DIR, f"{slot_id}.json")
        if not os.path.exists(save_path):
            return None
        try:
            with open(save_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Example: adjust keys to match your save structure
            return {
                "location": data.get("player", {}).get("location", "?"),
                "timestamp": data.get("timestamp", "Unknown"),
                "character_class": data.get("player", {}).get("character_class", ""),
                "turns_left": data.get("player", {}).get("turns_left", ""),
            }
        except Exception as e:
            # Optionally log error
            return None

    def process_player_input(self, command_str):
        """
        Processes the raw command string from the player, dispatches to appropriate handlers,
        and manages turn progression.
        """
        # Ensure logger is available
        logger = getattr(self, 'logger', logging.getLogger(__name__))

        if self.is_game_over and not self.player.get('qte_active'):
            logger.info("Attempted command after game over.")
            return {"message": "The game is over. " + (color_text("You won!", "success") if self.game_won else color_text("You lost.", "error")), 
                    "death": not self.game_won, 
                    "turn_taken": False}

        if self.player.get('qte_active'):
            logger.info(f"Processing QTE response: {command_str} for QTE: {self.player.get('qte_active')}")
            # _handle_qte_response returns a dict suitable for GameScreen
            qte_response_data = self._handle_qte_response(self.player['qte_active'], command_str)
            
            # GameScreen needs to know if a level transition was triggered by QTE success
            if qte_response_data.get("level_transition"):
                response["level_transition"] = qte_response_data["level_transition"] # Pass it up

        command_str_original = command_str
        command_str = command_str.strip().lower()
        words = command_str.split()

        if not words:
            return {"message": "Please enter a command.", "death": False, "turn_taken": False}

        verb = words[0]
        target_str = " ".join(words[1:])

        # Verb aliasing
        verb_aliases = {
            "go": "move", "get": "take", "look": "examine", "inspect": "examine",
            "inv": "inventory", "i": "inventory", "bag": "inventory",
            "q": "quit", "exit": "quit", "restart": "newgame", "again": "newgame",
            "actions": "list", "commands": "list",
            "l": "examine" # Common alias for look/examine
        }
        verb = verb_aliases.get(verb, verb)

        # Default response
        response = {
            "message": f"I don't know how to '{verb}'. Type 'list' for available actions.", 
            "death": False, 
            "turn_taken": False, # Default to false, specific commands will set to true
            "found_items": None,
            "new_location": None,
            "item_taken": None,
            "item_dropped": None,
            "item_revealed": False,
            "qte_triggered": None # To signal UI if a QTE starts
        }

        # --- Handle Non-Turn-Taking Meta Commands Early ---
        if verb == "quit":
            response["message"] = "Use the Exit button on the Title Screen or close the window to quit."
            return response
        if verb == "newgame":
            self.start_new_game(self.player.get("character_class", "Journalist")) # Restart with current class
            response["message"] = f"{color_text('--- New Game Started ---', 'special')}\n{self.get_room_description()}"
            response["new_location"] = self.player['location'] # Update UI with new location
            return response
        if verb == "save":
            # _command_save should return a dict with "message" and potentially "success"
            save_response = self._command_save(target_str if target_str else "quicksave")
            response["message"] = save_response.get("message", "Save status unknown.")
            return response # Saving does not take a turn
        if verb == "load":
            load_response = self._command_load(target_str if target_str else "quicksave")
            response["message"] = load_response.get("message", "Load status unknown.")
            if load_response.get("success"):
                response["new_location"] = self.player['location'] # Update UI
                response["message"] += f"\n{self.get_room_description()}"
            return response # Loading does not take a turn
        if verb == "help" or verb == "list":
            response = self._command_list_actions() # This method now returns a dict
            return response
        if verb == "inventory":
            response = self._command_inventory()
            return response
        if verb == "map": # Added map command
            response = self._command_map()
            return response


        # --- Pre-Command Status Effects (that might prevent action) ---
        status_messages, action_prevented = self._handle_status_effects_pre_action()
        if status_messages:
            # These messages will be prepended to the main action's message.
            # Store them temporarily.
            response["pre_action_status_message"] = "\n".join(status_messages)

        if action_prevented:
            response["message"] = response.get("pre_action_status_message", "") + \
                                  f"\n{color_text('You are unable to perform the action due to your condition.', 'warning')}"
            response["turn_taken"] = True # Attempting an action while incapacitated still takes a turn
            # Proceed to turn progression to handle hazard updates, turn decrement, etc.
        else:
            # --- Dispatch to Command Handlers (if action not prevented) ---
            command_methods = {
                "move": self._command_move, "examine": self._command_examine,
                "take": self._command_take, "search": self._command_search,
                "use": self._command_use, "drop": self._command_drop,
                "unlock": self._command_unlock,
            }

            if verb in command_methods:
                command_func = command_methods[verb]
                if verb == "use": # 'use' command might have multiple words for item and target
                    action_response = command_func(words[1:]) # Pass all words after "use"
                elif not target_str and verb not in ["examine"]: # Most actions need a target
                    action_response = {"message": f"{verb.capitalize()} what?", "turn_taken": False}
                elif verb == "examine" and not target_str: # "examine" alone means examine room
                    action_response = command_func(self.player['location']) # Examine current room
                else:
                    action_response = command_func(target_str)
                
                # Merge action_response into the main response
                response.update(action_response)
            else:
                # Default message for unknown verb already set. Turn not taken.
                response["turn_taken"] = False
        
        # --- Post-Command Processing ---
        # Combine pre-action status messages with the main action message
        if response.get("pre_action_status_message"):
            response["message"] = response["pre_action_status_message"] + "\n" + response.get("message", "")
            del response["pre_action_status_message"] # Clean up

        # If a transition is triggered by QTE or normal exit:
        if response.get("level_transition"): # This was the old flag from QTE response
            transition_details_from_qte = response.pop("level_transition")

        # If the command itself resulted in death (e.g., using an item fatally)
        if response.get("death"):
            self.is_game_over = True
            self.game_won = False
            logger.info(f"Command '{command_str_original}' resulted in death. Player HP: {self.player.get('hp')}")
            # Turn progression still happens to tick down status effects, world events, etc.,
            # unless the command explicitly set turn_taken to False (e.g. invalid command).
            if response.get("turn_taken", True): # Default to true if not specified
                turn_progression_messages = self._handle_turn_progression_and_final_checks()
                if turn_progression_messages:
                    response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_progression_messages).strip()).strip()
            return response

        # If the action was valid and took a turn (and didn't immediately result in game over)
        if not self.is_game_over and response.get("turn_taken"):
            turn_progression_messages = self._handle_turn_progression_and_final_checks()
            if turn_progression_messages:
                response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_progression_messages).strip()).strip()
            
            # Check if turn progression itself ended the game (e.g. HP loss, turns ran out)
            if self.is_game_over and not self.game_won:
                response["death"] = True # Ensure death flag is set if game ended by progression
        
        # If a QTE was triggered by the action or its consequences
        if response.get("qte_triggered"):
            qte_data = response["qte_triggered"]
            self.player['qte_active'] = qte_data.get("type")
            self.player['qte_duration'] = qte_data.get("duration")
            self.player['qte_context'] = qte_data.get("context")
            # The message for initiating the QTE should be part of response["message"]
            logger.info(f"QTE '{self.player['qte_active']}' triggered by command '{command_str_original}'.")

        # If a level transition was signaled (e.g., by QTE success logic that sets response["level_transition"])
        if response.get("level_transition"):
            transition_details = response.pop("level_transition") # Get and remove the transition signal
            next_level_id = transition_details.get("next_level_id")
            # The start_room_override for level transition is usually defined in LEVEL_REQUIREMENTS
            # or can be passed if the QTE context specifically dictated it.
            start_room_for_next_level = self.game_data.LEVEL_REQUIREMENTS.get(next_level_id, {}).get("entry_room")

            transition_message_data = self.transition_to_new_level(next_level_id, start_room_for_next_level)
            
            # Merge transition messages and update new_location for UI
            response["message"] = (response.get("message", "").strip() + "\n\n" + transition_message_data.get("message", "")).strip()
            response["new_location"] = transition_message_data.get("new_location") # For UI update
            
            # Achievement check for completing the *previous* level
            if self.achievements_system and hasattr(self.achievements_system, 'check_level_completion_achievements'):
                completed_level_id = transition_details.get("completed_level_id")
                if completed_level_id:
                    self.achievements_system.check_level_completion_achievements(self, completed_level_id) # Pass self (GameLogic)

        if response.get("level_transition_data"):
            transition_info = response["level_transition_data"]
            app = App.get_running_app()
            if app and self.player:
                app.interlevel_evaded_hazards = list(self.player.get('evaded_hazards_current_level', []))
                app.interlevel_next_level_id = transition_info.get("next_level_id")
                app.interlevel_next_start_room = transition_info.get("next_level_start_room")
                app.interlevel_completed_level_name = self.game_data.LEVEL_REQUIREMENTS.get(transition_info.get("completed_level_id"), {}).get("name", "The Area")
                # --- Narrative flags/snippets ---
                app.interlevel_narrative_flags = list(self.player.get("narrative_flags_collected", set()))
                app.interlevel_narrative_snippets = list(self.player.get("narrative_snippets_collected", []))
                # Final checks if game ended during this processing
       
        if not self.is_game_over and response.get("turn_taken"):
            turn_progression_messages = self._handle_turn_progression_and_final_checks()
            if turn_progression_messages:
                response["message"] = (response.get("message", "").strip() + "\n" + "\n".join(turn_progression_messages).strip()).strip()
            
            if self.is_game_over and not self.game_won:
                response["death"] = True 
        
        # If a QTE was triggered by a normal action (not a QTE response itself)
        # This part remains as is, for actions that start a QTE.
        if response.get("qte_triggered") and not self.player.get('qte_active'): # Ensure we don't overwrite an active QTE
            qte_data = response["qte_triggered"]
            # Call self.trigger_qte instead of directly setting player dict here
            self.trigger_qte(qte_data.get("type"), qte_data.get("duration"), qte_data.get("context"))
            # The message for initiating the QTE should be part of response["message"] from the action/hazard
            logger.info(f"QTE '{self.player['qte_active']}' triggered by command '{command_str}'.")

        return response

    def get_gui_map_string(self, width=35, height=7): # width/height are for Kivy label constraints
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
            if not dest_room_name and alt_key: # Check alternative key (e.g. "up" for "upstairs")
                dest_room_name = exits_dict.get(alt_key)
            
            if dest_room_name:
                dest_room_data = self.get_room_data(dest_room_name)
                is_locked = dest_room_data.get('locked', False) if dest_room_data else False
                visited = dest_room_name in self.player.get('visited_rooms', set())
                
                text_color_name = "exit" if visited else "default" 
                base_symbol = color_text(symbol_char, text_color_name)
                lock_indicator = color_text("(L)", "error") if is_locked else ""
                return f"{base_symbol}{lock_indicator}"
            return " " # Return a single space for non-existent exits to maintain some structure if needed by padding

        # Get cell content (markup included)
        u_cell = format_direction_cell("U", "upstairs", "up", exits)
        n_cell = format_direction_cell("N", "north", None, exits)
        w_cell = format_direction_cell("W", "west", None, exits)
        p_cell = color_text("P", "success") # Player
        e_cell = format_direction_cell("E", "east", None, exits)
        s_cell = format_direction_cell("S", "south", None, exits)
        d_cell = format_direction_cell("D", "downstairs", "down", exits)

        # Construct lines simply, Kivy's halign='center' will handle centering each line.
        # The number of spaces here is less critical for centering, more for visual separation
        # if a direction is missing.
        map_lines = [
            f"{u_cell}",
            f"{n_cell}",
            f"{w_cell} - {p_cell} - {e_cell}",
            f"{s_cell}",
            f"{d_cell}"
        ]
        
        final_map_string = location_line + "\n" + "\n".join(map_lines)
        return final_map_string

    def _command_break(self, target_name_str):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        current_room_name = self.player['location']
        current_room_data = self._get_current_room_data()
        response_messages = []
        turn_taken = True
        death_triggered = False

        if not target_name_str:
            return {"message": "Break what?", "death": False, "turn_taken": False}

        target_furniture_dict = self._get_furniture_piece(current_room_data, target_name_str)

        if not target_furniture_dict:
            return {"message": f"You don't see '{target_name_str}' here to break.", "death": False, "turn_taken": False}

        furniture_name = target_furniture_dict.get("name")
        if not target_furniture_dict.get("is_breakable"):
            return {"message": f"The {furniture_name} doesn't look like it can be forced open or broken easily.", "death": False, "turn_taken": True}

        # Check if player has a suitable tool if required by 'break_succeeds_on_item_type'
        # For simplicity, let's assume a basic "force" attempt first.
        # A more complex system could check for "use crowbar on cupboard" -> break attempt.
        # This _command_break is for a generic "break cupboard" attempt.

        # Track break attempts or integrity
        integrity_key = f"{current_room_name}_{furniture_name}_integrity"
        current_integrity = self.interaction_counters.get(integrity_key, target_furniture_dict.get("break_integrity", 1))

        if current_integrity <= 0: # Already broken
            response_messages.append(f"The {furniture_name} is already broken.")
            turn_taken = False
        else:
            response_messages.append(f"You attempt to force the {furniture_name}...")
            # Simple success/failure for now, could be dice roll or tool-dependent
            # For this example, let's say each attempt reduces integrity by 1
            current_integrity -= 1
            self.interaction_counters[integrity_key] = current_integrity

            if current_integrity <= 0:
                response_messages.append(color_text(target_furniture_dict.get("on_break_success_message", f"The {furniture_name} breaks open!"), "success"))
                
                # Mark as no longer breakable (or "broken") in the room's state if needed
                # self.current_level_rooms[current_room_name]['furniture'][index_of_furniture]['state'] = "broken" 

                # Spill items
                items_to_spill = target_furniture_dict.get("on_break_spill_items", [])
                if items_to_spill:
                    spilled_item_names = []
                    for spill_entry in items_to_spill:
                        item_name_to_add = spill_entry.get("name")
                        # Handle quantity if defined (e.g., "1d3")
                        # For now, assume quantity 1
                        if item_name_to_add:
                            # Add item to the room (not in a container, visible)
                            if item_name_to_add not in self.current_level_items_world_state: # If it's a new type of item
                                master_spill_item_data = self._get_item_data(item_name_to_add) # Get its master definition
                                if master_spill_item_data:
                                     self.current_level_items_world_state[item_name_to_add] = copy.deepcopy(master_spill_item_data)
                                else:
                                    self.logger.warning(f"No master data for spilled item '{item_name_to_add}'")
                                    continue
                            
                            # Update world state for the spilled item instance
                            self.current_level_items_world_state[item_name_to_add].update({
                                "location": current_room_name,
                                "container": None,
                                "is_hidden": False
                            })
                            self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name_to_add)
                            spilled_item_names.append(item_name_to_add)
                            logger.info(f"Item '{item_name_to_add}' spilled from broken {furniture_name}.")
                    if spilled_item_names:
                        response_messages.append(f"Contents spill out: {', '.join(spilled_item_names)}.")
                
                # Trigger hazard
                hazard_to_trigger = target_furniture_dict.get("on_break_trigger_hazard")
                if hazard_to_trigger and isinstance(hazard_to_trigger, dict):
                    if random.random() < hazard_to_trigger.get("chance", 1.0):
                        if self.hazard_engine:
                            new_haz_id = self.hazard_engine._add_active_hazard(
                                hazard_type=hazard_to_trigger.get("type"),
                                location=current_room_name,
                                initial_state_override=hazard_to_trigger.get("initial_state"),
                                target_object_override=hazard_to_trigger.get("object_name_override"),
                                support_object_override=hazard_to_trigger.get("support_object_override")
                            )
                            if new_haz_id:
                                response_messages.append(color_text(f"Your action on the {furniture_name} seems to have caused a new problem!", "warning"))
                                # Hazard engine will produce its own messages on its turn update
                        else:
                            self.logger.warning("Hazard engine not available to trigger hazard from break.")
                
                # Play sound
                # if target_furniture_dict.get("on_break_sound"): self.play_sound(...)

            else: # Failed to break it completely yet
                response_messages.append(color_text(target_furniture_dict.get("break_failure_message", f"You damaged the {furniture_name}, but it holds."), "warning"))

        # Check for broader environmental reactions to the "break" action itself
        # (e.g., if breaking something loud triggers a hazard that reacts to noise)
        if self.hazard_engine:
            hazard_resp = self.hazard_engine.check_action_hazard('break', furniture_name, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"): response_messages.append(hazard_resp["message"])
                if hazard_resp.get("death"): death_triggered = True
        
        return {"message": "\n".join(response_messages), "death": death_triggered, "turn_taken": turn_taken}

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

        # Match direction or alias
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

        # Special case: Front Porch → Foyer (must explicitly unlock)
        if current_room_name == "Front Porch" and destination_room_name == "Foyer" and destination_room_data.get('locked', False):
            return {
                "message": color_text("The front door is solidly locked. You'll need to unlock it first.", "warning"),
                "death": False,
                "turn_taken": False
            }

        # Handle locked doors (auto-unlock if player has key, except for special cases)
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

        # Level exit logic (evidence check and transition)
        level_id = self.player.get("current_level", 1)
        level_req = self.game_data.LEVEL_REQUIREMENTS.get(level_id, {})
        is_level_exit_room = level_req.get("exit_room") == current_room_name
        is_attempting_level_exit = destination_room_name == level_req.get("next_level_start_room")

        if is_level_exit_room and is_attempting_level_exit:
            required_evidence = set(level_req.get("evidence_needed", []))
            player_evidence = set(item for item in self.player.get("inventory", []) if self._get_item_data(item).get("is_evidence"))
            if not required_evidence.issubset(player_evidence):
                return {
                    "message": color_text("A sense of dread stops you. You feel there's crucial evidence still missing before you can leave this place.", "warning"),
                    "death": False,
                    "turn_taken": False
                }
            # Handle final level win
            if level_req.get("next_level_id") is None:
                self.game_won = True
                self.is_game_over = True
                return {
                    "message": color_text("You've gathered all you could and step out, a grim understanding dawning... You've survived.", "success") + f"\n{self.get_room_description(destination_room_name)}",
                    "death": False,
                    "turn_taken": True,
                    "new_location": destination_room_name
                }
            # Otherwise, transition to next level (let turn progression handle it)
            # Optionally, you could trigger a QTE or special sequence here.

        # Actual movement
        previous_location = self.player['location']
        self.player['location'] = destination_room_name
        self.player.setdefault('visited_rooms', set()).add(destination_room_name)

        move_message = f"You move from {previous_location} to {destination_room_name}."
        full_message = f"{unlock_message}\n{move_message}".strip()
        room_description = self.get_room_description(destination_room_name)
        full_message += f"\n\n{room_description}"

        # Hazard check on entering new room (e.g. weak floorboards)
        hazard_on_entry_messages = []
        death_from_entry_hazard = False
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
        turn_taken_by_examine = False
        item_revealed_or_transformed = False

        # 1. Examine item in inventory
        item_in_inventory = next((item for item in inventory if item.lower() == target_name_lower), None)
        if item_in_inventory:
            item_master_data = self._get_item_data(item_in_inventory)
            if item_master_data:
                action_message_parts.append(item_master_data.get('description', f"It's a {item_in_inventory}."))
                transform_target = item_master_data.get('transforms_into_on_examine')
                if transform_target:
                    if self._transform_item_in_inventory(item_in_inventory, transform_target):
                        action_message_parts.append(color_text(f"Upon closer inspection, it's actually a {transform_target}!", "special"))
                        item_revealed_or_transformed = True
                        turn_taken_by_examine = True
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

        # Special logic for revealing loose brick and fireplace cavity
        if target_name_lower == "fireplace":
            if "loose brick" not in self.revealed_items_in_rooms.setdefault(current_room_name, set()):
                self.revealed_items_in_rooms[current_room_name].add("loose brick")
                return {
                    "message": "You notice a loose brick in the fireplace.",
                    "death": False,
                    "turn_taken": False,
                    "item_revealed": True
                }

        # Modify the "fireplace" examination logic:
        if target_name_lower == "fireplace" and current_room_name == "Living Room":
            fireplace_desc = current_room_data.get('examine_details', {}).get("fireplace", "You examine the large, cold fireplace.")
            action_message_parts.append(fireplace_desc)

            loose_brick_name = self.game_data.ITEM_LOOSE_BRICK
            loose_brick_item_in_world = self.current_level_items_world_state.get(loose_brick_name)

            # Using the interaction_flags from game_data.py suggestion
            room_flags = self.current_level_rooms[current_room_name].get("interaction_flags", {})
            loose_brick_has_been_taken = room_flags.get("loose_brick_taken", False)
            cavity_already_revealed = room_flags.get("fireplace_cavity_revealed", False)

            # First examination: If loose brick is still in the wall and not yet revealed by this action
            if loose_brick_item_in_world and \
            loose_brick_item_in_world.get('location') == current_room_name and \
            not loose_brick_has_been_taken: # Check if it's effectively still 'in the wall'

                # Ensure it's visible if it was hidden
                if loose_brick_item_in_world.get('is_hidden') or loose_brick_name not in self.revealed_items_in_rooms.get(current_room_name, set()):
                    self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(loose_brick_name)
                    self.current_level_items_world_state[loose_brick_name]['is_hidden'] = False
                    action_message_parts.append(color_text("One brick near the bottom looks loose and out of place.", "special"))
                    item_revealed_or_transformed = True 
                else:
                    action_message_parts.append(color_text("The loose brick is still there.", "default"))


            # Second examination: If loose brick has been taken AND cavity not yet revealed
            elif loose_brick_has_been_taken and not cavity_already_revealed:
                action_message_parts.append(color_text("Where the loose brick was, you now see a dark cavity within the fireplace.", "special"))

                # Make "fireplace cavity" furniture visible/searchable
                # This assumes "fireplace cavity" is defined as furniture and might have an "is_hidden_container" flag
                for furn_idx, furn_dict in enumerate(self.current_level_rooms[current_room_name].get("furniture", [])):
                    if furn_dict.get("name") == "fireplace cavity" and furn_dict.get("is_hidden_container"):
                        self.current_level_rooms[current_room_name]["furniture"][furn_idx]["is_hidden_container"] = False
                        logger.info("Fireplace cavity container is now revealed.")
                        break
                self.revealed_items_in_rooms.setdefault(current_room_name, set()).add("fireplace cavity") # Ensure it can be targeted
                if "interaction_flags" in self.current_level_rooms[current_room_name]:
                    self.current_level_rooms[current_room_name]["interaction_flags"]["fireplace_cavity_revealed"] = True
                item_revealed_or_transformed = True

            # Subsequent examinations after cavity is revealed
            elif loose_brick_has_been_taken and cavity_already_revealed:
                action_message_parts.append(color_text("The cavity where the loose brick was is still there. It might be worth searching.", "default"))

            # Fallback if brick is present but already revealed by prior examine fireplace
            elif not loose_brick_has_been_taken:
                action_message_parts.append(color_text("The loose brick is still there.", "default"))


            return {
                "message": "\n".join(filter(None, action_message_parts)),
                "death": False, # Assuming no death from examining fireplace
                "turn_taken": False, # Examining scenery usually doesn't take a turn
                "item_revealed": item_revealed_or_transformed
            }

        if item_to_examine_in_room:
            master_item_data = self._get_item_data(item_to_examine_in_room)
            action_message_parts.append(master_item_data.get('description', f"It's a {item_to_examine_in_room}."))
            # Add hazard check if examining this item triggers something
        else:
            feature_to_examine = None
            feature_type = None
            if current_room_data.get('furniture'):
                for furn_dict in current_room_data['furniture']:
                    if furn_dict.get('name', '').lower() == target_name_lower:
                        feature_to_examine = furn_dict['name']
                        feature_type = 'furniture'
                        break
            if not feature_to_examine and current_room_data.get('objects'):
                for obj_name in current_room_data['objects']:
                    if obj_name.lower() == target_name_lower:
                        feature_to_examine = obj_name
                        feature_type = 'object'
                        break

            if feature_to_examine:
                examine_detail_key = feature_to_examine
                details = current_room_data.get('examine_details', {}).get(examine_detail_key)
                action_message_parts.append(details or f"You see nothing special about the {feature_to_examine}.")

                # Specific logic for "fireplace" revealing "loose brick"
                if feature_to_examine.lower() == "fireplace" and current_room_name == "Living Room":
                    loose_brick_name = self.game_data.ITEM_LOOSE_BRICK
                    brick_world_data = self.current_level_items_world_state.get(loose_brick_name)
                    if brick_world_data and brick_world_data.get('location') == current_room_name and brick_world_data.get('is_hidden'):
                        brick_world_data['is_hidden'] = False
                        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(loose_brick_name)
                        action_message_parts.append(color_text("You notice a loose brick near the bottom that wasn't obvious before.", "special"))
                        item_revealed_or_transformed = True
            elif target_name_lower == current_room_name.lower() or target_name_str == "":
                action_message_parts.append(self.get_room_description(current_room_name))
            else:
                action_message_parts.append(f"You don't see '{target_name_str}' here to examine.")

        # Hazard check for examining a feature (if not an item)
        if 'feature_to_examine' in locals() and feature_to_examine and self.hazard_engine:
            hazard_result = self.hazard_engine.check_action_hazard('examine', feature_to_examine, current_room_name)
            if hazard_result and isinstance(hazard_result, dict):
                if hazard_result.get("message"):
                    action_message_parts.append(hazard_result["message"])
                if hazard_result.get("death"):
                    death_triggered = True
                if hazard_result.get("message") or death_triggered:
                    turn_taken_by_examine = True

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

        # Find the item in the current room's world state
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

                    # Update item's state in the world
                    item_world_data['location'] = 'inventory'
                    item_world_data.pop('container', None)
                    item_world_data['is_hidden'] = False

                    if current_room_name in self.revealed_items_in_rooms:
                        self.revealed_items_in_rooms[current_room_name].discard(item_to_take_cased)

                    action_message_parts.append(f"You take the {item_to_take_cased}.")
                    turn_taken = True

                    # Handle evidence and achievements
                    if master_item_data.get("is_evidence"):
                        if self.achievements_system:
                            if not self.achievements_system.has_evidence(item_to_take_cased):
                                self.achievements_system.record_evidence(
                                    item_to_take_cased,
                                    master_item_data.get('name', item_to_take_cased),
                                    master_item_data.get('description', '')
                                )
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)
                        self.player.setdefault("found_evidence_count", 0)
                        self.player["found_evidence_count"] += 1

                        # --- Narrative flag/snippet logic ---
                        narrative_flag = master_item_data.get("narrative_flag_on_collect")
                        narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag:
                            self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet:
                            self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)

                    # Specific logic for taking "loose brick" revealing "Basement Key"
                    if item_to_take_cased.lower() == self.game_data.ITEM_LOOSE_BRICK.lower() and current_room_name == "Living Room":
                        basement_key_name = self.game_data.ITEM_BASEMENT_KEY
                        key_world_data = self.current_level_items_world_state.get(basement_key_name)
                        if key_world_data and key_world_data.get('location') == "Living Room" and key_world_data.get('is_hidden'):
                            key_world_data['is_hidden'] = False
                            self.revealed_items_in_rooms.setdefault("Living Room", set()).add(basement_key_name)
                            action_message_parts.append(color_text("As you pull the brick free, something metallic clatters out - the Basement Key!", "special"))
                            logger.info("Basement Key revealed after taking loose brick.")

                    if item_to_take_cased.lower() == self.game_data.ITEM_LOOSE_BRICK.lower() and current_room_name == "Living Room":
                        if "interaction_flags" in self.current_level_rooms[current_room_name]:
                            self.current_level_rooms[current_room_name]["interaction_flags"]["loose_brick_taken"] = True
                        logger.info("Loose brick taken from Living Room fireplace.")

                    # Hazard check for taking the item
                    if self.hazard_engine:
                        hazard_result = self.hazard_engine.check_action_hazard('take', item_to_take_cased, current_room_name)
                        if hazard_result and isinstance(hazard_result, dict):
                            if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                            if hazard_result.get("death"): death_triggered = True

            else:
                action_message_parts.append(f"You can't take the {item_to_take_cased}.")
        else:
            action_message_parts.append(f"You don't see '{item_name_str}' here to take.")

        return {
            "message": "\n".join(filter(None, action_message_parts)),
            "death": death_triggered,
            "turn_taken": turn_taken,
            "item_taken": item_taken_actual_name if not death_triggered and turn_taken else None
        }

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
        elif target_furniture_dict.get("locked"):
            lock_msg = f"The {canonical_furniture_name} is locked."
            required_key = target_furniture_dict.get("unlocks_with_item")
            if not required_key:
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
                item_world_data.get('is_hidden', False):

                    items_newly_found_names.append(item_name)
                    found_items_for_ui.append(item_name)

                    # Reveal the item in world state and revealed_items_in_rooms
                    item_world_data['is_hidden'] = False
                    self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_name)
                    logger.info(f"Item '{item_name}' revealed in {canonical_furniture_name} in {current_room_name}.")

                    # Handle evidence found
                    master_item_data = self._get_item_data(item_name)
                    if master_item_data and master_item_data.get("is_evidence"):
                        if self.achievements_system and not self.achievements_system.has_evidence(item_name):
                            self.achievements_system.record_evidence(
                                item_name, master_item_data.get('name', item_name), master_item_data.get('description', '')
                            )
                        self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE)

                        # --- Narrative flag/snippet logic ---
                        narrative_flag = master_item_data.get("narrative_flag_on_collect")
                        narrative_snippet = master_item_data.get("narrative_snippet_on_collect")
                        if narrative_flag:
                            self.player.setdefault("narrative_flags_collected", set()).add(narrative_flag)
                        if narrative_snippet:
                            self.player.setdefault("narrative_snippets_collected", []).append(narrative_snippet)

            if items_newly_found_names:
                action_message_parts.append(f"You find: {', '.join(item.capitalize() for item in items_newly_found_names)}.")
            else:
                action_message_parts.append("You find nothing new of interest.")

            # Hazard check on successful search
            if self.hazard_engine:
                hazard_result = self.hazard_engine.check_action_hazard('search', canonical_furniture_name, current_room_name)
                if hazard_result and isinstance(hazard_result, dict):
                    if hazard_result.get("message"): action_message_parts.append(hazard_result["message"])
                    if hazard_result.get("death"): death_triggered = True

        return {
            "message": "\n".join(filter(None, action_message_parts)),
            "death": death_triggered,
            "turn_taken": turn_taken,
            "found_items": found_items_for_ui if not death_triggered and turn_taken and found_items_for_ui else None
        }

    def _command_use(self, words):
        """Handles using an item, potentially on a target."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        message = "You can't use that."
        death_triggered = False
        turn_taken = True

        item_to_use_str = None
        target_object_str = None

        if not words:
            return {"message": "Use what?", "death": False, "turn_taken": False}

        # Parse "use item on target" or "use item"
        if "on" in words:
            try:
                on_index = words.index("on")
                item_to_use_str = " ".join(words[:on_index])
                target_object_str = " ".join(words[on_index+1:])
            except ValueError:
                item_to_use_str = " ".join(words)
        else:
            item_to_use_str = " ".join(words)

        # Find the item in inventory (case-insensitive)
        item_in_inventory_cased = next((inv_item for inv_item in self.player['inventory'] if inv_item.lower() == item_to_use_str.lower()), None)
        if not item_in_inventory_cased:
            return {"message": f"You don't have '{item_to_use_str}'.", "death": False, "turn_taken": False}

        item_master_data = self._get_item_data(item_in_inventory_cased)
        if not item_master_data:
            logger.error(f"Item '{item_in_inventory_cased}' in inventory but no master data found.")
            return {"message": "Error with item data.", "death": False, "turn_taken": False}

        current_room_name = self.player['location']

        # --- Special case: Using Bludworth's House Key on the front door from Front Porch ---
        if item_in_inventory_cased == "Bludworth's House Key" and \
        target_object_str and target_object_str.lower() == "front door" and \
        current_room_name == "Front Porch":
            front_door_object_exists = any(obj.lower() == "front door" for obj in self._get_current_room_data().get("objects", []))
            if not front_door_object_exists:
                return {"message": "There's no front door here to use the key on.", "death": False, "turn_taken": False}
            foyer_data = self.current_level_rooms.get("Foyer")
            if foyer_data and foyer_data.get("locked"):
                foyer_data["locked"] = False
                message = item_master_data.get("use_result", {}).get("front door", color_text("The front door is now unlocked.", "success"))
                logger.info("Front door unlocked using Bludworth's House Key via 'use' command.")
                # Optionally consume the key if one-time use
                # if item_master_data.get("consumable_on_use_for_target", {}).get("front door"):
                #     self.player['inventory'].remove(item_in_inventory_cased)
                #     message += f"\nThe {item_in_inventory_cased} remains in the lock."
                turn_taken = True
            elif foyer_data and not foyer_data.get("locked"):
                message = "The front door is already unlocked."
                turn_taken = False
            else:
                message = color_text("Error with Foyer data or the door state.", "error")
                turn_taken = False
            return {"message": message, "death": False, "turn_taken": turn_taken}

        # --- Specific High-Priority "Use" Cases (e.g., Lighter + Gas) ---
        if item_in_inventory_cased.lower() == "lighter":
            if self.hazard_engine:
                env_state = self.hazard_engine.get_env_state(current_room_name)
                if env_state.get('gas_level', 0) >= self.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD:
                    explosion_msg = self.hazard_engine.trigger_hazard_by_type('gas_leak', 'ignited', current_room_name,
                                                                            trigger_source_message=f"You flick the lighter...")
                    if self.is_game_over:
                        return {"message": explosion_msg or color_text("The room erupts in flames!", "error"), "death": True, "turn_taken": True}

        # --- General "Use Item on Target" Logic ---
        if target_object_str:
            allowed_targets_for_item = item_master_data.get("use_on", [])
            actual_target_cased = None
            if isinstance(allowed_targets_for_item, list):
                actual_target_cased = next((t for t in allowed_targets_for_item if t.lower() == target_object_str.lower()), None)

            if actual_target_cased:
                examinable_room_targets = self.get_examinable_targets_in_room()
                target_is_present_and_interactable = any(ert.lower() == actual_target_cased.lower() for ert in examinable_room_targets)
                if target_is_present_and_interactable:
                    use_results_dict = item_master_data.get("use_result", {})
                    result_msg_for_target = use_results_dict.get(actual_target_cased,
                        use_results_dict.get(actual_target_cased.lower(),
                            f"Using the {item_in_inventory_cased} on the {actual_target_cased} doesn't seem to do anything special."))
                    message = result_msg_for_target

                    # Example: Using "toolbelt" on "fireplace cavity"
                    if item_in_inventory_cased == "toolbelt" and actual_target_cased == "fireplace cavity":
                        self.interaction_counters["fireplace_reinforced"] = True
                        logger.info("Fireplace cavity reinforced with toolbelt.")

                    # Example: Using "Bloody Brick" or "loose brick" on "boarded window"
                    if item_in_inventory_cased.lower() in ["bloody brick", "loose brick"] and actual_target_cased.lower() == "boarded window":
                        logger.info(f"Brick used on boarded window in {current_room_name}.")

                    # Consume item if defined
                    if item_master_data.get("consumable_on_use"):
                        self.player['inventory'].remove(item_in_inventory_cased)
                        message += f"\nThe {item_in_inventory_cased} is used up."
                        logger.info(f"Item '{item_in_inventory_cased}' consumed.")

                    # Hazard check for using item on target
                    if self.hazard_engine:
                        hazard_resp = self.hazard_engine.check_action_hazard('use', actual_target_cased, current_room_name, item_used=item_in_inventory_cased)
                        if hazard_resp and isinstance(hazard_resp, dict):
                            if hazard_resp.get("message"): message += "\n" + hazard_resp["message"]
                            if hazard_resp.get("death"): death_triggered = True
                else:
                    message = f"You don't see '{target_object_str}' here to use the {item_in_inventory_cased} on."
                    turn_taken = False
            else:
                message = f"You can't use the {item_in_inventory_cased} on the {target_object_str}."
                # turn_taken remains True for attempting an invalid use

        # --- General "Use Item" (no target) ---
        else:
            general_use_effect_msg = item_master_data.get("general_use_effect_message")
            if general_use_effect_msg:
                message = general_use_effect_msg
                if item_master_data.get("heal_amount"):
                    heal_val = item_master_data["heal_amount"]
                    old_hp = self.player['hp']
                    self.player['hp'] = min(self.player['max_hp'], old_hp + heal_val)
                    message += f" You heal for {self.player['hp'] - old_hp} HP."
                    logger.info(f"Player used {item_in_inventory_cased}, healed to {self.player['hp']}.")
                if item_master_data.get("consumable_on_use"):
                    self.player['inventory'].remove(item_in_inventory_cased)
                    message += f"\nThe {item_in_inventory_cased} is used up."
                    logger.info(f"Item '{item_in_inventory_cased}' consumed.")
            else:
                message = f"You fiddle with the {item_in_inventory_cased}, but nothing specific happens."

        return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

    def _command_drop(self, item_name_str):
        """Handles dropping an item from inventory."""
        # ... (Implementation from your existing game_logic.py, to be analyzed) ...
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name_str:
            return {"message": "Drop what?", "turn_taken": False}

        item_name_lower = item_name_str.lower()
        item_to_drop_cased = next((item for item in self.player['inventory'] if item.lower() == item_name_lower), None)

        if not item_to_drop_cased:
            return {"message": f"You don't have '{item_name_str}' to drop.", "turn_taken": False}

        current_room_name = self.player['location']
        self.player['inventory'].remove(item_to_drop_cased)

        # Update item's world state
        item_world_data = self.current_level_items_world_state.get(item_to_drop_cased)
        if item_world_data:
            item_world_data['location'] = current_room_name
            item_world_data['container'] = None # Dropped directly into room
            item_world_data['is_hidden'] = False # Dropped items are visible
        else: # Should not happen if item was in inventory and world state is consistent
            logger.error(f"Item '{item_to_drop_cased}' dropped from inventory, but no corresponding world state found to update.")
            # Re-add to world state if completely missing (as a fallback)
            self.current_level_items_world_state[item_to_drop_cased] = {
                "location": current_room_name, "container": None, "is_hidden": False,
                "description": self._get_item_data(item_to_drop_cased).get("description", "A dropped item."), # Get original desc
                "takeable": True # Should be takeable again
                # Copy other relevant master data if needed
            }


        # Add to revealed_items_in_rooms so it's immediately visible in room description
        self.revealed_items_in_rooms.setdefault(current_room_name, set()).add(item_to_drop_cased)
        
        logger.info(f"Player dropped '{item_to_drop_cased}' in '{current_room_name}'.")
        return {"message": f"You drop the {item_to_drop_cased}.", "turn_taken": True, "item_dropped": item_to_drop_cased}
    
    def _command_unlock(self, target_name_str):
        """Handles unlocking doors or furniture."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        message = ""
        death_triggered = False
        turn_taken = True  # Attempting to unlock takes a turn
        unlocked_something = False

        target_name_lower = target_name_str.lower()
        current_room_name = self.player['location']
        current_room_data_world = self.current_level_rooms.get(current_room_name)
        inventory = self.player.get('inventory', [])

        if not current_room_data_world:
            return {"message": color_text("Error: Current room data missing.", "error"), "death": False, "turn_taken": False}

        # --- Special case: Unlocking the front door from the Front Porch ---
        if target_name_lower == "front door" and current_room_name == "Front Porch":
            foyer_room_data = self.current_level_rooms.get("Foyer")
            if "Bludworth's House Key" in inventory:
                if foyer_room_data:
                    foyer_room_data["locked"] = False
                    message = color_text("You use Bludworth's House Key and unlock the front door.", "success")
                    unlocked_something = True
                    logger.info("Front door unlocked with Bludworth's House Key.")
                else:
                    message = color_text("Error: Foyer room data not found.", "error")
            else:
                message = "You need a key for the front door."
            return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

        # --- Try to unlock an exit (door) ---
        found_target_exit = False
        for direction, dest_room_name_master in current_room_data_world.get("exits", {}).items():
            if direction.lower() == target_name_lower or dest_room_name_master.lower() == target_name_lower:
                found_target_exit = True
                dest_room_world_data = self.current_level_rooms.get(dest_room_name_master)
                if dest_room_world_data and dest_room_world_data.get("locked"):
                    dest_room_master_data = self.game_data.rooms.get(self.player['current_level'], {}).get(dest_room_name_master, {})
                    required_key_name = dest_room_master_data.get('unlocks_with')
                    if required_key_name and required_key_name in inventory:
                        dest_room_world_data["locked"] = False
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
                else:
                    message = f"The path '{target_name_str}' doesn't seem to lead anywhere valid."
                    turn_taken = False
                break

        # --- If not an exit, try to unlock furniture ---
        if not found_target_exit:
            target_furniture_dict_world = None
            furniture_list_world = current_room_data_world.get("furniture", [])
            for i, furn_dict_world in enumerate(furniture_list_world):
                if furn_dict_world.get("name", "").lower() == target_name_lower:
                    target_furniture_dict_world = furn_dict_world
                    furn_idx_world = i
                    break

            if target_furniture_dict_world and target_furniture_dict_world.get("locked"):
                furn_name_cased = target_furniture_dict_world["name"]
                furn_master_data = None
                for fm_dict in self.game_data.rooms.get(self.player['current_level'], {}).get(current_room_name, {}).get("furniture", []):
                    if fm_dict.get("name", "") == furn_name_cased:
                        furn_master_data = fm_dict
                        break
                required_key_name = furn_master_data.get("unlocks_with_item") if furn_master_data else None
                if required_key_name and required_key_name in inventory:
                    self.current_level_rooms[current_room_name]['furniture'][furn_idx_world]["locked"] = False
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

        # --- Hazard check if unlocking triggered something ---
        if unlocked_something and self.hazard_engine:
            hazard_resp = self.hazard_engine.check_action_hazard('unlock', target_name_str, current_room_name)
            if hazard_resp and isinstance(hazard_resp, dict):
                if hazard_resp.get("message"):
                    message += "\n" + hazard_resp["message"]
                if hazard_resp.get("death"):
                    death_triggered = True

        return {"message": message, "death": death_triggered, "turn_taken": turn_taken}

    def _command_inventory(self):
        """Displays the player's inventory."""
        inventory = self.player.get('inventory', [])
        if not inventory:
            return {"message": "Your inventory is empty.", "turn_taken": False}
        
        item_details = []
        for item_name in inventory:
            item_data = self._get_item_data(item_name) # Get master data for weight, type
            desc = item_name.capitalize()
            if item_data:
                if item_data.get("is_evidence"):
                    desc = color_text(desc, "evidence")
                else:
                    desc = color_text(desc, "item")
                # Add weight or type if desired: e.g. f"{desc} (Wt: {item_data.get('weight',1)})"
            item_details.append(desc)
            
        message = "You are carrying: " + ", ".join(item_details) + "."
        return {"message": message, "turn_taken": False}

    def _command_list_actions(self):
        """Generates a formatted string of possible actions for the player."""
        # (Implementation from your existing game_logic.py, to be analyzed for completeness)
        # For now, a placeholder:
        message_parts = [color_text("Possible actions:", "info")]
        # This should dynamically list valid verbs and targets based on current game state.
        # Example:
        # valid_moves = self.get_valid_directions() -> "Move: North, South"
        # examinable = self.get_examinable_targets_in_room() -> "Examine: Table, Door"
        # ... etc.
        message_parts.append("  Move [direction]")
        message_parts.append("  Examine [object/item/room]")
        message_parts.append("  Take [item]")
        message_parts.append("  Search [furniture]")
        message_parts.append("  Use [item] on [target]")
        message_parts.append("  Drop [item]")
        message_parts.append("  Unlock [door/furniture]")
        message_parts.append("  Inventory")
        message_parts.append("  Map")
        message_parts.append("  Save / Load")
        message_parts.append("  Quit / Newgame")
        return {"message": "\n".join(message_parts), "turn_taken": False}

    def _command_map(self):
        """Displays a textual map of the current area."""
        # This method can call a helper to generate the map string.
        # The helper could be in this class or in a dedicated map_utils.py
        # map_string = self._generate_text_map() # Example
        # For now, placeholder:
        map_string = "Text map feature coming soon!"
        if hasattr(self, 'get_gui_map_string'): # If the detailed one exists
            map_string = self.get_gui_map_string() # Use the more detailed one
        else:
            map_string = f"You are in the {self.player['location']}."
            exits = self.get_valid_directions()
            if exits:
                map_string += f"\nExits: {', '.join(exits)}"

        return {"message": map_string, "turn_taken": False}
        
    # Helper to get item master data (already defined in Phase 1, but relevant here)
    def _get_item_data(self, item_name):
        """Gets master data for a specific item."""
        target_name_lower = item_name.lower()
        # Check master copy (which should include items, evidence, keys)
        for name, data in self.current_level_items_master_copy.items():
            if name.lower() == target_name_lower:
                return copy.deepcopy(data) # Return a copy to prevent modification of master
        return None

    # Helper to get current room data (already defined in Phase 1)
    def _get_current_room_data(self):
        """Get the data for the room the player is currently in (from current_level_rooms)."""
        current_room_name = self.player.get('location')
        if not current_room_name:
            return None
        return self.current_level_rooms.get(current_room_name) # current_level_rooms is already a deepcopy

    # Helper to get a specific furniture piece from room data
    def _get_furniture_piece(self, room_data_dict, furniture_name_str):
        """
        Finds and returns the dictionary for a piece of furniture in the given room_data_dict.
        Case-insensitive search. Returns None if not found.
        """
        if not room_data_dict or not isinstance(room_data_dict.get("furniture"), list):
            return None
        target_lower = furniture_name_str.lower()
        for furn_dict in room_data_dict["furniture"]:
            if isinstance(furn_dict, dict) and furn_dict.get("name", "").lower() == target_lower:
                return furn_dict
        return None


    def _handle_status_effects_pre_action(self):
        """
        Handles status effects that might prevent or alter an action *before* it's taken.
        Returns a list of messages and a boolean indicating if the action was prevented.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        messages = []
        action_prevented = False

        if not isinstance(self.player.get("status_effects"), dict):
            self.player["status_effects"] = {} # Ensure it's a dict
            return messages, action_prevented

        # Example: 'stunned' effect prevents action
        if "stunned" in self.player["status_effects"]:
            effect_def = self.game_data.status_effects_definitions.get("stunned", {})
            messages.append(color_text(effect_def.get("message_on_action_attempt", "You are stunned and cannot act!"), "warning"))
            action_prevented = True
            logger.info("Player action prevented by 'stunned' status.")
        
        # Example: 'disoriented' might cause action failure (handled in process_player_input after this)
        # This function focuses on effects that *stop* an action before it's even dispatched.

        return messages, action_prevented

    def _handle_status_effects_tick(self):
        """
        Processes active status effects at the end of a turn (after action).
        Applies damage, decrements duration, and removes expired effects.
        Returns a list of messages related to status effect ticks.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        tick_messages = []
        effects_to_remove = []
        
        if not isinstance(self.player.get("status_effects"), dict):
            self.player["status_effects"] = {} # Ensure it's a dict
            return tick_messages # No effects to tick

        active_effects = copy.deepcopy(self.player["status_effects"]) # Iterate over a copy

        for effect_name, turns_left in active_effects.items():
            effect_def = self.game_data.status_effects_definitions.get(effect_name)
            if not effect_def:
                logger.warning(f"Status effect '{effect_name}' on player but not in definitions. Removing.")
                effects_to_remove.append(effect_name)
                continue

            # Message on tick
            msg_on_tick = effect_def.get("message_on_tick")
            if msg_on_tick:
                tick_messages.append(color_text(msg_on_tick, "warning"))

            # HP change per turn
            hp_change = effect_def.get("hp_change_per_turn", 0)
            if hp_change != 0:
                self.apply_damage_to_player(-hp_change, f"status effect: {effect_name}") # Negative for healing
                # apply_damage_to_player will log and check for game over
                if hp_change < 0: # Healing
                     tick_messages.append(color_text(f"You feel a bit better due to {effect_name}.", "success"))
                # Damage message will be part of apply_damage_to_player or a general "you lose HP"
            
            # Decrement duration
            self.player["status_effects"][effect_name] -= 1
            if self.player["status_effects"][effect_name] <= 0:
                effects_to_remove.append(effect_name)
                msg_on_expire = effect_def.get("message_on_wear_off")
                if msg_on_expire:
                    tick_messages.append(color_text(msg_on_expire, "info"))
                logger.info(f"Status effect '{effect_name}' expired.")

        for effect_name in effects_to_remove:
            if effect_name in self.player["status_effects"]:
                del self.player["status_effects"][effect_name]
        
        return tick_messages

    def _handle_turn_progression_and_final_checks(self):
        """
        Central method called after a turn-taking action.
        Updates world state (hazards), status effects, HP, turns, checks for game over.
        Returns a list of messages generated during this progression.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        progression_messages = []

        if self.is_game_over: # Should not happen if called correctly, but as a safeguard
            logger.warning("_handle_turn_progression called when game is already over.")
            return progression_messages

        # 1. Hazard Engine Update (environmental changes, autonomous hazard actions)
        if self.hazard_engine:
            hazard_update_msgs, death_from_hazards = self.hazard_engine.hazard_turn_update()
            if hazard_update_msgs:
                progression_messages.extend(hazard_update_msgs)
            if death_from_hazards: # Hazard engine might set self.is_game_over
                self.is_game_over = True # Ensure it's set here too
                self.game_won = False
                logger.info("Game over triggered by HazardEngine update.")
                # Death message should come from hazard_engine
                if not any("fatal" in msg.lower() or "die" in msg.lower() for msg in progression_messages):
                    progression_messages.append(color_text("The environment proved deadly!", "error"))


        # 2. Status Effects Tick (apply damage, decrement duration)
        # This should happen even if hazards caused game over, to resolve effects.
        status_tick_messages = self._handle_status_effects_tick()
        if status_tick_messages:
            progression_messages.extend(status_tick_messages)
        
        # Check for game over from status effect damage (apply_damage_to_player handles this)
        if self.player.get("hp", 0) <= 0 and not self.is_game_over:
            self.is_game_over = True
            self.game_won = False
            logger.info("Game over: Player HP <= 0 after status effect ticks.")
            if not any("fatal" in msg.lower() or "succumb" in msg.lower() for msg in progression_messages):
                 progression_messages.append(color_text("You succumb to your afflictions.", "error"))


        # 3. Decrement Player Turns Left (if game not already over)
        if not self.is_game_over:
            self.player["turns_left"] = self.player.get("turns_left", 0) - 1
            self.player["actions_taken"] = self.player.get("actions_taken", 0) + 1
            self.player["actions_taken_this_level"] = self.player.get("actions_taken_this_level", 0) + 1 # Increment per-level counter
           
            if self.player["turns_left"] <= 0:
                self.is_game_over = True
                self.game_won = False # Ran out of time
                logger.info("Game over: Turns ran out.")
                progression_messages.append(color_text("Time is up! Dawn breaks, and whatever malevolent force resides here claims you.", "error"))
        
        # 4. Final check for win conditions (e.g. if an action achieved a win state)
        # This is more for actions that directly win, not just surviving turns.
        # self.check_win_conditions() # This method would be defined if needed

        return progression_messages

    def apply_damage_to_player(self, damage_amount, source="an unknown source"):
        """Applies damage to the player and checks for game over."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.is_game_over: return

        # damage_amount can be negative for healing
        old_hp = self.player.get("hp", 0)
        new_hp = old_hp - damage_amount
        
        if damage_amount > 0: # Actual damage
            self.player["hp"] = max(0, new_hp)
            logger.info(f"Player took {damage_amount} damage from {source}. HP: {old_hp} -> {self.player['hp']}")
            # Message for damage can be added by the caller or here.
            # For example: self.game_logic.add_message_to_queue(f"Took {damage_amount} from {source}")
        elif damage_amount < 0: # Healing
            self.player["hp"] = min(self.player.get("max_hp", 10), new_hp) # Assuming max_hp exists
            logger.info(f"Player healed {-damage_amount} from {source}. HP: {old_hp} -> {self.player['hp']}")

        if self.player["hp"] <= 0:
            self.is_game_over = True
            self.game_won = False
            self.player['last_hazard_type'] = source # Store general source
            logger.info(f"Game Over: Player HP reached 0 from {source}.")
            # A generic death message can be added here if not provided by the source of damage.
            # e.g., return a death message string or set a flag for process_player_input to use.

    def apply_status_effect(self, effect_name, duration_override=None, messages_list=None):
        """
        Applies a status effect to the player.
        Appends a message to messages_list if provided.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not hasattr(self.game_data, 'status_effects_definitions'):
            logger.warning("status_effects_definitions not found in game_data.")
            return False
            
        effect_def = self.game_data.status_effects_definitions.get(effect_name)
        if not effect_def:
            logger.warning(f"Attempted to apply unknown status effect: {effect_name}")
            return False
        
        duration = duration_override if duration_override is not None else effect_def.get("duration", 1)
        
        if not isinstance(self.player.get("status_effects"), dict):
            self.player["status_effects"] = {}
            
        self.player["status_effects"][effect_name] = duration # Set or refresh duration
        
        apply_message = effect_def.get("message_on_apply", f"You are now {effect_name}.")
        if messages_list is not None:
            messages_list.append(color_text(apply_message, "warning"))
        else: # If no message list, log it or it might be silent
            logger.info(f"Applied status: {effect_name}. Message: {apply_message}")
            
        logger.info(f"Applied status effect: {effect_name} for {duration} turns.")
        return True

    def _handle_house_escape_sequence(self):
        """
        Handles the sequence when the player attempts to leave the house (Level 1 exit).
        This can result in a QTE.
        Returns a response dictionary.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        player_current_weight = self._calculate_player_inventory_weight()
        is_player_heavy = player_current_weight >= self.game_data.HEAVY_PLAYER_THRESHOLD

        response = {
            "message": "", "death": False, "turn_taken": True, # Attempting escape takes a turn
            "qte_triggered": None # Will be populated if QTE starts
        }

        # Logic for weak floorboards on the Front Porch during escape attempt
        floorboard_outcome_message = ""
        player_tripped_and_saved_by_floorboards = False

        if self.hazard_engine and self.player['location'] == self.game_data.ROOM_FRONT_PORCH:
            fp_hazard_id, fp_hazard_instance = None, None
            for hz_id, hz in self.hazard_engine.active_hazards.items():
                if hz['location'] == self.game_data.ROOM_FRONT_PORCH and hz['type'] == self.game_data.HAZARD_TYPE_WEAK_FLOORBOARDS:
                    fp_hazard_id, fp_hazard_instance = hz_id, hz
                    break
            
            if fp_hazard_instance:
                hazard_data = fp_hazard_instance['data']
                # Check for a specific "tripping_on_escape" state or similar in weak_floorboards definition
                # For this example, we'll assume a general 'tripping' state or a direct effect if heavy.
                tripping_state_def = hazard_data['states'].get("tripping_on_porch") # From game_data.hazards

                if is_player_heavy and tripping_state_def:
                    logger.info("Player is HEAVY on Front Porch during escape. Forcing 'tripping' outcome for weak floorboards.")
                    temp_messages = []
                    # This state change might have its own messages
                    self.hazard_engine._set_hazard_state(fp_hazard_id, "tripping_on_porch", temp_messages)
                    floorboard_outcome_message = "\n".join(temp_messages) # Use messages from state change
                    if not floorboard_outcome_message: # Fallback message
                         floorboard_outcome_message = tripping_state_def.get('description', "The porch groans and a board snaps under your weight, making you stumble!")
                    player_tripped_and_saved_by_floorboards = True # Key change: this implies QTE later
                else:
                    floorboard_outcome_message = color_text("You step confidently towards the exit, the old porch creaking but holding.", "default")
            else:
                logger.warning("ENDGAME (House Escape): Weak floorboards hazard not found on Front Porch!")
                floorboard_outcome_message = "You head for the exit..."
        
        response["message"] = floorboard_outcome_message

        # Wrecking Ball QTE sequence
        qte_message = ""
        if player_tripped_and_saved_by_floorboards:
            qte_message = color_text("\nAs you're on the ground, a massive WRECKING BALL smashes through the air where you would have been standing, obliterating the front of the house!", "special")
            qte_message += color_text(f"\nIt swings back, arcing directly towards you again! You have {self.game_data.QTE_DODGE_WRECKING_BALL_DURATION} seconds to type '{self.game_data.QTE_RESPONSE_DODGE.upper()}'!", "error")
        else: # Didn't trip, wrecking ball is an immediate threat
            qte_message = color_text("\nYou open the front door and step out. Suddenly, an immense shadow engulfs you. A massive WRECKING BALL, part of an unannounced demolition, swings directly towards you!", "error")
            qte_message += color_text(f"\nYou have a split second to react! Type '{self.game_data.QTE_RESPONSE_DODGE.upper()}' to avoid being crushed! ({self.game_data.QTE_DODGE_WRECKING_BALL_DURATION}s)", "special")

        response["message"] += f"\n{qte_message}"
        response["qte_triggered"] = {
            "type": self.game_data.QTE_TYPE_DODGE_WRECKING_BALL, # "dodge_wrecking_ball"
            "duration": self.game_data.QTE_DODGE_WRECKING_BALL_DURATION,
            "context": {
                "success_message": "You narrowly dodge the wrecking ball! You scramble away from the debris as the demolition crew realizes their near-fatal mistake, evidence clutched in your hand!",
                "failure_message": "You react too slowly. The wrecking ball connects with devastating force, and the world goes black.",
                "on_success_level_complete": True, # Custom flag for QTE handler
                "on_failure_fatal": True
            }
        }
        logger.info("House escape sequence initiated, wrecking ball QTE triggered.")
        return response

    def trigger_qte(self, qte_type, duration, context):
        """
        Called by HazardEngine or other systems to initiate a QTE.
        The UI (GameScreen) will observe player['qte_active'] to display the timer.
        """
        if self.player.get('qte_active'):
            self.logger.warning(f"Attempted to trigger QTE '{qte_type}' while QTE '{self.player['qte_active']}' is already active. Ignoring new QTE.")
            return

        self.player['qte_active'] = qte_type
        self.player['qte_duration'] = duration
        self.player['qte_context'] = context # context includes success/failure messages, damage, fatality, and hazard progression info
        
        # The QTE prompt message should be built by the caller (HazardEngine) and sent to the player via its messages_list
        # GameLogic itself doesn't append to output here, that's the job of the GameScreen based on messages from HazardEngine.
        self.logger.info(f"QTE '{qte_type}' triggered by system. Duration: {duration}s. Context: {context}")
        # The GameScreen will pick this up in its update loop or on_game_session_ready if a QTE is loaded.

    def _handle_qte_response(self, qte_type_from_player_state, user_input_str): # Renamed qte_type to avoid conflict
        """Handles player's response to an active QTE."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        
        # qte_type_from_player_state is self.player['qte_active']
        qte_context = self.player.get('qte_context', {})

        # Clear QTE state immediately *from player dict*
        self.player['qte_active'] = None
        self.player['qte_duration'] = 0
        # Keep qte_context local for processing this response

        response = { # This is the response dict for GameScreen
            "message": "", "death": False, "turn_taken": True, "success": False,
            "transition_to_level": None, "next_level_start_room": None
        }

        # Determine success based on qte_type and user_input_str
        qte_master_definition = self.game_data.qte_definitions.get(qte_type_from_player_state, {}) #
        valid_responses = qte_master_definition.get("valid_responses", [game_data.QTE_RESPONSE_DODGE]) # Fallback
        
        is_success = user_input_str.lower() in [vr.lower() for vr in valid_responses]

        if is_success:
            response["success"] = True
            response["message"] = color_text(qte_context.get("success_message", qte_master_definition.get("success_message_default", "You succeed!")), "success")
            self.player["score"] = self.player.get("score", 0) + qte_master_definition.get("score_on_success", 10)
            self.unlock_achievement(self.game_data.ACHIEVEMENT_QUICK_REFLEXES) # General achievement for QTE success

            # If QTE was triggered by a hazard, progress that hazard
            source_hazard_id = qte_context.get('qte_source_hazard_id')
            next_hazard_state_on_success = qte_context.get('next_state_for_hazard') # Could be specific for success if needed

            if source_hazard_id and next_hazard_state_on_success and self.hazard_engine:
                # We need a temporary list for messages from _set_hazard_state if we want to include them
                hazard_progression_messages = []
                if source_hazard_id in self.hazard_engine.active_hazards: # Ensure hazard still exists
                    self.hazard_engine._set_hazard_state(source_hazard_id, next_hazard_state_on_success, hazard_progression_messages)
                    if hazard_progression_messages:
                        response["message"] += "\n" + "\n".join(hazard_progression_messages)
                else:
                    logger.warning(f"QTE success: Source hazard {source_hazard_id} no longer active. Cannot progress its state.")
            
            # Handle level completion if QTE context specifies it (like wrecking ball)
            if qte_context.get("on_success_level_complete"):
                # ... (existing level completion logic from your _handle_qte_response) ...
                current_level_id = self.player.get("current_level", 1)
                level_reqs = self.game_data.LEVEL_REQUIREMENTS.get(current_level_id, {})
                next_level_id_val = level_reqs.get("next_level_id") # Renamed to avoid conflict
                
                if next_level_id_val is not None:
                    response["message"] += color_text(f"\nYou've survived Level {current_level_id}!", "special")
                    # The actual transition will be handled by GameScreen based on these flags being set
                    # by process_player_input after this QTE response is processed.
                    # For now, let's assume GameLogic's process_player_input or the main game loop
                    # will see these flags on the response and call self.transition_to_new_level.
                    # Or, we can directly set up the transition data here for process_player_input to consume.
                    response["level_transition"] = { # New key to signal transition
                        "next_level_id": next_level_id_val,
                        "completed_level_id": current_level_id # For achievements
                    }
                else: # Final level completed
                    self.game_won = True
                    self.is_game_over = True
                    response["message"] += color_text("\nIncredible! You've cheated Death and survived the final ordeal!", "success")


        else: # QTE Failure
            response["success"] = False
            response["message"] = color_text(qte_context.get("failure_message", qte_master_definition.get("failure_message_default", "You failed!")), "error")
            
            hp_damage = qte_context.get("hp_damage_on_failure", qte_master_definition.get("hp_damage_on_failure", 0))
            is_fatal = qte_context.get("is_fatal_on_failure", True) # Default to fatal if not specified by context

            if is_fatal:
                response["death"] = True
                self.is_game_over = True 
                self.game_won = False
                self.player['last_hazard_type'] = f"Failed QTE: {qte_type_from_player_state}"
                self.player['last_death_message'] = response["message"] # Use the QTE failure message
            elif hp_damage > 0:
                self.apply_damage_to_player(hp_damage, f"failing QTE {qte_type_from_player_state}")
                response["message"] += f" You take {hp_damage} damage."
                if self.player['hp'] <= 0: # Check if damage was fatal
                    response["death"] = True # is_game_over already set by apply_damage
                    self.player['last_death_message'] = response["message"] # Update last death message

            # If QTE was triggered by a hazard, progress that hazard even on failure (if not game over)
            if not self.is_game_over:
                source_hazard_id = qte_context.get('qte_source_hazard_id')
                next_hazard_state_on_failure = qte_context.get('next_state_for_hazard') # Could be specific state for failure if needed
                if source_hazard_id and next_hazard_state_on_failure and self.hazard_engine:
                    hazard_progression_messages = []
                    if source_hazard_id in self.hazard_engine.active_hazards:
                        self.hazard_engine._set_hazard_state(source_hazard_id, next_hazard_state_on_failure, hazard_progression_messages)
                        if hazard_progression_messages:
                             response["message"] += "\n" + "\n".join(hazard_progression_messages)
                    else:
                        logger.warning(f"QTE failure: Source hazard {source_hazard_id} no longer active.")
        
        self.player.pop('qte_context', None) # Clear context after use
        logger.info(f"QTE '{qte_type_from_player_state}' response processed. Success: {is_success}. Player HP: {self.player.get('hp')}")
        
        # If the QTE itself didn't end the game, but its consequences (like hazard state change) did, reflect that.
        if self.is_game_over and not response.get("death"):
            response["death"] = True # Game over was set by a side effect (e.g. hazard progression)

        return response

    def log_evaded_hazard(self, hazard_description_of_evasion):
        """Adds a description of an evaded hazard for the inter-level screen."""
        if self.player:
            self.player.setdefault('evaded_hazards_current_level', []).append(hazard_description_of_evasion)
            self.logger.info(f"Logged evaded hazard: {hazard_description_of_evasion}")

    def transition_to_new_level(self, new_level_id, start_room_override=None):
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        completed_level_id = self.player['current_level']
        logger.info(f"Transitioning from Level {completed_level_id} to Level {new_level_id}...")

        self.player['current_level'] = new_level_id
        level_start_info = self.game_data.LEVEL_REQUIREMENTS.get(new_level_id, {})
        self.player['location'] = start_room_override or level_start_info.get('entry_room')
        if not self.player['location']:
             logger.error(f"Cannot transition: No entry room defined for level {new_level_id}.")
             return None # Indicate failure
        self.player.setdefault('visited_rooms', set()).add(self.player['location'])

        # Reset per-level stats for the new level
        self.player['actions_taken_this_level'] = 0
        self.player['evidence_found_this_level'] = []
        self.player['evaded_hazards_current_level'] = [] 
            
        self._initialize_level_data(new_level_id) 
        
        if self.hazard_engine: # Re-initialize hazard engine for the new level
            self.hazard_engine.initialize_for_level(new_level_id)
            
        logger.info(f"Player transitioned to Level {new_level_id}, starting in {self.player['location']}.")
        
        return {
            "success": True,
            "next_level_id": new_level_id,
            "next_level_start_room": self.player['location'],
            "completed_level_id": completed_level_id,
            "new_room_description_for_ui": self.get_room_description()
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

    def unlock_achievement(self, achievement_id): # Wrapper for achievements system
        """Unlocks an achievement if the system is available."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.achievements_system:
            # The achievements_system.unlock method should return True if newly unlocked
            if self.achievements_system.unlock(achievement_id):
                 logger.info(f"Achievement '{achievement_id}' unlocked via GameLogic.")
                 # Notification is handled by AchievementsSystem's callback
                 return True
        else:
            logger.warning(f"Attempted to unlock achievement '{achievement_id}' but AchievementsSystem is not available.")
        return False



    def _get_item_data(self, item_name):
        """
        Gets master data for a specific item by its name (case-insensitive).
        Checks the current level's master copy of items.

        Args:
            item_name (str): The name of the item to retrieve.

        Returns:
            dict or None: A deep copy of the item's data if found, otherwise None.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not item_name:
            return None
        
        target_name_lower = item_name.lower()
        # current_level_items_master_copy should contain all items (items, evidence, keys) for the level
        for name, data in self.current_level_items_master_copy.items():
            if name.lower() == target_name_lower:
                return copy.deepcopy(data) # Return a copy to prevent modification of master
        
        logger.debug(f"Item data for '{item_name}' not found in current level's master copy.")
        return None

    def _get_current_room_data(self):
        """
        Get the data for the room the player is currently in.
        This refers to the modifiable copy of the room data for the current level.
        
        Returns:
            dict or None: The data dictionary for the current room, or None if not found.
        """
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
        """
        Get data for a specific room by name from the current level's modifiable room data.
        
        Args:
            room_name (str): The name of the room.

        Returns:
            dict or None: The data dictionary for the specified room, or None if not found.
        """
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
        """
        Generates the full, color-enhanced description for a room,
        including its base description, visible items, furniture, exits,
        and active hazard information.

        Args:
            room_name (str, optional): The name of the room. 
                                       Defaults to the player's current location.

        Returns:
            str: A formatted string describing the room.
        """
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
        description_parts.append(self._enhance_description_keywords(room_data.get("description", "An empty space.")))

        # Visible items (not in containers, not hidden)
        items_in_room_direct = []
        for item_key, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == room_name and \
               not item_world_data.get('container') and \
               not item_world_data.get('is_hidden'):
                item_master = self._get_item_data(item_key) # For type checking
                color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                items_in_room_direct.append(color_text(item_key.capitalize(), color_type))
        
        if items_in_room_direct:
            description_parts.append("\n" + color_text("You see here: ", "default") + ", ".join(items_in_room_direct) + ".")

        # Revealed items (from searches, not in inventory yet)
        revealed_items_in_room = []
        for item_key in self.revealed_items_in_rooms.get(room_name, set()):
            item_world_data = self.current_level_items_world_state.get(item_key)
            # Ensure it's still in this room, not in a container (already handled by search), and not taken
            if item_world_data and item_world_data.get('location') == room_name and \
               not item_world_data.get('container') and \
               item_key not in self.player.get('inventory', []):
                # Avoid duplicating if it was already listed by being non-hidden initially
                item_master = self._get_item_data(item_key)
                color_type = 'evidence' if item_master and item_master.get('is_evidence') else 'item'
                formatted_revealed_item = color_text(item_key.capitalize() + " (revealed)", color_type)
                if formatted_revealed_item not in items_in_room_direct : # Basic check to avoid exact duplicate strings
                    revealed_items_in_room.append(formatted_revealed_item)
        
        if revealed_items_in_room:
            description_parts.append("\n" + color_text("You've also noticed: ", "default") + ", ".join(revealed_items_in_room) + ".")


        # Room objects (scenery)
        room_objects_list = room_data.get("objects", [])
        if room_objects_list:
            description_parts.append("\n" + color_text("Objects: ", "default") + ", ".join(color_text(obj.capitalize(), 'item') for obj in room_objects_list) + ".") # item color for general objects
            
        # Furniture
        furniture_list_data = room_data.get("furniture", [])
        if furniture_list_data:
            furniture_descs = []
            for f_dict in furniture_list_data:
                f_name = f_dict.get("name", "unknown furniture").capitalize()
                f_desc = color_text(f_name, 'furniture')
                if f_dict.get("locked"):
                    f_desc += color_text(" (Locked)", "warning")
                furniture_descs.append(f_desc)
            description_parts.append("\n" + color_text("Furniture: ", "default") + ", ".join(furniture_descs) + ".")

        # Hazard Descriptions & Environmental State
        if self.hazard_engine:
            env_state = self.hazard_engine.get_env_state(room_name)
            hazard_descs_from_engine = self.hazard_engine.get_room_hazards_descriptions(room_name) # Already colored

            env_messages = []
            if env_state.get('gas_level', 0) >= self.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD: # Constant from game_data
                env_messages.append(color_text("The air is thick and heavy with gas!", "error"))
            elif env_state.get('gas_level', 0) >= 1:
                env_messages.append(color_text("You smell gas in the air.", "warning"))
            
            if env_state.get('is_on_fire'):
                env_messages.append(color_text("The room is on fire!", "fire"))
            elif env_state.get('is_sparking') and not any("spark" in hd.lower() for hd in hazard_descs_from_engine):
                # Avoid redundancy if a hazard description already mentions sparks
                env_messages.append(color_text("Electrical sparks crackle nearby!", "hazard"))

            if env_state.get('is_wet'):
                env_messages.append(color_text("The floor is wet here.", "default")) # Or 'info'
            
            if env_state.get('visibility') != "normal":
                env_messages.append(color_text(f"Visibility is {env_state.get('visibility')}.", "warning"))
            
            if env_state.get('noise_level',0) >= 3: # e.g. very loud
                 env_messages.append(color_text("It's deafeningly noisy here.", "warning"))
            elif env_state.get('noise_level',0) >= 1: # e.g. noticeable
                 env_messages.append(color_text("There's a noticeable background noise.", "default"))

            if env_messages:
                description_parts.append("\n" + "\n".join(env_messages))
            if hazard_descs_from_engine:
                description_parts.append("\n" + "\n".join(hazard_descs_from_engine))
        
        # Exits
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

        return "\n".join(filter(None, description_parts)).strip() # filter(None,...) removes empty strings

    def _enhance_description_keywords(self, description_text):
        """
        Enhances a given text by applying Kivy color markup to keywords.
        Used internally by get_room_description.
        """
        # This implementation can be simple or complex.
        # A more robust version might use regex for word boundaries.
        # For now, a basic split and check.
        
        # Define keywords and their associated text_type for color_text function
        keyword_map = {
            # Hazards & Dangers
            "hazard": "hazard", "danger": "hazard", "deadly": "hazard", "precarious": "hazard",
            "unstable": "hazard", "weak": "hazard", "floorboards": "hazard", "falling": "hazard",
            "collapse": "hazard", "sparking": "hazard", "gas": "warning", "electrified": "hazard",
            "fire": "fire", "flames": "fire", "burning": "fire", "smoldering": "fire",
            "smoke": "warning", "ash": "default", "heat": "fire", "explosion": "fire",
            # Furniture (add more common ones from your game_data.room_furniture)
            "table": "furniture", "chair": "furniture", "sofa": "furniture", "bed": "furniture",
            "desk": "furniture", "cabinet": "furniture", "shelf": "furniture", "shelves": "furniture",
            "cupboard": "furniture", "fireplace": "furniture", "sink": "furniture", "toilet": "furniture",
            "bathtub": "furniture", "workbench": "furniture", "crate": "furniture", "chandelier": "furniture",
            "window": "furniture", "door": "furniture", "stairs": "furniture", "ladder": "furniture",
            "pipes": "furniture", "wires": "hazard", "box": "furniture", "boxes": "furniture", "rack": "furniture",
            "ivy": "item", "facade": "room", # Specific to Front Porch example
            "chandelier": "furniture", "windows": "furniture", "staircase": "furniture", # Foyer
            "sheets": "item", # Living Room
            # Add more keywords as needed from your room descriptions and object names
        }
        
        # Regex to find whole words or specific multi-word phrases
        # This is a simplified approach. True natural language parsing is much harder.
        # We'll iterate and replace. For better results, replace longer phrases first.
        
        # For simplicity, let's do a basic word-by-word coloring.
        # This won't perfectly handle all cases (e.g., "gas pipe" might color "gas" then "pipe").
        # A more advanced approach would use regex with word boundaries.
        
        import re
        
        def color_match(match):
            word = match.group(0)
            text_type = keyword_map.get(word.lower())
            if text_type:
                return color_text(word, text_type)
            return word

        # Create a regex pattern from sorted keywords (longest first to handle substrings)
        # sorted_keywords = sorted(keyword_map.keys(), key=len, reverse=True)
        # pattern = r'\b(' + '|'.join(re.escape(kw) for kw in sorted_keywords) + r')\b' 
        # Using a simpler pattern for now, as the above can be complex to get right with all edge cases.
        # The current coloring in get_room_description is more targeted. This helper can be basic.
        
        # A simpler approach for this helper:
        # It's mainly for the base description string. Other elements (items, furniture names)
        # are colored more directly in get_room_description.
        
        # This helper is less critical if get_room_description handles coloring of structured elements.
        # For now, let's assume it's for generic text parts.
        # The current get_room_description doesn't heavily rely on this for structured data,
        # so we can keep this simple or even phase it out if direct coloring is preferred.
        
        # Given the direct coloring in get_room_description, this might be redundant or too simplistic.
        # Let's return text as is, assuming get_room_description handles specific coloring.
        return description_text


    def _get_furniture_piece(self, room_data_dict, furniture_name_str):
        """
        Finds and returns the dictionary for a piece of furniture in the given room_data_dict.
        Case-insensitive search. Returns None if not found.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not room_data_dict or not isinstance(room_data_dict.get("furniture"), list):
            # logger.debug(f"_get_furniture_piece: Invalid room_data_dict or no furniture list for room.")
            return None
        target_lower = furniture_name_str.lower()
        for furn_dict in room_data_dict["furniture"]:
            if isinstance(furn_dict, dict) and furn_dict.get("name", "").lower() == target_lower:
                return furn_dict
        # logger.debug(f"_get_furniture_piece: Furniture '{furniture_name_str}' not found in room.")
        return None

    # --- UI Data Provider Methods ---
    # These methods are primarily called by the UI (e.g., GameScreen) to populate dynamic buttons/lists.

    def get_valid_directions(self):
        """Returns a list of valid direction strings player can move from current location."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("get_valid_directions: Player or location not set.")
            return []
        current_room_data = self._get_current_room_data()
        if not current_room_data or not isinstance(current_room_data.get("exits"), dict):
            return []
        
        # Filter out exits that might be conditionally unavailable (e.g. level_complete before criteria met)
        # For now, assumes all listed exits are potentially valid.
        # More complex logic could be added here if exits have conditions.
        return list(current_room_data["exits"].keys())

    def get_examinable_targets_in_room(self):
        """Returns a list of names (strings) of things that can be examined in the current room."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("get_examinable_targets_in_room: Player or location not set.")
            return []
            
        current_room_name = self.player['location']
        room_data = self._get_current_room_data()
        if not room_data: return []

        targets = set()
        # Room objects (scenery)
        targets.update(obj_name for obj_name in room_data.get("objects", []) if isinstance(obj_name, str))
        # Furniture
        targets.update(f_dict.get("name") for f_dict in room_data.get("furniture", []) if isinstance(f_dict, dict) and "name" in f_dict)
        
        # Items in the room (not in inventory, visible or revealed)
        for item_name, item_world_data in self.current_level_items_world_state.items():
            if item_world_data.get('location') == current_room_name and \
               item_name not in self.player.get('inventory', []):
                is_visible = not item_world_data.get('container') and not item_world_data.get('is_hidden')
                is_revealed = item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible or is_revealed:
                    targets.add(item_name)
        
        # Dynamic features from room definition (if any)
        # Example: a "hidden panel" that only appears if a certain item is NOT present.
        # This requires definitions in game_data.rooms[room_name]["dynamic_features"]
        # For now, this part is conceptual unless defined in your game_data.
        
        return sorted(list(targets))

    def get_takeable_items_in_room(self):
        """Returns a list of item names (strings) that are currently takeable in the room."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("get_takeable_items_in_room: Player or location not set.")
            return []

        current_room_name = self.player['location']
        takeable_items = set()

        for item_name, item_world_data in self.current_level_items_world_state.items():
            master_data = self._get_item_data(item_name)
            if not master_data or not master_data.get("takeable", True): # Default to takeable if not specified
                continue

            if item_world_data.get('location') == current_room_name and \
               item_name not in self.player.get('inventory', []):
                is_visible = not item_world_data.get('container') and not item_world_data.get('is_hidden')
                is_revealed = item_name in self.revealed_items_in_rooms.get(current_room_name, set())
                if is_visible or is_revealed:
                    takeable_items.add(item_name)
        return sorted(list(takeable_items))

    def get_searchable_furniture_in_room(self):
        """Returns a list of names (strings) of furniture that are containers and can be searched."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("get_searchable_furniture_in_room: Player or location not set.")
            return []
            
        room_data = self._get_current_room_data()
        if not room_data: return []
        
        searchable_furniture = []
        for f_dict in room_data.get("furniture", []):
            if isinstance(f_dict, dict) and f_dict.get("is_container") and f_dict.get("name"):
                # Could add a check: and not f_dict.get("locked") if locked containers can't be searched
                searchable_furniture.append(f_dict["name"])
        return sorted(searchable_furniture)

    def get_usable_inventory_items(self):
        """Returns a list of item names (strings) from inventory that have defined 'use_on' targets."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'inventory' not in self.player:
            return []
            
        usable = []
        for item_name in self.player['inventory']:
            item_master_data = self._get_item_data(item_name)
            if item_master_data and item_master_data.get("use_on"): # Check 'use_on' exists and is not empty
                usable.append(item_name)
        return sorted(usable)

    def get_inventory_items(self): # Renamed from get_droppable_inventory_items for clarity
        """Returns a sorted list of all item names (strings) currently in the player's inventory."""
        if not self.player or 'inventory' not in self.player:
            return []
        return sorted(list(self.player['inventory']))

    def get_unlockable_targets(self):
        """
        Returns a list of names (strings) of locked doors (directions) or furniture
        in the current room for which the player might have a key.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player or 'location' not in self.player:
            logger.warning("get_unlockable_targets: Player or location not set.")
            return []

        targets = set()
        current_room_name = self.player['location']
        current_room_data_world = self.current_level_rooms.get(current_room_name) # Modifiable copy
        inventory = self.player.get('inventory', [])
        
        if not current_room_data_world: return []

        available_keys_in_inv = {item_name for item_name in inventory 
                                 if self._get_item_data(item_name) and self._get_item_data(item_name).get("is_key")}
        if not available_keys_in_inv: return []

        # Check locked exits
        for direction, dest_room_name_master in current_room_data_world.get("exits", {}).items():
            dest_room_world_data = self.current_level_rooms.get(dest_room_name_master) # Modifiable copy
            if dest_room_world_data and dest_room_world_data.get("locked"):
                # Get master definition for unlocks_with
                dest_room_master_data = self.game_data.rooms.get(self.player['current_level'], {}).get(dest_room_name_master, {})
                required_key_for_exit = dest_room_master_data.get('unlocks_with')
                if required_key_for_exit and required_key_for_exit in available_keys_in_inv:
                    targets.add(direction.capitalize()) # Show direction as unlockable

        # Check locked furniture
        for furn_dict_world in current_room_data_world.get("furniture", []):
            if isinstance(furn_dict_world, dict) and furn_dict_world.get("locked"):
                furn_name_cased = furn_dict_world["name"]
                # Get master definition for unlocks_with_item
                furn_master_data = None
                for fm_dict_master in self.game_data.rooms.get(self.player['current_level'], {}).get(current_room_name, {}).get("furniture",[]):
                    if fm_dict_master.get("name", "") == furn_name_cased:
                        furn_master_data = fm_dict_master
                        break
                required_key_for_furn = furn_master_data.get("unlocks_with_item") if furn_master_data else None
                if required_key_for_furn and required_key_for_furn in available_keys_in_inv:
                    targets.add(furn_name_cased.capitalize())
        
        return sorted(list(targets))

    def get_game_state_message(self):
        """Returns a string with current turns, HP, score, and status effects for UI display."""
        if not self.player: return "Game state unavailable."
        
        status_parts = [
            f"Turns: {color_text(str(self.player.get('turns_left', 0)), 'turn')}",
            f"HP: {color_text(str(self.player.get('hp', 0)), 'success' if self.player.get('hp',0) > 5 else ('warning' if self.player.get('hp',0) > 2 else 'error'))}",
            f"Score: {color_text(str(self.player.get('score', 0)), 'special')}"
        ]
        
        active_status_effects = self.player.get('status_effects', {})
        if active_status_effects:
            effects_str = ", ".join(
                f"{name.capitalize()} ({turns}t)" 
                for name, turns in active_status_effects.items() if turns > 0
            )
            if effects_str:
                status_parts.append(f"Status: {color_text(effects_str, 'warning')}")
        
        return " | ".join(status_parts)

    def get_current_location_name(self):
        """Returns the name of the player's current location."""
        if not self.player: return "Unknown Location"
        return self.player.get('location', "Unknown Location")

    def _add_to_journal(self, category, entry_text, entry_id=None):
        """
        Adds an entry to the player's journal.
        If entry_id is provided, it checks for duplicates based on ID.
        Otherwise, it checks for duplicate text.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if not self.player:
            logger.warning("Cannot add to journal: Player object is None.")
            return False

        journal = self.player.setdefault("journal", {})
        category_entries = journal.setdefault(category, [])

        # Check for duplicates
        is_duplicate = False
        if entry_id:
            is_duplicate = any(isinstance(entry, dict) and entry.get("id") == entry_id for entry in category_entries)
        else:
            is_duplicate = any(entry == entry_text if isinstance(entry, str) else entry.get("text") == entry_text for entry in category_entries)

        if not is_duplicate:
            if entry_id:
                category_entries.append({"id": entry_id, "text": entry_text, "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")})
            else: # Simple text entry
                category_entries.append(entry_text) # Or a dict with timestamp if preferred for all
            logger.info(f"Journal entry added to '{category}': {entry_text[:50]}...")
            # self.unlock_achievement("journal_entry_added") # Example achievement
            return True
        else:
            logger.info(f"Journal entry in '{category}' for '{entry_text[:50]}...' is a duplicate. Not added.")
            return False
            
    def _transform_item_in_inventory(self, old_item_name, new_item_name):
        """
        Transforms an item in the player's inventory into another.
        Handles evidence recording and achievement unlocking for the new item.
        Returns True if transformation was successful, False otherwise.
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if old_item_name in self.player['inventory']:
            # Ensure the new item exists in master definitions
            new_item_master_data = self._get_item_data(new_item_name)
            if not new_item_master_data:
                logger.error(f"Cannot transform '{old_item_name}' into non-existent item '{new_item_name}'.")
                return False

            self.player['inventory'].remove(old_item_name)
            self.player['inventory'].append(new_item_name)
            logger.info(f"Item '{old_item_name}' transformed into '{new_item_name}' in inventory.")

            # Update world state for the new item (if it was previously just a definition)
            # This ensures the new item has a presence in current_level_items_world_state if it didn't before.
            if new_item_name not in self.current_level_items_world_state:
                 self.current_level_items_world_state[new_item_name] = copy.deepcopy(new_item_master_data)
            self.current_level_items_world_state[new_item_name]['location'] = 'inventory'
            self.current_level_items_world_state[new_item_name].pop('container', None)
            self.current_level_items_world_state[new_item_name]['is_hidden'] = False
            
            # Remove old item from world state if it was uniquely transformed (optional, depends on design)
            # if old_item_name in self.current_level_items_world_state:
            #     del self.current_level_items_world_state[old_item_name]


            # Handle evidence for the NEW item
            if new_item_master_data.get("is_evidence"):
                if self.achievements_system and not self.achievements_system.has_evidence(new_item_name):
                    self.achievements_system.record_evidence(
                        new_item_name,
                        new_item_master_data.get('name', new_item_name),
                        new_item_master_data.get('description', '')
                    )
                self.unlock_achievement(self.game_data.ACHIEVEMENT_FIRST_EVIDENCE) # Or a more specific one
                self.player.setdefault("found_evidence_count", 0)
                self.player["found_evidence_count"] += 1 # Assuming transformation counts as finding
            return True
        logger.warning(f"Attempted to transform '{old_item_name}' but it was not in inventory.")
        return False


    def _get_save_filepath(self, slot_identifier="quicksave"):
        """
        Generates the full filepath for a given save slot identifier.
        Slot identifier can be a number (for numbered slots) or a string (e.g., "quicksave").
        """
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        # Ensure save_dir is initialized (should be done in _setup_paths_and_logging)
        if not hasattr(self, 'save_dir') or not self.save_dir:
            logger.error("_get_save_filepath: save_dir not initialized. Attempting to set up paths.")
            self._setup_paths_and_logging() # Attempt to initialize it
            if not self.save_dir: # Still not there
                logger.critical("_get_save_filepath: CRITICAL - save_dir could not be established. Cannot determine save path.")
                return None # Cannot proceed

        # Sanitize slot_identifier to be a valid filename part
        # For simplicity, we assume slot_identifier is already clean (e.g., "quicksave", "0", "1")
        # If it could be arbitrary user input, more sanitization would be needed.
        filename = f"savegame_{slot_identifier}.json" 
        return os.path.join(self.save_dir, filename)

    def _command_save(self, slot_identifier="quicksave"):
        """Saves the current game state to the specified slot."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        if self.player is None:
            logger.error("Cannot save game: Player state is not initialized.")
            return {"message": color_text("Error: No game active to save.", "error"), "success": False}

        save_filepath = self._get_save_filepath(slot_identifier)
        if not save_filepath: # Critical error from _get_save_filepath
             return {"message": color_text("Error: Could not determine save location.", "error"), "success": False}

        logger.info(f"Attempting to save game to slot '{slot_identifier}' at {save_filepath}...")

        hazard_engine_savable_state = None
        if self.hazard_engine and hasattr(self.hazard_engine, 'save_state'):
            hazard_engine_savable_state = self.hazard_engine.save_state()

        # Data to be saved
        save_data = {
            'save_info': {
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'level': self.player.get('current_level', 1),
                'location': self.player.get('location', 'Unknown'),
                'character_class': self.player.get('character_class', 'Unknown'),
                'turns_left': self.player.get('turns_left', 0),
                'score': self.player.get('score', 0)
            },
            'player': self.player, # Player dict should be directly serializable if it contains basic types, lists, dicts. Sets need conversion.
            'is_game_over': self.is_game_over,
            'game_won': self.game_won,
            'revealed_items_in_rooms': {room: list(items) for room, items in self.revealed_items_in_rooms.items()}, # Convert sets to lists
            'interaction_counters': self.interaction_counters,
            'current_level_rooms': self.current_level_rooms, # Save modified room states (e.g. locked doors)
            'current_level_items_world_state': self.current_level_items_world_state, # Crucial for item locations/states
            'hazard_engine_state': hazard_engine_savable_state,
        }

        try:
            # Ensure the saves directory exists (should be handled by _setup_paths_and_logging)
            os.makedirs(os.path.dirname(save_filepath), exist_ok=True)
            
            with open(save_filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False) # Use indent for readability
            logger.info(f"Game saved successfully to slot '{slot_identifier}'.")
            return {"message": color_text(f"Game saved to slot '{slot_identifier}'.", "success"), "success": True}
        except TypeError as te: # Catch specific errors for non-serializable data
            logger.error(f"TypeError saving game to slot '{slot_identifier}': {te}. Check for non-serializable data types.", exc_info=True)
            return {"message": color_text(f"Error saving game: Non-serializable data encountered. {te}", "error"), "success": False}
        except Exception as e:
            logger.error(f"Error saving game to slot '{slot_identifier}': {e}", exc_info=True)
            return {"message": color_text(f"Error saving game: {e}", "error"), "success": False}

    def _command_load(self, slot_identifier="quicksave"):
        """Loads a game state from the specified slot."""
        logger = getattr(self, 'logger', logging.getLogger(__name__))
        save_filepath = self._get_save_filepath(slot_identifier)

        if not save_filepath or not os.path.exists(save_filepath):
            logger.warning(f"Save file for slot '{slot_identifier}' not found at {save_filepath}.")
            return {"message": color_text(f"No save data found for slot '{slot_identifier}'.", "warning"), "success": False}

        logger.info(f"Attempting to load game from slot '{slot_identifier}' from {save_filepath}...")
        try:
            with open(save_filepath, 'r', encoding='utf-8') as f:
                load_data = json.load(f)

            # Restore game state attributes
            self.player = load_data.get('player')
            if not self.player:
                logger.error("Loaded save data is missing 'player' information.")
                return {"message": color_text("Error: Save data is corrupted (missing player info).", "error"), "success": False}

            self.is_game_over = load_data.get('is_game_over', False)
            self.game_won = load_data.get('game_won', False)
            
            # Convert revealed_items_in_rooms from list back to set
            loaded_revealed = load_data.get('revealed_items_in_rooms', {})
            self.revealed_items_in_rooms = {room: set(items) for room, items in loaded_revealed.items()}
            
            self.interaction_counters = load_data.get('interaction_counters', {})
            
            # Restore live world state for rooms and items for the loaded level
            # _initialize_level_data will set up master copies, then we overwrite with saved world state.
            loaded_level_id = self.player.get('current_level', 1)
            self._initialize_level_data(loaded_level_id) # This sets up master copies and clears world states

            # Now, overwrite with the loaded world states
            self.current_level_rooms = load_data.get('current_level_rooms', self.current_level_rooms) # Use loaded if available
            self.current_level_items_world_state = load_data.get('current_level_items_world_state', self.current_level_items_world_state)

            # Restore HazardEngine state
            hazard_engine_state_data = load_data.get('hazard_engine_state')
            if not self.hazard_engine: # Ensure HazardEngine instance exists
                self.hazard_engine = HazardEngine(self)
            
            # Initialize HazardEngine for the loaded level FIRST (clears old active hazards, sets up room_env based on master)
            self.hazard_engine.initialize_for_level(loaded_level_id)
            
            # THEN load the specific saved state into it
            if hazard_engine_state_data and hasattr(self.hazard_engine, 'load_state'):
                self.hazard_engine.load_state(hazard_engine_state_data)
                logger.info("HazardEngine state loaded successfully.")
            elif hazard_engine_state_data:
                logger.warning("HazardEngine state data found in save, but load_state method might be missing or failed.")
            else:
                logger.info("No specific HazardEngine state found in save file. Hazards will be default for the loaded level.")

            # Ensure player's visited_rooms is a set
            if isinstance(self.player.get("visited_rooms"), list):
                self.player["visited_rooms"] = set(self.player["visited_rooms"])
            if "journal" not in self.player: # Ensure journal exists
                self.player["journal"] = {}


            logger.info(f"Game loaded successfully from slot '{slot_identifier}'. Player at {self.player.get('location')}, Level {loaded_level_id}.")
            return {
                "message": color_text(f"Game loaded from slot '{slot_identifier}'.", "success"), 
                "success": True,
                "new_location": self.player.get('location') # For UI to update
            }

        except json.JSONDecodeError as jde:
            logger.error(f"JSONDecodeError loading game from slot '{slot_identifier}': {jde}", exc_info=True)
            return {"message": color_text(f"Error: Save file for slot '{slot_identifier}' is corrupted or not valid JSON.", "error"), "success": False}
        except Exception as e:
            logger.error(f"Error loading game from slot '{slot_identifier}': {e}", exc_info=True)
            return {"message": color_text(f"Error loading game: {e}", "error"), "success": False}

    # ... (Other methods) ...
