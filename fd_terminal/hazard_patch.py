# hazard_patch.py
import logging
from . import game_data # Assuming game_data.py is in the same package structure

# Define new hazards to be added or to update existing ones
# If a hazard_key in NEW_HAZARDS already exists in game_data.hazards,
# current logic will skip it. To update, you'd modify the logic in apply_hazard_patches.
NEW_HAZARDS = {
    "electrical_fire": {
        "name": "Electrical Fire",
        "initial_state": "smoldering",
        "placement_object": ["damaged outlet", "frayed appliance cord", "overloaded power strip"], # General types of objects it can be on
        "object_name_options": ["smoldering wires", "sparking appliance", "burning power strip"], # Specific names for instances
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.1,
                "target_state": "flames_erupt", # Target state for this hazard
                "message": "As you get closer, the {object_name} suddenly bursts into aggressive flames!"
            },
            "use": [ # Using a list to allow multiple 'use' rules
                {
                    "item_used_type": "water_container", # Player uses an item of this type
                    "chance_to_trigger": 0.9,
                    "target_state": "explosion",
                    "message": "You throw water on the {object_name}! It shorts violently and explodes!"
                },
                {
                    "item_used_type": "fire_extinguisher", # Player uses an item of this type
                    "chance_to_trigger": 0.8,
                    "target_state": "extinguished",
                    "message": "You use a fire extinguisher on the {object_name}, and the flames subside."
                }
            ]
        },
        "states": {
            "smoldering": {
                "description": "Acrid smoke billows from a {object_name} near the {support_object}. It smells like burning plastic.",
                "environmental_effect": {"visibility": "patchy_smoke", "noise_level": "+1"}, # Using '+' to indicate relative change potential
                "chance_to_progress": 0.3,
                "next_state": "minor_flames"
            },
            "minor_flames": {
                "description": "Small, hungry flames are now licking at the {object_name} on the {support_object}.",
                "environmental_effect": {"is_on_fire_object": True, "visibility": "patchy_smoke", "noise_level": "+1"},
                "chance_to_progress": 0.4,
                "next_state": "flames_erupt",
                "contact_status_effect": {"name": "burned", "duration": 1, "hp_damage": 1} # Direct contact
            },
            "flames_erupt": {
                "description": "The {object_name} is now fully engulfed in roaring flames, spreading rapidly!",
                "environmental_effect": {"is_on_fire": True, "visibility": "dense_smoke", "noise_level": "+2"}, # Sets room env
                "status_effect_on_room_entry": {"name": "burned", "duration": 2, "hp_damage": 2}, # If player enters room
                "hp_damage_per_turn_in_room": 2, # Damage per turn if player stays
                "sets_room_on_fire": True, # Flag for HazardEngine to potentially start a "spreading_fire" hazard in the room
                "death_message": "The fire consumes you before you can escape the {object_name}!", # Generic death message
                "instant_death_if_too_close": True # More specific condition for HazardEngine to evaluate
            },
            "explosion": {
                "description": "The {object_name} explodes violently, sending shrapnel and fire everywhere!",
                "instant_death_in_room": True, # If player is in the room during explosion state change
                "death_message": "You're caught in the fiery explosion from the {object_name}!",
                "environmental_effect": {"is_on_fire": True, "visibility": "dense_smoke", "noise_level": "+5"},
                "sets_room_on_fire": True
            },
            "extinguished": {
                "description": "The charred remains of the {object_name} smolder near the {support_object}. The immediate danger seems over.",
                "environmental_effect": {"is_on_fire_object": False, "visibility": "patchy_smoke"}
            }
        }
    },
    "spreading_fire": { # A hazard that represents the room itself being on fire
        "name": "Spreading Fire", # This is a room-level hazard, not tied to one object
        "initial_state": "burning_low",
        "placement_object": ["room_itself"], # Special placement type
        "object_name_options": ["room fire", "engulfing flames", "spreading inferno"], # Name for this instance
        "player_interaction": {
            "use": [
                {
                     "item_used_type": "fire_extinguisher",
                     "chance_to_trigger": 0.5, # Harder to put out a room fire
                     "target_state": "burning_low", # Knocks it back, doesn't fully extinguish easily
                     "message": "You fight back the flames with the extinguisher, reducing their intensity somewhat."
                }
            ]
        },
        "states": {
            "burning_low": {
                "description": "Parts of the room are on fire. The heat is intense, and smoke stings your eyes.",
                "environmental_effect": {"is_on_fire": True, "visibility": "patchy_smoke", "noise_level": "+1", "temperature_room": "+10"}, # Example temperature
                "status_effect_on_room_entry": {"name": "minor_burns", "duration": 2, "hp_damage": 1}, # Custom status effect
                "hp_damage_per_turn_in_room": 1,
                "chance_to_progress": 0.25, "next_state": "burning_high"
            },
            "burning_high": {
                "description": "The room is an inferno! Flames crawl up the walls and smoke chokes the air.",
                "environmental_effect": {"is_on_fire": True, "visibility": "dense_smoke", "noise_level": "+2", "temperature_room": "+20"},
                "status_effect_on_room_entry": {"name": "severe_burns", "duration": 3, "hp_damage": 2},
                "hp_damage_per_turn_in_room": 3,
                "chance_to_progress": 0.15, "next_state": "collapsing_structure", # Fire weakens structure
                "instant_death_if_trapped_too_long": True, 
                "turns_to_become_fatal": 2, # After 2 turns in this state, it's fatal
                "death_message": "The inferno becomes unbearable. You collapse, overcome by heat and smoke."
            },
            "collapsing_structure": {
                "description": "The fire has weakened the structure! The ceiling groans and parts begin to fall!",
                "environmental_effect": {"is_on_fire": True, "visibility": "dense_smoke", "noise_level": "+3", "temperature_room": "+15"},
                "autonomous_action": "check_hit_player", # HazardEngine calls _check_hit_player
                "hit_damage": 5, 
                "is_fatal_if_direct_hit": True, # If debris hits player
                "death_message": "Burning debris crashes down, crushing you.", # For direct hit
                "hp_damage_per_turn_in_room": 2 # Still taking fire damage from ambient heat
            },
            "burnt_out": { # Added a final state for when the fire dies down
                "description": "The room is a charred, smoldering ruin. The fire has consumed everything combustible.",
                "environmental_effect": {"is_on_fire": False, "visibility": "hazy_smoke", "temperature_room": "+5"}
            }
        }
    }
}

