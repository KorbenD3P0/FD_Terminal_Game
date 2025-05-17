import json
import logging
import os
import datetime # Added to use datetime.datetime.now()
from kivy.app import App # Moved here for direct use
# from kivy.clock import Clock # This import appears unused

class AchievementsSystem:
    """Manages tracking and displaying of player achievements."""
    
    def __init__(self, notify_callback=None):
        """Initialize the achievements system."""
        self.notify_callback = notify_callback
        self.achievements = {
            "first_evidence": {"name": "First Clue", "unlocked": False, "icon": "🔍", "description": "Find your first piece of crucial evidence."},
            "collector": {"name": "Collector", "unlocked": False, "icon": "📚", "description": "Collect 5 pieces of evidence."},
            "survivor": {"name": "Survivor", "unlocked": False, "icon": "🏆", "description": "Successfully survive a harrowing ordeal."},
            "survived_the_house": {"name": "House Escaped", "unlocked": False, "icon": "🏠", "description": "Escape the Bludworth House."},
            "survived_the_hospital": {"name": "Hospital Survived", "unlocked": False, "icon": "🏥", "description": "Make it through Lakeview Hospital."},
            "speedrun": {"name": "Speedrun", "unlocked": False, "icon": "⏱️", "description": "Complete a scenario with exceptional speed."},
            "quick_reflexes": {"name": "Quick Reflexes", "unlocked": False, "icon": "⚡", "description": "Successfully react to a sudden danger."}
        }
        
        # Initialize evidence_collection here
        self.evidence_collection = {} 

        # Path setup for achievements file
        try:
            # Ensure Kivy App is running before accessing user_data_dir
            app_instance = App.get_running_app()
            if app_instance:
                app_data_dir = app_instance.user_data_dir
                os.makedirs(app_data_dir, exist_ok=True) # Ensure directory exists
                self.achievements_file = os.path.join(app_data_dir, "player_achievements.json")
            else:
                # Fallback if app is not running (e.g., testing environment)
                # This path might not be ideal for packaged apps if App isn't running.
                logging.warning("Kivy App not running during AchievementsSystem init. Using CWD for achievements file.")
                self.achievements_file = os.path.join(os.getcwd(), "player_achievements.json")

        except Exception as e:
            # Broader exception catch for issues like `AttributeError` if `App.get_running_app()` is None
            logging.error(f"Error getting user_data_dir for achievements: {e}. Using CWD as fallback.")
            self.achievements_file = os.path.join(os.getcwd(), "player_achievements.json")
            # Ensure the fallback directory exists if it's CWD (though usually it does)
            # os.makedirs(os.getcwd(), exist_ok=True) # Not strictly necessary for CWD

        self.load_achievements() # Load existing achievements
        
    def unlock(self, achievement_id):
        """
        Unlock an achievement, save the state, and trigger a notification.

        Args:
            achievement_id (str): The ID of the achievement to unlock.

        Returns:
            bool: True if the achievement was newly unlocked, False otherwise.
        """
        if achievement_id not in self.achievements:
            logging.warning(f"Attempted to unlock non-existent achievement: {achievement_id}")
            return False
            
        if self.achievements[achievement_id]["unlocked"]:
            logging.info(f"Achievement '{achievement_id}' is already unlocked.")
            return False  # Already unlocked
            
        self.achievements[achievement_id]["unlocked"] = True
        self.save_achievements() # Save immediately after unlocking
        
        achievement_name = self.achievements[achievement_id]["name"]
        
        # Notification messages can be more generic or customized per achievement
        notification_messages = {
            "first_evidence": "You've found your first piece of evidence!",
            "collector": "You've collected numerous items!",
            "survivor": "You've survived against all odds!",
            "survived_the_house": "You've escaped the haunted house!",
            "survived_the_hospital": "You've made it through the hospital!",
            "speedrun": "You completed the game quickly!",
            "quick_reflexes": "Your quick reactions saved your life!"
        }
        
        notification_detail = notification_messages.get(achievement_id, f"You've unlocked: {achievement_name}!")
            
        if self.notify_callback:
            # The callback might expect title and message, or just one string.
            # Assuming title and message for now.
            self.notify_callback(f"Achievement Unlocked: {achievement_name}", notification_detail)
        
        logging.info(f"Achievement unlocked: {achievement_id} - {achievement_name}")
        return True
        
    def load_achievements(self):
        """Load achievements and evidence collection from file."""
        try:
            if os.path.exists(self.achievements_file):
                with open(self.achievements_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Load achievements status
                    saved_achievements_data = data.get("achievements", {})
                    for ach_id, ach_data in saved_achievements_data.items():
                        if ach_id in self.achievements:
                            # Update only specific fields like 'unlocked', preserve 'name', 'icon', 'description' from code
                            if isinstance(ach_data, dict) and "unlocked" in ach_data:
                                self.achievements[ach_id]["unlocked"] = ach_data["unlocked"]
                            elif isinstance(ach_data, bool): # Old format compatibility
                                self.achievements[ach_id]["unlocked"] = ach_data

                    # Load evidence collection
                    self.evidence_collection = data.get("evidence_collection", {})
                    logging.info(f"Achievements and evidence loaded from {self.achievements_file}")
            else:
                logging.info(f"Achievements file not found at {self.achievements_file}. Starting fresh.")
        except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logging.error(f"Error loading achievements data from {self.achievements_file}: {e}")
            # Optionally, reset to default if loading fails critically
            # self.achievements = { ... default structure ... }
            # self.evidence_collection = {}
            
    def save_achievements(self):
        """Save current achievements status and evidence collection to file."""
        try:
            # Consolidate data to save
            data_to_save = {
                "achievements": self.achievements,
                "evidence_collection": self.evidence_collection
            }
            with open(self.achievements_file, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=2, ensure_ascii=False)
            logging.info(f"Achievements and evidence saved to {self.achievements_file}")
        except Exception as e: # Catch broader exceptions during file write
            logging.error(f"Error saving achievements data to {self.achievements_file}: {e}")
            
    def get_all_achievements(self):
        """
        Return a list of all achievements with their status and details.
        Each item in the list is a dictionary.
        """
        return [{"id": ach_id, **ach_data} for ach_id, ach_data in self.achievements.items()]
        
    def get_unlocked_count(self):
        """Return the number of unlocked achievements."""
        return sum(1 for ach_data in self.achievements.values() if ach_data.get("unlocked", False))
    
    def record_evidence(self, evidence_id, evidence_name, evidence_description):
        """
        Records a piece of evidence found by the player.
        Unlocks "collector" achievement if criteria met.

        Args:
            evidence_id (str): Unique ID for the evidence.
            evidence_name (str): Display name of the evidence.
            evidence_description (str): Description of the evidence for the journal.

        Returns:
            bool: True if evidence was newly recorded, False if already recorded.
        """
        if evidence_id not in self.evidence_collection:
            self.evidence_collection[evidence_id] = {
                "name": evidence_name,
                "description": evidence_description,
                "found_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            logging.info(f"Evidence recorded: {evidence_id} - {evidence_name}")
            
            # Potentially unlock an achievement for finding N pieces of evidence
            if len(self.evidence_collection) >= 5: # Example: Collector achievement for 5 items
                self.unlock("collector") # unlock() will call save_achievements()
            else:
                self.save_achievements() # Save if collector wasn't unlocked by this item
            
            return True
        logging.info(f"Evidence '{evidence_id}' already recorded.")
        return False # Already recorded

    def has_evidence(self, evidence_id):
        """Checks if a specific piece of evidence has already been recorded."""
        return evidence_id in self.evidence_collection

    def check_game_completion_achievements(self, game_logic_instance):
        """
        Checks and unlocks achievements related to game completion status.
        Called by GameLogic when the game ends.
        """
        if not game_logic_instance or not hasattr(game_logic_instance, 'player'):
            logging.warning("GameLogic instance or player data not provided for game completion achievements.")
            return

        if game_logic_instance.game_won:
            self.unlock("survivor") 
            
            # Example: Check for speedrun based on turns taken (actions_taken)
            # Ensure 'actions_taken' is a valid attribute/key in player data
            actions_taken = game_logic_instance.player.get("actions_taken", float('inf')) # Default to infinity if not found
            if actions_taken < 50: # Example threshold for speedrun
                self.unlock("speedrun")
        # else:
            # Potentially unlock achievements for specific loss conditions if desired
            # e.g., self.unlock("first_death") or self.unlock("died_by_hazard_X")

        # Note: unlock() calls save_achievements(), so no separate save call needed here
        # unless multiple unlocks happen and you want to ensure it's saved after all.
        # For safety, one final save can be done, but it might be redundant.
        # self.save_achievements() # Generally not needed if unlock() saves.

    def check_level_completion_achievements(self, game_logic_instance, completed_level_id):
        """
        Checks and unlocks achievements for completing specific levels.
        Called by GameLogic when a level is completed.
        """
        if not game_logic_instance: # game_logic_instance might not be strictly needed if only level_id is used
            logging.warning("GameLogic instance not provided for level completion achievements.")
            # Continue if only level_id is needed

        if completed_level_id == 1: # Assuming level ID for "The Bludworth House" is 1
            self.unlock("survived_the_house")
        elif completed_level_id == 2: # Assuming level ID for "Lakeview Hospital" is 2
            self.unlock("survived_the_hospital")
        # Add more level-specific achievements here

        # unlock() calls save_achievements()
