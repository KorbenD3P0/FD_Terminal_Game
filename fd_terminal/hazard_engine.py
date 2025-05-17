import json # Not strictly used in this section, but often present
import random
import logging
import copy
import os # Not strictly used in this section
import datetime # Not strictly used in this section
import collections
from .utils import color_text # Assuming utils.py is in the same package
from kivy.app import App # Not strictly used in this section
from . import game_data # Assuming game_data.py is in the same package

# ==================================
# Hazard Engine Class
# ==================================
class HazardEngine:
    def __init__(self, game_logic_ref):
        """
        Initializes the HazardEngine.

        Args:
            game_logic_ref: A reference to the main GameLogic instance.
        """
        self.game_logic = game_logic_ref  # Reference to the main GameLogic instance
        self.active_hazards = {}          # Stores active hazard instances in the current level
        self.room_env = {}                # Stores environmental state per room (e.g., gas level, wetness)
        self.next_hazard_id = 0           # Counter for generating unique hazard instance IDs
        self.temporary_room_effects = [] # To store active temporary effects

        # Access master hazard definitions from game_data via game_logic_ref
        if self.game_logic and hasattr(self.game_logic, 'game_data') and hasattr(self.game_logic.game_data, 'hazards'):
            self.hazards_master_data = self.game_logic.game_data.hazards
        else:
            logging.error("HazardEngine: game_data.hazards not found via game_logic_ref. Hazard definitions will be missing.")
            self.hazards_master_data = {} # Fallback to empty dict

        # For tracking IDs processed in a single turn update to avoid cascading issues
        self.processed_hazards_this_turn = set()
        
        logging.info("HazardEngine initialized.")

    @property
    def player(self):
        """Provides convenient access to the player data from the GameLogic instance."""
        if not self.game_logic or not hasattr(self.game_logic, 'player') or self.game_logic.player is None:
            logging.error("HazardEngine.player: game_logic reference or player object not available!")
            # Return a default player structure to prevent crashes if absolutely necessary,
            # but this indicates a deeper setup problem.
            return {"location": "Unknown", "inventory": [], "hp": 0, "turns_left": 0, "status_effects": {}}
        return self.game_logic.player

    @property
    def rooms(self):
        """
        Provides convenient access to the current level's room data (modifiable copy) 
        from the GameLogic instance.
        """
        if not self.game_logic or not hasattr(self.game_logic, 'current_level_rooms'):
            logging.error("HazardEngine.rooms: game_logic reference or current_level_rooms not available!")
            return {}
        return self.game_logic.current_level_rooms # This is GameLogic's live copy of room data

    def _generate_hazard_id(self):
        """Generates a unique ID for a new hazard instance."""
        self.next_hazard_id += 1
        return f"haz_{self.next_hazard_id}"

    def initialize_for_level(self, level_id):
        """
        Initializes or resets the HazardEngine for a new game level.
        Clears existing active hazards and room environments, then places
        initial hazards for the specified level.

        Args:
            level_id (int or str): The identifier of the level to initialize.
        """
        logging.info(f"HazardEngine: Initializing for level {level_id}...")
        self.active_hazards.clear()
        self.room_env.clear()
        self.next_hazard_id = 0 # Reset ID counter for the new level

        # Ensure hazards_master_data is loaded
        if not self.hazards_master_data and self.game_logic and \
           hasattr(self.game_logic, 'game_data') and hasattr(self.game_logic.game_data, 'hazards'):
            self.hazards_master_data = self.game_logic.game_data.hazards
            logging.info("HazardEngine: Re-linked hazards_master_data.")
        elif not self.hazards_master_data:
             logging.error("HazardEngine: Cannot initialize level, hazards_master_data is still missing.")
             return


        current_level_rooms_data = self.rooms # Uses the property to get rooms from GameLogic
        if not current_level_rooms_data:
            logging.error(f"HazardEngine: No room data found for level {level_id} during hazard initialization via self.rooms.")
            return

        # Initialize environmental conditions for each room in the current level
        for room_name in current_level_rooms_data.keys():
            if self.game_logic and hasattr(self.game_logic, 'game_data') and \
               hasattr(self.game_logic.game_data, 'initial_environmental_conditions'):
                self.room_env[room_name] = copy.deepcopy(self.game_logic.game_data.initial_environmental_conditions)
            else:
                logging.error(f"HazardEngine: game_data.initial_environmental_conditions not found. Cannot set base env for {room_name}.")
                self.room_env[room_name] = {} # Fallback

        # Place hazards defined in the room data for the current level
        self._place_initial_hazards_for_level(level_id, current_level_rooms_data)
        
        # After placing initial hazards, update the environmental states based on them
        self.update_environmental_states() 
        
        logging.info(f"HazardEngine initialized for level {level_id}. Active hazards: {len(self.active_hazards)}. Room environments tracked: {len(self.room_env)}")

    def _place_initial_hazards_for_level(self, level_id, current_level_rooms_data):
        """
        Places initial hazards in rooms based on the 'hazards_present' and 'possible_hazards'
        definitions in the room data for the current level.

        Args:
            level_id (int or str): The current level ID (for logging/context).
            current_level_rooms_data (dict): The dictionary of room data for the current level.
        """
        logging.info(f"HazardEngine: Placing initial hazards for Level {level_id}...")

        for room_name, room_data in current_level_rooms_data.items():
            if not isinstance(room_data, dict):
                logging.warning(f"HazardEngine: Room data for '{room_name}' is not a dictionary. Skipping hazard placement.")
                continue

            # 1. Place hazards explicitly listed in 'hazards_present'
            for hazard_entry in room_data.get("hazards_present", []):
                self._process_hazard_entry_for_placement(hazard_entry, room_name, room_data, is_possible=False)

            # 2. Potentially place hazards from 'possible_hazards' (with chance)
            for hazard_entry in room_data.get("possible_hazards", []):
                self._process_hazard_entry_for_placement(hazard_entry, room_name, room_data, is_possible=True)
        logging.info(f"HazardEngine: Finished placing initial hazards for level {level_id}. Total active: {len(self.active_hazards)}")

    def _process_hazard_entry_for_placement(self, hazard_entry, room_name, room_data, is_possible):
        """
        Helper function to process a single hazard entry from either 
        'hazards_present' or 'possible_hazards' and attempt to add it.
        """
        hazard_type_to_add = None
        target_obj_override = None
        support_obj_override = None
        initial_state_override = None
        spawn_chance = 1.0 if not is_possible else 0.0 # Default for 'hazards_present' vs 'possible_hazards'

        if isinstance(hazard_entry, str):
            hazard_type_to_add = hazard_entry
            if is_possible: # Get default spawn chance for possible hazards if only type string is given
                if hazard_type_to_add in self.hazards_master_data:
                     spawn_chance = self.hazards_master_data[hazard_type_to_add].get("default_spawn_chance", 0.1)
                else:
                    logging.warning(f"HazardEngine: Hazard type '{hazard_type_to_add}' from 'possible_hazards' in room '{room_name}' not in master_data. Skipping.")
                    return
        elif isinstance(hazard_entry, dict):
            hazard_type_to_add = hazard_entry.get("type")
            target_obj_override = hazard_entry.get("object_name_override") # Updated key
            support_obj_override = hazard_entry.get("support_object_override") # Updated key
            initial_state_override = hazard_entry.get("initial_state")
            if is_possible:
                spawn_chance = hazard_entry.get("chance", 0.1) # Use defined chance if available
        else:
            logging.warning(f"HazardEngine: Invalid hazard entry format in room '{room_name}': {hazard_entry}")
            return

        if not hazard_type_to_add:
            logging.warning(f"HazardEngine: Hazard entry in room '{room_name}' is missing 'type'. Entry: {hazard_entry}")
            return

        if hazard_type_to_add not in self.hazards_master_data:
            logging.warning(f"HazardEngine: Hazard type '{hazard_type_to_add}' in room '{room_name}' is not defined in master_data. Skipping.")
            return

        # Check spawn chance for 'possible_hazards'
        if is_possible and random.random() >= spawn_chance:
            return # Did not meet spawn chance

        # Prevent duplicate hazards of the same type in the same room if not intended
        # This check might need refinement if multiple instances of same type are allowed with different object_names
        already_present = any(
            hz['type'] == hazard_type_to_add and hz['location'] == room_name
            for hz in self.active_hazards.values()
        )
        if already_present:
            # logging.info(f"HazardEngine: Hazard '{hazard_type_to_add}' already present in '{room_name}', skipping duplicate placement.")
            return

        # Add the hazard
        self._add_active_hazard(
            hazard_type=hazard_type_to_add,
            location=room_name,
            initial_state_override=initial_state_override,
            target_object_override=target_obj_override,
            support_object_override=support_obj_override,
        )
    
    def _add_active_hazard(self, hazard_type, location, 
                           initial_state_override=None,
                           target_object_override=None, 
                           support_object_override=None,
                           source_trigger_id=None,
                           default_placement_options=None):
        """
        Adds an instance of a specified hazard type to the game world.
        (Continuation of the method from previous context)
        """
        if hazard_type not in self.hazards_master_data:
            logging.warning(f"HazardEngine: Attempted to add unknown hazard type: {hazard_type}")
            return None

        hazard_id = self._generate_hazard_id()
        base_definition = self.hazards_master_data[hazard_type]

        final_object_name = target_object_override
        if not final_object_name:
            options = base_definition.get("object_name_options", [base_definition.get("name", hazard_type).lower().replace(" ", "_")])
            final_object_name = random.choice(options) if options else base_definition.get("name", hazard_type)

        final_support_object = support_object_override
        if not final_support_object:
            room_data_for_placement = self.rooms.get(location, {})
            all_potential_supports_in_room = []
            if room_data_for_placement and isinstance(room_data_for_placement, dict):
                room_furniture_names = [f.get("name") for f in room_data_for_placement.get("furniture", []) if isinstance(f, dict) and f.get("name")]
                room_object_names = room_data_for_placement.get("objects", [])
                all_potential_supports_in_room = room_furniture_names + room_object_names
            
            preferred_support_types = base_definition.get("placement_object", [])
            valid_preferred_supports = [s for s in all_potential_supports_in_room if s in preferred_support_types]

            if valid_preferred_supports:
                final_support_object = random.choice(valid_preferred_supports)
            elif all_potential_supports_in_room:
                final_support_object = random.choice(all_potential_supports_in_room)
            else:
                final_support_object = "an indeterminate spot" 
        
        final_initial_state = initial_state_override or base_definition.get('initial_state')
        
        if not final_initial_state or final_initial_state not in base_definition.get('states', {}):
            if base_definition.get('states'):
                try:
                    first_defined_state = list(base_definition['states'].keys())[0]
                    logging.warning(f"HazardEngine: Invalid or missing initial state for {hazard_type}. Using first state: '{first_defined_state}'.")
                    final_initial_state = first_defined_state
                except (IndexError, TypeError):
                    logging.error(f"HazardEngine: Hazard type {hazard_type} has no states defined. Cannot add hazard.")
                    return None
            else:
                logging.error(f"HazardEngine: Hazard type {hazard_type} has no states defined. Cannot add hazard.")
                return None

        new_hazard_instance = {
            "id": hazard_id, "type": hazard_type, "name": base_definition.get("name", hazard_type),
            "object_name": final_object_name, "support_object": final_support_object,
            "location": location, "state": final_initial_state,
            "data": copy.deepcopy(base_definition), "turns_in_state": 0,
            "aggression": base_definition.get("initial_aggression", 0),
            "triggered_by_hazard_id": source_trigger_id,
        }
        self.active_hazards[hazard_id] = new_hazard_instance
        logging.info(f"HazardEngine: Added active hazard ID {hazard_id}, Type '{hazard_type}' (as '{final_object_name}' on/near '{final_support_object}'), Location '{location}', Initial State '{final_initial_state}'.")
        return hazard_id

    def _set_hazard_state(self, hazard_id, new_state_name, messages_list):
        """
        Sets a hazard to a new state, applies effects, and handles consequences.
        (Continuation of the method from previous context)
        """
        hazard = self.active_hazards.get(hazard_id)
        if not hazard:
            logging.warning(f"HazardEngine: Hazard ID {hazard_id} not found for state change.")
            return False

        hazard_def_states = hazard['data'].get('states', {})
        old_state_name = hazard['state']

        if new_state_name is None:
            logging.info(f"HazardEngine: Removing hazard {hazard_id} ('{hazard['type']}') from {hazard['location']}.")
            del self.active_hazards[hazard_id]
            self.update_environmental_states()
            removal_message = hazard['data'].get("removal_message", f"The {hazard.get('object_name', hazard['type'])} is no longer an issue.")
            messages_list.append(color_text(removal_message, "success"))
            return True

        if new_state_name not in hazard_def_states:
            logging.warning(f"HazardEngine: Invalid state '{new_state_name}' for hazard {hazard_id}. Valid: {list(hazard_def_states.keys())}")
            return False

        if old_state_name == new_state_name: return True

        logging.info(f"HazardEngine: Hazard {hazard_id} ('{hazard['type']}') state: '{old_state_name}' -> '{new_state_name}'.")
        hazard['state'] = new_state_name
        hazard['turns_in_state'] = 0
        new_state_definition = hazard_def_states[new_state_name]
        self.update_environmental_states()

        desc_template = new_state_definition.get('description')
        if desc_template:
            try:
                formatted_desc = desc_template.format(
                    object_name=color_text(hazard.get('object_name', hazard['name']), 'hazard'),
                    support_object=color_text(hazard.get('support_object', 'its surroundings'), 'room')
                )
                messages_list.append(formatted_desc)
            except KeyError as e:
                logging.error(f"HazardEngine: KeyError in description for {hazard['type']}/{new_state_name}: {e}. Template: '{desc_template}'")
                messages_list.append(color_text(f"The {hazard.get('object_name', hazard['name'])} changes.", "warning"))

        player_is_present = self.player.get('location') == hazard['location']
        if player_is_present and not self.game_logic.is_game_over:
            hp_damage_on_state_change = new_state_definition.get("instant_hp_damage", 0)
            if hp_damage_on_state_change > 0:
                damage_source_name = hazard.get('object_name', hazard['name'])
                self.game_logic.apply_damage_to_player(hp_damage_on_state_change, f"effect from {damage_source_name}")
                messages_list.append(color_text(f"You take {hp_damage_on_state_change} damage from the {damage_source_name}!", "error"))

            status_effect_def = new_state_definition.get("status_effect_on_state_change")
            if status_effect_def and isinstance(status_effect_def, dict) and not self.game_logic.is_game_over:
                status_name = status_effect_def.get("name")
                status_duration = status_effect_def.get("duration")
                if status_name:
                    self.game_logic.apply_status_effect(status_name, status_duration, messages_list)

            if new_state_definition.get('instant_death_in_room') and not self.game_logic.is_game_over:
                death_msg_template = new_state_definition.get('death_message', f"The {hazard.get('object_name', hazard['name'])} escalates fatally!")
                messages_list.append(color_text(death_msg_template.format(object_name=hazard.get('object_name', 'area')), "error"))
                self.game_logic.is_game_over = True; self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard['type']; self.player['last_hazard_object_name'] = hazard.get('object_name', hazard['name'])
                logging.info(f"HazardEngine: Instant death by hazard {hazard_id} state '{new_state_name}'.")
                return True

        # --- New section for sets_room_on_fire ---
        # This should be after player effects for the current hazard state change are processed,
        # but before returning, as it might generate more messages or even end the game.
        if new_state_definition.get('sets_room_on_fire') and not self.game_logic.is_game_over:
            room_of_fire_hazard = hazard['location']
            # Check if a 'spreading_fire' hazard already exists in this room
            existing_room_fire_id = None
            for active_h_id, active_h_instance in self.active_hazards.items():
                if active_h_instance.get('type') == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE and \
                   active_h_instance.get('location') == room_of_fire_hazard:
                    existing_room_fire_id = active_h_id
                    break
            
            if not existing_room_fire_id:
                messages_list.append(color_text(f"The {hazard.get('object_name', 'fire from ' + hazard['type'])} ignites the surroundings in {room_of_fire_hazard}!", "error"))
                # Add a new 'spreading_fire' hazard
                self._add_active_hazard(
                    hazard_type=self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE,
                    location=room_of_fire_hazard,
                    initial_state_override="burning_low", # Or determine from intensity of source
                    target_object_override=f"fire spreading from {hazard.get('object_name', hazard['type'])}", # Descriptive
                    support_object_override="the room itself"
                )
                # The new spreading_fire hazard will have its own environmental effects applied
                # during the next full update_environmental_states or if explicitly triggered.
            else:
                # A spreading_fire already exists. Optionally, escalate its state.
                existing_fire_hazard = self.active_hazards.get(existing_room_fire_id)
                if existing_fire_hazard and existing_fire_hazard['state'] == "burning_low":
                    messages_list.append(color_text(f"The additional flames from {hazard.get('object_name', hazard['type'])} cause the fire in {room_of_fire_hazard} to intensify!", "error"))
                    self._set_hazard_state(existing_room_fire_id, "burning_high", messages_list)
            
            # After adding/modifying spreading_fire, the room's env state 'is_on_fire' should become True.
            # This is handled by update_environmental_states(), which is called after this _set_hazard_state in some flows.
            # Or, we can directly update the room_env here for immediate effect before full recalc.
            if room_of_fire_hazard in self.room_env:
                self.room_env[room_of_fire_hazard]['is_on_fire'] = True
                logging.info(f"HazardEngine: Room '{room_of_fire_hazard}' env directly set to is_on_fire=True due to '{hazard['type']}'.")
            
            # Potentially check for immediate gas explosion if gas is present
            self._check_global_environmental_reactions(messages_list) # This might trigger game over

            # If game ended due to direct effects or subsequent explosion, return
            if self.game_logic.is_game_over:
                return True
            
            # Trigger chained hazards if defined for the new state
            # (This might be a separate method call if complex)
            if new_state_definition.get("triggers_hazard_on_state_change") and isinstance(new_state_definition["triggers_hazard_on_state_change"], list):
                for trigger_rule in new_state_definition["triggers_hazard_on_state_change"]:
                    if not isinstance(trigger_rule, dict): continue

                    chance = trigger_rule.get("chance", 1.0)
                    # Add aggression influence on chance if defined
                    agg_influence = trigger_rule.get("aggression_influence_on_chance", 0.0)
                    current_aggression = hazard.get("aggression", self._calculate_aggression_factor())
                    chance += agg_influence * current_aggression
                    chance = min(1.0, max(0.0, chance))

                    if random.random() < chance:
                        condition_met = True # Assume true unless specific conditions fail
                        if trigger_rule.get("condition") == "player_in_room" and not player_is_present:
                            condition_met = False
                        # Add more specific condition checks here if needed, e.g., based on hazard.get('object_name')

                        if condition_met:
                            new_hazard_type = trigger_rule.get("type")
                            if new_hazard_type:
                                logging.info(f"HazardEngine: Hazard {hazard_id} ('{hazard['type']}') in state '{new_state_name}' triggering new hazard '{new_hazard_type}'.")
                                
                                # Prepare message for triggered hazard
                                trigger_message_template = trigger_rule.get("trigger_message")
                                if trigger_message_template:
                                    messages_list.append(color_text(trigger_message_template.format(
                                        source_name=hazard.get('object_name', hazard['name']),
                                        # Add other placeholders if your messages use them
                                    ), "warning"))
                                
                                self._add_active_hazard(
                                    hazard_type=new_hazard_type,
                                    location=hazard['location'], # Usually same location
                                    initial_state_override=trigger_rule.get("initial_state"),
                                    target_object_override=trigger_rule.get("target_object", trigger_rule.get("object_name_override")), # Use specific name if provided
                                    support_object_override=trigger_rule.get("support_object_override"),
                                    source_trigger_id=hazard_id
                                )
                                # Environmental states will be updated, and global reactions checked again if necessary
                                # after all hazards for the turn, or explicitly if needed.
                                self.update_environmental_states() 
                                self._check_global_environmental_reactions(messages_list) # Check again if a new hazard might interact
                                if self.game_logic.is_game_over: return True
            
            return True # State change successful


    def _mri_pull_through_window(self, hazard_id, hazard_instance, state_data, messages_list):
        """
        Handles the MRI pulling objects through the observation window,
        targeting the player if they are in the MRI Control Room.
        Triggers a QTE.
        """
        if self.game_logic.is_game_over:
            return

        # This hazard is in the MRI Scan Room, but its effect targets the MRI Control Room.
        # Room names are defined as constants in game_data.py
        mri_control_room_name = "MRI Control Room" # Assuming this is the exact name from game_data.rooms

        player_location = self.player.get('location')

        if player_location != mri_control_room_name:
            # Player is not in the control room, so they are not directly targeted by this specific action.
            # The hazard might still progress its state or have other environmental effects.
            messages_list.append(color_text(f"From the {mri_control_room_name}, you hear a tremendous crash and the sound of shattering glass as the {hazard_instance.get('object_name', 'MRI')} malfunctions further!", "warning"))
            # Progress the hazard to its next state as defined in game_data
            next_state_after_pull = state_data.get("next_state_on_qte_resolved") # Or a generic next_state if no QTE was meant for others
            if next_state_after_pull:
                self._set_hazard_state(hazard_id, next_state_after_pull, messages_list)
            return

        # Player IS in the MRI Control Room
        object_pulled_desc = state_data.get("object_type_pulled", "metallic debris")
        qte_type = state_data.get("qte_type_to_trigger", game_data.QTE_TYPE_DODGE_PROJECTILE) #
        qte_duration = state_data.get("qte_duration", 3.0)
        damage_on_fail = state_data.get("damage_on_qte_fail", 5)
        is_fatal_on_fail = state_data.get("fatal_on_qte_fail", False)
        next_state = state_data.get("next_state_on_qte_resolved", "mri_field_collapsed") # Default next state after sequence

        # Formulate the QTE prompt message
        qte_prompt_message = (
            f"The observation window explodes inwards! {object_pulled_desc.capitalize()} "
            f"erupts from the MRI Scan Room, flying straight at you!\n"
            f"Type \"{self.game_logic.game_data.QTE_RESPONSE_DODGE.upper()}\" to dodge! ({qte_duration}s)"
        )
        messages_list.append(color_text(qte_prompt_message, "hazard"))

        # Trigger QTE via GameLogic
        # GameLogic will handle the actual timer and response processing.
        # The HazardEngine sets up the parameters for the QTE.
        qte_context_for_game_logic = {
            "success_message": f"You narrowly DODGE the incoming {object_pulled_desc}!",
            "failure_message": f"The {object_pulled_desc} slams into you with brutal force!",
            "hp_damage_on_failure": damage_on_fail,
            "is_fatal_on_failure": is_fatal_on_fail,
            "on_success_hazard_id_to_progress": hazard_id, # For HazardEngine to know which hazard to update after QTE
            "on_failure_hazard_id_to_progress": hazard_id,
            "next_state_for_hazard": next_state,
            "qte_source_hazard_id": hazard_id, # Identify the hazard triggering it
            "qte_source_hazard_state": hazard_instance['state'] # Current state that triggered
        }

        if self.game_logic and hasattr(self.game_logic, 'trigger_qte'):
            self.game_logic.trigger_qte(qte_type, qte_duration, qte_context_for_game_logic)
        else:
            logging.error("HazardEngine: GameLogic reference or trigger_qte method not found!")
            # Fallback: if no QTE, assume failure for this dangerous event
            messages_list.append(color_text(f"The {object_pulled_desc} hits you as the system couldn't initiate a dodge sequence!", "error"))
            if is_fatal_on_fail:
                self.game_logic.apply_damage_to_player(999, f"undodged {object_pulled_desc} from MRI") # Ensure death
            else:
                self.game_logic.apply_damage_to_player(damage_on_fail, f"hit by {object_pulled_desc} from MRI")
            if hazard_id in self.active_hazards: # Check if hazard still exists
                 self._set_hazard_state(hazard_id, next_state, messages_list)
   
    def hazard_turn_update(self):
        """
        Processes all active hazards for the current game turn.
        Handles temporary effects, hazard progression, spreading fire, and global reactions.
        """
        messages = []
        agg_factor = self._calculate_aggression_factor()
        logging.debug(f"HazardEngine: --- Hazard Turn Update Start --- Aggression Factor: {agg_factor:.2f}")

        # --- Process Temporary Room Effects ---
        effects_to_remove_indices = []
        environment_changed_by_temp_effects = False
        for i, effect in enumerate(self.temporary_room_effects):
            effect['turns_left'] -= 1
            if effect['turns_left'] <= 0:
                effects_to_remove_indices.append(i)
                # Revert the effect
                if effect['room'] in self.room_env:
                    self.room_env[effect['room']][effect['key']] = effect['original_value']
                    environment_changed_by_temp_effects = True
                    logging.info(f"HazardEngine: Temporary effect expired in '{effect['room']}': '{effect['key']}' reverted to '{effect['original_value']}'.")
                    if effect['key'] == 'visibility' and effect['temp_value'] != effect['original_value']:
                        messages.append(color_text(f"The {effect['key']} in {effect['room']} returns to normal.", "info"))
        for i in sorted(effects_to_remove_indices, reverse=True):
            self.temporary_room_effects.pop(i)
        if environment_changed_by_temp_effects:
            self.update_environmental_states()

        self.processed_hazards_this_turn.clear()
        active_hazard_ids_this_cycle = list(self.active_hazards.keys())

        for hazard_id in active_hazard_ids_this_cycle:
            if self.game_logic.is_game_over: break
            if hazard_id in self.processed_hazards_this_turn: continue
            if hazard_id not in self.active_hazards: continue

            hazard = self.active_hazards[hazard_id]
            hazard['turns_in_state'] += 1

            hazard_aggression_increase = hazard['data'].get('aggression_per_turn_increase', 0.0)
            max_hazard_aggression = hazard['data'].get('max_aggression', 5.0)
            hazard['aggression'] = min(hazard.get('aggression', 0) + hazard_aggression_increase, max_hazard_aggression)

            current_state_name = hazard["state"]
            state_data = hazard["data"]["states"].get(current_state_name)
            if not state_data:
                logging.warning(f"HazardEngine: Hazard {hazard_id} ('{hazard['type']}') in unknown state '{current_state_name}'. Skipping update.")
                continue

            player_is_present = self.player.get('location') == hazard['location']

            # QTE pause logic for hazards awaiting QTE resolution
            is_this_hazard_awaiting_qte_resolution = (
                self.game_logic.player.get('qte_active') and
                self.game_logic.player.get('qte_context', {}).get('qte_source_hazard_id') == hazard_id and
                state_data.get('autonomous_action') == "_mri_pull_through_window"
            )
            if is_this_hazard_awaiting_qte_resolution:
                logging.debug(f"Hazard {hazard_id} is awaiting QTE resolution for state '{current_state_name}'. Skipping its autonomous action and progression this turn.")
                self.processed_hazards_this_turn.add(hazard_id)
                continue

            # Per-turn room effects
            if player_is_present and not self.game_logic.is_game_over:
                self._apply_per_turn_room_effects(hazard_id, hazard, state_data, messages)
                if self.game_logic.is_game_over: break

            # Autonomous actions
            autonomous_action_key = state_data.get('autonomous_action')
            if autonomous_action_key and not self.game_logic.is_game_over:
                can_run_globally = state_data.get("global_autonomous_action", False)
                if player_is_present or can_run_globally:
                    action_method = getattr(self, f"_{autonomous_action_key}", None)
                    if action_method and callable(action_method):
                        logging.debug(f"HazardEngine: Executing autonomous action '{autonomous_action_key}' for hazard {hazard_id}.")
                        action_method(hazard_id, hazard, state_data, messages)
                    else:
                        logging.warning(f"HazardEngine: Unknown autonomous_action_key or non-callable method: '{autonomous_action_key}' for hazard {hazard_id}")
                    if self.game_logic.is_game_over: break

            # State progression (if not paused by QTE)
            if not self.game_logic.player.get('qte_active') or \
            self.game_logic.player.get('qte_context', {}).get('qte_source_hazard_id') != hazard_id:

                # Progress state
                if "chance_to_progress" in state_data and "next_state" in state_data and not self.game_logic.is_game_over:
                    base_chance = state_data["chance_to_progress"]
                    aggro_boost_def = state_data.get("aggression_influence", {}).get("chance_to_progress_boost", 0.0)
                    current_aggression = hazard.get("aggression", agg_factor)
                    aggro_boost_val = aggro_boost_def * current_aggression
                    actual_chance = min(1.0, max(0.0, base_chance + aggro_boost_val))
                    if random.random() < actual_chance:
                        logging.debug(f"HazardEngine: Hazard {hazard_id} progressing state due to chance ({actual_chance:.2f}).")
                        self._set_hazard_state(hazard_id, state_data["next_state"], messages)
                        if self.game_logic.is_game_over: break
                        if hazard_id in self.active_hazards:
                            current_state_name = self.active_hazards[hazard_id]["state"]
                            state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                            if not state_data: continue
                        else: continue

                # Revert state
                if "chance_to_revert" in state_data and "revert_state" in state_data and not self.game_logic.is_game_over:
                    base_revert_chance = state_data.get("chance_to_revert", 0.05)
                    revert_agg_multiplier = state_data.get("aggression_influence", {}).get("revert_chance_multiplier", 1.0)
                    current_aggression = hazard.get("aggression", agg_factor)
                    effective_revert_chance = base_revert_chance * revert_agg_multiplier
                    if random.random() < effective_revert_chance:
                        revert_msg_template = state_data.get("revert_message", "The {object_name} seems to calm down a bit.")
                        messages.append(color_text(revert_msg_template.format(object_name=hazard.get('object_name', hazard['type'])), "info"))
                        self._set_hazard_state(hazard_id, state_data["revert_state"], messages)
                        if self.game_logic.is_game_over: break
                        if hazard_id in self.active_hazards:
                            current_state_name = self.active_hazards[hazard_id]["state"]
                            state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                            if not state_data: continue
                        else: continue

            # Hazard-to-hazard interactions
            if "hazard_interaction" in state_data and isinstance(state_data["hazard_interaction"], dict) and not self.game_logic.is_game_over:
                self._handle_hazard_to_hazard_interactions(hazard, state_data["hazard_interaction"], agg_factor, messages)
                if self.game_logic.is_game_over: break
                if hazard_id in self.active_hazards:
                    current_state_name = self.active_hazards[hazard_id]["state"]
                    state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                    if not state_data: continue
                else: continue

            # Decay logic
            decay_info = state_data.get("autonomous_decay")
            if not decay_info and hazard['type'] == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE:
                decay_info = state_data.get("autonomous_decay_to_burnt_out")
            if decay_info and isinstance(decay_info, dict) and not self.game_logic.is_game_over:
                decay_chance = decay_info.get("chance", 0.05)
                if random.random() < decay_chance:
                    decay_target_state = decay_info.get("target_state")
                    decay_message_template = decay_info.get("message", "The {object_name} seems to be diminishing.")
                    messages.append(color_text(decay_message_template.format(object_name=hazard.get('object_name', hazard['type'])), "info"))
                    self._set_hazard_state(hazard_id, decay_target_state, messages)
                    if self.game_logic.is_game_over: break
                    if hazard_id not in self.active_hazards: continue

            # --- Handle Spreading Fire to Adjacent Rooms ---
            if hazard['type'] == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE and \
            state_data.get("spreads_to_adjacent_room_chance", 0) > 0 and \
            not self.game_logic.is_game_over:

                spread_chance = state_data["spreads_to_adjacent_room_chance"]
                agg_influence_on_spread = state_data.get("aggression_influence", {}).get("spread_to_room_chance", 0.0)
                current_aggression = hazard.get("aggression", agg_factor)
                actual_spread_chance = min(1.0, max(0.0, spread_chance + (agg_influence_on_spread * current_aggression)))

                if random.random() < actual_spread_chance:
                    current_fire_room_data = self.rooms.get(hazard['location'])
                    if current_fire_room_data and current_fire_room_data.get("exits"):
                        for exit_dir, adj_room_name in current_fire_room_data["exits"].items():
                            if adj_room_name in self.rooms:
                                # Check if adjacent room is already on fire (or has a spreading_fire hazard)
                                adj_room_already_on_fire = False
                                existing_fire_in_adj_id = None
                                for adj_h_id, adj_h in self.active_hazards.items():
                                    if adj_h['location'] == adj_room_name and \
                                    adj_h['type'] == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE:
                                        adj_room_already_on_fire = True
                                        existing_fire_in_adj_id = adj_h_id
                                        break
                                if not adj_room_already_on_fire:
                                    messages.append(color_text(f"The inferno in {hazard['location']} spreads to the {adj_room_name}!", "error"))
                                    self._add_active_hazard(
                                        hazard_type=self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE,
                                        location=adj_room_name,
                                        initial_state_override="burning_low",
                                        target_object_override=f"fire spreading from {hazard['location']}",
                                        support_object_override="the room itself"
                                    )
                                    if adj_room_name in self.room_env:
                                        self.room_env[adj_room_name]['is_on_fire'] = True
                                elif existing_fire_in_adj_id:
                                    adj_fire_hazard = self.active_hazards.get(existing_fire_in_adj_id)
                                    if adj_fire_hazard and adj_fire_hazard['state'] == "burning_low":
                                        messages.append(color_text(f"The fire from {hazard['location']} intensifies the blaze in {adj_room_name}!", "error"))
                                        self._set_hazard_state(existing_fire_in_adj_id, "burning_high", messages)
                                if self.game_logic.is_game_over: break
                        if self.game_logic.is_game_over: break

            self.processed_hazards_this_turn.add(hazard_id)

        # After all hazards, check for global environmental reactions (e.g., gas explosions)
        if not self.game_logic.is_game_over:
            self._check_global_environmental_reactions(messages)

        death_occurred_this_turn = self.game_logic.is_game_over and not self.game_logic.game_won
        logging.debug(f"HazardEngine: --- Hazard Turn Update End --- Messages: {len(messages)}, Death: {death_occurred_this_turn}")
        return list(filter(None, messages)), death_occurred_this_turn

    def _calculate_aggression_factor(self):
        """Calculates global aggression factor."""
        if not self.game_logic or not self.player: return 0.0
        max_turns = self.game_logic.game_data.STARTING_TURNS 
        turns_left = self.player.get('turns_left', max_turns)
        if turns_left <= 0: return 2.0
        turns_used_ratio = (max_turns - turns_left) / float(max_turns)
        aggression = 0.0
        if turns_used_ratio < 0.33: aggression = turns_used_ratio * 0.5 
        elif turns_used_ratio < 0.66: aggression = 0.165 + (turns_used_ratio - 0.33) * 1.5 
        else: aggression = 0.66 + (turns_used_ratio - 0.66) * 2.5 
        return min(aggression, 2.0) 

    def _apply_per_turn_room_effects(self, hazard_id, hazard_instance, state_data, messages_list):
        """Applies per-turn effects if player is in the room."""
        if self.game_logic.is_game_over: return
        damage_per_turn = state_data.get("hp_damage_per_turn_in_room", 0)
        if damage_per_turn > 0:
            msg = state_data.get("hp_damage_per_turn_message", "The {object_name} harms you!")
            messages_list.append(color_text(msg.format(object_name=hazard_instance.get('object_name', hazard_instance['type'])), "error"))
            self.game_logic.apply_damage_to_player(damage_per_turn, f"effect of {hazard_instance.get('object_name', hazard_instance['type'])}")
            if self.game_logic.is_game_over: return

        status_def = state_data.get("status_effect_per_turn_in_room")
        if status_def and isinstance(status_def, dict):
            if status_def.get("name"): self.game_logic.apply_status_effect(status_def["name"], status_def.get("duration"), messages_list)
            if self.game_logic.is_game_over: return 

        if state_data.get("instant_death_if_trapped_too_long") and \
           hazard_instance['turns_in_state'] >= state_data.get("turns_to_become_fatal", 3):
            msg = state_data.get("death_message_if_trapped", "You succumb to the {object_name}.")
            messages_list.append(color_text(msg.format(object_name=hazard_instance.get('object_name', hazard_instance['type'])), "error"))
            self.game_logic.is_game_over = True; self.game_logic.game_won = False
            self.player['last_hazard_type'] = hazard_instance['type']; self.player['last_hazard_object_name'] = hazard_instance.get('object_name', hazard_instance['type'])

    def _handle_hazard_to_hazard_interactions(self, source_hazard, rules, agg_factor, messages_list):
        """Handles interactions between hazards in the same room."""
        if self.game_logic.is_game_over: return
        for other_h_id, other_h in list(self.active_hazards.items()): 
            if self.game_logic.is_game_over: break
            if other_h_id == source_hazard['id'] or other_h['location'] != source_hazard['location']: continue 
            
            rule = rules.get(other_h['type']) 
            if not rule or not isinstance(rule, dict): continue

            req_state = rule.get("requires_target_hazard_state")
            if req_state and other_h['state'] not in (req_state if isinstance(req_state, list) else [req_state]): continue
            
            chance = min(1.0, max(0.0, rule.get("chance", 0.5) + (rule.get("aggression_influence_on_chance", 0.0) * source_hazard.get("aggression", agg_factor))))
            if random.random() < chance:
                msg = rule.get("message", "The {source_hazard_object} reacts with {target_hazard_object}!")
                messages_list.append(color_text(msg.format(source_hazard_object=source_hazard.get("object_name", source_hazard['type']), target_hazard_object=other_h.get("object_name", other_h['type'])), "warning"))
                if rule.get("target_state"): self._set_hazard_state(other_h_id, rule["target_state"], messages_list)
                if self.game_logic.is_game_over: return 
                if rule.get("source_target_state") and source_hazard['id'] in self.active_hazards: 
                    self._set_hazard_state(source_hazard['id'], rule["source_target_state"], messages_list)
                    if self.game_logic.is_game_over: return
                    return # Source hazard changed, its interaction turn is done.

    def _move_hazard_toward_player(self, hazard_id, hazard, state_data, messages_list):
        """Moves mobile hazard towards player."""
        # (Simplified logic for brevity - assumes pathfinding and movement updates hazard['location'])
        pass # Full logic in previous snippets

    def _handle_hazard_player_room_entry(self, hazard_id, hazard, state_data, messages_list):
        """Handles effects when mobile hazard enters player's room."""
        # (Simplified logic for brevity - collision checks, status effects)
        pass # Full logic in previous snippets

    def _get_shortest_path(self, start_room, end_room):
        """BFS pathfinding."""
        # (Simplified logic for brevity)
        return None # Full logic in previous snippets

    def _check_hit_player(self, hazard_id, hazard, state_data, messages_list):
        """Handles falling objects hitting player."""
        # (Simplified logic for brevity - damage, fatality check)
        if self.game_logic.is_game_over: return
        player_is_present = self.player.get('location') == hazard['location']
        if player_is_present:
            is_fatal = state_data.get("is_fatal_if_direct_hit", state_data.get("instant_death_if_hit", False))
            hit_damage = state_data.get("hit_damage", 0 if is_fatal else 1) # Example damage
            msg_template = state_data.get("death_message" if is_fatal else "hit_message", "The {object_name} strikes!")
            messages_list.append(color_text(msg_template.format(object_name=hazard.get('object_name', hazard['type'])), "error"))
            if is_fatal:
                self.game_logic.is_game_over = True; self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard['type']; self.player['last_hazard_object_name'] = hazard.get('object_name', hazard['type'])
            elif hit_damage > 0:
                self.game_logic.apply_damage_to_player(hit_damage, f"hit by {hazard.get('object_name', hazard['type'])}")
            if state_data.get("chance_to_progress") == 1.0 and state_data.get("next_state"):
                 self._set_hazard_state(hazard_id, state_data["next_state"], messages_list)


    def _mri_pull_objects(self, hazard_id, hazard, state_data, messages_list):
        """Handles MRI pulling objects."""
        # (Simplified logic for brevity - check player inventory, room objects)
        pass # Full logic in previous snippets

    def _mri_explosion_countdown(self, hazard_id, hazard, state_data, messages_list):
        """Handles MRI explosion countdown."""
        # (Simplified logic for brevity - countdown, explosion effect)
        if self.game_logic.is_game_over: return
        if 'countdown_turns_remaining' not in hazard:
            hazard['countdown_turns_remaining'] = state_data.get("countdown_turns", 2)
        hazard['countdown_turns_remaining'] -= 1
        if hazard['countdown_turns_remaining'] > 0:
            messages_list.append(color_text(f"MRI whines... meltdown in {hazard['countdown_turns_remaining']}...", "error"))
        else:
            messages_list.append(color_text(state_data.get("explosion_death_message", "MRI explodes!"), "error"))
            if self.player.get('location') == hazard['location']:
                self.game_logic.is_game_over = True; self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard['type']; self.player['last_hazard_object_name'] = hazard.get('object_name', hazard['type'])
            self._set_hazard_state(hazard_id, state_data.get("next_state", "exploded"), messages_list)

    def _check_floor_hazards_on_move(self, room_name, messages_list):
        """
        Checks for items on the floor in the given room that are defined as floor hazards
        and applies their effects to the player if triggered.
        Called after a player successfully moves into a new room.
        """
        if self.game_logic.is_game_over:
            return

        items_in_room_world_state = self.game_logic.current_level_items_world_state
        player_affected = False

        for item_name, item_data in items_in_room_world_state.items():
            if item_data.get('location') == room_name and \
            not item_data.get('container') and \
            item_data.get('is_floor_hazard'): # Key flag from game_data.py

                floor_hazard_def = item_data.get('floor_hazard_effect')
                if not floor_hazard_def or not isinstance(floor_hazard_def, dict):
                    continue

                trigger_chance = floor_hazard_def.get('chance', 0.0)
                if random.random() < trigger_chance:
                    player_affected = True
                    effect_message = floor_hazard_def.get('message', f"You encounter a hazard from the {item_name} on the floor!")
                    messages_list.append(color_text(effect_message.format(item_name=item_name), "warning")) # Use .format in case item_name is needed
                    logging.info(f"HazardEngine: Player triggered floor hazard '{item_name}' in '{room_name}'.")

                    # Apply status effect
                    status_def = floor_hazard_def.get('status_effect')
                    if status_def and isinstance(status_def, dict):
                        status_name = status_def.get("name")
                        status_duration = status_def.get("duration")
                        if status_name:
                            self.game_logic.apply_status_effect(status_name, status_duration, messages_list)
                            if self.game_logic.is_game_over: return # Stop if status effect was fatal

                    # Apply HP damage
                    hp_damage = floor_hazard_def.get('hp_damage', 0) # Often part of status_effect, but can be separate
                    if 'hp_damage' in status_def : # Prioritize damage from status effect def if also present
                        hp_damage = status_def.get('hp_damage', hp_damage)
                    
                    if hp_damage > 0:
                        self.game_logic.apply_damage_to_player(hp_damage, f"stepping on {item_name}")
                        if self.game_logic.is_game_over: return # Stop if damage was fatal
                    
                    # Potentially consume or alter the item floor hazard after it triggers
                    if floor_hazard_def.get("consumes_on_trigger"):
                        # Remove item from world or mark as 'triggered'
                        logging.info(f"HazardEngine: Floor hazard '{item_name}' consumed after triggering.")
                        # Simplest: remove its floor_hazard_effect or is_floor_hazard flag
                        item_data.pop('is_floor_hazard', None) 
                        item_data.pop('floor_hazard_effect', None)
                        # Or, if it's a countable item (like "3 shards"), decrement quantity and remove if zero.
                        # This would require quantity tracking on world items. For now, just disabling the hazard part.

        # if player_affected: # No real need for a general message if specific ones were added.
            # messages_list.append(color_text("The floor in this room is treacherous!", "warning"))

    def _check_player_slip(self, hazard_id, hazard, state_data, messages_list):
        """Handles player slipping."""
        # (Simplified logic for brevity - damage, status effect)
        pass # Full logic in previous snippets

    def _check_fall_through(self, hazard_id, hazard, state_data, messages_list):
        """Handles player falling through floor."""
        # (Simplified logic for brevity - room change, damage, fatality)
        pass # Full logic in previous snippets
        
    def update_environmental_states(self):
        """Recalculates environmental state for all rooms."""
        if not self.game_logic or not self.rooms: return
        all_room_names = list(self.rooms.keys())
        for room_name in all_room_names:
            if hasattr(self.game_logic, 'game_data') and hasattr(self.game_logic.game_data, 'initial_environmental_conditions'):
                self.room_env[room_name] = copy.deepcopy(self.game_logic.game_data.initial_environmental_conditions)
            else: self.room_env[room_name] = {} 
            
            current_room_env = self.room_env[room_name]
            for h_instance in self.active_hazards.values():
                if h_instance.get("location") == room_name:
                    s_data = h_instance.get("data", {}).get("states", {}).get(h_instance.get("state"))
                    if s_data and "environmental_effect" in s_data:
                        effects_def = s_data["environmental_effect"]
                        for key, val_def in effects_def.items():
                            if key not in current_room_env: continue
                            if isinstance(current_room_env[key], bool):
                                if isinstance(val_def, bool) and val_def: current_room_env[key] = True
                            elif key in ["gas_level", "noise_level"]:
                                if isinstance(val_def, (int, float)): current_room_env[key] = max(current_room_env.get(key,0), val_def)
                            elif isinstance(current_room_env[key], str):
                                severity = {"normal":0, "dim":1, "hazy":1, "dark":2, "patchy_smoke":2, "very_dark":3, "dense_smoke":3, "zero":4}
                                if severity.get(str(val_def).lower(), -1) > severity.get(current_room_env[key].lower(), -1):
                                    current_room_env[key] = str(val_def)
            # Clamping
            if "gas_level" in current_room_env: current_room_env["gas_level"] = max(0.0, min(4.0, current_room_env["gas_level"]))
            if "noise_level" in current_room_env: current_room_env["noise_level"] = max(0, min(5, int(current_room_env["noise_level"])))
        self._handle_gas_spreading_and_decay()

    def _handle_gas_spreading_and_decay(self):
        """Handles gas diffusion and decay."""
        if not self.game_logic or not hasattr(self.game_logic, 'game_data'): return
        deltas = collections.defaultdict(float)
        for room_name, env in self.room_env.items():
            gas = env.get('gas_level', 0.0)
            if gas <= 0: continue
            room_data = self.rooms.get(room_name)
            if not room_data or not isinstance(room_data.get("exits"), dict): continue
            for _, adj_room in room_data["exits"].items():
                if adj_room in self.room_env:
                    adj_gas = self.room_env[adj_room].get('gas_level', 0.0)
                    if gas > adj_gas + self.game_logic.game_data.GAS_SPREAD_DIFFERENCE_THRESHOLD and \
                       random.random() < self.game_logic.game_data.GAS_SPREAD_CHANCE_PER_EXIT_PER_TURN:
                        spread = min(self.game_logic.game_data.GAS_SPREAD_AMOUNT_PER_TICK, (gas - adj_gas) / 2, gas)
                        deltas[adj_room] += spread; deltas[room_name] -= spread
            if random.random() < self.game_logic.game_data.GAS_DECAY_CHANCE_PER_TURN:
                deltas[room_name] -= self.game_logic.game_data.GAS_DECAY_RATE_PER_TURN
        for room_name, delta in deltas.items():
            if room_name in self.room_env and delta != 0:
                new_level = self.room_env[room_name].get('gas_level', 0.0) + delta
                self.room_env[room_name]['gas_level'] = max(0.0, min(4.0, new_level))

    def _check_global_environmental_reactions(self, messages_list):
        """Checks for room-wide reactions like gas explosions."""
        if self.game_logic.is_game_over: return
        for room_name, env_data in self.room_env.items():
            if self.game_logic.is_game_over: break 
            gas = env_data.get('gas_level', 0.0)
            sparking = env_data.get('is_sparking', False)
            on_fire = env_data.get('is_on_fire', False)
            if gas >= self.game_logic.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD and (sparking or on_fire):
                ign_src = "sparks" if sparking else "flames"
                messages_list.append(color_text(f"Gas in {room_name} ignites from {ign_src}!", "error"))
                messages_list.append(color_text("KA-BOOM! Massive explosion!", "error"))
                if self.player.get('location') == room_name:
                    self.game_logic.is_game_over = True; self.game_logic.game_won = False
                    self.player['last_hazard_type'] = "Gas Explosion"; self.player['last_hazard_object_name'] = room_name 
                    messages_list.append(color_text("You are obliterated in the explosion.", "error"))
                env_data['is_on_fire'] = True; env_data['gas_level'] = 0.0; env_data['is_sparking'] = False
                env_data['visibility'] = "dense_smoke"; env_data['noise_level'] = 5 
                for hz_id, hz in list(self.active_hazards.items()): # Update relevant hazards
                    if hz['location'] == room_name:
                        if hz['type'] == self.game_logic.game_data.HAZARD_TYPE_GAS_LEAK: self._set_hazard_state(hz_id, "sealed_leak", messages_list)
                        elif hz['type'] == self.game_logic.game_data.HAZARD_TYPE_FAULTY_WIRING and hz['state'] in ['sparking', 'arcing']: self._set_hazard_state(hz_id, "shorted_out", messages_list)
                if self.game_logic.is_game_over and self.player.get('location') == room_name: return

    def check_weak_floorboards_on_move(self, room_name, player_current_weight):
        active_floorboard_hazards = [
            (hz_id, hz_instance) for hz_id, hz_instance in self.active_hazards.items()
            if hz_instance['location'] == room_name and hz_instance['type'] == 'weak_floorboards'
        ]

        if not active_floorboard_hazards:
            return None

        hz_id, hazard_instance = active_floorboard_hazards[0] # Assuming one per room
        hazard_data = hazard_instance['data'] # This is the base definition from game_data.hazards

        base_chance = hazard_data.get('base_trigger_chance', 0.05)
        weight_factor = hazard_data.get('weight_factor', 0.1) # From game_data.py [cite: 1]

        trigger_chance = base_chance + (weight_factor * player_current_weight)
        # For the endgame on the Front Porch, if the player is "heavy", you might want to make it certain.
        # However, the GameLogic._handle_endgame_sequence will force it if heavy.
        # This general check can still use probability.
        trigger_chance = min(max(trigger_chance, 0.0), 1.0) # Clamp between 0.0 and 1.0

        logging.debug(f"Checking weak_floorboards in {room_name}. Player weight: {player_current_weight}. Chance: {trigger_chance*100:.2f}%")

        if random.random() < trigger_chance:
            outcome_state_name = hazard_data.get("room_specific_outcomes", {}).get(room_name)
            if not outcome_state_name: # Fallback if room not in specific outcomes
                outcome_state_name = "collapsing" 

            outcome_state_definition = hazard_data['states'].get(outcome_state_name)
            if not outcome_state_definition:
                logging.error(f"Invalid outcome state '{outcome_state_name}' for weak_floorboards in {room_name}.")
                return {"message": color_text("The floor feels unsteady but holds.", "warning"), "death": False, "special_outcome": "holds"}

            temp_messages = []
            # _set_hazard_state applies status effects and can return a death message (though "tripping" is not fatal)
            self._set_hazard_state(hz_id, outcome_state_name, temp_messages) 

            result_message = outcome_state_definition.get("message", "The floorboards react to your weight!")
            if temp_messages: # Prepend any messages from state change (e.g. "creaking")
                result_message = "\n".join(temp_messages) + "\n" + result_message

            is_fatal_outcome = outcome_state_definition.get("is_fatal", False)
            room_transfer_target = None
            if outcome_state_definition.get("room_transfer"):
                room_transfer_target = hazard_data.get("room_connections", {}).get(room_name)
                # Add safety check for room_transfer_target existence in self.rooms

            return {
                "message": result_message,
                "death": is_fatal_outcome,
                "room_transfer_to": room_transfer_target,
                "special_outcome": outcome_state_name # e.g., "tripping", "collapsing"
            }
        return None


    def get_env_state(self, room_name):
        """Gets the environmental state of a room."""
        if not hasattr(self.game_logic, 'game_data') or not hasattr(self.game_logic.game_logic.game_data, 'initial_environmental_conditions'): return {}
        return copy.deepcopy(self.room_env.get(room_name, copy.deepcopy(self.game_logic.game_logic.game_data.initial_environmental_conditions)))

    def get_room_hazards_descriptions(self, room_name):
        """Gets descriptions of active hazards in a room."""
        descriptions = []
        for hazard_id, hz in self.active_hazards.items():
            if hz.get('location') == room_name:
                state_data = hz.get('data', {}).get('states', {}).get(hz.get('state'))
                if state_data and state_data.get('description'):
                    try:
                        formatted_desc = state_data['description'].format(
                            object_name=color_text(hz.get('object_name', hz['name']), 'hazard'),
                            support_object=color_text(hz.get('support_object', 'its surroundings'), 'room')
                        )
                        if formatted_desc.strip(): descriptions.append(formatted_desc)
                    except KeyError: descriptions.append(color_text(f"A {hz.get('name', 'hazard')} ({hz.get('object_name','entity')}) is active.", "warning"))
        return descriptions
    
    def get_room_hazards(self, room_name): return self.get_room_hazards_descriptions(room_name)

    def _add_to_journal(self, category, entry):
        if self.game_logic and hasattr(self.game_logic, '_add_to_journal'): return self.game_logic._add_to_journal(category, entry)
        return False
        
    # In HazardEngine.save_state()
    def save_state(self):
        return {
            "active_hazards": copy.deepcopy(self.active_hazards),
            "room_env": copy.deepcopy(self.room_env),
            "next_hazard_id": self.next_hazard_id,
            "temporary_room_effects": copy.deepcopy(self.temporary_room_effects) # Add this
        }

    # In HazardEngine.load_state()
    def load_state(self, state_dict):
        if not state_dict: return
        self.active_hazards = copy.deepcopy(state_dict.get("active_hazards", {}))
        loaded_room_env = copy.deepcopy(state_dict.get("room_env", {}))
        # ... (existing room_env loading logic) ...
        self.next_hazard_id = state_dict.get("next_hazard_id", self.next_hazard_id)
        self.temporary_room_effects = copy.deepcopy(state_dict.get("temporary_room_effects", [])) # Add this
        # Ensure room_env reflects active temporary effects upon load
        for effect in self.temporary_room_effects:
            if effect['room'] in self.room_env and effect['key'] in self.room_env[effect['room']]:
                 self.room_env[effect['room']][effect['key']] = effect['temp_value']

        logging.info(f"HazardEngine state loaded. Active hazards: {len(self.active_hazards)}. Temp Effects: {len(self.temporary_room_effects)}")

    def _add_active_hazard(self, hazard_type, location, 
                           initial_state_override=None,
                           target_object_override=None, 
                           support_object_override=None,
                           source_trigger_id=None,
                           default_placement_options=None): # default_placement_options was from previous review, might not be used here
        """
        Adds an instance of a specified hazard type to the game world.

        Args:
            hazard_type (str): The key of the hazard in self.hazards_master_data.
            location (str): The room name where the hazard is located.
            initial_state_override (str, optional): Specific state to start in, overrides definition.
            target_object_override (str, optional): Specific name for this instance (e.g., "the sparking console").
                                                    Overrides random choice from object_name_options.
            support_object_override (str, optional): Specific support object (e.g., "on the workbench").
                                                     Overrides dynamic selection.
            source_trigger_id (str, optional): ID of another hazard that triggered this one.
            default_placement_options (list, optional): Not currently used directly here, but was part of _process_hazard_entry.
                                                       Support object selection is now more self-contained.

        Returns:
            str or None: The ID of the newly created hazard instance, or None if creation failed.
        """
        if hazard_type not in self.hazards_master_data:
            logging.warning(f"HazardEngine: Attempted to add unknown hazard type: {hazard_type}")
            return None

        hazard_id = self._generate_hazard_id()
        base_definition = self.hazards_master_data[hazard_type]

        # Determine actual object name for this instance
        final_object_name = target_object_override
        if not final_object_name:
            options = base_definition.get("object_name_options", [base_definition.get("name", hazard_type).lower().replace(" ", "_")])
            final_object_name = random.choice(options) if options else base_definition.get("name", hazard_type)

        # Determine support object (where it's located, e.g., "on the table")
        final_support_object = support_object_override
        if not final_support_object:
            # Logic to pick a support object if not overridden:
            # 1. Check 'placement_object' in hazard definition (list of preferred support types like "desk", "wall")
            # 2. See if any of those are present in the room's furniture or objects.
            # 3. Fallback if necessary.
            room_data_for_placement = self.rooms.get(location, {}) # self.rooms is GameLogic's current_level_rooms
            
            possible_supports_in_room = []
            if room_data_for_placement and isinstance(room_data_for_placement, dict):
                room_furniture_names = [f.get("name") for f in room_data_for_placement.get("furniture", []) if isinstance(f, dict) and f.get("name")]
                room_object_names = room_data_for_placement.get("objects", [])
                all_potential_supports_in_room = room_furniture_names + room_object_names
            else:
                all_potential_supports_in_room = []

            preferred_support_types = base_definition.get("placement_object", []) # e.g., ["desk", "wall panel"]
            
            valid_preferred_supports = [s for s in all_potential_supports_in_room if s in preferred_support_types]

            if valid_preferred_supports:
                final_support_object = random.choice(valid_preferred_supports)
            elif all_potential_supports_in_room: # Fallback to any object/furniture in the room
                final_support_object = random.choice(all_potential_supports_in_room)
            else: # Last resort
                final_support_object = "an indeterminate spot" 
        
        # Determine initial state
        final_initial_state = initial_state_override
        if not final_initial_state: # If no override, use definition's initial_state
            final_initial_state = base_definition.get('initial_state')
        
        # Validate the chosen initial state
        if not final_initial_state or final_initial_state not in base_definition.get('states', {}):
            # If still no valid state, try to pick the first defined state as a fallback
            if base_definition.get('states'):
                try:
                    first_defined_state = list(base_definition['states'].keys())[0]
                    if not final_initial_state: # If it was None from definition
                        logging.warning(f"HazardEngine: Hazard type {hazard_type} has no 'initial_state' defined. Using first state: '{first_defined_state}'.")
                    else: # If override was invalid
                        logging.warning(f"HazardEngine: Provided initial_state_override '{initial_state_override}' for {hazard_type} is invalid. Using first state: '{first_defined_state}'.")
                    final_initial_state = first_defined_state
                except (IndexError, TypeError):
                    logging.error(f"HazardEngine: Hazard type {hazard_type} has no states defined. Cannot add hazard.")
                    return None
            else: # No states defined at all
                logging.error(f"HazardEngine: Hazard type {hazard_type} has no states defined. Cannot add hazard.")
                return None

        new_hazard_instance = {
            "id": hazard_id,
            "type": hazard_type,
            "name": base_definition.get("name", hazard_type), # User-friendly name from definition
            "object_name": final_object_name,       # Specific instance name, e.g., "the sparking console"
            "support_object": final_support_object, # Where it is, e.g., "on the workbench"
            "location": location,
            "state": final_initial_state,
            "data": copy.deepcopy(base_definition), # Full master definition for reference during runtime
            "turns_in_state": 0,
            "aggression": base_definition.get("initial_aggression", 0), # Can be set in master def
            "triggered_by_hazard_id": source_trigger_id,
            # Add any other dynamic properties needed at instance level
        }
        self.active_hazards[hazard_id] = new_hazard_instance
        logging.info(f"HazardEngine: Added active hazard ID {hazard_id}, Type '{hazard_type}' (as '{final_object_name}' on/near '{final_support_object}'), Location '{location}', Initial State '{final_initial_state}'.")
        
        # Apply its initial environmental effect immediately after adding
        # self._apply_environmental_effect_from_hazard(new_hazard_instance) # This will be called by update_environmental_states
        # Instead of calling directly, let initialize_for_level call update_environmental_states once after all initial placements.
        # If a hazard is added mid-game (e.g., by another hazard), then update_environmental_states should be called.

        return hazard_id

    def _set_hazard_state(self, hazard_id, new_state_name, messages_list):
        """
        Sets a hazard to a new state, applies effects, and handles consequences.
        Appends generated messages to messages_list.
        If the new state is instantly fatal and the player is present, 
        it will update game_logic.is_game_over.

        Args:
            hazard_id (str): The ID of the hazard to modify.
            new_state_name (str or None): The name of the target state. If None, the hazard is removed.
            messages_list (list): A list to append user-facing messages to.

        Returns:
            bool: True if the state change (or removal) was successful, False otherwise.
        """
        hazard = self.active_hazards.get(hazard_id)
        if not hazard:
            logging.warning(f"HazardEngine: Hazard ID {hazard_id} not found for state change.")
            return False

        hazard_def_states = hazard['data'].get('states', {})
        old_state_name = hazard['state']

        if new_state_name is None: # Request to remove the hazard
            logging.info(f"HazardEngine: Removing hazard {hazard_id} ('{hazard['type']}') from {hazard['location']}.")
            
            # Prepare to remove its environmental effect by getting its old state data
            # old_state_data_for_removal = copy.deepcopy(hazard_def_states.get(old_state_name, {}))
            # old_state_data_for_removal['location_ref_for_removal'] = hazard['location'] # For _remove_environmental_effect

            del self.active_hazards[hazard_id]
            # self._remove_environmental_effect_from_hazard(old_state_data_for_removal) # Signal for env recalc
            self.update_environmental_states() # Recalculate all env states after removal
            
            removal_message = hazard['data'].get("removal_message", f"The {hazard.get('object_name', hazard['type'])} is no longer an issue.")
            messages_list.append(color_text(removal_message, "success"))
            return True

        if new_state_name not in hazard_def_states:
            logging.warning(f"HazardEngine: Attempted to set invalid state '{new_state_name}' for hazard {hazard_id} ('{hazard['type']}'). Valid: {list(hazard_def_states.keys())}")
            return False

        if old_state_name == new_state_name:
            logging.debug(f"HazardEngine: Hazard {hazard_id} already in state '{new_state_name}'. No change.")
            return True # No change needed, but not an error

        logging.info(f"HazardEngine: Hazard {hazard_id} ('{hazard['type']}' at '{hazard['location']}') changing state: '{old_state_name}' -> '{new_state_name}'.")

        # Update hazard instance
        hazard['state'] = new_state_name
        hazard['turns_in_state'] = 0
        new_state_definition = hazard_def_states[new_state_name]

        # Update overall room environment based on ALL active hazards after this state change
        self.update_environmental_states() # This is crucial

        # Add description of the new state to messages
        desc_template = new_state_definition.get('description')
        if desc_template:
            try:
                # Use the hazard's specific instance name and support object
                formatted_desc = desc_template.format(
                    object_name=color_text(hazard.get('object_name', hazard['name']), 'hazard'),
                    support_object=color_text(hazard.get('support_object', 'its surroundings'), 'room')
                )
                messages_list.append(formatted_desc)
            except KeyError as e:
                logging.error(f"HazardEngine: KeyError in hazard description format for {hazard['type']}/{new_state_name}: {e}. Template: '{desc_template}'")
                messages_list.append(color_text(f"The {hazard.get('object_name', hazard['name'])} changes.", "warning"))

        # Player-related effects if player is in the same room as the hazard
        player_is_present = self.player.get('location') == hazard['location']
        if player_is_present and not self.game_logic.is_game_over:
            # Apply direct HP damage specified in the new state definition
            hp_damage_on_state_change = new_state_definition.get("instant_hp_damage", 0)
            if hp_damage_on_state_change > 0:
                damage_source_name = hazard.get('object_name', hazard['name'])
                self.game_logic.apply_damage_to_player(hp_damage_on_state_change, f"effect from {damage_source_name}")
                messages_list.append(color_text(f"You take {hp_damage_on_state_change} damage from the {damage_source_name}!", "error"))
                # game_logic.apply_damage_to_player will set is_game_over if HP <= 0

            # Apply status effect specified in the new state definition
            status_effect_def = new_state_definition.get("status_effect_on_state_change") # More specific key
            if status_effect_def and isinstance(status_effect_def, dict) and not self.game_logic.is_game_over:
                status_name = status_effect_def.get("name")
                status_duration = status_effect_def.get("duration")
                if status_name:
                    # game_logic.apply_status_effect will handle appending its own message if messages_list is passed
                    self.game_logic.apply_status_effect(status_name, status_duration, messages_list)

            # Check for instant death flag in the new state if player is present
            if new_state_definition.get('instant_death_in_room') and not self.game_logic.is_game_over:
                death_msg_template = new_state_definition.get('death_message', f"The {hazard.get('object_name', hazard['name'])} escalates fatally!")
                messages_list.append(color_text(death_msg_template.format(object_name=hazard.get('object_name', 'area')), "error"))
                
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard['type']
                self.player['last_hazard_object_name'] = hazard.get('object_name', hazard['name'])
                logging.info(f"HazardEngine: Instant death triggered for player by hazard {hazard_id} ('{hazard['type']}') entering state '{new_state_name}'.")
                return True # State change occurred, game ended.

        # If game ended due to direct effects of this state change, return
        if self.game_logic.is_game_over:
            return True

        # Chain Reaction: Trigger another hazard based on this state change
        # This logic will be detailed more in Phase 3 (Turn Update) as it's a common part of progression.
        # For now, a placeholder indicating where it would go.
        # self._handle_chained_hazard_triggers(hazard, new_state_definition, messages_list)
        
        return True # State change successful
        
    def hazard_turn_update(self):
        """
        Processes all active hazards for the current game turn.
        Handles autonomous state progression, actions, player-seeking, and chain reactions.

        Returns:
            tuple: (list_of_messages, death_occurred_bool)
                   A list of messages generated by hazard activities this turn,
                   and a boolean indicating if any hazard activity resulted in player death.
        """
        messages = []
        # Aggression factor can influence hazard behavior (e.g., chance to progress state)
        agg_factor = self._calculate_aggression_factor() 
        logging.debug(f"HazardEngine: --- Hazard Turn Update Start --- Aggression Factor: {agg_factor:.2f}")

        self.processed_hazards_this_turn.clear() # Reset for this turn
        active_hazard_ids_this_cycle = list(self.active_hazards.keys()) # Iterate over a copy in case of mid-loop modifications

        for hazard_id in active_hazard_ids_this_cycle:
            if self.game_logic.is_game_over: break # Stop processing if game ended mid-update
            if hazard_id in self.processed_hazards_this_turn: continue 
            if hazard_id not in self.active_hazards: continue # Hazard might have been removed by another

            hazard = self.active_hazards[hazard_id]
            hazard['turns_in_state'] += 1
            
            # Accumulate aggression for the hazard instance if defined
            hazard_aggression_increase = hazard['data'].get('aggression_per_turn_increase', 0.0)
            max_hazard_aggression = hazard['data'].get('max_aggression', 5.0) # Max aggression for this specific hazard type
            hazard['aggression'] = min(hazard.get('aggression', 0) + hazard_aggression_increase, max_hazard_aggression)

            current_state_name = hazard["state"]
            state_data = hazard["data"]["states"].get(current_state_name)
            if not state_data:
                logging.warning(f"HazardEngine: Hazard {hazard_id} ('{hazard['type']}') in unknown state '{current_state_name}'. Skipping update.")
                continue

            player_is_present = self.player.get('location') == hazard['location']

            # 1. Apply Per-Turn Room Effects (if player is present)
            if player_is_present and not self.game_logic.is_game_over:
                self._apply_per_turn_room_effects(hazard_id, hazard, state_data, messages)
                if self.game_logic.is_game_over: break 
            
            # 2. Autonomous Actions defined for the current state
            autonomous_action_key = state_data.get('autonomous_action')
            if autonomous_action_key and not self.game_logic.is_game_over:
                can_run_globally = state_data.get("global_autonomous_action", False) # Action runs even if player not present
                if player_is_present or can_run_globally:
                    action_method = getattr(self, f"_{autonomous_action_key}", None) # e.g., _mri_pull_objects
                    if action_method and callable(action_method):
                        logging.debug(f"HazardEngine: Executing autonomous action '{autonomous_action_key}' for hazard {hazard_id}.")
                        action_method(hazard_id, hazard, state_data, messages) # Pass state_data for context
                    else:
                        logging.warning(f"HazardEngine: Unknown autonomous_action_key or non-callable method: '{autonomous_action_key}' for hazard {hazard_id}")
                    if self.game_logic.is_game_over: break

            # 3. Chance to Progress State
            if "chance_to_progress" in state_data and "next_state" in state_data and not self.game_logic.is_game_over:
                base_chance = state_data["chance_to_progress"]
                # Aggression influence can be defined per state
                aggro_boost_def = state_data.get("aggression_influence", {}).get("chance_to_progress_boost", 0.0)
                # Use hazard's own accumulated aggression or global aggression factor
                current_aggression = hazard.get("aggression", agg_factor) 
                aggro_boost_val = aggro_boost_def * current_aggression
                
                actual_chance = min(1.0, max(0.0, base_chance + aggro_boost_val))
                
                if random.random() < actual_chance:
                    logging.debug(f"HazardEngine: Hazard {hazard_id} progressing state due to chance ({actual_chance:.2f}).")
                    self._set_hazard_state(hazard_id, state_data["next_state"], messages)
                    if self.game_logic.is_game_over: break
                    # If state changed, re-fetch current_state_name and state_data for subsequent checks in this turn
                    if hazard_id in self.active_hazards:
                        current_state_name = self.active_hazards[hazard_id]["state"]
                        state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                        if not state_data: continue # Should not happen if next_state is valid
                    else: continue # Hazard was removed by state change

            # 4. Chance to Revert State
            if "chance_to_revert" in state_data and "revert_state" in state_data and not self.game_logic.is_game_over:
                base_revert_chance = state_data.get("chance_to_revert", 0.05)
                revert_agg_multiplier = state_data.get("aggression_influence", {}).get("revert_chance_multiplier", 1.0) # 1.0 = no change
                current_aggression = hazard.get("aggression", agg_factor)
                effective_revert_chance = base_revert_chance * revert_agg_multiplier 

                if random.random() < effective_revert_chance:
                    revert_msg_template = state_data.get("revert_message", "The {object_name} seems to calm down a bit.")
                    messages.append(color_text(revert_msg_template.format(object_name=hazard.get('object_name', hazard['type'])), "info"))
                    self._set_hazard_state(hazard_id, state_data["revert_state"], messages)
                    if self.game_logic.is_game_over: break
                    if hazard_id in self.active_hazards: # Re-fetch state if changed
                        current_state_name = self.active_hazards[hazard_id]["state"]
                        state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                        if not state_data: continue
                    else: continue

            # 5. Hazard Interactions (hazard affecting another hazard in the same room)
            if "hazard_interaction" in state_data and isinstance(state_data["hazard_interaction"], dict) and not self.game_logic.is_game_over:
                self._handle_hazard_to_hazard_interactions(hazard, state_data["hazard_interaction"], agg_factor, messages)
                if self.game_logic.is_game_over: break 
                # Re-fetch current hazard's state_data if it changed itself during interaction
                if hazard_id in self.active_hazards:
                    current_state_name = self.active_hazards[hazard_id]["state"]
                    state_data = self.active_hazards[hazard_id]["data"]["states"].get(current_state_name)
                    if not state_data: continue
                else: continue


            # 6. Autonomous Decay (e.g., fire burning out)
            # Check for a general 'autonomous_decay' or a more specific one like 'autonomous_decay_to_burnt_out'
            decay_info = state_data.get("autonomous_decay") 
            if not decay_info and hazard['type'] == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE: # Example for specific type
                 decay_info = state_data.get("autonomous_decay_to_burnt_out") # This key is from game_data.py

            if decay_info and isinstance(decay_info, dict) and not self.game_logic.is_game_over:
                decay_chance = decay_info.get("chance", 0.05)
                if random.random() < decay_chance:
                    decay_target_state = decay_info.get("target_state") # Can be None to remove hazard
                    decay_message_template = decay_info.get("message", "The {object_name} seems to be diminishing.")
                    messages.append(color_text(decay_message_template.format(object_name=hazard.get('object_name', hazard['type'])), "info"))
                    self._set_hazard_state(hazard_id, decay_target_state, messages) # _set_hazard_state handles None state (removal)
                    if self.game_logic.is_game_over: break
                    if hazard_id not in self.active_hazards: continue # Hazard removed by decay

            self.processed_hazards_this_turn.add(hazard_id)

        # After all individual hazard updates, check for global environmental reactions (e.g., gas explosion from sparks)
        if not self.game_logic.is_game_over:
            # _check_global_environmental_reactions will be reviewed in Phase 4
            self._check_global_environmental_reactions(messages) 
        
        # Consolidate death status from any point in the update
        death_occurred_this_turn = self.game_logic.is_game_over and not self.game_logic.game_won

        logging.debug(f"HazardEngine: --- Hazard Turn Update End --- Messages: {len(messages)}, Death: {death_occurred_this_turn}")
        return list(filter(None, messages)), death_occurred_this_turn

    def _calculate_aggression_factor(self):
        """
        Calculates a global aggression factor based on game progress (e.g., turns left).
        Returns a float, e.g., 0.0 (early game) to 1.0 or higher (late game).
        """
        if not self.game_logic or not self.player: return 0.0 
        
        max_turns = self.game_logic.game_data.STARTING_TURNS 
        turns_left = self.player.get('turns_left', max_turns)

        if turns_left <= 0: return 2.0 # Max aggression if time is up or very low
        
        turns_used_ratio = (max_turns - turns_left) / float(max_turns)
        
        aggression = 0.0
        if turns_used_ratio < 0.33: 
            aggression = turns_used_ratio * 0.5 
        elif turns_used_ratio < 0.66: 
            aggression = 0.165 + (turns_used_ratio - 0.33) * 1.5 
        else: 
            aggression = 0.66 + (turns_used_ratio - 0.66) * 2.5 
            
        aggression = min(aggression, 2.0) 
        return aggression

    def _apply_per_turn_room_effects(self, hazard_id, hazard_instance, state_data, messages_list):
        """
        Applies effects that occur each turn a player is in a room with an active hazard state.
        Examples: taking damage from fire, status effect from toxic fumes.
        """
        if self.game_logic.is_game_over: return

        damage_per_turn = state_data.get("hp_damage_per_turn_in_room", 0)
        if damage_per_turn > 0:
            damage_message_template = state_data.get("hp_damage_per_turn_message", "The {object_name} continues to harm you!")
            messages_list.append(color_text(damage_message_template.format(
                object_name=hazard_instance.get('object_name', hazard_instance['type'])
            ), "error"))
            self.game_logic.apply_damage_to_player(damage_per_turn, f"ongoing effect of {hazard_instance.get('object_name', hazard_instance['type'])}")
            if self.game_logic.is_game_over: return

        status_def_per_turn = state_data.get("status_effect_per_turn_in_room")
        if status_def_per_turn and isinstance(status_def_per_turn, dict):
            status_name = status_def_per_turn.get("name")
            status_duration = status_def_per_turn.get("duration") 
            if status_name:
                self.game_logic.apply_status_effect(status_name, status_duration, messages_list)
                if self.game_logic.is_game_over: return 

        if state_data.get("instant_death_if_trapped_too_long"):
            turns_to_become_fatal = state_data.get("turns_to_become_fatal", 3) 
            if hazard_instance['turns_in_state'] >= turns_to_become_fatal:
                death_message_template = state_data.get("death_message_if_trapped", "You've been exposed to the {object_name} for too long and succumb.")
                messages_list.append(color_text(death_message_template.format(
                    object_name=hazard_instance.get('object_name', hazard_instance['type'])
                ), "error"))
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard_instance['type']
                self.player['last_hazard_object_name'] = hazard_instance.get('object_name', hazard_instance['type'])
                logging.info(f"HazardEngine: Player died from being trapped too long with hazard {hazard_id} ('{hazard_instance['type']}') in state '{hazard_instance['state']}'.")

    def _handle_hazard_to_hazard_interactions(self, source_hazard, source_state_interaction_rules, agg_factor, messages_list):
        """
        Handles interactions where one hazard (source_hazard) in its current state
        affects other hazards in the same room.
        """
        if self.game_logic.is_game_over: return

        for other_h_id, other_h_instance in list(self.active_hazards.items()): 
            if self.game_logic.is_game_over: break
            if other_h_id == source_hazard['id'] or other_h_instance['location'] != source_hazard['location']:
                continue 
            
            interaction_def = source_state_interaction_rules.get(other_h_instance['type']) 
            if not interaction_def or not isinstance(interaction_def, dict):
                continue

            required_target_state = interaction_def.get("requires_target_hazard_state")
            if required_target_state:
                other_current_state = other_h_instance['state']
                if isinstance(required_target_state, list) and other_current_state not in required_target_state:
                    continue
                elif isinstance(required_target_state, str) and other_current_state != required_target_state:
                    continue
            
            base_interaction_chance = interaction_def.get("chance", 0.5)
            agg_boost_on_interaction = interaction_def.get("aggression_influence_on_chance", 0.0) * source_hazard.get("aggression", agg_factor)
            final_interaction_chance = min(1.0, max(0.0, base_interaction_chance + agg_boost_on_interaction))

            if random.random() < final_interaction_chance:
                interaction_msg_template = interaction_def.get("message", "The {source_hazard_object} reacts with the {target_hazard_object}!")
                messages_list.append(color_text(interaction_msg_template.format(
                    source_hazard_object=source_hazard.get("object_name", source_hazard['type']),
                    target_hazard_object=other_h_instance.get("object_name", other_h_instance['type'])
                ), "warning"))

                target_new_state = interaction_def.get("target_state")
                if target_new_state:
                    self._set_hazard_state(other_h_id, target_new_state, messages_list)
                    if self.game_logic.is_game_over: return 
                
                source_new_state_after_interaction = interaction_def.get("source_target_state")
                if source_new_state_after_interaction and source_hazard['id'] in self.active_hazards: 
                    self._set_hazard_state(source_hazard['id'], source_new_state_after_interaction, messages_list)
                    if self.game_logic.is_game_over: return
                    return # Source hazard changed, its turn update for interactions is done.

    # --- Autonomous Action Implementations ---
    # These are called by hazard_turn_update via getattr if defined in a hazard's state.

    def _move_hazard_toward_player(self, hazard_id, hazard_instance, state_data, messages_list): # state_data passed for context
        """Moves a mobile hazard one step closer to the player using BFS pathfinding."""
        if not hazard_instance['data'].get('can_move_between_rooms'):
            logging.debug(f"Hazard {hazard_id} cannot move between rooms.")
            return

        player_room = self.player['location']
        current_hazard_room = hazard_instance['location']

        if current_hazard_room == player_room:
            # Hazard is already in player's room, check for collision/interaction
            self._handle_hazard_player_room_entry(hazard_id, hazard_instance, state_data, messages_list)
            return

        # Determine if hazard should seek player this turn
        # 'state_data' is the definition for the hazard's *current* state
        base_seek_chance = state_data.get('player_seek_chance', hazard_instance['data'].get('player_seek_chance', 0.1))
        agg_factor_for_seek = hazard_instance.get("aggression", self._calculate_aggression_factor()) # Use instance or global
        
        # Aggression influence on seek chance (e.g., from hazard definition)
        agg_influence_on_seek = state_data.get("aggression_influence", {}).get("player_seek_chance_boost", 0.1) * agg_factor_for_seek
        current_seek_chance = min(1.0, max(0.0, base_seek_chance + agg_influence_on_seek))

        if random.random() > current_seek_chance:
            logging.debug(f"Hazard {hazard_id} did not seek player this turn (chance: {current_seek_chance:.2f}).")
            # Optional: random movement if not seeking but aggressive and allowed by state
            if agg_factor_for_seek > 1.0 and random.random() < (agg_factor_for_seek * 0.05) and state_data.get('can_move_randomly_if_not_seeking'):
                room_data_for_move = self.rooms.get(current_hazard_room) # self.rooms is GameLogic's current_level_rooms
                if room_data_for_move and room_data_for_move.get("exits"):
                    possible_next_rooms = [
                        r_name for r_name in room_data_for_move["exits"].values()
                        if r_name in self.rooms and not self.rooms[r_name].get('locked')
                    ]
                    if possible_next_rooms:
                        hazard_instance['location'] = random.choice(possible_next_rooms)
                        messages_list.append(color_text(f"The {hazard_instance.get('object_name', 'hazard')} wanders aimlessly to the {hazard_instance['location']}.", "info"))
                        logging.info(f"Hazard {hazard_id} moved randomly to {hazard_instance['location']}.")
            return

        # Pathfinding
        full_path = self._get_shortest_path(current_hazard_room, player_room)
        if full_path and len(full_path) > 1:
            next_step_room = full_path[1]
            
            # Movement constraints check (example)
            # movement_constraints = hazard_instance['data'].get("movement_constraints")
            # if movement_constraints == "same_floor_only":
            #    if self.rooms.get(current_hazard_room,{}).get('floor_level') != self.rooms.get(next_step_room,{}).get('floor_level'):
            #        logging.debug(f"Hazard {hazard_id} cannot move to {next_step_room} due to floor constraint.")
            #        return

            hazard_instance['location'] = next_step_room
            
            move_msg_template_key = "move_description_seek" if next_step_room != player_room else "enter_player_room_description_seek"
            desc_template = state_data.get(move_msg_template_key, 
                                           hazard_instance['data'].get(move_msg_template_key, 
                                                                      "The {name} moves purposefully."))
            messages_list.append(color_text(desc_template.format(
                name=hazard_instance.get('object_name', 'hazard'),
                current_room=current_hazard_room, # For more descriptive messages
                next_room=next_step_room,
                player_room=player_room
                ), "warning"))
            logging.info(f"Hazard {hazard_id} ('{hazard_instance['type']}') moved from {current_hazard_room} to {next_step_room} seeking player.")

            if next_step_room == player_room:
                self._handle_hazard_player_room_entry(hazard_id, hazard_instance, state_data, messages_list)
        else:
            logging.debug(f"Hazard {hazard_id} could not find path from {current_hazard_room} to {player_room} or is already there.")

    def _handle_hazard_player_room_entry(self, hazard_id, hazard_instance, state_data, messages_list):
        """Handles effects when a mobile hazard enters or is already in the player's room."""
        if self.game_logic.is_game_over: return
        if self.player.get('location') != hazard_instance['location']: return # Should not happen if called correctly

        logging.debug(f"Hazard {hazard_id} ('{hazard_instance['type']}') in same room as player. Checking for collision/effects.")
        
        # Check for collision effects defined in the hazard's master data (collision_effects.player)
        player_collision_rules = hazard_instance['data'].get('collision_effects', {}).get('player', {})
        if player_collision_rules and random.random() < player_collision_rules.get('chance', 0.0):
            effect_type = player_collision_rules.get('effect')
            collision_msg = player_collision_rules.get("message", f"The {hazard_instance.get('object_name','hazard')} collides with you!")
            messages_list.append(color_text(collision_msg, "warning"))

            if effect_type == 'trip':
                status_to_apply = player_collision_rules.get("status_effect")
                if status_to_apply and isinstance(status_to_apply, dict):
                    self.game_logic.apply_status_effect(status_to_apply.get("name"), status_to_apply.get("duration"), messages_list)
            
            elif effect_type == 'direct_damage':
                damage = player_collision_rules.get("hp_damage", 1)
                self.game_logic.apply_damage_to_player(damage, f"collision with {hazard_instance.get('object_name','hazard')}")
                # apply_damage_to_player handles game over if HP <= 0
            
            elif effect_type == 'fatal_collision': # Example of a more direct fatal outcome
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard_instance['type']
                self.player['last_hazard_object_name'] = hazard_instance.get('object_name', 'mobile hazard')
                messages_list.append(color_text(player_collision_rules.get("fatal_message", "The collision is fatal!"), "error"))
                logging.info(f"Player killed by fatal collision with hazard {hazard_id}.")
        
        # Even if no direct collision, the hazard's presence might have other per-turn effects
        # These are handled by _apply_per_turn_room_effects if player is present.
        # This function is more about the *entry* or *direct bump* interaction.

    def _get_shortest_path(self, start_room, end_room):
        """Simple BFS to find the shortest path (list of room names) between two rooms."""
        if start_room == end_room: return [start_room] # Path to self is just self
        if not self.rooms: # self.rooms is GameLogic's current_level_rooms
            logging.warning("_get_shortest_path: No room data available (self.rooms is empty/None).")
            return None 

        queue = collections.deque([(start_room, [start_room])])
        visited = {start_room}

        while queue:
            current_room_name, path = queue.popleft()
            # Access room data using self.rooms (which points to GameLogic's current_level_rooms)
            current_room_data = self.rooms.get(current_room_name) 
            if not current_room_data or not isinstance(current_room_data.get("exits"), dict):
                continue # Skip if room data or exits are invalid

            for _, next_room_candidate_name in current_room_data["exits"].items():
                if next_room_candidate_name == end_room:
                    return path + [next_room_candidate_name]
                
                if next_room_candidate_name not in visited:
                    next_room_data = self.rooms.get(next_room_candidate_name)
                    # Pathfind only through unlocked rooms
                    if next_room_data and not next_room_data.get('locked', False):
                        visited.add(next_room_candidate_name)
                        queue.append((next_room_candidate_name, path + [next_room_candidate_name]))
        
        logging.debug(f"No path found from {start_room} to {end_room}.")
        return None # No path found

    # --- Stubs for other autonomous actions mentioned in game_data.hazards ---
    def _check_hit_player(self, hazard_id, hazard_instance, state_data, messages_list):
        """Placeholder for hazards that might hit the player (e.g., falling objects)."""
        if self.game_logic.is_game_over: return
        player_is_present = self.player.get('location') == hazard_instance['location']
        if player_is_present:
            # Logic from wobbly_ceiling_fan or loose_object
            hit_damage = state_data.get("hit_damage", state_data.get("instant_hp_damage", 0)) # Use a consistent key or prioritize
            is_fatal = state_data.get("is_fatal_if_direct_hit", state_data.get("instant_death_if_hit", False))
            
            # Use a specific death message from the state if available, otherwise a generic one
            death_message_template = state_data.get("death_message", "The {object_name} strikes you fatally!")
            hit_message_template = state_data.get("hit_message", "The {object_name} hits you!")

            message_to_show = death_message_template if is_fatal else hit_message_template
            
            messages_list.append(color_text(message_to_show.format(
                object_name=hazard_instance.get('object_name', hazard_instance['type'])
            ), "error"))

            if is_fatal:
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard_instance['type']
                self.player['last_hazard_object_name'] = hazard_instance.get('object_name', hazard_instance['type'])
            elif hit_damage > 0:
                self.game_logic.apply_damage_to_player(hit_damage, f"being hit by {hazard_instance.get('object_name', hazard_instance['type'])}")
            
            # If the hazard state implies it's now 'fallen' or 'inactive' after hitting
            if state_data.get("chance_to_progress") == 1.0 and state_data.get("next_state"):
                 self._set_hazard_state(hazard_id, state_data["next_state"], messages_list)
        logging.debug(f"HazardEngine: _check_hit_player for {hazard_id} - Player present: {player_is_present}")

    def _mri_pull_objects(self, hazard_id, hazard_instance, state_data, messages_list):
        """Placeholder for MRI pulling objects in the room or from player."""
        if self.game_logic.is_game_over: return
        logging.debug(f"HazardEngine: _mri_pull_objects for {hazard_id} activated.")
        # This would involve:
        # 1. Checking player's inventory for metallic items (as in GameLogic._mri_pull_player_items).
        # 2. Checking the room's defined metallic objects (e.g., from room_data or hazard_instance.data.room_metal_objects).
        # 3. Applying damage or fatal outcomes based on what's pulled.
        # For now, refers to the logic that was previously in GameLogic for player items.
        if hasattr(self.game_logic, '_mri_pull_player_items_logic_for_hazard_engine'): # Hypothetical refactor
            self.game_logic._mri_pull_player_items_logic_for_hazard_engine(hazard_id, hazard_instance, state_data, messages_list)
        else: # Fallback or simplified version
            if self.player.get('location') == hazard_instance['location']:
                messages_list.append(color_text(f"The {hazard_instance.get('object_name','MRI machine')} hums powerfully, and you feel a strong magnetic pull!", "warning"))
                # Simplified: check for a generic "metallic_item_in_room" flag or a specific item
                # This needs more detailed data in game_data.py for room contents.

    def _mri_explosion_countdown(self, hazard_id, hazard_instance, state_data, messages_list):
        """Handles the MRI explosion countdown."""
        if self.game_logic.is_game_over: return
        
        if 'countdown_turns_remaining' not in hazard_instance: # Initialize countdown
            hazard_instance['countdown_turns_remaining'] = state_data.get("countdown_turns", 2) # Get from state_data
            # Initial countdown message should come from the state that *starts* this autonomous action
            # or the description of the "catastrophic_failure" state itself.
            # messages_list.append(color_text(state_data.get("countdown_message", "The MRI is about to explode!"), "error"))
        
        hazard_instance['countdown_turns_remaining'] -= 1
        
        if hazard_instance['countdown_turns_remaining'] > 0:
            messages_list.append(color_text(f"The {hazard_instance.get('object_name','MRI machine')} whines ominously... meltdown in {hazard_instance['countdown_turns_remaining']}...", "error"))
        else: # Countdown finished
            explosion_message = state_data.get("explosion_death_message", # This key is from mri_machine_hazard in game_data
                                               f"The {hazard_instance.get('object_name','MRI machine')} explodes catastrophically!")
            messages_list.append(color_text(explosion_message, "error"))
            
            player_is_present = self.player.get('location') == hazard_instance['location']
            # Could also affect adjacent rooms based on explosion_radius_rooms from state_data
            
            if player_is_present:
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard_instance['type']
                self.player['last_hazard_object_name'] = hazard_instance.get('object_name', hazard_instance['type'])
            
            # Set the MRI to its 'exploded' state (or whatever next_state is defined for catastrophic_failure)
            next_state_after_explosion = state_data.get("next_state", "exploded") # from mri_machine_hazard's catastrophic_failure state
            self._set_hazard_state(hazard_id, next_state_after_explosion, messages_list)
        logging.debug(f"HazardEngine: _mri_explosion_countdown for {hazard_id}, turns left: {hazard_instance.get('countdown_turns_remaining', 0)}")

    def _check_player_slip(self, hazard_id, hazard_instance, state_data, messages_list):
        """Placeholder for hazards that might cause the player to slip (e.g., water puddle)."""
        if self.game_logic.is_game_over: return
        player_is_present = self.player.get('location') == hazard_instance['location']
        if player_is_present:
            # Logic for slipping, e.g. from water_puddle's slip_hazard state
            slip_damage = state_data.get("slip_damage", 0)
            slip_message_template = state_data.get("slip_message", "You slip on the {object_name}!")
            
            # Chance to slip can be added here if not 100%
            # if random.random() < state_data.get("slip_chance", 1.0):
            messages_list.append(color_text(slip_message_template.format(
                object_name=hazard_instance.get('object_name', hazard_instance['type'])
            ), "warning"))
            if slip_damage > 0:
                self.game_logic.apply_damage_to_player(slip_damage, f"slipping on {hazard_instance.get('object_name', hazard_instance['type'])}")
            # Potentially apply a status effect like "prone" or "stumbled"
            # status_on_slip = state_data.get("status_effect_on_slip")
            # if status_on_slip: self.game_logic.apply_status_effect(...)
        logging.debug(f"HazardEngine: _check_player_slip for {hazard_id} - Player present: {player_is_present}")

    def _check_fall_through(self, hazard_id, hazard_instance, state_data, messages_list):
        """Placeholder for hazards where player might fall through (e.g., weak floorboards collapsing not due to direct move)."""
        if self.game_logic.is_game_over: return
        player_is_present = self.player.get('location') == hazard_instance['location']
        if player_is_present:
            # This is for spontaneous collapse. Movement-triggered collapse is in GameLogic/check_weak_floorboards_on_move
            fall_outcome_message = state_data.get("fall_outcome_message", "The floor beneath you gives way!")
            messages_list.append(color_text(fall_outcome_message, "error"))
            
            is_fatal = state_data.get("is_fatal_if_no_target", True) # Or specific 'is_fatal' flag
            fall_damage = state_data.get("fall_damage", 3)
            target_room_override = state_data.get("fall_target_room_override")

            if target_room_override and target_room_override in self.rooms:
                messages_list.append(color_text(f"You plummet into the {target_room_override} below!", "warning"))
                self.player['location'] = target_room_override
                self.player.setdefault('visited_rooms', set()).add(target_room_override)
                messages_list.append(self.game_logic.get_room_description(target_room_override)) # Show new room
                if fall_damage > 0:
                    self.game_logic.apply_damage_to_player(fall_damage, f"falling through floor to {target_room_override}")
            elif is_fatal:
                self.game_logic.is_game_over = True
                self.game_logic.game_won = False
                self.player['last_hazard_type'] = hazard_instance['type']
                self.player['last_hazard_object_name'] = hazard_instance.get('object_name', hazard_instance['type'])
            elif fall_damage > 0:
                 self.game_logic.apply_damage_to_player(fall_damage, "falling (no specific target room)")
            
            # Hazard itself likely transitions to a "hole" or "collapsed" state
            next_state_for_hazard = state_data.get("next_state_after_fall", "hole")
            self._set_hazard_state(hazard_id, next_state_for_hazard, messages_list)

        logging.debug(f"HazardEngine: _check_fall_through for {hazard_id} - Player present: {player_is_present}")


    def _apply_environmental_effect_from_hazard(self, hazard_instance):
        """
        Applies the environmental effects of a single hazard's current state to its room's environment.
        This method directly modifies self.room_env[location].
        It's typically called when a hazard is first added or changes state, before a full
        recalculation by update_environmental_states if an immediate reflection is needed,
        though update_environmental_states is the more comprehensive way to set room_env.

        Args:
            hazard_instance (dict): The active hazard instance.
        """
        if not hazard_instance or not isinstance(hazard_instance, dict):
            logging.warning("HazardEngine: Invalid hazard_instance passed to _apply_environmental_effect_from_hazard.")
            return

        state_data = hazard_instance.get('data', {}).get('states', {}).get(hazard_instance.get('state'))
        if not state_data: 
            logging.debug(f"HazardEngine: No state data for hazard {hazard_instance.get('id')} in state {hazard_instance.get('state')}, no direct env effect to apply.")
            return

        env_effects_def = state_data.get('environmental_effect')
        if not env_effects_def or not isinstance(env_effects_def, dict):
            return # No environmental effects defined for this state

        location = hazard_instance.get('location')
        if not location or location not in self.room_env:
            logging.warning(f"HazardEngine: Location '{location}' not found in room_env for applying effect from hazard {hazard_instance.get('id')}.")
            # Initialize if missing, though it should be set up by initialize_for_level
            if location and self.game_logic and hasattr(self.game_logic, 'game_data') and \
               hasattr(self.game_logic.game_data, 'initial_environmental_conditions'):
                self.room_env[location] = copy.deepcopy(self.game_logic.game_data.initial_environmental_conditions)
            else:
                return # Cannot proceed

        current_room_env = self.room_env[location]
        logging.debug(f"HazardEngine: Applying direct env effects from hazard {hazard_instance.get('id')} state '{hazard_instance.get('state')}' to room '{location}'. Initial room_env: {current_room_env}")

        for effect_key, effect_value_def in env_effects_def.items():
            if effect_key not in current_room_env:
                logging.warning(f"HazardEngine: Unknown environmental effect key '{effect_key}' defined for hazard {hazard_instance.get('type')}. Skipping.")
                continue

            current_val = current_room_env.get(effect_key)

            if isinstance(effect_value_def, bool): # Set directly
                current_room_env[effect_key] = effect_value_def
            elif isinstance(effect_value_def, (int, float)): # Set absolute value
                 current_room_env[effect_key] = effect_value_def
            elif isinstance(effect_value_def, str):
                if effect_value_def.startswith("+") or effect_value_def.startswith("-"): # Incremental
                    try:
                        change = float(effect_value_def)
                        # Ensure current_val is numeric for arithmetic
                        if not isinstance(current_val, (int, float)): current_val = 0.0
                        new_val = current_val + change
                        
                        # Clamping based on effect_key
                        if effect_key == "gas_level": new_val = max(0.0, min(4.0, new_val))
                        elif effect_key == "noise_level": new_val = max(0, min(5, int(new_val))) # Assuming noise is int
                        # Add other clamps as needed
                        current_room_env[effect_key] = new_val
                    except ValueError:
                        logging.warning(f"HazardEngine: Invalid incremental value for env effect {effect_key}: {effect_value_def}")
                else: # Set string value directly (e.g., visibility = "smoky")
                    current_room_env[effect_key] = effect_value_def
            logging.debug(f"HazardEngine: Room '{location}' env effect '{effect_key}' updated to '{current_room_env[effect_key]}'.")
        logging.debug(f"HazardEngine: Final room_env for '{location}' after direct effect: {current_room_env}")


    def update_environmental_states(self):
        """
        Recalculates the environmental state for all rooms based on the current
        active states of all hazards. This is the definitive update for room_env.
        """
        if not self.game_logic or not self.rooms: 
            logging.error("HazardEngine.update_environmental_states: GameLogic or current_level_rooms not available.")
            return

        all_room_names_in_level = list(self.rooms.keys()) # Get all rooms for the current level

        for room_name in all_room_names_in_level:
            # Reset to base conditions for the room before recalculating
            if self.game_logic and hasattr(self.game_logic, 'game_data') and \
               hasattr(self.game_logic.game_data, 'initial_environmental_conditions'):
                self.room_env[room_name] = copy.deepcopy(self.game_logic.game_data.initial_environmental_conditions)
            else: # Should not happen if initialized correctly
                self.room_env[room_name] = {} 
            
            current_room_env_being_built = self.room_env[room_name]

            # Aggregate effects from all hazards active in this room
            for hazard_instance in self.active_hazards.values():
                if hazard_instance.get("location") == room_name:
                    state_data = hazard_instance.get("data", {}).get("states", {}).get(hazard_instance.get("state"))
                    if state_data and "environmental_effect" in state_data:
                        env_effects_def = state_data["environmental_effect"]
                        for effect_key, effect_value_def in env_effects_def.items():
                            if effect_key not in current_room_env_being_built: 
                                logging.warning(f"HazardEngine: Effect key '{effect_key}' from hazard '{hazard_instance.get('type')}' not in base env conditions for room '{room_name}'. Adding it.")
                                # current_room_env_being_built[effect_key] = None # Or some default based on type
                                # Better to ensure initial_environmental_conditions is complete.
                                # For now, we'll only operate on keys already present from initial_environmental_conditions.
                                continue

                            # Logic for applying/aggregating effects:
                            # Booleans: if any hazard sets it true, it's true.
                            if isinstance(current_room_env_being_built[effect_key], bool):
                                if isinstance(effect_value_def, bool) and effect_value_def:
                                    current_room_env_being_built[effect_key] = True
                            
                            # Numeric (like gas_level, noise_level): sum changes or take max?
                            # Current _apply_environmental_effect_from_hazard uses direct set or +/-.
                            # For an aggregate, summing changes or taking max is more common.
                            # Let's refine: gas_level and noise_level should accumulate.
                            elif effect_key in ["gas_level", "noise_level"]:
                                base_val = self.game_logic.game_data.initial_environmental_conditions.get(effect_key, 0)
                                current_val_in_room = current_room_env_being_built.get(effect_key, base_val)
                                
                                change = 0.0
                                if isinstance(effect_value_def, (int, float)): # If it's an absolute value from hazard
                                    # This interpretation is tricky. Does each hazard *set* the level, or *add* to it?
                                    # Let's assume hazard definitions provide an *absolute contribution* or a *delta*.
                                    # If it's a delta (e.g. "+1"), it should be parsed.
                                    # If it's absolute (e.g. "2"), how to aggregate? Max? Sum?
                                    # The _apply_environmental_effect_from_hazard parses "+/-" for deltas.
                                    # For aggregation, let's assume effect_value_def from hazard is its *contribution*.
                                    # So, we sum these contributions relative to the base.
                                    # This means effect_value_def should represent the *change* from normal.
                                    # E.g., gas_leak state: {"gas_level": "+1"} means it adds 1 to base.
                                    # Or, if {"gas_level": 1}, it means it contributes 1.
                                    # Let's assume the latter for aggregation: sum of contributions.
                                    # This means initial_environmental_conditions should be all zeros for accumulables.
                                    
                                    # Re-evaluating: Simpler if hazard state just *sets* a property.
                                    # If multiple hazards set 'is_sparking', it's true.
                                    # If one sets gas_level to 1 and another to 2, what's the room level? Max?
                                    # Let's use the logic from _apply_environmental_effect_from_hazard for individual application.
                                    # The aggregation should take the "strongest" effect.
                                    
                                    # For numeric values like gas_level, let's take the MAX value set by any hazard.
                                    if isinstance(effect_value_def, (int, float)):
                                        current_room_env_being_built[effect_key] = max(current_val_in_room, effect_value_def)
                                    elif isinstance(effect_value_def, str) and (effect_value_def.startswith('+') or effect_value_def.startswith('-')):
                                        try:
                                            delta = float(effect_value_def)
                                            # This is complex for aggregation. Let's assume direct setting for now.
                                            # If we sum deltas, we need to start from base for each hazard.
                                            # Sticking to MAX for simplicity in aggregation of absolute values from hazards.
                                            # If a hazard says "gas_level: 2", the room's gas_level becomes at least 2.
                                        except ValueError: pass


                            # Strings (like visibility): last one wins or specific hierarchy?
                            elif isinstance(current_room_env_being_built[effect_key], str):
                                # Example: if one hazard makes visibility "smoky" and another "dense_smoke",
                                # "dense_smoke" should prevail. Requires an order of severity.
                                severity_order = {"normal":0, "dim":1, "hazy":1, "dark":2, "patchy_smoke":2, "very_dark":3, "dense_smoke":3, "zero":4}
                                current_severity = severity_order.get(current_room_env_being_built[effect_key].lower(), -1)
                                new_effect_severity = severity_order.get(str(effect_value_def).lower(), -1)
                                if new_effect_severity > current_severity:
                                    current_room_env_being_built[effect_key] = str(effect_value_def)
            
            # Clamp accumulated/maxed values after all hazards in the room are processed
            if "gas_level" in current_room_env_being_built: 
                current_room_env_being_built["gas_level"] = max(0.0, min(4.0, current_room_env_being_built["gas_level"]))
            if "noise_level" in current_room_env_being_built: 
                current_room_env_being_built["noise_level"] = max(0, min(5, int(current_room_env_being_built["noise_level"])))
            
            logging.debug(f"HazardEngine: Final aggregated environmental state for room '{room_name}': {current_room_env_being_built}")

        # After updating all rooms based on local hazards, handle inter-room effects like gas spreading
        self._handle_gas_spreading_and_decay()


    def _handle_gas_spreading_and_decay(self):
        """Handles gas diffusion between connected rooms and natural decay of gas in rooms."""
        if not self.game_logic or not hasattr(self.game_logic, 'game_data'): return

        gas_deltas = collections.defaultdict(float) # Stores net change for each room's gas level

        # Calculate Spread
        for room_name, env_state in self.room_env.items():
            current_gas_level = env_state.get('gas_level', 0.0)
            if current_gas_level <= 0: continue

            room_data = self.rooms.get(room_name) # self.rooms is GameLogic's current_level_rooms
            if not room_data or not isinstance(room_data.get("exits"), dict): continue

            # Spread to adjacent rooms
            for _, adjacent_room_name in room_data["exits"].items():
                if adjacent_room_name in self.room_env: # Ensure adjacent room is part of current level
                    adjacent_env_state = self.room_env[adjacent_room_name]
                    adjacent_gas_level = adjacent_env_state.get('gas_level', 0.0)
                    
                    # Condition for spreading: significant difference and random chance
                    if current_gas_level > adjacent_gas_level + self.game_logic.game_data.GAS_SPREAD_DIFFERENCE_THRESHOLD (0.5): # e.g., spread if diff > 0.5
                        if random.random() < self.game_logic.game_data.GAS_SPREAD_CHANCE_PER_EXIT_PER_TURN:
                            spread_amount = self.game_logic.game_data.GAS_SPREAD_AMOUNT_PER_TICK 
                            
                            # Ensure spread doesn't make source negative or target exceed source (simple model)
                            actual_spread = min(spread_amount, (current_gas_level - adjacent_gas_level) / 2, current_gas_level)
                            
                            gas_deltas[adjacent_room_name] += actual_spread
                            gas_deltas[room_name] -= actual_spread
                            logging.debug(f"HazardEngine: Gas spread: {actual_spread:.2f} from '{room_name}' ({current_gas_level:.2f}) to '{adjacent_room_name}' ({adjacent_gas_level:.2f}).")
        
        # Calculate Decay
        for room_name, env_state in self.room_env.items():
            current_gas_level = env_state.get('gas_level', 0.0)
            if current_gas_level > 0:
                if random.random() < self.game_logic.game_data.GAS_DECAY_CHANCE_PER_TURN:
                    decay_amount = self.game_logic.game_data.GAS_DECAY_RATE_PER_TURN
                    gas_deltas[room_name] -= decay_amount # Decay reduces gas
                    logging.debug(f"HazardEngine: Gas decay in '{room_name}': -{decay_amount:.2f}. Current before delta: {current_gas_level:.2f}")

        # Apply all calculated deltas
        for room_name, delta in gas_deltas.items():
            if room_name in self.room_env and delta != 0:
                new_level = self.room_env[room_name].get('gas_level', 0.0) + delta
                self.room_env[room_name]['gas_level'] = max(0.0, min(4.0, new_level)) # Clamp
                logging.info(f"HazardEngine: Room '{room_name}' gas level changed by {delta:.2f} to {self.room_env[room_name]['gas_level']:.2f}.")


    def _check_global_environmental_reactions(self, messages_list):
        """
        Checks for room-wide environmental reactions based on the aggregated
        environmental state (e.g., gas explosion if gas level is high and there's a spark/fire).
        This is called at the end of hazard_turn_update.
        """
        if self.game_logic.is_game_over: return

        for room_name, env_data in self.room_env.items():
            if self.game_logic.is_game_over: break 

            # Check for Gas Explosion
            gas_level = env_data.get('gas_level', 0.0)
            is_sparking_in_room = env_data.get('is_sparking', False)
            is_on_fire_in_room = env_data.get('is_on_fire', False) # Room itself is on fire

            if gas_level >= self.game_logic.game_data.GAS_LEVEL_EXPLOSION_THRESHOLD and \
               (is_sparking_in_room or is_on_fire_in_room):
                
                ignition_source_str = "sparks" if is_sparking_in_room else "flames"
                messages_list.append(color_text(f"The high concentration of gas in the {room_name} ignites from {ignition_source_str}!", "error"))
                messages_list.append(color_text("KA-BOOM! A massive explosion rips through the area!", "error"))
                logging.info(f"HazardEngine: Gas explosion in '{room_name}' due to gas level {gas_level:.2f} and ignition source '{ignition_source_str}'.")
                
                # Player in room?
                if self.player.get('location') == room_name:
                    self.game_logic.is_game_over = True
                    self.game_logic.game_won = False
                    self.player['last_hazard_type'] = "Gas Explosion"
                    self.player['last_hazard_object_name'] = room_name 
                    messages_list.append(color_text("You are caught in the heart of the explosion and instantly obliterated.", "error"))

                # Update room environment post-explosion
                env_data['is_on_fire'] = True 
                env_data['gas_level'] = 0.0 
                env_data['is_sparking'] = False # Sparks consumed by explosion
                env_data['visibility'] = "dense_smoke" 
                env_data['noise_level'] = 5 

                # Deactivate specific hazards in this room that contributed or would be consumed
                for hz_id, hz_instance in list(self.active_hazards.items()):
                    if hz_instance['location'] == room_name:
                        if hz_instance['type'] == self.game_logic.game_data.HAZARD_TYPE_GAS_LEAK:
                            # Gas leak source might be destroyed or just stop leaking
                            self._set_hazard_state(hz_id, "sealed_leak", messages_list) # Or a new "exploded_pipe" state
                        elif hz_instance['type'] == self.game_logic.game_data.HAZARD_TYPE_FAULTY_WIRING and \
                             hz_instance['state'] in ['sparking', 'arcing']:
                            self._set_hazard_state(hz_id, "shorted_out", messages_list)
                        elif hz_instance['type'] == self.game_logic.game_data.HAZARD_TYPE_SPREADING_FIRE: # If room fire was already there
                            # It might intensify or just continue. For now, no change to its state,
                            # as the room env 'is_on_fire' is now true.
                            pass
                        # Consider other hazards that might be destroyed by an explosion

                if self.game_logic.is_game_over and self.player.get('location') == room_name:
                    return # Player died in this room's explosion, stop checking other rooms.
            
    def check_action_hazard(self, verb, target_name, current_room_name, item_used=None):
        agg_factor = self._calculate_aggression_factor()
        action_messages = []
        action_caused_death = False
        interaction_occurred_directly = False # Flag for direct interaction
        interaction_occurred_indirectly = False #

        # --- Part 1: Check for DIRECT interactions (player's target IS the hazard or its support) ---
        # This part is largely your existing logic.
        for hazard_id, hazard in list(self.active_hazards.items()):
            if self.game_logic.is_game_over: break
            if hazard['location'] != current_room_name: continue

            is_direct_target_of_action = (
                target_name.lower() == hazard.get('object_name','').lower() or
                target_name.lower() == hazard.get('support_object','').lower()
            )
            is_type_target = target_name.lower() == hazard.get('name','').lower() # Less common for direct

            if is_direct_target_of_action or is_type_target:
                hazard_def_player_interaction_rules = hazard['data'].get('player_interaction', {})
                action_rule = hazard_def_player_interaction_rules.get(verb.lower())

                if action_rule and isinstance(action_rule, dict):
                    # ... (existing logic for state checks, item checks, chance, effects) ...
                    # If an interaction happens:
                    #   interaction_occurred_directly = True
                    #   action_messages.append(...)
                    #   self._set_hazard_state(...)
                    #   if self.game_logic.is_game_over: action_caused_death = True; break
                    # (Simplified representation of your existing direct interaction logic)
                    pass # Placeholder for brevity

            if action_caused_death: break
        # --- End of Part 1 ---

        # --- Part 2: Check for INDIRECT interactions (action on target_name affects OTHER hazards) ---
        if not action_caused_death: # Only proceed if direct interaction wasn't fatal
            for hazard_id, hazard_b in list(self.active_hazards.items()): # Hazard B (the one potentially affected)
                if self.game_logic.is_game_over: break
                if hazard_b['location'] != current_room_name: continue

                indirect_trigger_rules = hazard_b['data'].get("triggered_by_room_action", [])
                for rule in indirect_trigger_rules:
                    if rule.get("action_verb", "").lower() == verb.lower():
                        # Check if the player's target_name matches rule.on_target_type or rule.on_target_name
                        target_matches = False
                        player_target_object_type = None # You'd need a way to get the "type" of target_name
                        
                        # Example: Get type of furniture/object player is targeting
                        # room_data = self.game_logic.get_room_data(current_room_name)
                        # for furn in room_data.get("furniture", []):
                        #     if furn.get("name", "").lower() == target_name.lower():
                        #         player_target_object_type = furn.get("type", "furniture") # Assuming furniture has a 'type'
                        #         break
                        # if not player_target_object_type:
                        #     # Check room objects, etc.
                        #     pass


                        if rule.get("on_target_name", "").lower() == target_name.lower():
                            target_matches = True
                        # elif rule.get("on_target_type") and player_target_object_type == rule.get("on_target_type"):
                        #     target_matches = True 
                        # This part needs a robust way to determine the "type" of `target_name` if using `on_target_type`.
                        # For simplicity, let's assume `target_name` is specific enough or `on_target_name` is used.
                        # A simpler check for now if `on_target_type` is used:
                        elif rule.get("on_target_type") and rule.get("on_target_type").lower() in target_name.lower(): # Basic substring match for type
                            target_matches = True


                        item_matches = True # Assume true if no item requirement
                        if rule.get("item_used"):
                            item_matches = item_used and item_used.lower() == rule.get("item_used").lower()
                        
                        state_matches = True # Assume true if no state requirement
                        if rule.get("if_hazard_in_state"):
                            required_states = rule["if_hazard_in_state"]
                            state_matches = hazard_b["state"] in (required_states if isinstance(required_states, list) else [required_states])

                        if target_matches and item_matches and state_matches:
                            base_indirect_chance = rule.get("chance_to_trigger", 1.0)
                            # aggression can influence this too
                            actual_indirect_chance = min(1.0, max(0.0, base_indirect_chance + (agg_factor * rule.get("aggression_modifier", 0.0))))

                            if random.random() < actual_indirect_chance:
                                interaction_occurred_indirectly = True # Use a different flag or add to a list of interactions
                                effect_on_hazard_b = rule.get("effect_on_self", {})
                                
                                msg = effect_on_hazard_b.get("message_to_player", f"Your action on {target_name} affects the nearby {hazard_b.get('object_name', 'hazard')}.")
                                action_messages.append(color_text(msg.format(
                                    player_target=target_name.capitalize(), # What player acted on
                                    hazard_b_name=hazard_b.get('object_name', hazard_b['type']) # The affected hazard
                                ), "warning"))

                                new_state_for_hazard_b = effect_on_hazard_b.get("target_state")
                                if new_state_for_hazard_b is not None:
                                    self._set_hazard_state(hazard_id, new_state_for_hazard_b, action_messages)
                                    if self.game_logic.is_game_over: action_caused_death = True; break
                                
                                # ... handle other effects from 'effect_on_self' like direct damage if applicable ...

                    if action_caused_death: break # from inner loop over rules
                if action_caused_death: break # from outer loop over hazards (hazard_b)
        # --- End of Part 2 ---

        final_message_str = "\n".join(filter(None, action_messages)).strip()
        return {
            "message": final_message_str if final_message_str or interaction_occurred_directly or interaction_occurred_indirectly else None,
            "death": action_caused_death
        }


    def get_env_state(self, room_name):
        """
        Gets the current aggregated environmental state of a specified room.

        Args:
            room_name (str): The name of the room.

        Returns:
            dict: A copy of the room's environmental state dictionary. 
                  Returns a copy of initial_environmental_conditions if room not found.
        """
        if not self.game_logic or not hasattr(self.game_logic, 'game_data') or \
           not hasattr(self.game_logic.game_data, 'initial_environmental_conditions'):
            logging.error("HazardEngine.get_env_state: Missing game_data.initial_environmental_conditions.")
            return {} # Should not happen with proper setup

        return copy.deepcopy(self.room_env.get(room_name, 
                            copy.deepcopy(self.game_logic.game_data.initial_environmental_conditions)))

    def _move_and_interact(self, hazard_id, hazard_instance, state_data, messages_list):
        """
        Handles movement and subsequent collision interactions for mobile hazards
        like the robot vacuum.
        """
        if self.game_logic.is_game_over:
            return

        original_room = hazard_instance['location']
        can_move_rooms = hazard_instance['data'].get('can_move_between_rooms', False)
        movement_logic = hazard_instance['data'].get('movement_logic', 'random')
        agg_factor = hazard_instance.get("aggression", self._calculate_aggression_factor())

        next_room_candidate = original_room

        # 1. Determine Target Room for Movement
        if can_move_rooms:
            target_room_for_move = None
            primary_target_sought = False

            if movement_logic == "seek_target_type_then_player" or movement_logic == "seek_target_type":
                seekable_hazard_types = hazard_instance['data'].get('seekable_target_types', [])
                closest_target_hazard_room = None
                shortest_path_len = float('inf')

                for other_h_id, other_h in self.active_hazards.items():
                    if other_h['type'] in seekable_hazard_types:
                        # Check if this specific hazard state defines specific target states
                        # For now, just finding the type is enough to head towards it.
                        path_to_other_h = self._get_shortest_path(original_room, other_h['location'])
                        if path_to_other_h and len(path_to_other_h) < shortest_path_len:
                            shortest_path_len = len(path_to_other_h)
                            closest_target_hazard_room = other_h['location']
                
                if closest_target_hazard_room:
                    target_room_for_move = closest_target_hazard_room
                    primary_target_sought = True
                    logging.debug(f"Hazard {hazard_id} seeking primary target type, aiming for room: {target_room_for_move}")
                    # Check if hazard should transition state upon finding/reaching its primary target
                    if original_room == target_room_for_move and state_data.get('on_target_found_next_state'):
                        # If already in target room and seeking target type, transition (e.g., robot vac near gas)
                        self._set_hazard_state(hazard_id, state_data['on_target_found_next_state'], messages_list)
                        return # State changed, further actions handled by new state
                    elif state_data.get('proximity_to_target_next_state') and original_room == target_room_for_move:
                        # This specific condition is for 'approaching_gas_source' state
                        self._set_hazard_state(hazard_id, state_data['proximity_to_target_next_state'], messages_list)
                        return


            if not primary_target_sought and (movement_logic == "seek_target_type_then_player" or movement_logic == "seek_player_bfs"):
                player_seek_chance_base = state_data.get('player_seek_chance', hazard_instance['data'].get('player_seek_chance_if_no_primary_target', 0.1))
                agg_influence_seek = hazard_instance['data'].get('aggression_influence', {}).get('player_seek_chance_boost', 0.0) * agg_factor
                if random.random() < (player_seek_chance_base + agg_influence_seek):
                    target_room_for_move = self.player['location']
                    logging.debug(f"Hazard {hazard_id} seeking player, aiming for room: {target_room_for_move}")


            if target_room_for_move and target_room_for_move != original_room:
                path = self._get_shortest_path(original_room, target_room_for_move)
                if path and len(path) > 1:
                    next_room_candidate = path[1]
            elif state_data.get('can_move_randomly_if_not_seeking', False): # Random movement if no target and allowed
                room_data_current = self.rooms.get(original_room)
                if room_data_current and room_data_current.get("exits"):
                    possible_next_rooms = [
                        r_name for r_name in room_data_current["exits"].values()
                        if r_name in self.rooms and not self.rooms[r_name].get('locked')
                    ]
                    if possible_next_rooms:
                        next_room_candidate = random.choice(possible_next_rooms)
                        logging.debug(f"Hazard {hazard_id} moving randomly to: {next_room_candidate}")


        # 2. Execute Movement
        if next_room_candidate != original_room:
            hazard_instance['location'] = next_room_candidate
            # Add movement message (can be generic or from hazard def)
            move_desc = hazard_instance['data'].get('move_description', "The {object_name} moves.")
            messages_list.append(color_text(move_desc.format(object_name=hazard_instance.get('object_name', 'hazard')), "info"))
            logging.info(f"Hazard {hazard_id} ('{hazard_instance['type']}') moved from {original_room} to {next_room_candidate}.")

        # 3. Check for Collisions in the (potentially new) room
        current_room_of_hazard = hazard_instance['location']
        
        # 3a. Collision with Player (if player is in the same room)
        if self.player['location'] == current_room_of_hazard:
            player_collision_rules = hazard_instance['data'].get('collision_effects', {}).get('player', {})
            if player_collision_rules and random.random() < (player_collision_rules.get('chance', 0.0) + (agg_factor * 0.05)): # Slight agg boost
                effect_type = player_collision_rules.get('effect')
                collision_msg_template = player_collision_rules.get("message", "The {object_name} collides with you!")
                messages_list.append(color_text(collision_msg_template.format(object_name=hazard_instance.get('object_name')), "warning"))

                if effect_type == 'trip':
                    status_to_apply = player_collision_rules.get("status_effect")
                    if status_to_apply and isinstance(status_to_apply, dict):
                        self.game_logic.apply_status_effect(status_to_apply.get("name"), status_to_apply.get("duration"), messages_list)
                elif effect_type == 'direct_damage':
                    damage = player_collision_rules.get("hp_damage", 1)
                    self.game_logic.apply_damage_to_player(damage, f"collision with {hazard_instance.get('object_name')}")
                elif effect_type == 'fatal_collision':
                    self.game_logic.is_game_over = True; self.game_logic.game_won = False
                    self.player['last_hazard_type'] = hazard_instance['type']
                    self.player['last_hazard_object_name'] = hazard_instance.get('object_name')
                    messages_list.append(color_text(player_collision_rules.get("fatal_message", "The collision is fatal!"), "error"))
                    return # Game over

        # 3b. Collision with other specified targets (e.g., other hazards)
        defined_collision_targets = hazard_instance['data'].get('collision_targets', [])
        if "player" in defined_collision_targets: # Player already handled
            defined_collision_targets.remove("player")

        for other_h_id, other_h_instance in list(self.active_hazards.items()):
            if self.game_logic.is_game_over: return
            if other_h_id == hazard_id or other_h_instance['location'] != current_room_of_hazard:
                continue

            # Check if other_h_instance.type is in defined_collision_targets for the moving hazard
            target_type_for_collision_rules = None
            if other_h_instance['type'] in defined_collision_targets: # e.g., "loose_object"
                target_type_for_collision_rules = other_h_instance['type']
            # Could add more complex matching here if needed (e.g. based on object names)

            if target_type_for_collision_rules:
                collision_rule_for_type = hazard_instance['data'].get('collision_effects', {}).get(target_type_for_collision_rules)
                if collision_rule_for_type and random.random() < (collision_rule_for_type.get('chance', 0.0) + (agg_factor * 0.05)):
                    collision_effect = collision_rule_for_type.get('effect')
                    effect_msg_template = collision_rule_for_type.get("message", "The {object_name} bumps into the {target_object_name}!")
                    messages_list.append(color_text(effect_msg_template.format(
                        object_name=hazard_instance.get('object_name'),
                        target_object_name=other_h_instance.get('object_name')
                    ), "info"))
                    logging.info(f"Hazard {hazard_id} collided with {other_h_id} ({target_type_for_collision_rules}). Effect: {collision_effect}")

                    if collision_effect == "knock_over": # Example effect
                        target_hazard_new_state = collision_rule_for_type.get("target_hazard_state")
                        if target_hazard_new_state:
                            self._set_hazard_state(other_h_id, target_hazard_new_state, messages_list)
                            if self.game_logic.is_game_over: return
                    # Add more collision effects here (e.g., 'damage_target_hazard', 'destroy_target_hazard')

    def get_room_hazards_descriptions(self, room_name):
        descriptions = []
        for hazard_id, hazard_instance in self.active_hazards.items():
            if hazard_instance.get('location') == room_name:
                state_data = hazard_instance.get('data', {}).get('states', {}).get(hazard_instance.get('state'))
                if state_data and state_data.get('description'):
                    desc_template = state_data['description']
                    try:
                        formatted_desc = desc_template.format(
                            object_name=color_text(hazard_instance.get('object_name', hazard_instance['name']), 'hazard'),
                            support_object=color_text(hazard_instance.get('support_object', 'its surroundings'), 'room'),
                            # Add fallback for {object} and any other keys you use in templates
                            object=color_text(hazard_instance.get('object_name', hazard_instance['name']), 'hazard'),
                            name=color_text(hazard_instance.get('name', hazard_instance['type']), 'hazard'),
                        )
                        if formatted_desc.strip():
                            descriptions.append(formatted_desc)
                    except KeyError as e:
                        logging.error(f"HazardEngine: KeyError in hazard description format for {hazard_instance['type']}/{hazard_instance['state']}: {e}. Template: '{desc_template}'")
                        descriptions.append(color_text(f"A {hazard_instance.get('name', 'mysterious hazard')} ({hazard_instance.get('object_name','entity')}) is present and active.", "warning"))
        return descriptions
    
    def get_room_hazards(self, room_name): # Alias for backward compatibility if used elsewhere
        """Alias for get_room_hazards_descriptions."""
        return self.get_room_hazards_descriptions(room_name)

    def _add_to_journal(self, category, entry): # Proxy method
        """
        Adds an entry to the player's journal via the GameLogic instance.
        (This is a proxy method; actual journal logic is in GameLogic or AchievementsSystem)
        """
        if self.game_logic and hasattr(self.game_logic, '_add_to_journal'):
            return self.game_logic._add_to_journal(category, entry)
        logging.warning("HazardEngine: _add_to_journal called, but game_logic or its _add_to_journal method is unavailable.")
        return False
        
    # --- Persistence Methods ---

    def save_state(self):
        """
        Collects the current state of the HazardEngine for serialization.

        Returns:
            dict: A dictionary containing the serializable state of the HazardEngine.
        """
        # Ensure all data within active_hazards and room_env is JSON serializable.
        # Deepcopy to avoid modifying live state if any transformations are needed here (usually not).
        # Sets within hazard instances (if any) would need conversion to lists here or before.
        # Currently, hazard instances seem to use basic types, lists, and dicts.
        return {
            "active_hazards": copy.deepcopy(self.active_hazards),
            "room_env": copy.deepcopy(self.room_env),
            "next_hazard_id": self.next_hazard_id
            # processed_hazards_this_turn is transient, no need to save.
        }

    def apply_temporary_room_effect(self, room_name, effect_key, temp_value, duration_turns, effect_message=None):
        """
        Applies a temporary change to a room's environmental state.

        Args:
            room_name (str): The name of the room.
            effect_key (str): The key in room_env to change (e.g., "visibility").
            temp_value (any): The temporary value for the effect_key.
            duration_turns (int): How many turns the effect lasts.
            effect_message (str, optional): A message to show the player.
        """
        if room_name not in self.room_env:
            logging.warning(f"HazardEngine: Cannot apply temporary effect, room '{room_name}' not in room_env.")
            return [] # Return empty list for messages

        messages_to_return = []
        if effect_message:
            messages_to_return.append(effect_message)

        # Check if a similar temporary effect is already active for this key and room
        # If so, perhaps refresh its duration or let the new one override.
        # For simplicity, let's allow overriding/stacking (last one applied is visible, but all tick down).
        # A more robust system might only allow one temp effect per key or specific override rules.

        original_value = self.room_env[room_name].get(effect_key)

        # Store the original value before applying the temporary one *only if no other temp effect for this key is active*
        # This is tricky if effects stack. For now, let's assume a simple model:
        # the first temporary effect stores the true original, subsequent ones might store an already temporary value.
        # A better way: only one temporary effect per effect_key per room.
        
        # Remove any existing temp effect for the same room and key to avoid conflicts with original_value
        existing_effect_index = -1
        for i, effect in enumerate(self.temporary_room_effects):
            if effect['room'] == room_name and effect['key'] == effect_key:
                original_value = effect['original_value'] # Preserve the true original if we're replacing
                existing_effect_index = i
                break
        if existing_effect_index != -1:
            logging.info(f"HazardEngine: Replacing existing temporary '{effect_key}' effect in '{room_name}'.")
            self.temporary_room_effects.pop(existing_effect_index)

        self.temporary_room_effects.append({
            'room': room_name,
            'key': effect_key,
            'original_value': original_value, # Store what it was before this temp effect
            'temp_value': temp_value,
            'turns_left': duration_turns
        })

        # Apply the temporary effect immediately
        self.room_env[room_name][effect_key] = temp_value
        logging.info(f"HazardEngine: Applied temporary effect in '{room_name}': {effect_key} set to '{temp_value}' for {duration_turns} turns. Original was '{original_value}'.")
        
        # Update global environmental states to reflect this change immediately if needed,
        # though hazard_turn_update will also call it.
        # For an immediate visual change (like visibility), this might be good.
        # self.update_environmental_states() # This might be too broad if called frequently.
        # Consider if GameLogic needs to append a message about the effect.
        return messages_to_return

    def load_state(self, state_dict):
        """
        Restores the HazardEngine's state from a previously saved dictionary.
        Assumes that initialize_for_level has already been called for the loaded level
        to set up base room_env. This method then overwrites with saved specifics.

        Args:
            state_dict (dict): The dictionary containing the saved state.
        """
        if not state_dict:
            logging.warning("HazardEngine: load_state called with empty or None state_dict.")
            return

        self.active_hazards = copy.deepcopy(state_dict.get("active_hazards", {}))
        
        # For room_env, merge loaded data over the freshly initialized room_env for the level.
        # initialize_for_level should have set up self.room_env with all rooms for the current level.
        loaded_room_env_data = copy.deepcopy(state_dict.get("room_env", {}))
        for room_name, env_data in loaded_room_env_data.items():
            if room_name in self.room_env: # Only update rooms that exist in the current level's setup
                self.room_env[room_name].update(env_data) # Update existing entries
            else: # If save file has env data for a room not in current level's base setup (should be rare)
                self.room_env[room_name] = env_data # Add it

        self.next_hazard_id = state_dict.get("next_hazard_id", self.next_hazard_id) # Use loaded or current if missing
        
        # Ensure all loaded hazard instances have their 'data' field properly linked or copied
        # (deepcopy in save_state should handle this, but a check could be added if issues arise)
        # for hz_id, hz_instance in self.active_hazards.items():
        #    if 'data' not in hz_instance and hz_instance.get('type') in self.hazards_master_data:
        #        hz_instance['data'] = copy.deepcopy(self.hazards_master_data[hz_instance['type']])

        logging.info(f"HazardEngine state loaded. Active hazards: {len(self.active_hazards)}. Next ID: {self.next_hazard_id}")

