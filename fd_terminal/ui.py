# filepath: /home/dallas/Desktop/FD_GUI_Refactored/ui.py

from kivy.app import App
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget # Widget is imported twice, once is enough
# from kivy.uix.widget import Widget # Duplicate import
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.properties import BooleanProperty, StringProperty, NumericProperty, ObjectProperty
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.uix.behaviors import FocusBehavior
from kivy.uix.recycleview.layout import LayoutSelectionBehavior
from kivy.core.window import Window # Used for text_size binding
from kivy.core.text import LabelBase
from kivy.clock import Clock
from kivy.metrics import dp
# from kivy.core.text import LabelBase # Duplicate import
from kivy.utils import get_color_from_hex 
# from kivy.utils import platform # platform is not used directly here, commented out
from kivy.graphics import Color, Rectangle
from kivy.uix.popup import Popup
# Relative imports for game logic and data (assuming standard package structure)
# These should work if ui.py is part of the same package as game_logic, game_data, etc.
from .game_logic import GameLogic
from . import game_data
from .utils import color_text, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_ORANGE, COLOR_LIGHT_GREY, COLOR_BLUE, COLOR_PURPLE, COLOR_WHITE, COLOR_MAGENTA # utils.py provides color constants
from .achievements import AchievementsSystem 

import os
import logging # Standard logging
import datetime # Used in JournalScreen
import random # For IntroScreen and random font selection
import json   # For save/load operations (though mostly handled by GameLogic)
import sys    # For resource_path
import glob   # For random font selection

REGISTERED_FONT_NAMES = set()

