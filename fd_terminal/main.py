import os
import logging
from kivy.config import Config
Config.set('input', 'mouse', 'mouse,disable_multitouch')
Config.set('input', 'wm_touch', '') # May also help disable simulated touch events from window manager
Config.set('input', 'wm_pen', '')   # Disable pen events if not needed

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
# from kivy.core.window import Window # Uncomment if you use Window.size
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.uix.label import Label

# Use relative imports for modules within the fd_terminal package
# These assume main.py is part of a package 'fd_terminal'
# If running main.py directly as a script from its own directory, 
# and other .py files are siblings, direct imports might work,
# but relative imports are better for package structure.
print("--- Attempting relative import: from . import hazard_patch ---") # Debug print
from . import hazard_patch # Make sure hazard_patch.py is in the same directory/package
from . import game_data    # Make sure game_data.py is in the same directory/package
# game_logic is usually instantiated within screens or the app, not imported directly at module level here usually
# from . import game_logic # GameLogic is instantiated by GameScreen
from .ui import (
    TitleScreen,
    IntroScreen,
    GameScreen,
    WinScreen,
    LoseScreen,
    AchievementsScreen,
    TutorialScreen,
    CharacterSelectScreen,
    InterLevelScreen,
    JournalScreen,
    SaveGameScreen,
    LoadGameScreen
)
from .achievements import AchievementsSystem
from .tony_todd_tribute import TonyToddTribute # Assuming tony_todd_tribute.py is in the same package

# Initialize logging (can be done here or in the top-level launcher)
# For Kivy apps, it's often good to do this after the App instance is available
# to use App.user_data_dir for log files, especially for packaged apps.
# The current setup tries to use user_data_dir but has a fallback.

# Global log_file_path variable, might be better encapsulated or configured in on_start
log_file_path = "fd_terminal_app.log" # Default if app instance not ready

# Basic logging configuration (will be re-evaluated in on_start for user_data_dir)
# This initial config might write to CWD if app.user_data_dir isn't available yet.
logging.basicConfig(filename=log_file_path, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filemode='w') # Use 'w' to overwrite log on each start, or 'a' to append.

def cleanup_corrupted_saves():
    import os
    import json
    
    save_dir = os.path.join(os.path.dirname(__file__), 'saves')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
        return
        
    for filename in os.listdir(save_dir):
        if not filename.startswith('savegame_') or not filename.endswith('.json'):
            continue
            
        # Delete any files with {} in the name (improperly formatted)
        if "{}" in filename:
            try:
                os.remove(os.path.join(save_dir, filename))
                print(f"Removed improperly named save file: {filename}")
            except Exception as e:
                print(f"Error removing file {filename}: {e}")
            continue
            
        # Check if file content is valid JSON
        filepath = os.path.join(save_dir, filename)
        try:
            with open(filepath, 'r') as f:
                content = f.read()
                if not content.strip():
                    continue
                json.loads(content)  # Test if valid JSON
        except json.JSONDecodeError:
            backup_path = filepath + ".corrupted"
            try:
                os.rename(filepath, backup_path)
                print(f"Renamed corrupted save {filename} to {filename}.corrupted")
            except Exception as e:
                print(f"Error handling corrupted file {filename}: {e}")