# Define new items to be added or to update existing ones
NEW_ITEMS = {
    "fire extinguisher": {
        "description": "A standard red fire extinguisher. Could be very useful against flames.",
        "takeable": True,
        "weight": 3, 
        "type": "fire_extinguisher", # Specific type for interaction rules
        "is_metallic": True, # For MRI, etc.
        "use_on": ["electrical_fire", "spreading_fire", "minor_flames_on_object"], # Hazard types or specific object states
        "examine_details": "It's fully charged. Instructions: Pull pin, Aim at base of fire, Squeeze lever, Sweep side to side."
        # The actual effect of using it is defined in the HAZARD's player_interaction rules.
    },
    "rubber gloves": { # Example item for faulty_wiring_interactive
        "description": "Thick, insulated rubber gloves. Might offer protection from electricity.",
        "takeable": True,
        "weight": 0.5,
        "type": "protective_gear", # General type
        "use_on": ["faulty_wiring_interactive"], # Can be used on this specific hazard
        "examine_details": "Rated for up to 1000 volts. Or so the faded label claims."
    },
    "cup of water": { # Example for dousing electrical fire (bad idea)
        "description": "A plastic Individual cup sloshing with water.",
        "takeable": True,
        "weight": 1,
        "is_liquid": True, # Indicates it's a liquid container
        "is_spillable": True, # Can spill if dropped
        "is_conductive": True, # Water is conductive
        "type": "water_container", # Specific type
        "use_on": ["electrical_fire", "thirsty_plant"], # Example targets
        "examine_details": "It's just plain water."
    }
}

def apply_hazard_patches():
    """Applies the new hazard definitions to the game_data.hazards dictionary."""
    if hasattr(game_data, 'hazards') and isinstance(game_data.hazards, dict):
        for hazard_key, hazard_def in NEW_HAZARDS.items():
            if hazard_key not in game_data.hazards:
                game_data.hazards[hazard_key] = hazard_def
                logging.info(f"Patched game_data with new hazard: {hazard_key}")
            else:
                # To update/override existing hazards:
                # game_data.hazards[hazard_key].update(hazard_def)
                # logging.info(f"Updated existing hazard definition: {hazard_key}")
                logging.info(f"Hazard '{hazard_key}' already exists in game_data.hazards. Patch skipped to avoid override.")
    else:
        logging.error("game_data.hazards dictionary not found or not a dict. Cannot apply hazard patches.")

def apply_item_patches():
    """Applies the new item definitions to the game_data.items dictionary."""
    if hasattr(game_data, 'items') and isinstance(game_data.items, dict):
        for item_key, item_def in NEW_ITEMS.items():
            if item_key not in game_data.items:
                game_data.items[item_key] = item_def
                logging.info(f"Patched game_data with new item: {item_key}")
            else:
                # To update/override existing items:
                # game_data.items[item_key].update(item_def)
                # logging.info(f"Updated existing item definition: {item_key}")
                logging.info(f"Item '{item_key}' already exists in game_data.items. Patch skipped to avoid override.")
    else:
        logging.error("game_data.items dictionary not found or not a dict. Cannot apply item patches.")

def apply_all_patches(app_instance=None): # app_instance is not used here but kept for consistency
    """Main function to call to apply all patches (hazards, items, etc.)."""
    logging.info("Applying data patches from hazard_patch.py...")
    apply_hazard_patches()
    apply_item_patches()
    # Add calls to other patching functions if you create more (e.g., for rooms, characters)
    logging.info("Data patch application complete.")

# This ensures that if this script is run directly (e.g., for testing the patch mechanism),
# it can also attempt to patch. However, it's primarily meant to be imported and called by main.py.
if __name__ == "__main__":
    # Basic logging setup for standalone testing
    if not logging.getLogger().hasHandlers(): # Avoid reconfiguring if already set by an importer
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # For standalone testing, game_data might need to be a mock or a simple dict here.
    # If game_data is complex or relies on other modules not set up, this direct run might fail.
    # This assumes game_data can be imported and has 'hazards' and 'items' attributes.
    try:
        apply_all_patches()
        # Example test prints (won't work if game_data isn't properly mocked/available standalone)
        # print("Electrical Fire definition after patch:", game_data.hazards.get("electrical_fire"))
        # print("Fire Extinguisher definition after patch:", game_data.items.get("fire_extinguisher"))
    except ImportError:
        logging.error("Could not import game_data for standalone patch testing. Ensure it's accessible.")
    except AttributeError:
        logging.error("game_data module is missing 'hazards' or 'items' attributes for standalone patch testing.")