# --- Asset Handling ---
def resource_path(relative_path):
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    Adjusts path based on whether the app is running from a PyInstaller bundle.
    """
    # Determine the base path, prioritizing PyInstaller's _MEIPASS attribute
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path is None:
        # If not bundled, assume the base path is the directory of the current script (ui.py)
        # and then go up one level to the project root if assets are structured like 'project_root/assets'.
        # This might need adjustment based on your exact project structure.
        # If ui.py is in 'fd_terminal' package, and assets is 'fd_terminal/assets', then:
        # base_path = os.path.dirname(os.path.abspath(__file__))
        # If assets is at the same level as 'fd_terminal' package:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")) # Goes up one directory
                                                                               # from ui.py to project root.
                                                                               # This assumes ui.py is in a subdirectory
                                                                               # like 'fd_terminal/ui.py' and assets is 'project_root/assets'
                                                                               # If ui.py is at root with assets, then os.path.abspath(".") is fine.
                                                                               # Given the from .game_logic imports, ui.py is likely in a package.

    # If _MEIPASS is not set, and the above relative path logic isn't perfect for your dev setup,
    # you might fall back to os.path.abspath(".") if assets are relative to where you run python.
    # For development, it's often easier if assets are relative to the script being run or a known root.
    # The provided code had a more complex fallback for non-MEIPASS, let's simplify slightly for clarity here.
    # The key is that `base_path` should point to where the 'assets' folder can be found.
    if base_path is None: # Fallback if not in _MEIPASS and relative pathing is tricky
        base_path = os.path.abspath(".") # Assumes assets is relative to CWD if not bundled.

    asset_path = os.path.join(base_path, relative_path)
    
    # Original code had a secondary check:
    # if not os.path.exists(asset_path):
    #     asset_path = os.path.join(base_path, "fd_terminal", relative_path)
    # This implies that sometimes assets might be in 'assets/' and sometimes in 'fd_terminal/assets/'.
    # For consistency, it's better to have one reliable assets location.
    # If assets are always within the package, then:
    # base_path_for_package_assets = os.path.dirname(os.path.abspath(__file__))
    # asset_path = os.path.join(base_path_for_package_assets, relative_path)
    
    logging.debug(f"Resource path resolved: '{relative_path}' -> '{asset_path}' (Base: '{base_path}')")
    if not os.path.exists(asset_path):
        logging.warning(f"Resource NOT FOUND at resolved path: {asset_path}")
        # Attempt another common structure for development if assets are in package next to ui.py
        alt_base_path = os.path.dirname(os.path.abspath(__file__))
        alt_asset_path = os.path.join(alt_base_path, relative_path)
        if os.path.exists(alt_asset_path):
            logging.info(f"Found resource at alternate package path: {alt_asset_path}")
            return alt_asset_path
        # Fallback to the original PyInstaller check for "fd_terminal" subdirectory within bundle
        if hasattr(sys, '_MEIPASS'): # If bundled
             bundled_subdir_path = os.path.join(base_path, "fd_terminal", relative_path)
             if os.path.exists(bundled_subdir_path):
                 logging.info(f"Found resource at bundled subdirectory path: {bundled_subdir_path}")
                 return bundled_subdir_path

    return asset_path


# --- Font Registration ---
# Attempt to register a "default" game font and a "random" thematic font.
# DEFAULT_FONT is used for most UI text for readability.
# RANDOM_FONT_NAME is used for thematic titles (e.g., TitleScreen).

DEFAULT_FONT_REGULAR_NAME = "RobotoMonoRegular" # Changed from "RobotoMono-Bold" to avoid confusion if only regular is used
DEFAULT_FONT_BOLD_NAME = "RobotoMonoBold"    # Explicitly named bold variant

RANDOM_FONT_NAME = "BloodyMary" # Default random font if dynamic selection fails

try:
    # Register default fonts
    default_font_regular_path = resource_path(os.path.join("assets", "fonts", "RobotoMono-Regular.ttf"))
    default_font_bold_path = resource_path(os.path.join("assets", "fonts", "RobotoMono-Bold.ttf"))

    if os.path.exists(default_font_regular_path):
        LabelBase.register(name=DEFAULT_FONT_REGULAR_NAME, fn_regular=default_font_regular_path)
        logging.info(f"Registered default font: {DEFAULT_FONT_REGULAR_NAME} from {default_font_regular_path}")
    else:
        logging.error(f"Default regular font not found at: {default_font_regular_path}. UI text might use Kivy's default.")

    if os.path.exists(default_font_bold_path):
        LabelBase.register(name=DEFAULT_FONT_BOLD_NAME, fn_regular=default_font_bold_path) # Kivy uses fn_regular for bold if fn_bold not given
        logging.info(f"Registered default bold font: {DEFAULT_FONT_BOLD_NAME} from {default_font_bold_path}")
    else:
        logging.error(f"Default bold font not found at: {default_font_bold_path}.")

except Exception as e:
    logging.error(f"Error registering default fonts: {e}", exc_info=True)

def get_random_font():
    """Selects a random .ttf or .otf font from the assets/fonts directory."""
    try:
        # Use get_resource_path for more robust path handling across platforms/packaged apps
        font_dir = resource_path(os.path.join("assets", "fonts"))
        logging.debug(f"Looking for random fonts in {font_dir}")
        
        if not os.path.isdir(font_dir):
            logging.warning(f"Font directory not found: {font_dir}. Cannot select random font.")
            return RANDOM_FONT_NAME # Fallback to pre-defined RANDOM_FONT_NAME
            
        font_files = glob.glob(os.path.join(font_dir, "*.ttf")) + glob.glob(os.path.join(font_dir, "*.otf"))
        
        # Exclude default fonts from random selection if they are also in the list
        font_files = [f for f in font_files if "RobotoMono-Regular" not in f and "RobotoMono-Bold" not in f]

        # Use the correct way to access registered fonts (fix for the original error)
        registered_fonts = getattr(LabelBase, '_fonts', {}).keys()
        
        if not font_files:
            logging.warning(f"No random fonts found in {font_dir} (excluding defaults). Using fallback thematic font.")
            # Attempt to register the fallback thematic font if not already
            fallback_font_path = resource_path(os.path.join("assets", "fonts", "Bloody_Mary.ttf"))
            if os.path.exists(fallback_font_path) and RANDOM_FONT_NAME not in registered_fonts:
                LabelBase.register(name=RANDOM_FONT_NAME, fn_regular=fallback_font_path)
                logging.info(f"Registered fallback thematic font: {RANDOM_FONT_NAME} from {fallback_font_path}")
            elif RANDOM_FONT_NAME in registered_fonts:
                 logging.info(f"Fallback thematic font '{RANDOM_FONT_NAME}' already registered.")
            else:
                logging.error(f"Fallback thematic font 'Bloody_Mary.ttf' not found at {fallback_font_path}.")
            return RANDOM_FONT_NAME # Return the name

        selected_font_path = random.choice(font_files)
        selected_font_name = os.path.splitext(os.path.basename(selected_font_path))[0].replace(" ", "_") # Sanitize name
        
        # Register if not already (Kivy warns if re-registering with same name but different file)
        if selected_font_name not in REGISTERED_FONT_NAMES:
            LabelBase.register(name=selected_font_name, fn_regular=selected_font_path)
            REGISTERED_FONT_NAMES.add(selected_font_name)
            logging.info(f"Registered random font: {selected_font_name} from {selected_font_path}")
            return selected_font_name
        else:
            logging.info(f"Randomly selected font '{selected_font_name}' already registered. Using it.")
            return selected_font_name
            
    except Exception as e:
        logging.error(f"Error in get_random_font: {e}", exc_info=True)
        return RANDOM_FONT_NAME # Fallback

# Determine the random font to be used for titles etc.
THEMATIC_FONT_NAME = get_random_font()
logging.info(f"Thematic font for this session: {THEMATIC_FONT_NAME}")
class BaseScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.05, 0.05, 0.05, 1) # Dark background color
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def go_to_screen(self, screen_name, direction='left'):
        self.manager.transition.direction = direction
        self.manager.current = screen_name

    def play_sound(self, sound_name):
        # Placeholder for sound playing logic
        # app = App.get_running_app()
        # if hasattr(app, 'sound_manager'): app.sound_manager.play(sound_name)
        logging.debug(f"Sound: Play '{sound_name}' (not implemented yet)")
        pass

# --- QTE Popup ---
class QTEPopup(Popup):
    qte_prompt = StringProperty("QTE Active!")
    qte_time_left = NumericProperty(5.0)
    qte_expected_input = StringProperty("") 
    qte_input_type = StringProperty("word") 
    qte_mash_count = NumericProperty(0)
    qte_target_mash_count = NumericProperty(10)
    
    def __init__(self, qte_type, qte_duration, qte_context, game_screen_callback, **kwargs):
        super().__init__(**kwargs)
        self.title = "QUICK TIME EVENT!"
        self.title_font = DEFAULT_FONT_BOLD_NAME
        self.title_size = dp(20)
        self.size_hint = (0.8, 0.5)
        self.auto_dismiss = False  # Player must interact or timeout

        self.qte_type = qte_type
        self.qte_time_left = float(qte_duration)
        self.qte_context_data = qte_context
        self.resolve_qte_callback = game_screen_callback

        # Extract QTE parameters from context
        self.qte_prompt = qte_context.get("ui_prompt_message", "Respond Quickly!")
        self.qte_expected_input = qte_context.get("expected_input_word", "dodge").lower()
        self.qte_input_type = qte_context.get("input_type", "word")
        self.qte_target_mash_count = qte_context.get("target_mash_count", 10)
        self.qte_mash_count = 0

        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        # Prompt label
        self.prompt_label = Label(
            text=self.qte_prompt, 
            font_name=DEFAULT_FONT_REGULAR_NAME, 
            font_size=dp(18),
            halign='center', 
            markup=True
        )
        self.prompt_label.bind(width=lambda i, w: setattr(i, 'text_size', (w*0.9, None)))
        layout.add_widget(self.prompt_label)

        # Timer label
        self.timer_label = Label(
            text=f"Time: {self.qte_time_left:.1f}s", 
            font_name=DEFAULT_FONT_BOLD_NAME, 
            font_size=dp(22),
            color=get_color_from_hex(COLOR_RED), 
            size_hint_y=None, 
            height=dp(30)
        )
        layout.add_widget(self.timer_label)

        # Different input types
        if self.qte_input_type == "word" or self.qte_input_type == "sequence_input_qte":
            self.text_input = TextInput(
                hint_text=f"Type '{self.qte_expected_input.upper()}'", 
                multiline=False,
                font_name=DEFAULT_FONT_REGULAR_NAME, 
                font_size=dp(16),
                size_hint_y=None, 
                height=dp(40)
            )
            self.text_input.bind(on_text_validate=self.on_input_enter)
            layout.add_widget(self.text_input)
            
        elif self.qte_input_type == "button_mash":
            # Add mash progress indicator
            self.mash_progress_label = Label(
                text=f"Progress: {self.qte_mash_count}/{self.qte_target_mash_count}",
                font_name=DEFAULT_FONT_REGULAR_NAME, 
                font_size=dp(16),
                size_hint_y=None, 
                height=dp(30)
            )
            layout.add_widget(self.mash_progress_label)
            
            # Add mash button
            self.mash_button = Button(
                text="MASH!", 
                font_name=DEFAULT_FONT_BOLD_NAME, 
                font_size=dp(20),
                size_hint_y=None, 
                height=dp(60)
            )
            self.mash_button.bind(on_press=self.on_mash_event)
            layout.add_widget(self.mash_button)
            
        elif self.qte_input_type == "button":
            # Generic action button
            self.action_button = Button(
                text=self.qte_expected_input.upper(), 
                font_name=DEFAULT_FONT_BOLD_NAME, 
                font_size=dp(18),
                size_hint_y=None, 
                height=dp(50)
            )
            self.action_button.bind(on_release=self.on_button_press)
            layout.add_widget(self.action_button)
        
        self.content = layout
        self._countdown_event = None
        self._keyboard = None

    def on_mash_event(self, instance=None):
        """Handles a single mash event (button press or key press)."""
        if self.qte_input_type != "button_mash" or self.qte_mash_count >= self.qte_target_mash_count:
            return  # Not a mash QTE or already succeeded

        self.qte_mash_count += 1
        if hasattr(self, 'mash_progress_label'):
             self.mash_progress_label.text = f"Progress: {self.qte_mash_count}/{self.qte_target_mash_count}"
        
        if self.qte_mash_count >= self.qte_target_mash_count:
            self.success("mash_success")  # Signal success to GameLogic

    def _on_keyboard_down_mash(self, keyboard, keycode, text, modifiers):
        if self.qte_input_type == "button_mash" and keycode[1] == 'spacebar':
            self.on_mash_event()
            return True  # Key event consumed
        return False

    def _keyboard_closed_mash(self):
        if self._keyboard:
            self._keyboard.unbind(on_key_down=self._on_keyboard_down_mash)
            self._keyboard = None

    def open(self, *args, **kwargs):
        super().open(*args, **kwargs)
        
        # Set focus based on QTE type
        if self.qte_input_type == "word" and hasattr(self, 'text_input'):
            Clock.schedule_once(lambda dt: setattr(self.text_input, 'focus', True), 0.2)
        elif self.qte_input_type == "button_mash":
            # Register keyboard for mashing
            self._keyboard = Window.request_keyboard(self._keyboard_closed_mash, self, 'text')
            if self._keyboard and hasattr(self._keyboard, 'widget'):
                self._keyboard.bind(on_key_down=self._on_keyboard_down_mash)
            # Focus the mash button
            if hasattr(self, 'mash_button'):
                Clock.schedule_once(lambda dt: setattr(self.mash_button, 'focus', True), 0.2)
        
        self._countdown_event = Clock.schedule_interval(self.update_timer, 0.1)
        logging.info(f"QTEPopup opened. Type: {self.qte_type}, Expected: '{self.qte_expected_input}', Duration: {self.qte_time_left:.1f}s, InputType: {self.qte_input_type}")

    def update_timer(self, dt):
        self.qte_time_left -= dt
        if self.qte_time_left <= 0:
            self.qte_time_left = 0
            self.timer_label.text = "Time: 0.0s"
            
            # Handle timeout differently for button_mash
            if self.qte_input_type == "button_mash" and self.qte_mash_count < self.qte_target_mash_count:
                self.timeout()
            elif self.qte_input_type != "button_mash":
                self.timeout()
            return False  # Stop scheduling
            
        self.timer_label.text = f"Time: {self.qte_time_left:.1f}s"
        return True

    def on_input_enter(self, instance):
        typed_word = instance.text.strip().lower()
        if typed_word == self.qte_expected_input:
            self.success(typed_word)
        else:
            self.failure("Incorrect input.")

    def on_button_press(self, instance):
        # For button QTEs, pressing the button means success
        self.success(self.qte_expected_input)

    def dismiss(self, *args, **kwargs):
        # Ensure keyboard is released when popup is dismissed for any reason
        if self.qte_input_type == "button_mash" and self._keyboard:
            self._keyboard.release()
            self._keyboard = None
        super().dismiss(*args, **kwargs)

    def success(self, player_response):
        logging.info(f"QTE '{self.qte_type}' SUCCESS. Response: '{player_response}'")
        if self._countdown_event:
            Clock.unschedule(self._countdown_event)
            self._countdown_event = None
        self.dismiss()
        if self.resolve_qte_callback:
            self.resolve_qte_callback(qte_type=self.qte_type, success=True, response=player_response, context=self.qte_context_data)

    def failure(self, reason="Unknown"):
        logging.info(f"QTE '{self.qte_type}' FAILED. Reason: {reason}")
        if self._countdown_event:
            Clock.unschedule(self._countdown_event)
            self._countdown_event = None
        self.dismiss()
        if self.resolve_qte_callback:
            self.resolve_qte_callback(qte_type=self.qte_type, success=False, response=reason, context=self.qte_context_data)

    def timeout(self):
        logging.info(f"QTE '{self.qte_type}' TIMED OUT.")
        if self._countdown_event:
            Clock.unschedule(self._countdown_event)
            self._countdown_event = None
        self.dismiss()
        if self.resolve_qte_callback:
            self.resolve_qte_callback(qte_type=self.qte_type, success=False, response=game_data.SIGNAL_QTE_TIMEOUT, context=self.qte_context_data)

# --- Title Screen ---
class TitleScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super().__init__(**kwargs)
        self.achievements_system = achievements_system 
        
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        
        title_label = Label(
            text=f"[b][color={COLOR_WHITE}]Final Destination[/color] [color={COLOR_RED}]Terminal[/color][/b]",
            font_name=THEMATIC_FONT_NAME, # Use the randomly selected thematic font
            font_size=dp(60), # Adjusted for dp
            markup=True,
            size_hint_y=None,
            height=dp(100),
            halign='center',
            valign='middle'
        ) 
        layout.add_widget(title_label)
        
        # Ensure text wraps if window is too narrow
        def update_text_size_for_title(instance, value):
            instance.text_size = (instance.width, None)
        title_label.bind(width=update_text_size_for_title)

        buttons_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(300)) # Adjusted height
        
        btn_new_game = Button(text="New Game", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), on_release=self.start_new_game_flow)
        btn_load_game = Button(text="Load Game", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), on_release=lambda x: self.go_to_screen('load_game'))
        btn_achievements = Button(text="Achievements", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), on_release=lambda x: self.go_to_screen('achievements'))
        btn_tutorial = Button(text="How to Play", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), on_release=lambda x: self.go_to_screen('tutorial'))
        btn_exit = Button(text="Exit Game", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), on_release=App.get_running_app().stop)
        
        buttons_layout.add_widget(btn_new_game)
        buttons_layout.add_widget(btn_load_game)
        buttons_layout.add_widget(btn_achievements)
        buttons_layout.add_widget(btn_tutorial)
        buttons_layout.add_widget(btn_exit)
        
        layout.add_widget(BoxLayout(size_hint_y=0.2)) # Spacer
        layout.add_widget(buttons_layout)
        layout.add_widget(BoxLayout(size_hint_y=0.3)) # Spacer
        
        self.add_widget(layout)

    def start_new_game_flow(self, instance):
        """Initiates the new game flow, usually by going to character selection or intro."""
        app = App.get_running_app()
        app.start_new_session_flag = True # Signal GameScreen to create fresh GameLogic

        # Decide whether to go to character select or intro
        # For now, let's assume CharacterSelect is the next step for a new game.
        self.go_to_screen('character_select', direction='left')

# --- Character Select Screen ---
class CharacterSelectScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        
        layout.add_widget(Label(
            text="[b]Select Your Character[/b]", 
            markup=True, 
            font_name=DEFAULT_FONT_BOLD_NAME, 
            font_size=dp(24), 
            size_hint_y=0.15 # Adjusted for better spacing
        ))
        
        # Descriptions for character classes
        # Accessing from game_data directly. Ensure game_data is imported.
        char_classes = game_data.CHARACTER_CLASSES if hasattr(game_data, 'CHARACTER_CLASSES') else {}
        
        grid = GridLayout(cols=1, spacing=dp(8), size_hint_y=0.7) # Grid for character buttons and descriptions
        
        for char_name, char_info in char_classes.items():
            char_button_text = f"{char_name} - {char_info.get('description', 'No special abilities.')}"
            btn = Button(
                text=char_button_text, 
                font_name=DEFAULT_FONT_REGULAR_NAME, 
                font_size=dp(16),
                on_release=lambda x, cn=char_name: self.select_character(cn),
                size_hint_y=None,
                height=dp(50),
                halign='center', # Center text on button
                valign='middle'
            )
            btn.bind(width=lambda instance, value: setattr(instance, 'text_size', (value * 0.9, None))) # Text wrapping
            grid.add_widget(btn)
            
        layout.add_widget(grid)
        
        btn_back = Button(
            text="Back to Title", 
            size_hint_y=None, 
            height=dp(50), 
            font_name=DEFAULT_FONT_BOLD_NAME, 
            font_size=dp(18),
            on_release=lambda x: self.go_to_screen('title', 'right')
        )
        layout.add_widget(Widget(size_hint_y=0.05)) # Spacer
        layout.add_widget(btn_back)
        layout.add_widget(Widget(size_hint_y=0.05)) # Spacer
        
        self.add_widget(layout)

    def select_character(self, char_class):
        app = App.get_running_app()
        app.selected_character_class = char_class
        logging.info(f"Character selected: {char_class}")
        
        # GameScreen will pick up app.selected_character_class when it starts a new session.
        # No need to call game_screen.prepare_new_game_session here directly if TitleScreen's
        # start_new_game_flow already sets app.start_new_session_flag = True.
        # GameScreen.on_enter will handle the new session setup.
        
        self.go_to_screen('intro', direction='left')

# --- Intro Screen ---
class IntroScreen(BaseScreen):
    """Displays the introductory story text for the game."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info("IntroScreen initializing")
        
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        intro_title = Label(
            text="The Premonition...",
            font_name=THEMATIC_FONT_NAME, # Use thematic font
            font_size=dp(30),
            size_hint_y=None,
            height=dp(45), # Adjusted height
            color=get_color_from_hex(COLOR_RED) # Use defined color constant
        )
        layout.add_widget(intro_title)

        self.intro_text_label = Label(
            text="Loading premonition...",
            markup=True,
            valign='top',
            halign='left', # Changed to left for better readability of paragraphs
            font_name=DEFAULT_FONT_REGULAR_NAME, # Use readable default font
            font_size=dp(16), # Adjusted size
            padding=(dp(10), dp(10)),
            size_hint_y=None # Height will be driven by texture_size
        )
        self.intro_text_label.bind(
            texture_size=self._update_intro_label_height,
            width=self._update_intro_label_text_size # For text wrapping
        )

        scroll_view = ScrollView(size_hint=(1, 1)) # Takes remaining space
        scroll_view.add_widget(self.intro_text_label)
        layout.add_widget(scroll_view)

        # Button layout at the bottom
        button_layout_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), padding=(0, dp(5)))
        # Add spacers to center the button
        button_layout_box.add_widget(Widget(size_hint_x=0.25)) 
        self.continue_button = Button(
            text="Continue to the ER Entrance...",
            font_name=DEFAULT_FONT_BOLD_NAME,
            font_size=dp(18),
            size_hint_x=0.5, # Button takes 50% of horizontal space
            size_hint_y=None,
            height=dp(50)
        )
        self.continue_button.bind(on_press=self.proceed_to_game)
        button_layout_box.add_widget(self.continue_button)
        button_layout_box.add_widget(Widget(size_hint_x=0.25))
        layout.add_widget(button_layout_box)

        self.add_widget(layout)

    def _update_intro_label_height(self, instance, texture_size_value):
        instance.height = texture_size_value[1] # Set height to fit content

    def _update_intro_label_text_size(self, instance, width_value):
        # Update text_size for wrapping, considering padding
        instance.text_size = (width_value - dp(20), None) 

    def on_enter(self, *args):
        """Generate and display the intro text when the screen is entered."""
        logging.info("IntroScreen on_enter: Generating intro text.")
        # Generate and set the intro text
        # Ensure disaster details are generated if they don't exist on app instance
        app = App.get_running_app()
        if not hasattr(app, 'current_disaster_details') or not app.current_disaster_details:
            self._ensure_disaster_details_generated(app)
            
        self.intro_text_label.text = self._generate_intro_text_from_app_details()
        # Scroll to top after text is set
        Clock.schedule_once(lambda dt: setattr(self.intro_text_label.parent, 'scroll_y', 1), 0.1)

    def _generate_intro_text_from_app_details(self):
        app = App.get_running_app()
        if not app or not app.current_disaster_details:
            logging.warning("IntroScreen: app.current_disaster_details not found for text generation.")
            return "A chilling premonition grips you..." # Fallback
        details = app.current_disaster_details
        intro_base = (f"Welcome to McKinley, population: {color_text('dropping like flies.', 'error')}\n\n"
            "Local tales speak of 'Death's List'. It was nonsense to you. Past tense.\n\n"
            "You arrive at Hope River Hospital, accompanying the body of the most recent ex-survivor of a disaster that almost killed you both.")
        disaster_desc_template = details.get("full_description_template", "A terrible disaster occurred.")
        try:
            formatted_disaster_description = disaster_desc_template.format(
                visionary=color_text(details.get("visionary", "a figure"), 'special'),
                warning=color_text(details.get("warning", "Watch out!"), 'warning'),
                killed_count=color_text(str(details.get("killed_count", 0)), 'warning'),
                survivor_fates=color_text(details.get("survivor_fates", "met grim ends."), 'item'))
        except KeyError as e:
            logging.warning(f"IntroScreen: Missing placeholder: {e}"); formatted_disaster_description = disaster_desc_template
        full_intro = (f"{intro_base}\n\n"
            f"You both recently walked away from {color_text(details.get('event_description', 'a disaster'), 'special')} killed a lot of people.\n\n"
            f"{formatted_disaster_description}\n\nNow, you're the last one left.\n\n"
            f"Your goal: find {color_text('ANY', 'error')} evidence that might help you cheat Death before your time runs out.\n"
            f"Type '{color_text('list', 'command')}' or use buttons for actions.\n\n"
            f"{color_text('Explore, interact, examine, and watch your step!', 'info')}\n\n"
            f"{color_text('Good luck...', 'special')}")
        return full_intro

    def _ensure_disaster_details_generated(self, app_instance):
        if hasattr(app_instance, 'current_disaster_details') and app_instance.current_disaster_details:
            return
        logging.info("IntroScreen: current_disaster_details not found on app instance. Generating now.")
        
        gd = game_data 
        if not hasattr(gd, 'disasters') or not gd.disasters:
            logging.error("IntroScreen: Cannot generate disaster details, game_data.disasters is missing.")
            app_instance.current_disaster_details = None
            return

        chosen_disaster_key = random.choice(list(gd.disasters.keys()))
        disaster_info = gd.disasters[chosen_disaster_key]
        
        chosen_visionary = "a mysterious figure" 
        disaster_categories = disaster_info.get("categories", []) 

        visionary_category_map = {
            "transportation_air": ["transport_staff", "strangers_distinctive"],
            "transportation_road": ["emergency_services", "bystanders_general", "transport_staff"],
            "transportation_water": ["transport_staff", "outdoor_nature_authority"],
            "mechanical_failure": ["maintenance_technical", "strangers_distinctive"],
            "natural_disaster": ["outdoor_nature_authority", "emergency_services", "bystanders_general"],
            "environmental": ["outdoor_nature_authority", "emergency_services"], # "environmental_hazard" in disaster categories
            "outdoor_locations": ["outdoor_nature_authority", "bystanders_general"],
            "industrial": ["maintenance_technical", "emergency_services"], # "industrial_accident" in disaster categories
            "explosion": ["emergency_services", "strangers_distinctive", "maintenance_technical"], # "explosion_related" in disaster categories
            "workplace_hazard": ["maintenance_technical", "service_workers_venue"],
            "entertainment_venue": ["service_workers_venue", "maintenance_technical", "bystanders_general"],
            "public_safety": ["emergency_services", "bystanders_general"], # New mapping
            "structural_collapse": ["emergency_services", "maintenance_technical", "bystanders_general"],
            "public_transit_hub": ["transport_staff", "emergency_services", "bystanders_general"],
            "recreational_setting": ["service_workers_venue", "bystanders_general", "outdoor_nature_authority"],
            "fire_related": ["emergency_services", "bystanders_general"],
            "infrastructure_failure": ["maintenance_technical", "emergency_services"],
            "urban_disaster": ["emergency_services", "bystanders_general", "strangers_distinctive"],
            "flood_related": ["emergency_services", "outdoor_nature_authority"],
            "geological_event": ["emergency_services", "strangers_distinctive"],
            "coastal_disaster": ["outdoor_nature_authority", "emergency_services"],
            "man_made_disaster": ["emergency_services", "maintenance_technical"],
            "medical_facility_failure": ["emergency_services"], # From new disaster
            "cascading_disaster": ["emergency_services", "strangers_distinctive"], # From new disaster
            "height_related_danger": ["maintenance_technical", "bystanders_general"], # From new disaster
            "workplace_hazard_public_impact": ["emergency_services", "service_workers_venue"], # From new disaster
            "rural_disaster": ["outdoor_nature_authority", "bystanders_general"], # From new disaster
        }

        possible_visionary_categories = []
        if disaster_categories: 
            for cat in disaster_categories:
                # Match disaster categories (e.g., "industrial_accident") with keys in visionary_category_map
                if cat in visionary_category_map:
                    possible_visionary_categories.extend(visionary_category_map[cat])
                # Also check if parts of the disaster category match (e.g. "industrial" in "industrial_accident")
                for map_key in visionary_category_map.keys():
                    if map_key in cat:
                         possible_visionary_categories.extend(visionary_category_map[map_key])
        
        if not possible_visionary_categories:
            if "plane" in chosen_disaster_key.lower() or "flight" in chosen_disaster_key.lower():
                possible_visionary_categories.extend(visionary_category_map.get("transportation_air", []))
            elif "highway" in chosen_disaster_key.lower() or "route" in chosen_disaster_key.lower():
                possible_visionary_categories.extend(visionary_category_map.get("transportation_road", []))
            elif "fire" in chosen_disaster_key.lower() and "forest" not in chosen_disaster_key.lower(): 
                possible_visionary_categories.extend(visionary_category_map.get("fire_related", ["emergency_services", "bystanders_general"]))
            elif "wildfire" in chosen_disaster_key.lower() or "forest" in chosen_disaster_key.lower():
                 possible_visionary_categories.extend(visionary_category_map.get("natural_disaster", []) + visionary_category_map.get("outdoor_locations", []))
        
        unique_possible_visionary_cats = list(set(possible_visionary_categories))
        random.shuffle(unique_possible_visionary_cats) 

        selected_visionaries_list = None
        # Ensure CATEGORIZED_VISIONARIES is correctly accessed from gd (game_data module)
        if hasattr(gd, 'CATEGORIZED_VISIONARIES'):
            for v_cat_key in unique_possible_visionary_cats:
                if v_cat_key in gd.CATEGORIZED_VISIONARIES and gd.CATEGORIZED_VISIONARIES[v_cat_key]:
                    selected_visionaries_list = gd.CATEGORIZED_VISIONARIES[v_cat_key]
                    break 
            if not selected_visionaries_list:
                fallback_cats = ["strangers_distinctive", "bystanders_general", "children_youths"]
                random.shuffle(fallback_cats)
                for fb_cat in fallback_cats:
                    if fb_cat in gd.CATEGORIZED_VISIONARIES and gd.CATEGORIZED_VISIONARIES[fb_cat]:
                        selected_visionaries_list = gd.CATEGORIZED_VISIONARIES[fb_cat]
                        break
            if selected_visionaries_list:
                chosen_visionary = random.choice(selected_visionaries_list)
        else:
            logging.warning("game_data.CATEGORIZED_VISIONARIES not found. Using default visionary.")
        
        warnings = disaster_info.get("warnings", ["Watch out!"])
        warning = random.choice(warnings) if warnings else "Watch out!"
        
        killed_count_val = disaster_info.get("killed_count", 0)
        if callable(killed_count_val): killed_count_val = killed_count_val()
        elif isinstance(killed_count_val, tuple) and len(killed_count_val) == 2: 
            killed_count_val = random.randint(killed_count_val[0], killed_count_val[1])
        
        # --- INTEGRATED MODIFIED FATE SELECTION LOGIC ---
        survivor_fate_list = getattr(gd, 'survivor_fates', ["drowned", "crushed", "disappeared"]) # Default if not found

        min_fates_to_show = 3
        max_fates_to_show = 5 # You can adjust this maximum
        
        available_fates_count = len(survivor_fate_list)
        
        num_fates_to_select = 0 # Initialize
        if available_fates_count == 0:
            formatted_fates = "met unknown fates" # Should not happen if default is used
        elif available_fates_count < min_fates_to_show:
            # If fewer than min_fates_to_show are available, show all of them
            num_fates_to_select = available_fates_count
        else:
            # Select a number of fates between min_fates_to_show and max_fates_to_show (or available_fates_count if smaller)
            upper_bound_for_random = min(max_fates_to_show, available_fates_count)
            # Ensure randint lower bound is not greater than upper bound
            if min_fates_to_show > upper_bound_for_random : #This can happen if available_fates_count is < min_fates_to_show but > 0
                num_fates_to_select = upper_bound_for_random
            else:
                num_fates_to_select = random.randint(min_fates_to_show, upper_bound_for_random)

        if num_fates_to_select > 0:
            selected_fates = random.sample(survivor_fate_list, num_fates_to_select)
            
            if len(selected_fates) == 1:
                formatted_fates = selected_fates[0]
            elif len(selected_fates) == 2:
                formatted_fates = f"{selected_fates[0]} and {selected_fates[1]}"
            else: # 3 or more
                formatted_fates = ", ".join(selected_fates[:-1]) + f", and {selected_fates[-1]}"
        elif available_fates_count > 0 : # If num_fates_to_select ended up 0 but fates were available (edge case)
             selected_fates = random.sample(survivor_fate_list, 1) # pick at least one
             formatted_fates = selected_fates[0]
        else: # No fates available and num_fates_to_select is 0
            formatted_fates = "met unknown fates"
        # --- END OF INTEGRATED MODIFIED FATE SELECTION LOGIC ---
        
        app_instance.current_disaster_details = {
            "event_description": chosen_disaster_key,
            "full_description_template": disaster_info.get("description", ""), 
            "visionary": chosen_visionary, 
            "warning": warning, 
            "killed_count": int(killed_count_val), 
            "survivor_fates": formatted_fates 
        }
        logging.info(f"IntroScreen: Generated disaster details: {app_instance.current_disaster_details['event_description']} with visionary: {chosen_visionary} and fates: {formatted_fates}")

    def proceed_to_game(self, instance):
        """Switches to the 'game' screen."""
        logging.info("IntroScreen: Proceeding to GameScreen.")
        self.go_to_screen('game', direction='left')