cleanup_corrupted_saves()
class FinalDestinationApp(App):
    # Application-level properties to share data/state between screens if needed
    selected_character_class = None # Stores selected character class from CharacterSelectScreen
    current_disaster_details = None # Stores generated disaster details from IntroScreen
    last_game_score = 0             # For displaying on Win/Lose screens
    last_death_reason = "Death's design was fulfilled." # Default death reason
    start_new_session_flag = False # To signal GameScreen to start a fresh GameLogic instance
    interlevel_evaded_hazards = []
    interlevel_next_level_id = None
    interlevel_next_start_room = None
    interlevel_completed_level_name = ""
    interlevel_completed_level_id = None
    interlevel_completed_level_data = None
    
    def build(self):
        """
        This method is called when the application starts and initializes the root widget.
        """
        self.title = "Final Destination Terminal"
        
        # Main layout for the entire application
        self.main_layout = BoxLayout(orientation='vertical')
        
        # Configure logging to use user_data_dir (safer place for logs)
        # This is a good place to ensure logging is set up correctly.
        self._configure_app_logging()

        logging.info("FinalDestinationApp: build() method called.")
        
        # Show the tribute screen first, which then calls initialize_game_ui
        # Using Clock.schedule_once ensures that the main window is created before the modal view.
        Clock.schedule_once(self.show_tribute_screen, 0.1) 
        
        # The tribute screen's on_complete callback will call self.initialize_game_ui()
        # So, initialize_game_ui() should not be called directly here if tribute is shown.
        # If tribute is skipped or fails, initialize_game_ui should be the fallback.
        
        return self.main_layout # Return the root layout

    def _configure_app_logging(self):
        """Configures logging to use the app's user_data_dir."""
        try:
            user_dir = self.user_data_dir # Access Kivy's user_data_dir
            log_dir = os.path.join(user_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            app_log_file = os.path.join(log_dir, "fd_terminal_app.log")

            # Remove existing handlers to avoid duplicate logs if basicConfig was called globally
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
                handler.close() # Important to close file handlers

            # Set up new handler
            file_handler = logging.FileHandler(app_log_file, mode='w') # 'w' for overwrite, 'a' for append
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s',
                                          datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            
            root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.INFO) # Set level for the root logger

            logging.info(f"Application logging configured to: {app_log_file}")

        except Exception as e:
            logging.error(f"Error configuring application logging: {e}", exc_info=True)
            # Fallback to basicConfig if user_data_dir setup fails (already done globally, but as a note)
            # logging.basicConfig(filename="fd_terminal_app_fallback.log", level=logging.INFO, ...)


    def show_tribute_screen(self, dt):
        """
        Displays the Tony Todd tribute screen.
        The tribute screen will call self.initialize_game_ui upon completion.
        """
        logging.info("Showing Tony Todd tribute screen.")
        try:
            # TonyToddTribute is a ModalView, it will display over main_layout
            tribute = TonyToddTribute(on_complete=self.initialize_game_ui_after_tribute)
            tribute.open()
        except Exception as e:
            logging.error(f"Could not display tribute screen: {e}", exc_info=True)
            # Fallback: If tribute fails, initialize the main UI directly
            self.initialize_game_ui() # Call the main UI setup

    def initialize_game_ui_after_tribute(self):
        """Callback from tribute screen to initialize the main game UI."""
        logging.info("Tribute complete. Initializing main game UI.")
        self.initialize_game_ui()

    def initialize_game_ui(self):
        """
        Initializes the main game UI, including the ScreenManager and screens.
        This is called after the tribute screen or if the tribute fails.
        """
        logging.info("Initializing Game UI (ScreenManager and screens)...")
        try:
            # Initialize achievements system (passed to screens that need it)
            # Ensure it's created only once per app lifecycle if intended as a singleton.
            if not hasattr(self, 'achievements_system'): # Create if not exists
                self.achievements_system = AchievementsSystem(notify_callback=self.show_achievement_notification_kivy)
            
            # Create the ScreenManager if it doesn't exist or needs to be fresh
            # Store it as an instance variable to access it later if needed (e.g., for global navigation methods)
            if not hasattr(self, 'screen_manager') or self.screen_manager is None:
                self.screen_manager = ScreenManager(transition=SlideTransition(direction='left', duration=0.3))
            else: # Clear existing screens if re-initializing (e.g. after an error)
                self.screen_manager.clear_widgets()


            # Add screens to the ScreenManager
            # Pass necessary systems (like achievements_system) to screens that require them.
            self.screen_manager.add_widget(TitleScreen(name='title', achievements_system=self.achievements_system))
            self.screen_manager.add_widget(IntroScreen(name='intro')) 
            self.screen_manager.add_widget(CharacterSelectScreen(name='character_select'))
            self.screen_manager.add_widget(TutorialScreen(name='tutorial'))
            self.screen_manager.add_widget(GameScreen(name='game', achievements_system=self.achievements_system))
            self.screen_manager.add_widget(WinScreen(name='win'))
            self.screen_manager.add_widget(LoseScreen(name='lose'))
            self.screen_manager.add_widget(LoadGameScreen(name='load_game')) 
            self.screen_manager.add_widget(SaveGameScreen(name='save_game')) 
            self.screen_manager.add_widget(AchievementsScreen(name='achievements', achievements_system=self.achievements_system))
            self.screen_manager.add_widget(JournalScreen(name='journal', achievements_system=self.achievements_system)) 

            # Apply data patches 
            if not getattr(self, '_patches_applied', False): 
                hazard_patch.apply_all_patches() 
                self._patches_applied = True
                logging.info("Data patches applied via hazard_patch.py.")

            # Add the ScreenManager to the main layout
            self.main_layout.clear_widgets()
            self.main_layout.add_widget(self.screen_manager) # Use self.screen_manager
            
            # Set initial screen (optional, Kivy defaults to first added if not set)
            # self.screen_manager.current = 'title' # Or whatever your desired start screen is

            logging.info("Game UI Initialized successfully with ScreenManager.")

        except Exception as e:
            logging.error(f"Error during initialize_game_ui: {e}", exc_info=True)
            error_label = Label(text=f"Failed to initialize game UI:\n{e}\nPlease check logs.")
            self.main_layout.clear_widgets()
            self.main_layout.add_widget(error_label)

    def show_achievement_notification_kivy(self, title, message):
        """
        Placeholder callback for displaying achievement notifications using Kivy.
        This would typically involve creating and opening a Popup or a custom notification widget.
        """
        # from kivy.uix.popup import Popup # Example import
        # from kivy.uix.label import Label # Example import
        # popup_content = Label(text=message, markup=True, text_size=(Window.width * 0.7, None))
        # popup_content.bind(texture_size=popup_content.setter('size'))
        # popup = Popup(title=title,
        #               content=popup_content,
        #               size_hint=(0.8, None), # Width is 80% of screen
        #               height=popup_content.texture_size[1] + dp(80), # Adjust height for title and padding
        #               title_font=DEFAULT_FONT, # Assuming DEFAULT_FONT is defined
        #               title_size='18sp',
        #               auto_dismiss=True)
        # popup.open()
        logging.info(f"KIVY NOTIFICATION (App Level): {title} - {message}")
        # A simple print for now, as Popups can be more involved with styling.
        print(f"ACHIEVEMENT UNLOCKED (App Level): {title} - {message}")


    def on_start(self):
        """
        Called when the Kivy application is starting (after build() has run).
        Good place for loading app-wide resources or saved states.
        """
        logging.info("FinalDestinationApp on_start called.")
        # Load achievements if the system has been initialized
        if hasattr(self, 'achievements_system') and self.achievements_system:
            try:
                self.achievements_system.load_achievements()
                logging.info("Achievements loaded in on_start.")
            except Exception as e:
                logging.error(f"Error loading achievements in on_start: {e}", exc_info=True)
        else:
            logging.warning("AchievementsSystem not available at on_start, achievements not loaded at this point.")
        
        # Any other on_start logic (e.g., loading global settings)

    def on_stop(self):
        """
        Called when the Kivy application is stopping.
        Good place for saving any application-wide states.
        """
        logging.info("FinalDestinationApp on_stop called.")
        # Save achievements if the system is initialized
        if hasattr(self, 'achievements_system') and self.achievements_system:
            try:
                self.achievements_system.save_achievements()
                logging.info("Achievements saved in on_stop.")
            except Exception as e:
                logging.error(f"Error saving achievements in on_stop: {e}", exc_info=True)
        
        # Any other on_stop logic (e.g., saving global settings)

# Entry point for the application
if __name__ == '__main__': # This structure is typical for Kivy apps
     FinalDestinationApp().run()