# --- Tutorial Screen ---
class TutorialScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        
        layout.add_widget(Label(
            text="[b]How to Play[/b]", 
            markup=True, 
            font_name=DEFAULT_FONT_BOLD_NAME, 
            font_size=dp(24), 
            size_hint_y=0.1
        ))
        
        tutorial_text_content = (
            f"{color_text('Welcome to Final Destination Terminal!', COLOR_PURPLE)}\n\n"
            "You've narrowly escaped a catastrophe, but Death doesn't like to be cheated. "
            "You find yourself at the abandoned Bludworth residence, seeking clues about Death's design "
            "and how others might have survived... or failed.\n\n"
            f"[b]Objective:[/b]\n"
            f"- Explore each location (e.g., The House, The Hospital) to find {color_text('Evidence', COLOR_ORANGE)} related to past events and victims.\n"
            f"- Some evidence is crucial to understanding how to proceed or {color_text('survive the current level', COLOR_GREEN)}.\n"
            f"- Manage your {color_text('Health (HP)', COLOR_GREEN)} and {color_text('Turns Left', COLOR_YELLOW)}. Running out of either means Death catches up.\n\n"
            f"[b]Interacting with the World:[/b]\n"
            f"- {color_text('Text Input:', COLOR_CYAN)} Type commands like '{color_text('move north', COLOR_LIGHT_GREY)}', '{color_text('examine table', COLOR_LIGHT_GREY)}', or '{color_text('take key', COLOR_LIGHT_GREY)}'.\n"
            f"- {color_text('Action Buttons:', COLOR_CYAN)} Use the main action buttons (Move, Examine, etc.) at the bottom left. Selecting an action will show available targets.\n"
            f"- {color_text('Contextual Buttons:', COLOR_CYAN)} After selecting a main action, specific targets (objects, items, directions) will appear as buttons.\n\n"
            f"[b]Key Commands (examples):[/b]\n"
            f"- '{color_text('list', COLOR_LIGHT_GREY)}' or '{color_text('help', COLOR_LIGHT_GREY)}': Shows available actions in your current situation.\n"
            f"- '{color_text('examine [object/item/room]', COLOR_LIGHT_GREY)}': Get more details. Examining items in your inventory can reveal new information.\n"
            f"- '{color_text('search [furniture]', COLOR_LIGHT_GREY)}': Look inside containers like desks or cabinets to find hidden items.\n"
            f"- '{color_text('take [item]', COLOR_LIGHT_GREY)}': Pick up an item you can see or have found.\n"
            f"- '{color_text('use [item] on [target]', COLOR_LIGHT_GREY)}': Use an item from your inventory on something in the room.\n"
            f"- '{color_text('inventory', COLOR_LIGHT_GREY)}' or '{color_text('i', COLOR_LIGHT_GREY)}': Check what you're carrying.\n"
            f"- '{color_text('map', COLOR_LIGHT_GREY)}': View a map of your surroundings.\n"
            f"- '{color_text('journal', COLOR_LIGHT_GREY)}': Review collected evidence and clues.\n\n"
            f"[b]Hazards & QTEs:[/b]\n"
            f"- The environment is {color_text('dangerous', COLOR_RED)}. Hazards can change, interact, or be triggered by your actions.\n"
            f"- Pay attention to descriptions! {color_text('Sparks', COLOR_MAGENTA)}, {color_text('gas smells', COLOR_ORANGE)}, or {color_text('unstable objects', COLOR_MAGENTA)} are bad signs.\n"
            f"- Quick Time Events ({color_text('QTEs', COLOR_RED)}) may occur. You'll have a few seconds to type the correct command (e.g., 'DODGE') to survive.\n\n"
            f"[b]Good luck. You'll need it.[/b]"
        )
        
        scroll_view = ScrollView(size_hint_y=0.8)
        scroll_label = Label(
            text=tutorial_text_content, 
            font_name=DEFAULT_FONT_REGULAR_NAME, 
            font_size=dp(15), # Slightly smaller for more text
            markup=True, 
            size_hint_y=None, # Height determined by content
            halign='left', 
            valign='top',
            padding=(dp(5), dp(5))
        )
        scroll_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value - dp(10), None))) # Word wrapping
        scroll_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1])) # Fit height to text
        
        scroll_view.add_widget(scroll_label)
        layout.add_widget(scroll_view)
        
        btn_back = Button(
            text="Back to Title", 
            size_hint_y=None, # Explicit height
            height=dp(50), 
            font_name=DEFAULT_FONT_BOLD_NAME, 
            font_size=dp(18),
            on_release=lambda x: self.go_to_screen('title', 'right')
        )
        layout.add_widget(btn_back)
        self.add_widget(layout)

class EvadedHazardEntry(RecycleDataViewBehavior, Label):
    """ Displays a single evaded hazard. """
    index = None
    selected = BooleanProperty(False)
    selectable = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        ''' Catch and handle the view changes '''
        self.index = index
        self.text = data.get('text', '')
        self.markup = True
        self.font_name = DEFAULT_FONT_REGULAR_NAME
        self.font_size = dp(14)
        self.halign = 'left'
        self.valign = 'top'
        self.text_size = (rv.width * 0.9, None) # Ensure wrapping
        self.size_hint_y = None
        self.height = self.texture_size[1] + dp(10) # Add padding
        return super(EvadedHazardEntry, self).refresh_view_attrs(rv, index, data)

    def on_touch_down(self, touch):
        ''' Add selection on touch down '''
        if super(EvadedHazardEntry, self).on_touch_down(touch):
            return True
        if self.collide_point(*touch.pos) and self.selectable:
            return self.parent.select_with_touch(self.index, touch)

    def apply_selection(self, rv, index, is_selected):
        ''' Respond to a selection change. '''
        self.selected = is_selected
        # You can change background color or something on selection if desired
   
    def proceed_to_next_level(self, instance):
        """
        Handles transition to the next level, win screen, or title screen.
        Ensures GameLogic and UI state are updated appropriately.
        """
        app = App.get_running_app()
        app.start_new_session_flag = False  # Always continuing, not starting fresh

        # If there is a next level, go to the game screen (GameLogic state should already be set)
        if getattr(self, 'next_level_id', None):
            self.go_to_screen('game', direction='left')
            return

        # If there is no next level, check if the game was won
        game_logic = getattr(app, 'game_logic', None)
        if game_logic and getattr(game_logic, 'game_won', False):
            self.go_to_screen('win', direction='fade')
        else:
            # No next level and not explicitly won (e.g., end of content)
            self.go_to_screen('title', direction='right')

class InterLevelScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_level_id = None
        self.next_level_start_room = None

        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15)) # Adjusted padding/spacing
        
        self.title_label = Label(
            text="[b]Level Complete![/b]", markup=True,
            font_name=THEMATIC_FONT_NAME, font_size=dp(32), # Slightly smaller
            size_hint_y=None, height=dp(45), color=get_color_from_hex(COLOR_GREEN)
        )
        layout.add_widget(self.title_label)

        # Narrative Text Area
        self.narrative_label = Label(
            text="Loading transition...", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            font_size=dp(16), size_hint_y=0.2, halign='center', valign='top',
            padding=(dp(5), dp(5))
        )
        self.narrative_label.bind(width=lambda i, w: setattr(i, 'text_size', (w * 0.9, None))) # Wrapping
        layout.add_widget(self.narrative_label)
        
        # Stats Display
        stats_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(10))
        self.score_label = Label(text="Score: --", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(15))
        self.turns_taken_label = Label(text="Turns This Level: --", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(15))
        self.evidence_count_label = Label(text="Evidence Found: --", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(15))
        stats_layout.add_widget(self.score_label)
        stats_layout.add_widget(self.turns_taken_label)
        stats_layout.add_widget(self.evidence_count_label)
        layout.add_widget(stats_layout)

        layout.add_widget(Label( # Separator/Title for evaded hazards
            text="[u]Hazards Evaded This Level:[/u]", markup=True,
            font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(17), # Adjusted size
            size_hint_y=None, height=dp(25), padding=(0, dp(5)) # Added padding
        ))

        self.rv = RecycleView(size_hint=(1, 0.45), scroll_type=['bars', 'content']) # Adjusted height hint
        self.rv.viewclass = EvadedHazardEntry
        self.rv_layout = RecycleBoxLayout(orientation='vertical', size_hint_y=None,
                                          default_size=(None, dp(45)), default_size_hint=(1, None), # Adjusted default_size
                                          padding=dp(10), spacing=dp(5))
        self.rv_layout.bind(minimum_height=self.rv_layout.setter('height'))
        self.rv.add_widget(self.rv_layout)
        layout.add_widget(self.rv)

        self.continue_button = Button(
            text="Continue to Next Area", font_name=DEFAULT_FONT_BOLD_NAME,
            size_hint_y=None, height=dp(50), font_size=dp(18)
        )
        self.continue_button.bind(on_release=self.proceed_to_next_level)
        layout.add_widget(Widget(size_hint_y=0.05)) # Spacer
        layout.add_widget(self.continue_button)
        self.add_widget(layout)

    def on_enter(self, *args):
        super().on_enter(*args) # Call parent's on_enter if it does anything
        app = App.get_running_app()
        evaded_hazards = getattr(app, 'interlevel_evaded_hazards', [])
        self.next_level_id = getattr(app, 'interlevel_next_level_id', None)
        self.next_level_start_room = getattr(app, 'interlevel_next_start_room', None)
        
        completed_level_name = getattr(app, 'interlevel_completed_level_name', 'The Previous Area')
        self.title_label.text = f"[b]{completed_level_name} Survived![/b]"

        # Set Narrative Text
        narrative = getattr(app, 'interlevel_narrative_text', "You take a deep breath, the echoes of danger still fresh...")
        self.narrative_label.text = color_text(narrative, 'special') # Example color

        # Set Stats
        score = getattr(app, 'interlevel_score_for_level', 0)
        turns_this_level = getattr(app, 'interlevel_turns_taken_for_level', 0)
        evidence_this_level_count = getattr(app, 'interlevel_evidence_found_for_level_count', 0)

        self.score_label.text = f"Total Score: {color_text(str(score), 'special')}"
        self.turns_taken_label.text = f"Turns Taken: {color_text(str(turns_this_level), 'turn')}"
        self.evidence_count_label.text = f"Evidence Found: {color_text(str(evidence_this_level_count), 'evidence')}"

        if evaded_hazards:
            self.rv.data = [{'text': f"- {color_text(hazard_desc, 'hazard')}"} for hazard_desc in evaded_hazards]
        else:
            self.rv.data = [{'text': color_text("You navigated the area with remarkable caution (or luck!).", 'default')}]
        
        if self.next_level_id:
            next_level_name = game_data.LEVEL_REQUIREMENTS.get(self.next_level_id, {}).get("name", "the Unknown")
            self.continue_button.text = f"Proceed to {next_level_name}"
        else: # No next level, means game won or ended differently
            self.continue_button.text = "Conclude Journey" # Or "View Final Score" etc.
            # If this is the ultimate win screen, the logic in proceed_to_next_level should go to 'win'
            if App.get_running_app().game_logic and App.get_running_app().game_logic.game_won:
                 self.continue_button.text = "Claim Your Fate (Win)" # Placeholder text
            else: # Should ideally not happen if next_level_id is None after last defined level
                 self.continue_button.text = "Return to Main Menu"

    def proceed_to_next_level(self, instance):
        """
        Handles transition to the next level, win screen, or title screen.
        Ensures GameLogic and UI state are updated appropriately.
        """
        app = App.get_running_app()
        app.start_new_session_flag = False  # Always continuing, not starting fresh

        # If there is a next level, go to the game screen (GameLogic state should already be set)
        if getattr(self, 'next_level_id', None):
            self.go_to_screen('game', direction='left')
            return

        # If there is no next level, check if the game was won
        game_logic = getattr(app, 'game_logic', None)
        if game_logic and getattr(game_logic, 'game_won', False):
            self.go_to_screen('win', direction='fade')
        else:
            # No next level and not explicitly won (e.g., end of content)
            self.go_to_screen('title', direction='right')
class GameScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        logging.info("GameScreen initializing...")

        self.achievements_system = achievements_system
        self.game_logic = GameLogic(achievements_system=self.achievements_system)

        self.game_started = False
        self.pending_load = False
        self.load_slot_identifier = "quicksave"
        self.selected_action = None
        self.selected_use_item = None
        
        # QTE handling variables
        self.qte_timer_event = None
        self.active_qte_type = None
        self.qte_remaining_time = 0
        self.qte_context = {}
        self.active_qte_popup = None # To hold the QTEPopup instance if using popup approach
        
        self.contextual_target_generators = {
            "move": self.get_valid_directions_for_ui,
            "examine": self.get_examinable_targets_for_ui,
            "take": self.get_takeable_items_for_ui,
            "search": self.get_searchable_furniture_for_ui,
            "use": self.get_usable_inventory_items_for_ui,
            "drop": self.get_inventory_items_for_ui,
            "unlock": self.get_unlockable_targets_for_ui
        }

        # --- Main Layout Structure ---
        root_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        self.qte_timer_label = Label(
            text="", font_name=DEFAULT_FONT_BOLD_NAME, markup=True,
            size_hint_y=None, height=dp(30), color=get_color_from_hex(COLOR_RED)
        )
        root_layout.add_widget(self.qte_timer_label)
        main_split_layout = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=1)

        # --- LEFT PANEL ---
        left_panel = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_x=0.45)

        # Map Display
        map_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.35)
        self.map_title_label = Label(
            text="[b]Map[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME,
            size_hint_y=None, height=dp(25), halign='left', valign='middle'
        )
        self.map_title_label.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width, None)))
        self.map_label = Label(
            text="Initializing map...",
            markup=True,
            font_name=DEFAULT_FONT_REGULAR_NAME,
            font_size=dp(12),
            valign='top',
            halign='center',
            padding=(dp(5), dp(5)),
            size_hint_y=None
        )
        self.map_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        self.map_scroll = ScrollView(size_hint=(1, 1))
        self.map_scroll.add_widget(self.map_label)
        map_outer_layout.add_widget(self.map_title_label)
        map_outer_layout.add_widget(self.map_scroll)
        left_panel.add_widget(map_outer_layout)
        self.map_scroll.bind(width=lambda instance, width_val: setattr(self.map_label, 'text_size', (width_val - dp(10), None)))

        # Inventory Display
        inventory_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.20)
        self.inventory_title_label = Label(
            text="[b]Inventory[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME,
            size_hint_y=None, height=dp(25), halign='left', valign='middle'
        )
        self.inventory_title_label.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width, None)))
        self.inventory_content_label = Label(
            text="Empty", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            valign='top', halign='left', padding=(dp(5), dp(2)), size_hint_y=None
        )
        self.inventory_content_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        self.inventory_scroll = ScrollView(size_hint=(1, 1))
        self.inventory_scroll.add_widget(self.inventory_content_label)
        inventory_outer_layout.add_widget(self.inventory_title_label)
        inventory_outer_layout.add_widget(self.inventory_scroll)
        left_panel.add_widget(inventory_outer_layout)
        self.inventory_scroll.bind(width=lambda instance, width_val: setattr(self.inventory_content_label, 'text_size', (width_val - dp(10), None)))

        # Contextual Actions
        contextual_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.25)
        self.contextual_label = Label(
            text="[b]Actions:[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME,
            size_hint_y=None, height=dp(25), halign='left', valign='middle'
        )
        self.contextual_label.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width, None)))
        self.contextual_buttons_layout = BoxLayout(
            orientation='vertical', size_hint_y=None, spacing=dp(3), padding=(0, dp(2))
        )
        self.contextual_buttons_layout.bind(minimum_height=self.contextual_buttons_layout.setter('height'))
        contextual_buttons_scroll = ScrollView(size_hint=(1, 1))
        contextual_buttons_scroll.add_widget(self.contextual_buttons_layout)
        contextual_outer_layout.add_widget(self.contextual_label)
        contextual_outer_layout.add_widget(contextual_buttons_scroll)
        left_panel.add_widget(contextual_outer_layout)

        # Main Action Category Buttons
        main_action_buttons_scroll = ScrollView(size_hint=(1, None), height=dp(50), do_scroll_y=False, do_scroll_x=True)
        self.main_action_buttons_layout = BoxLayout(
            orientation='horizontal', size_hint_x=None, spacing=dp(5), padding=(dp(5), dp(5))
        )
        self.main_action_buttons_layout.bind(minimum_width=self.main_action_buttons_layout.setter('width'))
        action_buttons_config = [
            ("Move", "move"), ("Examine", "examine"), ("Take", "take"), ("Search", "search"),
            ("Use", "use"), ("Drop", "drop"), ("Unlock", "unlock"), ("Inv.", "inventory"),
            ("Journal", "journal"), ("Map", "map_display"), ("List", "list_actions"),
            ("Save", "save_game"), ("Load", "load_game"), ("Menu", "main_menu")
        ]
        for btn_text, action_key in action_buttons_config:
            btn = Button(
                text=btn_text, font_name=DEFAULT_FONT_BOLD_NAME, size_hint_x=None, width=dp(90),
                on_press=lambda instance, key=action_key: self.on_main_action_button_press(key), font_size=dp(13)
            )
            self.main_action_buttons_layout.add_widget(btn)
        main_action_buttons_scroll.add_widget(self.main_action_buttons_layout)
        left_panel.add_widget(main_action_buttons_scroll)

        # Text Input Field
        self.input_field = TextInput(
            hint_text="Or type command here...", multiline=False, size_hint_y=None, height=dp(40),
            font_name=DEFAULT_FONT_REGULAR_NAME, font_size=dp(14), padding=[dp(6), dp(6), dp(6), dp(6)]
        )
        self.input_field.bind(on_text_validate=self.process_input_from_text_field)
        left_panel.add_widget(self.input_field)
        main_split_layout.add_widget(left_panel)

        # --- RIGHT PANEL ---
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.55, spacing=dp(5))
        status_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(10))
        self.health_label = Label(
            text="HP: --", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            size_hint_x=0.33, halign='left', valign='middle'
        )
        self.turns_label = Label(
            text="Turns: --", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            size_hint_x=0.34, halign='center', valign='middle'
        )
        self.score_label = Label(
            text="Score: 0", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            size_hint_x=0.33, halign='right', valign='middle'
        )
        for label_widget in [self.health_label, self.turns_label, self.score_label]:
            label_widget.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width, None)))
            status_layout.add_widget(label_widget)
        right_panel.add_widget(status_layout)
        self.output_label = Label(
            text="Initializing game...\n", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
            font_size=dp(15), size_hint_y=None, valign='top', halign='left', padding=(dp(8), dp(8))
        )
        self.output_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        self.output_scroll_view = ScrollView(size_hint_y=1)
        self.output_scroll_view.add_widget(self.output_label)
        self.output_scroll_view.bind(width=lambda instance, width_val: setattr(self.output_label, 'text_size', (width_val - dp(16), None)))
        right_panel.add_widget(self.output_scroll_view)
        main_split_layout.add_widget(right_panel)

        root_layout.add_widget(main_split_layout)
        self.add_widget(root_layout)

        self.clear_and_display_general_actions()
        logging.info("GameScreen initialized.")

    def clear_and_display_general_actions(self):
        """Clears contextual buttons and displays the main action buttons."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = "[b]Choose an action:[/b]"
        self.selected_action = None
        self.selected_use_item = None

    def on_enter(self, *args):
        super().on_enter(*args)
        logging.info("GameScreen on_enter called.")
        app = App.get_running_app()

        if self.pending_load:
            logging.info(f"GameScreen: Pending load for slot '{self.load_slot_identifier}'.")
            self.start_new_game_session_from_load(self.load_slot_identifier)
            self.pending_load = False
        elif not self.game_started or (hasattr(app, 'start_new_session_flag') and app.start_new_session_flag):
            logging.info("GameScreen: Starting new game session.")
            self.output_label.text = "" 

            char_class = getattr(app, 'selected_character_class', "Journalist")
            
            self.game_logic = GameLogic(achievements_system=self.achievements_system)
            self.game_logic.start_new_game(character_class=char_class)
            
            if hasattr(app, 'current_disaster_details') and app.current_disaster_details:
                self.game_logic.player['disaster_context'] = app.current_disaster_details
                logging.info(f"Applied disaster context: {app.current_disaster_details.get('event_description')}")

            initial_desc = self.game_logic.get_room_description()
            
            first_entry_text = ""
            current_room_data = self.game_logic.get_room_data(self.game_logic.player['location'])
            if current_room_data:
                first_entry_text = current_room_data.get("first_entry_text", "")
            
            full_initial_message = f"{initial_desc}"
            if first_entry_text and self.game_logic.player['location'] not in self.game_logic.player.get("visited_rooms_first_text", set()):
                 full_initial_message += f"\n\n{color_text(first_entry_text, COLOR_PURPLE)}"
                 self.game_logic.player.setdefault("visited_rooms_first_text", set()).add(self.game_logic.player['location'])
            
            self._append_to_output(full_initial_message)
            self.game_started = True
            if hasattr(app, 'start_new_session_flag'):
                app.start_new_session_flag = False
        else:
            logging.info("GameScreen: Resuming existing game session.")

        self.on_game_session_ready()

    def start_new_game_session_from_load(self, load_slot_identifier):
        logging.info(f"GameScreen: Attempting to load game from slot '{load_slot_identifier}'.")
        load_response = self.game_logic.load_game(load_slot_identifier)
        
        self.output_label.text = "" 
        if load_response and load_response.get("success"):
            self._append_to_output(load_response.get("message", "Game loaded."))
            self._append_to_output(self.game_logic.get_room_description())
            self.game_started = True
        else:
            error_msg = load_response.get("message", "Failed to load game. Unknown error.")
            self._append_to_output(color_text(f"Failed to load game: {error_msg}", COLOR_RED))
            logging.warning("Load failed, starting a new game as fallback.")
            app = App.get_running_app()
            char_class = getattr(app, 'selected_character_class', "Journalist")
            self.game_logic.start_new_game(character_class=char_class)
            self._append_to_output(f"Starting a new game instead.\n{self.game_logic.get_room_description()}")
            self.game_started = True
        
        self.on_game_session_ready()

    def on_game_session_ready(self):
        if not self.game_logic or not self.game_logic.player:
            logging.error("GameScreen.on_game_session_ready: game_logic or player is None!")
            self._append_to_output(color_text("CRITICAL ERROR: Game state is not available.", COLOR_RED))
            return

        logging.debug("GameScreen.on_game_session_ready: Updating all UI elements.")
        self.update_all_ui_elements()
        self.clear_and_display_general_actions()
        self.input_field.focus = True

        if self.game_logic.player.get('qte_active'):
            qte_type = self.game_logic.player['qte_active']
            duration = self.game_logic.player.get('qte_duration', game_data.QTE_DEFAULT_DURATION)
            qte_context = self.game_logic.player.get('qte_context', {})
            
            # Use the popup approach if configured for it, otherwise use the timer
            if hasattr(self, 'USE_QTE_POPUP') and self.USE_QTE_POPUP:
                self.start_qte_popup(qte_type, duration, qte_context)
            else:
                self.start_qte_timer(qte_type, duration, qte_context)
        else:
            # Cancel any active QTE UI
            self.cancel_qte_popup()
            self.cancel_qte_timer()

    # --- UI Update Methods ---
    def _append_to_output(self, text_to_append, clear_previous=False):
        if clear_previous:
            self.output_label.text = text_to_append
        else:
            if self.output_label.text and not self.output_label.text.strip().endswith("\n"):
                 self.output_label.text += "\n\n" 
            self.output_label.text += text_to_append
        Clock.schedule_once(lambda dt: setattr(self.output_scroll_view, 'scroll_y', 0), 0.01)

    def update_all_ui_elements(self):
        if not self.game_logic or not self.game_logic.player:
            logging.warning("update_all_ui_elements: game_logic or player not available.")
            return

        hp_val = self.game_logic.player.get('hp', 0)
        hp_color_name = 'success' if hp_val > 5 else ('warning' if hp_val > 2 else 'error')
        self.health_label.text = f"HP: {color_text(str(hp_val), hp_color_name)}"

        turns_val = self.game_logic.player.get('turns_left', 0)
        turns_color_name = 'turn'  # Default yellow for turns
        if turns_val <= 10: turns_color_name = 'warning'  # Orange for low turns
        if turns_val <= 5: turns_color_name = 'error'  # Red for very low turns
        self.turns_label.text = f"Turns: {color_text(str(turns_val), turns_color_name)}"
        
        score_val = self.game_logic.player.get('score', 0)
        self.score_label.text = f"Score: {color_text(str(score_val), COLOR_PURPLE)}"
        
        self.update_map_display()
        self.update_inventory_display()
        logging.debug("All UI elements updated.")

    def update_map_display(self):
        if self.game_logic and self.game_logic.player:
            map_area_width_pixels = self.map_scroll.width - dp(10) 
            avg_char_width_pixels = dp(7.5) 
            map_width_chars = max(20, int(map_area_width_pixels / avg_char_width_pixels)) if avg_char_width_pixels > 0 else 20
            map_height_lines = 10 
            map_string = self.game_logic.get_gui_map_string(width=map_width_chars, height=map_height_lines)
            self.map_label.text = map_string
        else: 
            self.map_label.text = "Map data unavailable."

    def update_inventory_display(self):
        if self.game_logic and self.game_logic.player:
            inventory_list = self.game_logic.player.get('inventory', [])
            if inventory_list:
                colored_items = []
                for item_name in inventory_list:
                    item_master_data = self.game_logic._get_item_data(item_name)
                    item_color_name = 'item'  # Default green
                    if item_master_data and item_master_data.get('is_evidence'):
                        item_color_name = 'evidence'  # Orange
                    elif item_master_data and item_master_data.get('is_key'):
                        item_color_name = 'special'  # Purple for keys
                    colored_items.append(color_text(item_name.capitalize(), item_color_name))
                self.inventory_content_label.text = ", ".join(colored_items)
            else:
                self.inventory_content_label.text = "Empty"
        else:
            self.inventory_content_label.text = "Inventory unavailable."

    # --- UI Interaction Wrappers for GameLogic ---
    def get_valid_directions_for_ui(self):
        return self.game_logic.get_valid_directions() if self.game_logic else []

    def get_examinable_targets_for_ui(self):
        return self.game_logic.get_examinable_targets_in_room() if self.game_logic else []

    def get_takeable_items_for_ui(self):
        return self.game_logic.get_takeable_items_in_room() if self.game_logic else []

    def get_searchable_furniture_for_ui(self):
        return self.game_logic.get_searchable_furniture_in_room() if self.game_logic else []

    def get_usable_inventory_items_for_ui(self):
        return self.game_logic.get_usable_inventory_items() if self.game_logic else []

    def get_inventory_items_for_ui(self):
        return self.game_logic.get_inventory_items() if self.game_logic else []

    def get_unlockable_targets_for_ui(self):
        return self.game_logic.get_unlockable_targets() if self.game_logic else []

    # --- Button Handlers & UI Flow ---
    def on_main_action_button_press(self, action_key):
        """Handles presses of the primary action category buttons."""
        logging.debug(f"Main action button pressed: {action_key}")
        
        # Ignore button presses if QTE is active
        if self.active_qte_popup or self.active_qte_type:
            return
        
        # Simple commands processed directly
        if action_key == "inventory":
            self.show_inventory_with_examine_buttons()
            return
        if action_key == "list_actions":
            self.process_command("list")  # Or "help"
            return
        if action_key == "save_game":
            self.manager.current = 'save_game'  # Navigate to SaveGameScreen
            return
        if action_key == "load_game":
            self.manager.current = 'load_game'  # Navigate to LoadGameScreen
            return
        if action_key == "main_menu":
            self.go_to_screen('title', 'right')  # Navigate to TitleScreen
            return
        if action_key == "journal":
            self.go_to_screen('journal')
            return
        if action_key == "map_display":
            self.process_command("map")  # Prints map to output
            return

        # Actions requiring a target
        if action_key in self.contextual_target_generators:
            self.selected_action = action_key
            self.populate_target_buttons_for_action(action_key)
        else:
            logging.warning(f"Unknown main action key: {action_key}")
            self._append_to_output(color_text(f"Action '{action_key}' not yet implemented.", COLOR_RED))

    def populate_target_buttons_for_action(self, action_type):
        """Populates the contextual_buttons_layout with specific targets for the selected action."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"[b]Select target to {color_text(action_type.capitalize(), COLOR_PURPLE)}:[/b]"
        
        target_generator_method = self.contextual_target_generators.get(action_type)
        if not target_generator_method:
            self.contextual_buttons_layout.add_widget(Label(text=f"No target generator for '{action_type}'."))
            logging.error(f"No target generator method defined for action type: {action_type}")
            return

        targets = target_generator_method()  # Call the UI wrapper method

        if not targets:
            no_targets_label = Label(
                text=f"No targets available to {action_type}.", markup=True, 
                size_hint_y=None, halign='center', valign='middle', padding=(dp(5), dp(5))
            )
            no_targets_label.bind(texture_size=lambda i, ts: setattr(i, 'height', ts[1] + dp(10)))
            no_targets_label.bind(width=lambda i, w: setattr(i, 'text_size', (w - dp(10), None)))
            self.contextual_buttons_layout.add_widget(no_targets_label)
        else:
            for target_item_name in targets:
                btn = self.create_contextual_button(
                    text=target_item_name.capitalize(), 
                    command_tuple=(action_type, target_item_name)
                )
                self.contextual_buttons_layout.add_widget(btn)
        
        back_btn = self.create_contextual_button(text="< Back to Actions", command_tuple=("back", None))
        self.contextual_buttons_layout.add_widget(back_btn)

    def create_contextual_button(self, text, command_tuple, width_dp=None, height_dp=dp(40)):
        """Helper to create styled contextual buttons."""
        import re  # For stripping markup
        clean_text = re.sub(r'\[color=[^]]*\](.*?)\[/color\]', r'\1', text)
        clean_text = re.sub(r'\[/?b\]', '', clean_text)  # Strip bold tags for button text

        btn = Button(
            text=clean_text,
            font_name=DEFAULT_FONT_REGULAR_NAME,
            size_hint_y=None,
            height=height_dp,
            font_size=dp(13)
        )
        if width_dp:
            btn.size_hint_x = None
            btn.width = dp(width_dp)
        else:  # Full width within its parent (BoxLayout column)
            btn.size_hint_x = 1 

        # Basic styling (can be expanded based on command_tuple[0] or text content)
        if command_tuple[0] == "back" or "cancel" in command_tuple[0].lower():
            btn.background_color = get_color_from_hex(COLOR_LIGHT_GREY)  # Grey for back/cancel
            btn.color = get_color_from_hex("#333333")  # Dark text
        elif command_tuple[0] == "move":
            btn.background_color = get_color_from_hex(COLOR_CYAN)
            btn.color = get_color_from_hex("#000000")
        elif command_tuple[0] == "examine":
            btn.background_color = get_color_from_hex(COLOR_GREEN)
            btn.color = get_color_from_hex("#000000")
        elif command_tuple[0] == "take":
            btn.background_color = get_color_from_hex(COLOR_BLUE)

        btn.bind(on_press=lambda x: self.on_target_button_press(command_tuple))
        
        btn.text_size = (btn.width * 0.9, None)  # Enable wrapping
        btn.halign = 'center'
        btn.valign = 'middle'
        btn.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width * 0.9, None)))
        
        return btn

    def on_target_button_press(self, command_tuple):
        # Ignore button presses if QTE is active
        if self.active_qte_popup or self.active_qte_type:
            return
            
        action_type, target_name = command_tuple
        logging.debug(f"Contextual button pressed: Action='{action_type}', Target='{target_name}'")

        if action_type == "back" or action_type == "cancel_use":
            self.clear_and_display_general_actions()
            self.selected_action = None
            self.selected_use_item = None
            return

        if action_type == "use":
            if not self.selected_use_item: 
                # This means 'target_name' is the item FROM INVENTORY to be used
                self.selected_use_item = target_name 
                self.populate_use_on_what_buttons(self.selected_use_item)
            else: 
                # This means 'target_name' is the OBJECT IN ROOM to use the selected_use_item on
                command = f"use {self.selected_use_item.lower()} on {target_name.lower()}"
                self.process_command(command)
                # Reset state for next "use" sequence or other action
                self.selected_use_item = None
                self.clear_and_display_general_actions() 
        else:  # For move, examine, take, drop, unlock, search
            command = f"{action_type.lower()} {target_name.lower()}"
            self.process_command(command)
            # If the action doesn't lead to another specific UI state (like "search" results),
            # then revert to general actions.
            if action_type not in ["search"]:  # "search" has its own follow-up UI for taking items
                self.clear_and_display_general_actions()
            self.selected_action = None  # Reset selected main action

    def populate_use_on_what_buttons(self, item_to_use_name):
        """Populates buttons for selecting what to use an item on."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"[b]Use {color_text(item_to_use_name.capitalize(), COLOR_GREEN)} on what?:[/b]"

        # Get all examinable objects/furniture in the room as potential targets
        possible_use_targets = self.game_logic.get_examinable_targets_in_room() if self.game_logic else []

        if not possible_use_targets:
            self.contextual_buttons_layout.add_widget(Label(text="Nothing here to use that on."))
        else:
            for target_obj_name in possible_use_targets:
                btn = self.create_contextual_button(
                    text=target_obj_name.capitalize(),
                    command_tuple=("use", target_obj_name)  # action_type is "use", target_name is the object to use item on
                )
                self.contextual_buttons_layout.add_widget(btn)
        
        cancel_btn = self.create_contextual_button(text="< Cancel Use", command_tuple=("cancel_use", None))
        self.contextual_buttons_layout.add_widget(cancel_btn)

    def process_input_from_text_field(self, instance):
        """Processes command from the text input field."""
        command = instance.text.strip()
        if command:
            # If QTE popup is active, route input to it
            if self.active_qte_popup:
                # The QTE popup should handle the input itself
                # This code path is likely not reached if popup has its own input field
                logging.debug(f"Input text with QTE popup active: '{command}'")
                pass
            # If inline QTE is active, handle it
            elif self.active_qte_type:
                logging.debug(f"QTE Input: '{command}' for QTE Type: '{self.active_qte_type}'")
                self.process_command(command)
            else:  # Normal command processing
                self.process_command(command)
        instance.text = ""  # Clear input field

    def process_command(self, command_str):
        """Central method to process any command, update UI, and check game state."""
        if not self.game_logic or not self.game_logic.player:
            self._append_to_output(color_text("ERROR: Game logic not ready.", COLOR_RED))
            return

        app = App.get_running_app()

        # QTE response handling
        if self.active_qte_type:
            logging.info(f"Processing QTE response via process_command: '{command_str}' for QTE '{self.active_qte_type}'")
            qte_response_data = self.game_logic.process_player_input(command_str)
            self._append_to_output(qte_response_data.get("message", "QTE response processed."))
            self.cancel_qte_timer()  # Clean up timer-based QTE UI

            if qte_response_data.get("death"):
                self.navigate_to_end_screen()
            elif qte_response_data.get("transition_to_level"):
                self.handle_level_transition(qte_response_data)
            self.update_all_ui_elements()
            self.clear_and_display_general_actions()
            return

        # Normal command processing
        self._append_to_output(f"\n> {color_text(command_str, COLOR_CYAN)}")
        response_data = self.game_logic.process_player_input(command_str)

        # Output main message
        if response_data.get("message"):
            self._append_to_output(response_data["message"])

        # Handle found items after search
        if response_data.get("found_items") and self.selected_action == "search":
            searched_furniture_name = command_str.split(" ", 1)[1] if len(command_str.split(" ", 1)) > 1 else "area"
            self.populate_take_buttons_from_search_results(response_data["found_items"], searched_furniture_name)
        elif self.selected_action != "use":
            self.clear_and_display_general_actions()

        # QTE trigger
        if response_data.get("qte_triggered"):
            qte_info = response_data["qte_triggered"]
            qte_context = qte_info.get("context", {})
            
            # Use the popup approach if configured for it, otherwise use the timer
            if hasattr(self, 'USE_QTE_POPUP') and self.USE_QTE_POPUP:
                self.start_qte_popup(qte_info["type"], qte_info["duration"], qte_context)
            else:
                self.start_qte_timer(qte_info["type"], qte_info["duration"], qte_context)

        # Level transition (new level, inter-level screen)
        if response_data.get("level_transition_data"):
            transition_info = response_data["level_transition_data"]
            # Store inter-level stats and narrative for InterLevelScreen
            app.interlevel_evaded_hazards = list(self.game_logic.player.get('evaded_hazards_current_level', []))
            app.interlevel_next_level_id = transition_info.get("next_level_id")
            app.interlevel_next_start_room = transition_info.get("next_level_start_room")
            completed_level_id = transition_info.get("completed_level_id")
            app.interlevel_completed_level_name = self.game_data.LEVEL_REQUIREMENTS.get(completed_level_id, {}).get("name", "The Area")
            app.interlevel_score_for_level = self.game_logic.player.get('score', 0)
            app.interlevel_turns_taken_for_level = self.game_logic.player.get('actions_taken_this_level', 0)
            app.interlevel_evidence_found_for_level_count = len(self.game_logic.player.get('evidence_found_this_level', []))
            
            # Set appropriate narrative text based on level
            if completed_level_id == 1:
                app.interlevel_narrative_text = "The hospital's sterile corridors now behind you, the key to Bludworth's house feels like a lead weight... and your only hope."
            elif completed_level_id == 2:
                app.interlevel_narrative_text = "Bludworth's secrets are chilling, but you've survived his home. What awaits next?"
            else:
                app.interlevel_narrative_text = "You've cheated Death once more... for now."
                
            # Achievement check for level completion
            if self.achievements_system and hasattr(self.achievements_system, 'check_level_completion_achievements'):
                if completed_level_id:
                    self.achievements_system.check_level_completion_achievements(self.game_logic, completed_level_id)
            self.manager.current = 'inter_level'
            return

        # Handle direct level transition (legacy, or if not using inter-level screen)
        if response_data.get("level_transition"):
            self.handle_level_transition(response_data["level_transition"])

        # Handle death/game over
        if response_data.get("death") or self.game_logic.is_game_over:
            if self.achievements_system and hasattr(self.achievements_system, 'check_game_completion_achievements'):
                self.achievements_system.check_game_completion_achievements(self.game_logic)
            self.navigate_to_end_screen()
            return

        self.update_all_ui_elements()

    def populate_take_buttons_from_search_results(self, found_items_list, searched_furniture_name):
        """Displays buttons for taking items found during a search."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"[b]Items found in {color_text(searched_furniture_name.capitalize(), COLOR_BLUE)}:[/b]"
        
        if not found_items_list:
            self.contextual_buttons_layout.add_widget(Label(text="Nothing new to take.", size_hint_y=None, height=dp(40)))
        else:
            for item_name in found_items_list:
                btn = self.create_contextual_button(
                    text=f"Take {item_name.capitalize()}",
                    command_tuple=("take", item_name)
                )
                self.contextual_buttons_layout.add_widget(btn)
        
        done_btn = self.create_contextual_button(text="Done Searching", command_tuple=("back", None))
        self.contextual_buttons_layout.add_widget(done_btn)

    def handle_level_transition(self, transition_data):
        """Handles UI and logic for transitioning to a new level."""
        logging.info(f"UI: Handling level transition to {transition_data.get('next_level_id')}")
        
        self.output_label.text = ""  # Clear output for the new level
        self._append_to_output(transition_data.get("message", "Transitioning to a new area..."))
        
        # Display new room description
        if self.game_logic:
            self._append_to_output(self.game_logic.get_room_description())

        # Check achievements for completing the *previous* level
        if self.achievements_system and hasattr(self.achievements_system, 'check_level_completion_achievements'):
            previous_level_id = transition_data.get("completed_level_id")  # GameLogic should provide this
            if previous_level_id:
                self.achievements_system.check_level_completion_achievements(self.game_logic, previous_level_id)
        
        # Display new room description (might be redundant if already in message from GameLogic)
        if self.game_logic and self.game_logic.player:  # Ensure game_logic is still valid
            if not self.output_label.text.strip().endswith(self.game_logic.get_room_description(self.game_logic.player['location']).strip()):
                self._append_to_output(self.game_logic.get_room_description())
        
        self.update_all_ui_elements()
        self.clear_and_display_general_actions()
        next_level_id = transition_data.get("next_level_id", "unknown")
        logging.info(f"UI: Level transition to {next_level_id} UI refresh complete.")

    # --- QTE Handling Methods: Timer-Based Approach ---
    def start_qte_timer(self, qte_type, duration, qte_context=None):
        self.cancel_qte_timer()  # Ensure no old timer is running
        self.active_qte_type = qte_type
        self.qte_remaining_time = float(duration)
        self.qte_context = qte_context if qte_context else {}  # Store context for resolution
        
        self.update_qte_timer_display()
        self.qte_timer_event = Clock.schedule_interval(self._qte_countdown, 0.1)
        
        self.disable_action_buttons(True)  # Disable normal action buttons/input
        self.input_field.hint_text = self.qte_context.get("input_prompt", "TYPE QUICKLY!").upper()
        self.input_field.focus = True
        logging.info(f"UI: QTE '{qte_type}' started. Duration: {duration}s. Prompt: {self.input_field.hint_text}")

    def _qte_countdown(self, dt):
        if not self.active_qte_type:  # QTE might have been resolved by quick input
            if self.qte_timer_event: Clock.unschedule(self.qte_timer_event)
            return False

        self.qte_remaining_time -= dt
        if self.qte_remaining_time <= 0:
            self.qte_remaining_time = 0
            self.update_qte_timer_display()
            self.qte_timeout_callback() 
            return False  # Stop the interval
        self.update_qte_timer_display()
        return True 

    def cancel_qte_timer(self):
        if self.qte_timer_event:
            Clock.unschedule(self.qte_timer_event)
            self.qte_timer_event = None
        
        was_active = self.active_qte_type is not None
        self.active_qte_type = None
        self.qte_remaining_time = 0
        self.qte_context = {}
        self.update_qte_timer_display() 
        
        self.disable_action_buttons(False)  # Re-enable actions
        self.input_field.hint_text = "Or type command here..."
        
        if self.game_logic and self.game_logic.player: 
            self.game_logic.player['qte_active'] = None  # Inform GameLogic
        if was_active:
            logging.info("UI: QTE timer cancelled or resolved.")

    def qte_timeout_callback(self, *args): 
        logging.info(f"UI: QTE '{self.active_qte_type if self.active_qte_type else 'Unknown'}' timed out.")
        if self.active_qte_type: 
            # Send a special command to GameLogic to indicate timeout failure
            # GameLogic's process_player_input needs to recognize this internal signal
            self.process_command(game_data.SIGNAL_QTE_TIMEOUT) 
            # cancel_qte_timer will be called by process_command after QTE is resolved (even on timeout)
        else:  # Should not happen if active_qte_type was set
            self.cancel_qte_timer() 

    def update_qte_timer_display(self):
        if self.active_qte_type and self.qte_remaining_time > 0:
            self.qte_timer_label.text = color_text(f"TIME: {self.qte_remaining_time:.1f}s", COLOR_RED)
        else:
            self.qte_timer_label.text = ""

    # --- QTE Handling Methods: Popup-Based Approach ---
    def start_qte_popup(self, qte_type, duration, qte_context):
        """Instantiates and opens the QTEPopup."""
        if self.active_qte_popup:  # If one is already open, dismiss it first
            self.active_qte_popup.dismiss()
            self.active_qte_popup = None
        
        logging.info(f"GameScreen: Starting QTE Popup. Type: {qte_type}, Duration: {duration}, Context: {qte_context}")
        
        # Ensure context has necessary fields for QTEPopup
        qte_context.setdefault("ui_prompt_message", f"QTE: {qte_type.replace('_', ' ').title()}!")
        qte_context.setdefault("expected_input_word", "action")  # GameLogic should provide this
        qte_context.setdefault("input_type", "word")  # "word" or "button"

        self.active_qte_popup = QTEPopup(
            qte_type=qte_type,
            qte_duration=duration,
            qte_context=qte_context,
            game_screen_callback=self.resolve_qte_from_popup
        )
        self.active_qte_popup.open()
        self.disable_action_buttons(True)  # Disable background game controls
        self.input_field.focus = False  # QTEPopup's input field should get focus

    def resolve_qte_from_popup(self, qte_type, success, response, context):
        """Callback from QTEPopup when QTE is resolved (success, failure, timeout)."""
        logging.info(f"GameScreen: QTE '{qte_type}' resolved from popup. Success: {success}, Response: '{response}'")
        self.active_qte_popup = None  # Clear the reference
        self.disable_action_buttons(False)  # Re-enable game controls
        self.input_field.focus = True  # Return focus to main input

        if not self.game_logic:
            logging.error("GameScreen.resolve_qte_from_popup: game_logic is None!")
            return

        # Pass the result to GameLogic to handle consequences
        qte_result_data = self.game_logic._handle_qte_response(qte_type, response)
        
        if qte_result_data.get("message"):
            self._append_to_output(qte_result_data["message"])
        
        if qte_result_data.get("death"):
            self.navigate_to_end_screen()
        elif qte_result_data.get("level_transition_data"):  # Handle if QTE success leads to level transition
            app = App.get_running_app()
            transition_info = qte_result_data["level_transition_data"]
            app.interlevel_evaded_hazards = list(self.game_logic.player.get('evaded_hazards_current_level', []))
            # ... (copy relevant interlevel data population from process_command) ...
            self.manager.current = 'inter_level'
        
        self.update_all_ui_elements()
        self.clear_and_display_general_actions()  # Ensure UI is back to normal

    def cancel_qte_popup(self):
        """Dismisses the QTE popup if it's active."""
        if self.active_qte_popup:
            self.active_qte_popup.dismiss()  # This will trigger its internal cleanup
            self.active_qte_popup = None
        self.disable_action_buttons(False)
        self.input_field.focus = True
        if self.game_logic and self.game_logic.player: 
            self.game_logic.player['qte_active'] = None  # Inform GameLogic
        logging.info("GameScreen: QTE Popup cancelled/dismissed by GameScreen.")

    def disable_action_buttons(self, disable=True):
        # Disable main action category buttons
        for child_widget in self.main_action_buttons_layout.children:
            if isinstance(child_widget, Button):
                child_widget.disabled = disable
        # Disable contextual buttons (though they are usually cleared during QTE)
        for child_widget in self.contextual_buttons_layout.children:
            if isinstance(child_widget, Button):
                child_widget.disabled = disable
        # Disable text input field or change its behavior
        self.input_field.disabled = disable 
        if disable:
            self.input_field.text = ""  # Clear any text if disabling
            self.input_field.hint_text = "QTE Active - Use Popup!"  # Update hint when QTE is active
        else:
            self.input_field.hint_text = "Or type command here..."
            self.input_field.focus = True

    def navigate_to_end_screen(self):
        app = App.get_running_app()
        if self.game_logic and self.game_logic.player:  # Store final stats
            app.last_game_score = self.game_logic.player.get('score', 0)
            if not self.game_logic.game_won:
                # GameLogic should set a clear death message in player state or a dedicated attribute
                app.last_death_reason = self.game_logic.player.get('last_death_message', 
                                       self.game_logic.player.get('last_hazard_type', "Death's Design"))
            else:  # Game won
                app.last_death_reason = ""  # No death reason if won
        
        # Clear game-specific app state
        app.selected_character_class = None
        app.current_disaster_details = None
        app.start_new_session_flag = False  # Reset for next new game

        # Reset GameScreen state for potential new game later
        self.game_started = False
        self.game_logic = None  # Crucial: Release GameLogic instance to allow fresh start

        if hasattr(app, 'game_won_flag_for_screen_nav') and app.game_won_flag_for_screen_nav:  # Check flag from App
            self.go_to_screen('win', 'fade')  # Use a different transition for end screens
            delattr(app, 'game_won_flag_for_screen_nav')  # Consume flag
        else:
            self.go_to_screen('lose', 'fade')
        
        logging.info("Navigated to end screen. GameScreen state reset.")

    def show_inventory_with_examine_buttons(self):
        """Displays inventory items with an 'Examine' button for each."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = "[b]Your Inventory:[/b]"
        
        if not self.game_logic:
            self.contextual_buttons_layout.add_widget(Label(text="Game logic not available."))
            return

        inventory_list = self.game_logic.get_inventory_items()  # Use GameLogic method

        if not inventory_list:
            self.contextual_buttons_layout.add_widget(Label(text="Inventory is empty."))
        else:
            for item_name in inventory_list:
                item_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(5))
                
                # Determine item color
                item_master_data = self.game_logic._get_item_data(item_name)
                item_color_name = 'item'  # Default
                if item_master_data and item_master_data.get('is_evidence'): item_color_name = 'evidence'
                elif item_master_data and item_master_data.get('is_key'): item_color_name = 'special'
                
                item_label = Label(
                    text=color_text(item_name.capitalize(), item_color_name), 
                    markup=True, 
                    font_name=DEFAULT_FONT_REGULAR_NAME,
                    size_hint_x=0.7, 
                    halign='left', valign='middle'
                )
                item_label.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width * 0.95, None)))  # Allow wrapping for long names
                
                examine_btn = Button(
                    text="Examine",
                    font_name=DEFAULT_FONT_REGULAR_NAME,
                    font_size=dp(12),
                    size_hint_x=0.3,
                    on_press=lambda btn_instance, item_to_examine=item_name: self.process_command(f"examine {item_to_examine.lower()}")
                )
                item_box.add_widget(item_label)
                item_box.add_widget(examine_btn)
                self.contextual_buttons_layout.add_widget(item_box)
        
        back_btn = self.create_contextual_button(text="< Back to Actions", command_tuple=("back", None))
        self.contextual_buttons_layout.add_widget(back_btn)

    def _handle_resize(self, window, width, height):
        """Adjusts text_size of labels on window resize to ensure proper wrapping."""
        # Map Label
        if hasattr(self, 'map_label') and self.map_label.parent:  # map_label is child of map_scroll
            self.map_label.text_size = (self.map_scroll.width - dp(10), None)
        # Inventory Label
        if hasattr(self, 'inventory_content_label') and self.inventory_content_label.parent:
            self.inventory_content_label.text_size = (self.inventory_scroll.width - dp(10), None)
        # Output Label
        if hasattr(self, 'output_label') and self.output_scroll_view:
            self.output_label.text_size = (self.output_scroll_view.width - dp(16), None)
        # Title Labels (Map, Inventory, Contextual)
        for label_widget_name in ['map_title_label', 'inventory_title_label', 'contextual_label']:
            if hasattr(self, label_widget_name):
                label_instance = getattr(self, label_widget_name)
                if label_instance and label_instance.parent:
                    label_instance.text_size = (label_instance.width, None)
        # Status Bar Labels
        for label_widget_name in ['health_label', 'turns_label', 'score_label']:
            if hasattr(self, label_widget_name):
                label_instance = getattr(self, label_widget_name)
                if label_instance and label_instance.parent:
                    label_instance.text_size = (label_instance.width, None)

# --- Win Screen ---
class WinScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20),
                           # Add background for this specific screen if desired
                           # canvas_before=[Color(0.1, 0.3, 0.1, 1), Rectangle(size=self.size, pos=self.pos)]
                           )
        # self.bind(size=self._update_bg_rect, pos=self._update_bg_rect) # If adding custom bg

        layout.add_widget(Label(
            text=f"[b][color={COLOR_GREEN}]YOU SURVIVED... THIS TIME[/color][/b]", 
            markup=True, font_name=THEMATIC_FONT_NAME, font_size=dp(34) # Larger thematic font
        ))
        self.score_display = Label(text="Final Score: 0", font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(22))
        layout.add_widget(self.score_display)
        
        # Add a congratulatory message or flavor text
        flavor_text = Label(
            text="Death may have been cheated, but its shadow always lingers.\nPerhaps you've learned enough to stay one step ahead... for now.",
            font_name=DEFAULT_FONT_REGULAR_NAME, font_size=dp(16), markup=True,
            halign='center', text_size=(Window.width*0.7, None) # Enable wrapping
        )
        flavor_text.bind(width=lambda i, w: setattr(i, 'text_size', (w*0.8, None))) # Adjust text_size on width change
        layout.add_widget(flavor_text)

        btn_main_menu = Button(
            text="Return to Main Menu", font_name=DEFAULT_FONT_BOLD_NAME, 
            size_hint_y=None, height=dp(50), font_size=dp(18),
            on_release=lambda x: self.go_to_screen('title','right')
        )
        layout.add_widget(Widget(size_hint_y=0.1)) # Spacer
        layout.add_widget(btn_main_menu)
        self.add_widget(layout)

    # def _update_bg_rect(self, instance, value): # If adding custom bg
    #     if hasattr(self, 'canvas_before') and self.canvas.before.children:
    #         rect = self.canvas.before.children[-1] # Assuming Rectangle is last
    #         if isinstance(rect, Rectangle):
    #             rect.pos = instance.pos
    #             rect.size = instance.size
                
    def on_enter(self, *args):
        app = App.get_running_app()
        self.score_display.text = f"Final Score: {getattr(app, 'last_game_score', 0)}"
        # Potentially play a victory sound
        self.play_sound("win_game") 


# --- Lose Screen ---
class LoseScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        # Add a specific, darker background for the lose screen
        # with self.canvas.before:
        #     Color(0.2, 0.05, 0.05, 1) # Dark redish tone
        #     self.lose_bg_rect = Rectangle(size=self.size, pos=self.pos)
        # self.bind(size=self._update_lose_bg_rect, pos=self._update_lose_bg_rect)

        layout.add_widget(Label(
            text=f"[b][color={COLOR_RED}]DEATH HAS CLAIMED YOU[/color][/b]", 
            markup=True, font_name=THEMATIC_FONT_NAME, font_size=dp(38) # Larger thematic font
        ))
        
        self.death_reason_label = Label(
            text="Cause of Death: Unknown", 
            font_name=DEFAULT_FONT_REGULAR_NAME, font_size=dp(18), 
            markup=True, text_size=(Window.width*0.8, None), # Enable wrapping
            halign='center', padding=(0, dp(10))
        )
        self.death_reason_label.bind(width=lambda i, w: setattr(i, 'text_size', (w*0.8, None)))
        layout.add_widget(self.death_reason_label)

        # Add some flavor text for losing
        flavor_text = Label(
            text="No one escapes Death forever. Your time was up.\nPerhaps another soul will fare better... or perhaps not.",
            font_name=DEFAULT_FONT_REGULAR_NAME, font_size=dp(16), markup=True,
            halign='center', text_size=(Window.width*0.7, None)
        )
        flavor_text.bind(width=lambda i, w: setattr(i, 'text_size', (w*0.8, None)))
        layout.add_widget(flavor_text)

        btn_main_menu = Button(
            text="Return to Main Menu", font_name=DEFAULT_FONT_BOLD_NAME, 
            size_hint_y=None, height=dp(50), font_size=dp(18),
            on_release=lambda x: self.go_to_screen('title','right')
        )
        layout.add_widget(Widget(size_hint_y=0.1)) # Spacer
        layout.add_widget(btn_main_menu)
        self.add_widget(layout)
    
    # def _update_lose_bg_rect(self, instance, value): # If adding custom bg
    #     if hasattr(self, 'lose_bg_rect'):
    #         self.lose_bg_rect.pos = instance.pos
    #         self.lose_bg_rect.size = instance.size

    def on_enter(self, *args):
        app = App.get_running_app()
        reason = getattr(app, 'last_death_reason', "The design caught up with you.")
        # Ensure reason is colored if it's not already (GameLogic might pre-color it)
        if f"[color={COLOR_RED}]" not in reason: # Simple check
            reason = color_text(reason, 'error') # Use error color
        self.death_reason_label.text = f"Cause of Death:\n{reason}"
        # Potentially play a lose sound
        self.play_sound("lose_game")

# --- Achievements Screen (from new ui.py, looks good) ---
class AchievementsScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super().__init__(**kwargs)
        self.achievements_system = achievements_system
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        layout.add_widget(Label(text="[b]Achievements[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, size_hint_y=0.1, font_size=dp(24)))
        self.scroll_view = ScrollView(size_hint_y=0.8); self.grid_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.grid_layout.bind(minimum_height=self.grid_layout.setter('height')); self.scroll_view.add_widget(self.grid_layout); layout.add_widget(self.scroll_view)
        btn_back = Button(text="< Back", font_name=DEFAULT_FONT_BOLD_NAME, size_hint_y=0.1, height=dp(50), on_release=lambda x: self.go_to_screen('title', 'right'))
        layout.add_widget(btn_back); self.add_widget(layout)

    def on_enter(self, *args):
        self.grid_layout.clear_widgets()
        if self.achievements_system:
            # Sort: Unlocked first, then by name
            sorted_achievements = sorted(
                self.achievements_system.get_all_achievements(), # Use getter method
                key=lambda ach: (not ach['unlocked'], ach['name']) 
            )
            for ach_data in sorted_achievements: # ach_data is now a dict
                status_color_name = 'success' if ach_data['unlocked'] else 'error'
                icon = ach_data.get('icon', '▪') # Default icon
                text = f"{icon} [b]{ach_data['name']}[/b] ({color_text('Unlocked' if ach_data['unlocked'] else 'Locked', status_color_name)})\n   {ach_data['description']}"
                
                ach_label = Label(text=text, font_name=DEFAULT_FONT_REGULAR_NAME, markup=True, 
                                  size_hint_y=None, height=dp(70), # Fixed height for consistency
                                  halign='left', valign='top', padding=(dp(5),dp(5)))
                # Bind text_size to width for wrapping
                ach_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value - dp(10), None)))
                self.grid_layout.add_widget(ach_label)
        else:
            self.grid_layout.add_widget(Label(text="Achievements system not available.", font_name=DEFAULT_FONT_REGULAR_NAME))


# --- Journal Screen (from new ui.py, needs minor adjustments for consistency) ---
class JournalScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs): # achievements_system holds evidence
        super().__init__(**kwargs)
        self.achievements_system = achievements_system 
        
        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        main_layout.add_widget(Label(
            text="[b]Evidence Journal[/b]", markup=True, 
            font_name=DEFAULT_FONT_BOLD_NAME, size_hint_y=0.08, font_size=dp(24) # Reduced height slightly
        ))
        
        content_layout = BoxLayout(orientation='horizontal', size_hint_y=0.82, spacing=dp(10)) # Increased height slightly
        
        # Left Panel: List of Evidence
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.4, spacing=dp(5))
        left_panel.add_widget(Label(
            text="Collected Evidence:", font_name=DEFAULT_FONT_BOLD_NAME, 
            size_hint_y=None, height=dp(30), font_size=dp(16) # Added font size
        ))
        self.entry_scroll = ScrollView()
        self.entry_list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.entry_list_layout.bind(minimum_height=self.entry_list_layout.setter('height'))
        self.entry_scroll.add_widget(self.entry_list_layout)
        left_panel.add_widget(self.entry_scroll)
        content_layout.add_widget(left_panel)
        
        # Right Panel: Details of Selected Evidence
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=dp(5))
        self.details_title = Label(
            text="Select Evidence to View Details", markup=True, 
            font_name=DEFAULT_FONT_BOLD_NAME, font_size=dp(20), 
            size_hint_y=None, height=dp(35) # Adjusted height
        )
        self.details_description_scroll = ScrollView()
        self.details_description = Label(
            text="", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME, 
            font_size=dp(15), # Good readable size
            size_hint_y=None, padding=(dp(8),dp(8)), # Added padding
            halign='left', valign='top'
        )
        self.details_description.bind(width=lambda i, w: setattr(i, 'text_size', (w - dp(16), None))) # Wrapping
        self.details_description.bind(texture_size=self.details_description.setter('size')) # Fit height
        self.details_description_scroll.add_widget(self.details_description)
        right_panel.add_widget(self.details_title)
        right_panel.add_widget(self.details_description_scroll)
        content_layout.add_widget(right_panel)
        
        main_layout.add_widget(content_layout)
        
        btn_back = Button(
            text="< Back to Game", font_name=DEFAULT_FONT_BOLD_NAME, 
            size_hint_y=0.1, height=dp(50), font_size=dp(18), # Consistent font size
            on_release=lambda x: self.go_to_screen('game', 'right')
        )
        main_layout.add_widget(btn_back)
        self.add_widget(main_layout)

    def on_enter(self, *args):
        self.populate_evidence_list()
        self.details_title.text = "Select Evidence to View Details"
        self.details_description.text = "Click on an evidence item from the list to see its details here."
        self.details_description_scroll.scroll_y = 1 # Scroll to top

    def populate_evidence_list(self):
        self.entry_list_layout.clear_widgets()
        if not self.achievements_system or not self.achievements_system.evidence_collection:
            self.entry_list_layout.add_widget(Label(
                text="No evidence collected yet.", 
                font_name=DEFAULT_FONT_REGULAR_NAME, size_hint_y=None, height=dp(40)
            ))
            return
        
        # Sort evidence by found_date (most recent first, or oldest first)
        # Assuming found_date is stored as a string that can be sorted chronologically.
        # If not, conversion to datetime objects might be needed for sorting.
        try:
            sorted_evidence = sorted(
                self.achievements_system.evidence_collection.items(), 
                key=lambda item: item[1].get('found_date', str(datetime.datetime.min)), # Sort by date
                reverse=True # Most recent first
            )
        except Exception as e:
            logging.error(f"JournalScreen: Error sorting evidence: {e}")
            sorted_evidence = list(self.achievements_system.evidence_collection.items()) # Fallback to unsorted

        for ev_id, ev_data in sorted_evidence:
            btn_text = ev_data.get('name', ev_id).capitalize()
            btn = Button(
                text=btn_text, font_name=DEFAULT_FONT_REGULAR_NAME, 
                font_size=dp(14), # Slightly smaller for list items
                size_hint_y=None, height=dp(40),
                halign='left', padding_x=dp(10) # Align text left with padding
            )
            btn.bind(on_release=lambda x, eid=ev_id: self.show_evidence_details(eid))
            self.entry_list_layout.add_widget(btn)
            
    def show_evidence_details(self, evidence_id):
        evidence_data = self.achievements_system.evidence_collection.get(evidence_id, {})
        self.details_title.text = color_text(evidence_data.get('name', 'Unknown Evidence').capitalize(), 'evidence')
        
        desc = evidence_data.get('description', 'No details available for this evidence.')
        found_date_str = evidence_data.get('found_date', 'an unknown time')
        
        # Add character association if present
        character_assoc = evidence_data.get('character', None) # Assuming 'character' key from game_data.evidence
        char_info_text = ""
        if character_assoc:
            char_info_text = f"\n\n[size={int(dp(13))}sp][color={COLOR_LIGHT_GREY}]Associated with: {color_text(character_assoc, COLOR_PURPLE)}[/color][/size]"

        self.details_description.text = (
            f"[b]Description:[/b]\n{desc}\n\n"
            f"[size={int(dp(13))}sp][color={COLOR_LIGHT_GREY}]Found: {found_date_str}[/color][/size]"
            f"{char_info_text}"
        )
        self.details_description_scroll.scroll_y = 1 # Scroll to top of details

class SaveGameScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]Save Game[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, size_hint_y=0.1, font_size=dp(24)))
        
        # ScrollView for save slots
        scroll_view = ScrollView(size_hint_y=0.7) # Added ScrollView
        self.slots_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        self.slots_layout.bind(minimum_height=self.slots_layout.setter('height')) # For ScrollView
        scroll_view.add_widget(self.slots_layout)
        layout.add_widget(scroll_view)

        self.status_label = Label(text="", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME, size_hint_y=0.1, font_size=dp(16))
        layout.add_widget(self.status_label)
        
        buttons_bottom_layout = BoxLayout(size_hint_y=0.1, height=dp(50), spacing=dp(10)) # Layout for back button
        btn_back = Button(text="< Back to Game", font_name=DEFAULT_FONT_BOLD_NAME, 
                          on_release=lambda x: self.go_to_screen('game', 'right'))
        buttons_bottom_layout.add_widget(btn_back)
        layout.add_widget(buttons_bottom_layout)
        
        self.add_widget(layout)

    def on_enter(self, *args):
        self.populate_save_slots()
        self.status_label.text = "Select a slot to save or delete."

    def populate_save_slots(self):
        self.slots_layout.clear_widgets()
        slots_to_show = ["quicksave"] + [f"slot_{i}" for i in range(1, GameLogic.MAX_SAVE_SLOTS + 1)] #

        game_screen = self.manager.get_screen('game')
        if not game_screen or not game_screen.game_logic:
            self.status_label.text = color_text("Cannot access game data for save slots.", COLOR_RED)
            return

        for slot_id in slots_to_show:
            slot_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), spacing=dp(10)) #
            
            preview_info = game_screen.game_logic.get_save_slot_info(slot_id) #
            display_text = f"{slot_id.replace('_', ' ').capitalize()}"
            if preview_info:
                loc = preview_info.get('location', '?') #
                ts = preview_info.get('timestamp', 'No date') #
                char_class = preview_info.get('character_class', '') #
                turns = preview_info.get('turns_left', '') #
                display_text += f" - {char_class}, {loc} (Turns: {turns})\n   {ts}" #
                if preview_info.get("corrupted"): # Handle corrupted flag from GameLogic
                    display_text += color_text(" (Corrupted)", COLOR_RED) #
            else:
                display_text += color_text(" (Empty Slot)", COLOR_LIGHT_GREY) #

            save_btn = Button(text=display_text, markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
                              size_hint_x=0.7, halign='left', padding_x=dp(10))
            save_btn.text_size = (Window.width * 0.8 * 0.7, None)  # Adjust for button width within slot_box
            save_btn.bind(on_release=lambda x, s_id=slot_id: self.confirm_save(s_id)) #
            slot_box.add_widget(save_btn)

            delete_btn = Button(text="Del", size_hint_x=0.3, font_name=DEFAULT_FONT_BOLD_NAME)
            if not preview_info: # Disable delete if slot is empty
                delete_btn.disabled = True
            delete_btn.bind(on_release=lambda x, s_id=slot_id: self.confirm_delete_popup(s_id))
            slot_box.add_widget(delete_btn)
            
            self.slots_layout.add_widget(slot_box)

    def confirm_save(self, slot_identifier): #
        gs = self.manager.get_screen('game') #
        if gs and gs.game_logic: #
            save_response = gs.game_logic.save_game(slot_identifier) #
            self.status_label.text = save_response.get("message", "Save status unknown.") #
            if save_response.get("success"): #
                self.play_sound("save_success") #
                self.populate_save_slots() #
        else: #
            self.status_label.text = color_text("Cannot save: No active game logic.", COLOR_RED) #

    def confirm_delete_popup(self, slot_identifier):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        content.add_widget(Label(text=f"Really delete save slot '{slot_identifier.replace('_',' ').capitalize()}'?\nThis cannot be undone.",
                                 font_name=DEFAULT_FONT_REGULAR_NAME, halign='center'))
        
        buttons_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        
        yes_btn = Button(text="Yes, Delete", font_name=DEFAULT_FONT_BOLD_NAME)
        yes_btn.bind(on_release=lambda x: self.do_delete_save(slot_identifier))
        
        no_btn = Button(text="No, Cancel", font_name=DEFAULT_FONT_BOLD_NAME)
        
        buttons_layout.add_widget(yes_btn)
        buttons_layout.add_widget(no_btn)
        content.add_widget(buttons_layout)

        self.popup = Popup(title="Confirm Deletion", content=content,
                           size_hint=(0.7, 0.4), auto_dismiss=False)
        no_btn.bind(on_release=self.popup.dismiss)
        self.popup.open()

    def do_delete_save(self, slot_identifier):
        if hasattr(self, 'popup') and self.popup:
            self.popup.dismiss()
            self.popup = None

        gs = self.manager.get_screen('game')
        if gs and gs.game_logic:
            delete_response = gs.game_logic.delete_save_game(slot_identifier)
            self.status_label.text = delete_response.get("message", "Delete status unknown.")
            if delete_response.get("success"):
                self.play_sound("delete_success") # Placeholder for a sound
                self.populate_save_slots() # Refresh the list
        else:
            self.status_label.text = color_text("Cannot delete: No active game logic.", COLOR_RED)

class LoadGameScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]Load Game[/b]", markup=True, font_name=DEFAULT_FONT_BOLD_NAME, size_hint_y=0.1, font_size=dp(24)))
        
        # ScrollView for load slots (Ensure this structure is used if not already)
        scroll_view = ScrollView(size_hint_y=0.7)
        self.slots_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=None)
        self.slots_layout.bind(minimum_height=self.slots_layout.setter('height'))
        scroll_view.add_widget(self.slots_layout)
        layout.add_widget(scroll_view)

        self.status_label = Label(text="", markup=True, font_name=DEFAULT_FONT_REGULAR_NAME, size_hint_y=0.1, font_size=dp(16))
        layout.add_widget(self.status_label)
        
        # This button's text and action will be set in on_enter
        self.btn_back_dynamic = Button(
            font_name=DEFAULT_FONT_BOLD_NAME,
            size_hint_y=0.1, # Consistent with other screens
            height=dp(50)    # Consistent height
        )
        layout.add_widget(self.btn_back_dynamic)
        
        self.add_widget(layout)

    def on_enter(self, *args): 
        self.populate_load_slots()
        self.status_label.text = "Select a slot to load."

        game_screen = self.manager.get_screen('game')
        # Check if a game session is active and GameLogic is initialized in GameScreen
        if game_screen and getattr(game_screen, 'game_started', False) and getattr(game_screen, 'game_logic', None) is not None:
            self.btn_back_dynamic.text = "< Back to Game"
            self.btn_back_dynamic.unbind(on_release=None)  # Clear previous bindings
            self.btn_back_dynamic.bind(on_release=self._go_to_game_screen_action)
        else:
            self.btn_back_dynamic.text = "< Back to Title"
            self.btn_back_dynamic.unbind(on_release=None)  # Clear previous bindings
            self.btn_back_dynamic.bind(on_release=self._go_to_title_screen_action)

    def _go_to_game_screen_action(self, instance):
        """Helper method to navigate to the game screen."""
        self.go_to_screen('game', 'right')

    def _go_to_title_screen_action(self, instance):
        """Helper method to navigate to the title screen."""
        self.go_to_screen('title', 'right')
    
    def populate_load_slots(self):
        self.slots_layout.clear_widgets()
        slots_to_show = ["quicksave"] + [f"slot_{i}" for i in range(1, GameLogic.MAX_SAVE_SLOTS + 1)] #
        found_any_saves = False

        temp_game_logic = GameLogic() #

        for slot_id in slots_to_show:
            preview_info = temp_game_logic.get_save_slot_info(slot_id) #
            
            display_text = f"{slot_id.replace('_', ' ').capitalize()}"
            if preview_info:
                found_any_saves = True
                loc = preview_info.get('location', '?') #
                ts = preview_info.get('timestamp', 'No date') #
                char_class = preview_info.get('character_class', '') #
                turns = preview_info.get('turns_left', '') #
                display_text += f" - {char_class}, {loc} (Turns: {turns})\n   {ts}" #
                
                # Check for corrupted flag (as added in SaveGameScreen)
                if preview_info.get("corrupted"): #
                    display_text += color_text(" (Corrupted - Cannot Load)", COLOR_RED) #
                    btn = Label(text=display_text, markup=True, font_name=DEFAULT_FONT_REGULAR_NAME,
                                size_hint_y=None, height=dp(60),
                                halign='left', padding_x=dp(10), color=get_color_from_hex(COLOR_LIGHT_GREY)) # Make it a label
                    btn.text_size = (Window.width * 0.8, None)
                else:
                    btn = Button(text=display_text, markup=True, font_name=DEFAULT_FONT_REGULAR_NAME, 
                                 size_hint_y=None, height=dp(60),
                                 halign='left', padding_x=dp(10))
                    btn.text_size = (Window.width * 0.8, None) 
                    btn.bind(on_release=lambda x, s_id=slot_id: self.load_game_action(s_id)) #
                self.slots_layout.add_widget(btn)
            else: 
                 empty_slot_label = Label(
                     text=f"{display_text} {color_text('(Empty Slot)', COLOR_LIGHT_GREY)}", #
                     markup=True, font_name=DEFAULT_FONT_REGULAR_NAME, 
                     size_hint_y=None, height=dp(60), color=(0.7,0.7,0.7,1), #
                     halign='left', padding_x=dp(10)
                 )
                 empty_slot_label.text_size = (Window.width * 0.8, None) #
                 self.slots_layout.add_widget(empty_slot_label)

        if not found_any_saves: 
            self.slots_layout.add_widget(Label(
                text="No save games found.", font_name=DEFAULT_FONT_REGULAR_NAME, 
                size_hint_y=None, height=dp(50)
            )) #

    def load_game_action(self, slot_identifier):
        game_screen = self.manager.get_screen('game') #
        if game_screen:
            game_screen.pending_load = True #
            game_screen.load_slot_identifier = slot_identifier  #
            
            self.status_label.text = f"Preparing to load game from '{slot_identifier}'..." #
            self.play_sound("load_attempt") #
            
            Clock.schedule_once(lambda dt: self.go_to_screen('game', 'left'), 0.2) #
        else: 
            self.status_label.text = color_text("Critical Error: Game screen not found.", COLOR_RED) #

