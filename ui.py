# filepath: /home/dallas/Desktop/FD_GUI_Refactored/ui.py

from kivy.app import App
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.widget import Widget
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.text import LabelBase
from kivy.utils import get_color_from_hex # platform is not used directly here
from kivy.graphics import Color, Rectangle
from game_logic import GameLogic
import game_data
from utils import color_text, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_ORANGE, COLOR_LIGHT_GREY, COLOR_BLUE, COLOR_PURPLE, COLOR_WHITE, COLOR_MAGENTA
from achievements import AchievementsSystem
import os
import logging
import datetime
import random # For IntroScreen
import json   # For save/load operations
import os
import logging
import datetime
import random # For IntroScreen
import sys
import glob

def resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', None)
    if base_path is None:
        base_path = os.path.abspath(".")
    asset_path = os.path.join(base_path, relative_path)
    if not os.path.exists(asset_path):
        asset_path = os.path.join(base_path, "fd_terminal", relative_path)
    return asset_path

def get_random_font():
    font_dir = resource_path(r"assets\fonts")
    font_files = glob.glob(os.path.join(font_dir, "*.ttf")) + glob.glob(os.path.join(font_dir, "*.otf"))
    if not font_files:
        # Fallback to default if no fonts found
        font_path = resource_path(r"assets\fonts\Bloody_Mary.ttf")
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font file not found at: {font_path}")
        return "Bloody_Mary", font_path
    font_path = random.choice(font_files)
    font_name = os.path.splitext(os.path.basename(font_path))[0]
    LabelBase.register(name=font_name, fn_regular=font_path)
    return font_name, font_path

LabelBase.register(
    name="RobotoMono-Bold",
    fn_regular=resource_path(r"assets\fonts\RobotoMono-Bold.ttf")
)

RANDOM_FONT_NAME, RANDOM_FONT_PATH = get_random_font()

from kivy.core.text import LabelBase
DEFAULT_FONT = "RobotoMono-Bold"  # Or whatever font you registered
font_path = resource_path(r"assets/fonts/RobotoMono-Bold.ttf")
print("Resolved font path:", font_path)
LabelBase.register(name=DEFAULT_FONT, fn_regular=font_path)

# --- Base Screen with Background ---
class BaseScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.05, 0.05, 0.05, 1) 
            self.rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size

    def go_to_screen(self, screen_name, direction='left'):
        self.manager.transition.direction = direction
        self.manager.current = screen_name

    def play_sound(self, sound_name):
        # app = App.get_running_app()
        # if hasattr(app, 'sound_manager'): app.sound_manager.play(sound_name)
        pass

# --- Title Screen ---
class TitleScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super().__init__(**kwargs)
        self.achievements_system = achievements_system # Passed from App
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        title_label = Label(
            text="[b][color=ffffff]Final Destination[/color] [color=ff2222]Terminal[/color][/b]",
            font_name=RANDOM_FONT_NAME,
            font_size='60sp',
            markup=True,
            size_hint_y=None,
            height=dp(100),
            halign='center',
            valign='middle'
        ) 
        layout.add_widget(title_label)
        
        def update_text_size(instance, value):
            instance.text_size = (instance.width, None)
        title_label.bind(width=update_text_size)

        buttons_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(300))
        btn_new_game = Button(text="New Game", font_name=DEFAULT_FONT, font_size='20sp', on_release=self.start_new_game_flow)
        btn_load_game = Button(text="Load Game", font_name=DEFAULT_FONT, font_size='20sp', on_release=lambda x: self.go_to_screen('load_game'))
        btn_achievements = Button(text="Achievements", font_name=DEFAULT_FONT, font_size='20sp', on_release=lambda x: self.go_to_screen('achievements'))
        btn_tutorial = Button(text="How to Play", font_name=DEFAULT_FONT, font_size='20sp', on_release=lambda x: self.go_to_screen('tutorial'))
        btn_exit = Button(text="Exit Game", font_name=DEFAULT_FONT, font_size='20sp', on_release=App.get_running_app().stop)
        buttons_layout.add_widget(btn_new_game); buttons_layout.add_widget(btn_load_game); buttons_layout.add_widget(btn_achievements); buttons_layout.add_widget(btn_tutorial); buttons_layout.add_widget(btn_exit)
        
        layout.add_widget(BoxLayout(size_hint_y=0.2)); layout.add_widget(buttons_layout); layout.add_widget(BoxLayout(size_hint_y=0.3))
        self.add_widget(layout)

    def start_new_game_flow(self, instance):
        game_screen = self.manager.get_screen('game')
        if game_screen and hasattr(game_screen, 'prepare_new_game_session'):
            game_screen.prepare_new_game_session() # Initialize a fresh GameLogic instance
        self.go_to_screen('intro', direction='right') # Or character_select

# --- Character Select Screen ---
class CharacterSelectScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]Select Your Character[/b]", markup=True, font_name=DEFAULT_FONT, font_size='24sp', size_hint_y=0.2))
        btn_journalist = Button(text="Journalist (Default)", font_name=DEFAULT_FONT, on_release=lambda x: self.select_character("Journalist"))
        btn_emt = Button(text="EMT (More Health)", font_name=DEFAULT_FONT, on_release=lambda x: self.select_character("EMT"))
        btn_detective = Button(text="Detective (More Perception)", font_name=DEFAULT_FONT, on_release=lambda x: self.select_character("Detective"))
        btn_medium = Button(text="Medium (More Intuition)", font_name=DEFAULT_FONT, on_release=lambda x: self.select_character("Medium"))
        layout.add_widget(btn_journalist)
        layout.add_widget(btn_emt)
        layout.add_widget(btn_detective)
        layout.add_widget(btn_medium)
        btn_back = Button(text="Back to Title", size_hint_y=None, height=dp(50), font_name=DEFAULT_FONT, on_release=lambda x: self.go_to_screen('title', 'right'))
        layout.add_widget(btn_back)
        self.add_widget(layout)

    def select_character(self, char_class):
        app = App.get_running_app()
        app.selected_character_class = char_class
        game_screen = self.manager.get_screen('game')
        if game_screen and hasattr(game_screen, 'prepare_new_game_session'):
             game_screen.prepare_new_game_session(character_class=char_class)
        self.go_to_screen('intro', direction='left')

# --- Intro Screen ---
class IntroScreen(BaseScreen):
    """Displays the introductory story text for the game."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logging.info("IntroScreen initializing")
        
        # We'll initialize this in on_enter to ensure it exists when needed
        self.game_logic = None
        
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))

        intro_title = Label(
            text="The Premonition...",
            font_size=dp(30),
            size_hint_y=None,
            height=dp(40),
            font_name=DEFAULT_FONT,
            color=get_color_from_hex("#" + COLOR_RED)
        )
        layout.add_widget(intro_title)

        self.intro_text_label = Label(
            text="Loading premonition...",
            markup=True,
            valign='top',
            halign='center',
            font_name=DEFAULT_FONT,
            font_size='18sp',
            padding=(dp(10), dp(10)),
            size_hint_y=None
        )
        # Bind both size and texture_size to update height and wrapping
        self.intro_text_label.bind(
            texture_size=self._update_intro_label_height,
            width=self._update_intro_label_text_size
        )

        scroll_view = ScrollView(size_hint=(1, 1))
        scroll_view.add_widget(self.intro_text_label)
        layout.add_widget(scroll_view)

        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(60), padding=(0, dp(10)))
        button_layout.add_widget(Widget(size_hint_x=0.3)) # Spacer
        self.continue_button = Button(
            text="Continue to the House...",
            size_hint=(0.4, None), # Relative width
            height=dp(50), # Fixed height
            font_name=DEFAULT_FONT,
            font_size=dp(16)
        )
        self.continue_button.bind(on_press=self.proceed_to_game)
        button_layout.add_widget(self.continue_button)
        button_layout.add_widget(Widget(size_hint_x=0.3)) # Spacer
        layout.add_widget(button_layout)

        self.add_widget(layout)

    def _update_intro_label_height(self, instance, value):
        # Set the label's height to fit its content
        instance.height = instance.texture_size[1]

    def _update_intro_label_text_size(self, instance, value):
        # Set the label's text_size to its width for wrapping
        instance.text_size = (instance.width - dp(20), None)

    def on_enter(self, *args):
        """Generate the intro text when the screen is entered"""
        # Get GameLogic reference from the GameScreen if possible
        game_screen = self.manager.get_screen('game')
        if game_screen and hasattr(game_screen, 'game_logic') and game_screen.game_logic:
            self.game_logic = game_screen.game_logic
        else:
            # Create temporary instance just for data access if needed
            self.game_logic = GameLogic()
            
        # Generate and set the intro text
        self.intro_text_label.text = self.generate_intro_text()
        
        # Save disaster details to app for later use
        self._save_disaster_details_to_app()
        
    def _save_disaster_details_to_app(self):
        """Save disaster details to app for use in the game"""
        app = App.get_running_app()
        
        # Get disaster data
        gd = game_data  # Using imported module directly
        if not hasattr(gd, 'disasters') or not gd.disasters:
            logging.warning("No disaster data found in game_data")
            return
            
        chosen_disaster_key = random.choice(list(gd.disasters.keys()))
        disaster_info = gd.disasters[chosen_disaster_key]
        chosen_visionary = random.choice(gd.visionaries) if hasattr(gd, 'visionaries') and gd.visionaries else "a mysterious figure"
        
        # Get warning from disaster info
        warnings = disaster_info.get("warnings", ["Watch out!"])
        warning = random.choice(warnings) if warnings else "Watch out!"
        
        # Get killed count
        killed_count_val = disaster_info.get("killed_count", 0)
        if callable(killed_count_val):
            killed_count_val = killed_count_val()
        elif isinstance(killed_count_val, tuple) and len(killed_count_val) == 2:
            killed_count_val = random.randint(killed_count_val[0], killed_count_val[1])
        
        # Handle survivor fates
        survivor_fate_list = []
        # Check for survivor_fates array in game_data
        if hasattr(gd, 'survivor_fates'):
            survivor_fate_list = gd.survivor_fates
        # If no survivor_fates array exists, create some defaults
        else:
            survivor_fate_list = [
                "drowned in a freak accident",
                "killed by falling debris",
                "found dead in mysterious circumstances", 
                "disappeared without a trace",
                "died in suspicious accidents"
            ]
            
        # Format multiple fates together
        num_fates = random.randint(1, min(3, len(survivor_fate_list)))
        selected_fates = random.sample(survivor_fate_list, num_fates)
        formatted_fates = ", ".join(selected_fates[:-1]) + f", and {selected_fates[-1]}" if len(selected_fates) > 1 else selected_fates[0]
        
        # Store in app for later reference
        app.current_disaster_details = {
            "event_description": chosen_disaster_key,
            "full_description_template": disaster_info.get("description", ""),
            "visionary": chosen_visionary,
            "warning": warning,
            "killed_count": killed_count_val,
            "survivor_fates": formatted_fates
        }
        
    def proceed_to_game(self, instance):
        """Switches to the 'game' screen."""
        self.go_to_screen('game', direction='left')  # GameScreen's on_enter will handle session start

    def generate_intro_text(self):
        """Generates the dynamic introductory text for the game."""
        gd = game_data  # Using imported module directly

        # Use COLOR_RED instead of the default "warning" style
        intro_base = (
            f"Welcome to McKinley, population: {color_text('dropping like flies.', 'error')}\n\n"
            "Local tales speak of numerous accidental deaths, murders, and suicides attributed to something called 'Death's List'. "
            "It was always nonsense to you. Past tense.\n\n"
            "You've just arrived at the abandoned residence of one William Bludworth - who has not been seen in some time, "
            "but it is said he held evidence proving Death was a force of nature out to claim survivors of multiple casualty disasters. "
            "If anyone could have given answers, it was him. Maybe there's still a chance."
        )

        # Error handling if no disaster data is available
        if not hasattr(gd, 'disasters') or not gd.disasters:
            logging.warning("No disaster data found in game_data")
            return f"{intro_base}\n\n{color_text('[Error: No disaster data found.]', 'error')}"

        chosen_disaster_key = random.choice(list(gd.disasters.keys()))
        disaster_data = gd.disasters[chosen_disaster_key]

        killed_count_val = disaster_data.get('killed_count', 0)
        chosen_visionary = random.choice(gd.visionaries) if gd.visionaries else "a mysterious figure"
        disaster_warnings = disaster_data.get('warnings', [])
        chosen_warning = random.choice(disaster_warnings) if disaster_warnings else "Look out!"

        # Handle survivor fates
        survivor_fate_list = []
        # Check for survivor_fates array in game_data
        if hasattr(gd, 'survivor_fates'):
            survivor_fate_list = gd.survivor_fates
        # If no survivor_fates array exists, create some defaults
        else:
            survivor_fate_list = [
                "drowned in a freak accident",
                "killed by falling debris",
                "found dead in mysterious circumstances", 
                "disappeared without a trace",
                "died in suspicious accidents"
            ]
            
        # Format multiple fates together
        num_fates = random.randint(1, min(3, len(survivor_fate_list)))
        selected_fates = random.sample(survivor_fate_list, num_fates)
        formatted_fates = ", ".join(selected_fates[:-1]) + f", and {selected_fates[-1]}" if len(selected_fates) > 1 else selected_fates[0]

        disaster_description_template = disaster_data.get("description", "A terrible disaster occurred.")
        try:
            formatted_disaster_description = disaster_description_template.format(
                visionary=color_text(chosen_visionary, 'special'),
                warning=color_text(chosen_warning, 'warning'),
                killed_count=color_text(str(killed_count_val), 'warning'),
                survivor_fates=color_text(formatted_fates, 'item')
            )
        except KeyError as e:
            logging.warning(f"Missing placeholder in disaster description for '{chosen_disaster_key}': {e}")
            formatted_disaster_description = disaster_description_template

        full_intro = (
            f"{intro_base}\n\n"
            f"You're so invested now because, as fate would have it, you recently walked away from {color_text(chosen_disaster_key, 'special')} ended many lives.\n\n"
            f"{formatted_disaster_description}\n\nNow, even the person who saved you is gone; you're the last one left.\n\n"
            f"Your goal is to find {color_text('ANY', 'error')} evidence related to people who saw Death coming before your own time runs out. Somebody out there HAD to find an answer that will help you stay alive..right?\n\n"
            "You have a limited number of turns before dawn.\n"
            f"Type '{color_text('list', 'command')}' or use the buttons to see available actions.\n\n"
            f"{color_text('Explore the grounds, interact with objects or examine the things you find to learn their connection to Final Destination, and watch your step!', 'info')}\n\n"
            f"{color_text('Good luck...', 'special')}"
        )
        
        return full_intro

# --- Tutorial Screen ---
class TutorialScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # ... (Your existing Tutorial Screen layout and text - ensure font_name=DEFAULT_FONT is used) ...
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]How to Play[/b]", markup=True, font_name=DEFAULT_FONT, font_size='24sp', size_hint_y=0.1))
        tutorial_text = (
            "Welcome!\n\n"
            "- Type commands: 'move north', 'examine table', 'take key'.\n"
            "- Use action buttons for common interactions.\n"
            "- Goal: Find evidence and survive each level.\n"
            "- HP: Your health. Turns: Actions left.\n"
            "- Beware of hazards! They can change, interact, or be fatal.\n"
            "- Use 'help' for commands. Access 'Journal' for evidence.\n"
            "- Save/Load via Menu (Title Screen)."
        )
        scroll_view = ScrollView(size_hint_y=0.8); scroll_label = Label(text=tutorial_text, font_name=DEFAULT_FONT, font_size='16sp', markup=False, size_hint_y=None, text_size=(Window.width*0.85, None), halign='left', valign='top')
        scroll_label.bind(texture_size=scroll_label.setter('size')); scroll_view.add_widget(scroll_label); layout.add_widget(scroll_view)
        btn_back = Button(text="Back to Title", size_hint_y=0.1, height=dp(50), font_name=DEFAULT_FONT, on_release=lambda x: self.go_to_screen('title', 'right'))
        layout.add_widget(btn_back); self.add_widget(layout)

class GameScreen(Screen):
    def __init__(self, achievements_system=None, **kwargs):
        super(GameScreen, self).__init__(**kwargs)
        logging.info("GameScreen initializing with new layout")
        self.game_logic = GameLogic()
        self.achievements_system = achievements_system
        self.game_started = False
        self.pending_load = False
        self.load_slot = 1 
        self.selected_action = None
        self.selected_use_item = None
        self.qte_timer_event = None
        self.active_qte_type = None 
        self.qte_remaining_time = 0

        # Use self.get_valid_directions instead of self.game_logic.get_valid_directions
        self.contextual_target_generators = {
            "move": self.get_valid_directions,
            "examine": self.get_examinable_targets_in_room,
            "take": self.get_takeable_items_in_room, 
            "search": self.get_searchable_furniture_in_room,
            "use": self.get_usable_inventory_items,
            "drop": self.get_inventory_items,
            "unlock": self.get_unlockable_targets
    }

        root_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(5))
        main_split = BoxLayout(orientation='horizontal', spacing=dp(10), size_hint_y=1)

        # --- LEFT SIDE PANEL (Vertical) ---
        left_panel = BoxLayout(orientation='vertical', spacing=dp(8), size_hint_x=0.45)
        self.qte_timer_label = Label(text="", font_name=DEFAULT_FONT, markup=True, size_hint_y=None, height=dp(30))

        # Map (Expanded)
        map_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.4) 
        self.map_title_label = Label(text="Map:", size_hint_y=None, height=dp(20), halign='left', valign='middle', bold=True)
        self.map_title_label.bind(size=self.map_title_label.setter('text_size'))
        self.map_label = Label(
            text="...", markup=True, font_name='RobotoMono-Bold', font_size=dp(12), 
            valign='top', halign='left', padding=(dp(5),dp(5)), size_hint_y=None
        )
        self.map_label.bind(texture_size=self.map_label.setter('size'))
        map_scroll = ScrollView(size_hint=(1,1)); map_scroll.add_widget(self.map_label)
        map_outer_layout.add_widget(self.map_title_label); map_outer_layout.add_widget(map_scroll)
        left_panel.add_widget(map_outer_layout)
        map_scroll.bind(width=lambda instance, width_val: setattr(self.map_label, 'text_size', (width_val - dp(10), None)))

        # Inventory (Adjusted height)
        inventory_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.25) 
        self.inventory_title_label = Label(text="Inventory:", size_hint_y=None, height=dp(20), halign='left', valign='middle', bold=True)
        self.inventory_title_label.bind(size=self.inventory_title_label.setter('text_size'))
        self.inventory_content_label = Label(text="Empty", markup=True, valign='top', halign='left', padding=(dp(5),0), size_hint_y=None)
        self.inventory_content_label.bind(texture_size=self.inventory_content_label.setter('size'))
        inventory_scroll = ScrollView(size_hint=(1,1)); inventory_scroll.add_widget(self.inventory_content_label)
        inventory_outer_layout.add_widget(self.inventory_title_label); inventory_outer_layout.add_widget(inventory_scroll)
        left_panel.add_widget(inventory_outer_layout)
        inventory_scroll.bind(width=lambda instance, width_val: setattr(self.inventory_content_label, 'text_size', (width_val - dp(10), None)))

        # Contextual Actions
        contextual_outer_layout = BoxLayout(orientation='vertical', size_hint_y=0.2) 
        self.contextual_label = Label(text="Actions:", markup=True, size_hint_y=None, height=dp(20), halign='left', valign='middle', bold=True)
        self.contextual_label.bind(size=self.contextual_label.setter('text_size'))
        self.contextual_buttons_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(2), padding=(0,dp(2)))
        self.contextual_buttons_layout.bind(minimum_height=self.contextual_buttons_layout.setter('height'))
        contextual_buttons_scroll = ScrollView(size_hint=(1,1)); contextual_buttons_scroll.add_widget(self.contextual_buttons_layout)
        contextual_outer_layout.add_widget(self.contextual_label); contextual_outer_layout.add_widget(contextual_buttons_scroll)
        left_panel.add_widget(contextual_outer_layout)

        # Main Action Buttons (Fixed height)
        main_action_buttons_scroll = ScrollView(size_hint=(1, None), height=dp(50), do_scroll_y=False, do_scroll_x=True)
        action_layout = BoxLayout(orientation='horizontal', size_hint_x=None, spacing=dp(5), padding=(dp(5), dp(5)))
        action_layout.bind(minimum_width=action_layout.setter('width'))
        action_buttons_config = [
            ("Move", self.on_main_action_button_press), ("Examine", self.on_main_action_button_press),
            ("Take", self.on_main_action_button_press), ("Search", self.on_main_action_button_press),
            ("Use", self.on_main_action_button_press), ("Drop", self.on_main_action_button_press),
            ("Unlock", self.on_main_action_button_press),
            ("Inventory", self.on_main_action_button_press), 
            ("List", self.on_main_action_button_press), 
            ("Save", self.on_main_action_button_press), ("Load", self.on_main_action_button_press),
            ("Main Menu", self.on_main_action_button_press)
        ]
        for text, callback in action_buttons_config:
            btn = Button(text=text, size_hint_x=None, width=dp(85), on_press=callback, font_size=dp(12))
            action_layout.add_widget(btn)
        main_action_buttons_scroll.add_widget(action_layout)
        left_panel.add_widget(main_action_buttons_scroll)

        # Input Field (Fixed height)
        self.input_field = TextInput(hint_text="Or type command...", multiline=False, size_hint_y=None, height=dp(40), font_size=dp(14))
        self.input_field.bind(on_text_validate=self.process_input_from_text_field)
        left_panel.add_widget(self.input_field)

        # --- RIGHT SIDE PANEL (Vertical) ---
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.55, spacing=dp(5)) 

        # Status Bar (Moved to Right Panel)
        status_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(30), spacing=dp(10))
        self.turns_label = Label(text="Turns: --", markup=True, size_hint_x=0.5, halign='left', valign='middle') 
        self.score_label = Label(text="Score: 0", markup=True, size_hint_x=0.5, halign='right', valign='middle') 
        self.health_label = Label(text="Health: --", markup=True, size_hint_x=0.5, halign='center', valign='middle')
        self.health_label.bind(size=self.health_label.setter('text_size'))
        status_layout.add_widget(self.health_label)
        for label in [self.turns_label, self.score_label]:
            label.bind(size=label.setter('text_size'))
            status_layout.add_widget(label)
        right_panel.add_widget(status_layout) 

        # Output ScrollView
        self.output_label = Label(
            text="Initializing game...\n", markup=True, size_hint_y=None,
            valign='top', halign='left', padding=(dp(5), dp(5))
        )
        self.output_label.bind(texture_size=self.output_label.setter('size'))
        self.output_scroll_view = ScrollView(size_hint_y=1) 
        self.output_scroll_view.add_widget(self.output_label)
        self.output_scroll_view.bind(width=lambda instance, width_val: setattr(self.output_label, 'text_size', (width_val - dp(10), None)))
        right_panel.add_widget(self.output_scroll_view) 

        main_split.add_widget(left_panel)
        main_split.add_widget(right_panel) 
        root_layout.add_widget(main_split)
        self.add_widget(root_layout)
        Window.bind(on_resize=self._handle_resize)
        self.clear_and_display_general_actions()

        self.dynamic_actions_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(2), padding=(0, dp(2)))
        self.dynamic_actions_layout.bind(minimum_height=self.dynamic_actions_layout.setter('height'))

    # --- UI Helper Methods ---
    def get_valid_directions(self):
        """Gets valid movement directions from current room."""
        if not self.game_logic or not self.game_logic.player:
            return []
            
        current_room = self.game_logic.player.get('location')
        room_data = self.game_logic.get_room_data(current_room)
        return list(room_data.get("exits", {}).keys()) if room_data else []

    def _get_current_room_data(self):
        """Helper method to get the current room data from game logic."""
        if not self.game_logic:
            return None
            
        # Get current room from game_logic
        current_room = self.game_logic.player.get('location')
        if not current_room:
            return None
            
        # Get room data using game_logic's method
        return self.game_logic.get_room_data(current_room)

    def get_examinable_targets_in_room(self):
        room_data = self._get_current_room_data()
        if not room_data or not self.game_logic or not hasattr(self.game_logic, 'items'): 
            return []
            
        targets = set() # Use set to avoid duplicates
        targets.update(room_data.get("objects", []))
        targets.update([f["name"] for f in room_data.get("furniture", []) 
                    if isinstance(f, dict) and "name" in f])
        
        # Add visible or revealed items
        current_room_name = self.game_logic.player.get('location')
        revealed_here = getattr(self.game_logic, 'revealed_items_in_rooms', {}).get(current_room_name, set())
        
        for item_name, item_data in self.game_logic.items.items():
            if item_data.get('location') == current_room_name:
                is_revealed = item_name in revealed_here
                is_directly_visible = not item_data.get('container') and not item_data.get('is_hidden', False)
                if (is_revealed or is_directly_visible) and item_name not in self.game_logic.player.get('inventory', []):
                    targets.add(item_name)
                    
        return sorted(list(targets)) # Return sorted list

    def get_unlockable_targets(self):
        """Returns a list of locked doors/furniture names the player might unlock."""
        targets = set()
        current_room_data = self._get_current_room_data()
        inventory = self.player.get('inventory', [])
        available_keys = {item for item in inventory if self._get_item_data(item).get("is_key")}

        if not current_room_data or not available_keys:
            return []

        # Check locked exits
        for direction, dest_room_name in current_room_data.get("exits", {}).items():
            dest_room_data = self.rooms.get(dest_room_name)
            if dest_room_data and dest_room_data.get("locked"):
                 # Check if player has the key for this destination room name
                 if any(self._get_item_data(key_name).get("unlocks", "").lower() == dest_room_name.lower() for key_name in available_keys):
                      targets.add(direction.capitalize()) # Add the direction

        # Check locked furniture
        for furn_dict in current_room_data.get("furniture", []):
            if isinstance(furn_dict, dict) and furn_dict.get("locked"):
                furn_name = furn_dict["name"]
                # Check if player has the key for this furniture name
                if any(self._get_item_data(key_name).get("unlocks", "").lower() == furn_name.lower() for key_name in available_keys):
                     targets.add(furn_name.capitalize()) # Add the furniture name

        return sorted(list(targets))

    def get_takeable_items_in_room(self):
        takeable = set() # Use set
        
        # Safety check if game_logic exists and has required attributes
        if not self.game_logic:
            return []
            
        room_name = self.game_logic.player.get('location', '')
        room_data = self._get_current_room_data()
        
        # Check if we have valid room data and items data
        if not room_data or not hasattr(self.game_logic, 'items') or self.game_logic.items is None:
            return []
            
        # Check room objects first
        for obj_name in room_data.get("objects", []):
            item_data = self.game_logic._get_item_data(obj_name)
            if item_data and item_data.get("takeable") and obj_name not in self.game_logic.player.get('inventory', []):
                takeable.add(obj_name)
                
        # Check revealed items
        revealed_items = getattr(self.game_logic, 'revealed_items_in_rooms', {}).get(room_name, set())
        for item_name in revealed_items:
            item_data = self.game_logic._get_item_data(item_name)
            if item_data and item_data.get('location') == room_name and \
            item_data.get('takeable') and item_name not in self.game_logic.player.get('inventory', []):
                takeable.add(item_name)
                
        return sorted(list(takeable)) # Return sorted list

    def get_searchable_furniture_in_room(self):
        room_data = self._get_current_room_data()
        if not room_data: return []
        # Use the imported module directly
        container_list = getattr(game_data, 'container_furniture', [])
        return sorted([f["name"] for f in room_data.get("furniture", [])
                if isinstance(f, dict) and f.get("name") in container_list])

    def get_usable_inventory_items(self):
         inventory = self.player.get("inventory", [])
         usable = []
         if self.items is None: return []
         for item_name in inventory:
              item_data = self._get_item_data(item_name)
              if item_data and item_data.get("use_on"): # Check if 'use_on' exists and is not empty/None
                   usable.append(item_name)
         return sorted(usable)

    def get_inventory_items(self):
        return sorted(list(self.player.get("inventory", [])))

    def get_possible_actions(self):
        """Generates a formatted string of possible actions and targets."""
        room_data = self._get_current_room_data()
        if not room_data or self.items is None: return "No actions available."

        actions_dict = {}
        # Populate actions based on helper methods
        valid_moves = self.get_valid_directions()
        if valid_moves: actions_dict["Move"] = valid_moves # Use capitalized verb for display
        examinable = self.get_examinable_targets_in_room()
        if examinable: actions_dict["Examine"] = examinable
        takeable = self.get_takeable_items_in_room()
        if takeable: actions_dict["Take"] = takeable
        searchable_furn = self.get_searchable_furniture_in_room()
        if searchable_furn: actions_dict["Search"] = searchable_furn
        # Use action requires items in inventory that have 'use_on' defined
        usable_items = self.get_usable_inventory_items()
        if usable_items: actions_dict["Use"] = usable_items # Show items you *can* use
        # Drop action requires items in inventory
        inventory_items = self.get_inventory_items()
        if inventory_items: actions_dict["Drop"] = inventory_items

        # Unlock logic (can be simplified using helper methods)
        unlock_targets = set()
        available_keys = {item for item in inventory_items if self._get_item_data(item).get("is_key")}

        # Check locked exits
        for direction, dest_room_name in room_data.get("exits", {}).items():
             dest_room_data = self.rooms.get(dest_room_name)
             if dest_room_data and dest_room_data.get("locked"):
                  for key_name in available_keys:
                       if self._get_item_data(key_name).get("unlocks", "").lower() == dest_room_name.lower():
                            unlock_targets.add(direction) # Add the direction/exit name
                            break # Found a key for this exit

        # Check locked furniture
        for furn_dict in room_data.get("furniture", []):
             if isinstance(furn_dict, dict) and furn_dict.get("locked"):
                  furn_name = furn_dict["name"]
                  for key_name in available_keys:
                       if self._get_item_data(key_name).get("unlocks", "").lower() == furn_name.lower():
                            unlock_targets.add(furn_name) # Add the furniture name
                            break # Found a key for this furniture

        if unlock_targets: actions_dict["Unlock"] = sorted(list(unlock_targets))

        # Format output string
        output_lines = [color_text("You can:", "info")]
        for verb, targets in actions_dict.items():
             if targets: # Only add if there are targets for the action
                  # Capitalize targets for display
                  capitalized_targets = [str(t).capitalize() for t in targets]
                  output_lines.append(f"  {color_text(verb, 'special')}: {', '.join(capitalized_targets)}")

        return "\n".join(output_lines) if len(output_lines) > 1 else "No specific actions available right now."

    def _handle_resize(self, window, width, height):
        """Force update text sizes on window resize. Ensures all labels re-wrap properly."""
        # Output label (main text area)
        if hasattr(self, 'output_scroll_view') and self.output_scroll_view and hasattr(self, 'output_label'):
            self.output_label.text_size = (self.output_scroll_view.width - dp(10), None)

        # Map label
        if hasattr(self, 'map_label') and self.map_label and self.map_label.parent:
            self.map_label.text_size = (self.map_label.parent.width - dp(10), None)

        # Inventory content label
        if hasattr(self, 'inventory_content_label') and self.inventory_content_label and self.inventory_content_label.parent:
            self.inventory_content_label.text_size = (self.inventory_content_label.parent.width - dp(10), None)

        # List of labels to update using their own width (status bar, etc.)
        own_width_labels = ['turns_label', 'score_label', 'health_label']
        for name in own_width_labels:
            label = getattr(self, name, None)
            if label and label.parent:
                label.text_size = (label.width - dp(5), None)

        # List of labels to update using their parent width (section titles, etc.)
        parent_width_labels = ['inventory_title_label', 'contextual_label', 'map_title_label']
        for name in parent_width_labels:
            label = getattr(self, name, None)
            if label and label.parent:
                label.text_size = (label.parent.width - dp(5), None)
                
    def _update_output_label_text_size(self, instance, size):
        """Dynamically update output_label's text_size for wrapping."""
        self.output_label.text_size = (size[0] - dp(10), None)

    def prepare_new_game_session(self, character_class=None):
        """Instantiates GameLogic for a new game. Called before intro/game screen."""
        self.game_logic = GameLogic(achievements_system=self.achievements_system)
        self.player = None
        app = App.get_running_app()
        # Use character class from app if passed, else default
        if not character_class:
            character_class = "Journalist"
        self.player = game_data.get_initial_player_state(character_class)
        
    def start_new_game_session_from_load(self, load_slot):
        """Instantiates GameLogic and loads a game state."""
        if not self.game_logic: # Ensure game_logic instance exists
            self.game_logic = GameLogic(achievements_system=self.achievements_system)
            # A fresh GameLogic is made, then load_game_state overwrites its state.
        
        load_response = self.game_logic.load_game_state(load_slot)
        if load_response["success"]:
            self.output_label.text = "" # Clear previous game's output
            self.update_ui(load_response["message"]) # Display loaded room
        else:
            self.update_ui(color_text(f"Failed to load game: {load_response['message']}", "error"))
            self.prepare_new_game_session() # Start fresh if load fails
            self.output_label.text = ""
            self.update_ui(f"Starting a new game instead.\n{self.game_logic.get_room_description()}")
        
        self.on_game_session_ready() # Final UI updates

    def process_input_from_text_field(self, instance):
        """Processes command from the text input field."""
        command = instance.text.strip()
        if getattr(self, 'endgame_qte_active', False):
            if command.lower() == "dodge!":
                self.finish_endgame_qte(success=True)
            else:
                self.update_ui("[color=ff2222]That's not the right word! Type 'dodge!'![/color]")
            instance.text = ""
            return
        if command:
            self.process_command(command)
        instance.text = "" # Clear input field

    def clear_and_display_general_actions(self):
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = "What will you do?"
        self.selected_action = None
        self.selected_use_item = None

    def update_map_display(self):
        """Gets the map string from game logic and updates the map label."""
        if self.game_logic:
            map_area_width = Window.width * 0.45 - dp(30) # Adjusted for 45% width
            char_width_pixels = dp(11) * 0.6
            map_width_chars = max(20, int(map_area_width / char_width_pixels)) # Ensure minimum width
            map_height_lines = 12 # Corresponds roughly to dp(220) height
            map_string = self.game_logic.get_gui_map_string(width=map_width_chars, height=map_height_lines)
            self.map_label.text = map_string
        else: self.map_label.text = "Map data unavailable."

    def on_enter(self, *args):
        super().on_enter(*args)
        app = App.get_running_app()
        
        # If game_logic isn't set up (e.g., direct navigation or returning from a full app restart path)
        # Or if we intend to always start a fresh session context when GameScreen is entered after title flow.
        if not self.game_logic or getattr(app, 'start_new_session_flag', False):
            logging.info("GameScreen on_enter: GameLogic not found or new session flagged.")
            character_class = getattr(app, 'selected_character_class', None)
            disaster_details = getattr(app, 'current_disaster_details', None)
            
            if not self.game_logic: # Only create new if absolutely no instance exists
                 self.game_logic = GameLogic(achievements_system=self.achievements_system)
            
            self.game_logic.start_new_game(character_class=character_class)
            if disaster_details:
                self.game_logic.player['disaster_context'] = disaster_details
            
            self.output_label.text = "" # Clear previous output for a truly new game
            initial_desc = self.game_logic.get_room_description()
            first_entry_text = self.game_logic.get_room_data().get("first_entry_text", "")
            full_initial_message = f"{initial_desc}"
            # Check if this is indeed the very first entry into this specific room for this session
            if first_entry_text and self.game_logic.player['location'] not in self.game_logic.player.get("visited_rooms_first_text", set()):
                 full_initial_message += f"\n\n{color_text(first_entry_text, 'special')}"
                 self.game_logic.player.setdefault("visited_rooms_first_text", set()).add(self.game_logic.player['location'])
            self.update_ui(full_initial_message)
            
            if hasattr(app, 'start_new_session_flag'):  # Ensure proper indentation and structure
                delattr(app, 'start_new_session_flag')  # Consume the flag
                delattr(app, 'start_new_session_flag') # Consume the flag
        
        self.on_game_session_ready()

    def on_main_action_button_press(self, instance):
        """Handles presses of the primary action buttons (Move, Examine, etc.)."""
        action_type = instance.text.lower()

        if action_type == "inventory":
            self.show_inventory_with_examine()
            return
        if action_type == "save":
            self.manager.current = 'save_game'
            return

        if action_type in ["inventory", "list", "save", "load", "restart"]:
            command = action_type
            if action_type == "restart":
                self._start_new_game_sequence() # Use the new game sequence method
                return
            self.process_command(command)
        else: # Actions requiring a target
            self.selected_action = action_type
            self.populate_target_buttons_for_action(action_type)

    def on_game_session_ready(self):
        """Called after game_logic is confirmed to be initialized."""
        if not self.game_logic or not self.game_logic.player:
            logging.error("on_game_session_ready called but game_logic or player is None!")
            return

        self.update_ui()
        self.update_dynamic_action_buttons()
        
        if self.game_logic.player.get('qte_active'):
            qte_type = self.game_logic.player['qte_active']
            duration = self.game_logic.player.get('qte_duration', game_data.QTE_DODGE_WRECKING_BALL_DURATION)
            # qte_setup_message should be set by GameLogic when initiating QTE
            qte_message_prompt = self.game_logic.player.get('qte_setup_message', 
                                 color_text(f"QTE '{qte_type}' is active! Type your action!", "error"))
            self.update_ui(qte_message_prompt)  # Re-display QTE prompt
            self.start_qte_timer(qte_type, self.game_logic.player.get('qte_duration', game_data.QTE_DODGE_WRECKING_BALL_DURATION))
        else:
            self.cancel_qte_timer()

    def populate_target_buttons_for_action(self, action_type):
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"Select target to {color_text(action_type.capitalize(), 'special')}:"
        target_generator = self.contextual_target_generators.get(action_type)
        if not target_generator:
            self.contextual_buttons_layout.add_widget(Label(text=f"No target generator for '{action_type}'."))
        else:
            targets = target_generator()
            if not targets:
                # This is where the "No targets available" label is added.
                no_targets_label = Label(
                    text=f"No targets available to {action_type}.",
                    markup=True, 
                    size_hint_y=None,
                    halign='center',   
                    valign='middle',
                    padding=(dp(5), dp(5))
                )
                # Bind texture_size to update the label's height
                def set_label_height(instance, texture_size):
                    instance.height = texture_size[1] + dp(10)
                no_targets_label.bind(texture_size=set_label_height)
                # Bind width to update text_size for wrapping
                def update_text_wrap(instance, new_width):
                    instance.text_size = (new_width - dp(10), None)
                no_targets_label.bind(width=update_text_wrap)
                self.contextual_buttons_layout.add_widget(no_targets_label)
            else:
                for target_item in targets:
                    target_name = target_item if isinstance(target_item, str) else target_item.get('name', 'Unknown Target')
                    btn = self.create_contextual_button(text=target_name.capitalize(), command_tuple=(action_type, target_name))
                    self.contextual_buttons_layout.add_widget(btn)
        back_btn = self.create_contextual_button(text="Back to Actions", command_tuple=("back", None))
        self.contextual_buttons_layout.add_widget(back_btn)
        
    def create_contextual_button(self, text, command_tuple, width_dp=150, height_dp=35):
        """Helper to create styled contextual buttons."""
        # Strip Kivy markup tags to get clean text
        clean_text = text
        if "[color=" in text:
            # Extract the actual text from between color tags
            import re
            clean_text = re.sub(r'\[color=[^]]*\](.*?)\[/color\]', r'\1', text)
        
        # Create button with the clean text
        btn = Button(
            text=clean_text,
            size_hint=(None, None),
            size=(dp(width_dp), dp(height_dp)),
            font_size=dp(12)
        )
        
        # Apply different button styling based on text content or command type
        if command_tuple[0] == "move":
            btn.background_color = get_color_from_hex(f"#77{COLOR_CYAN}")
        elif "furniture" in text.lower():
            btn.background_color = get_color_from_hex(f"#77{COLOR_BLUE}")
        elif "hazard" in text.lower() or any(word in text.lower() for word in ["unstable", "precarious", "weak", "danger"]):
            btn.background_color = get_color_from_hex(f"#77{COLOR_MAGENTA}")
        elif "evidence" in text.lower():
            btn.background_color = get_color_from_hex(f"#77{COLOR_ORANGE}")
        elif "fire" in text.lower():
            btn.background_color = get_color_from_hex(f"#77{COLOR_RED}")
        elif command_tuple[0] == "examine":
            btn.background_color = get_color_from_hex(f"#77{COLOR_GREEN}")
            
        # Set up the button's action
        btn.bind(on_press=lambda x: self.on_target_button_press(command_tuple))
        
        # For text wrapping on buttons if text is too long
        btn.text_size = (btn.width - dp(10), None)
        btn.halign = 'center'
        btn.valign = 'middle'
        btn.bind(size=lambda instance, value: setattr(instance, 'text_size', (instance.width - dp(10), None)))
        
        return btn

    def on_target_button_press(self, command_tuple):
        action_type, target_name = command_tuple
        if action_type == "back" or action_type == "cancel_use":
            self.clear_and_display_general_actions(); self.selected_action = None; self.selected_use_item = None; return
        if action_type == "use":
            if not self.selected_use_item: 
                self.selected_use_item = target_name 
                self.populate_use_on_what_buttons(self.selected_use_item)
            else: 
                command = f"use {self.selected_use_item.lower()} on {target_name.lower()}"
                self.process_command(command)
                self.selected_use_item = None; self.clear_and_display_general_actions() 
        else:
            command = f"{action_type.lower()} {target_name.lower()}"
            self.process_command(command)
            if action_type not in ["search"]: self.clear_and_display_general_actions(); self.selected_action = None
            
    def populate_use_on_what_buttons(self, item_to_use):
        """Populates buttons for selecting what to use an item on."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"Use {color_text(item_to_use.capitalize(), 'item')} on what?"

        # Get all examinable objects in the room as potential targets
        # This provides a broad list of things the item could potentially be used on.
        # game_logic would then validate if the "use X on Y" is a valid interaction.
        possible_use_targets = self.game_logic.get_examinable_targets_in_room()

        if not possible_use_targets:
            self.contextual_buttons_layout.add_widget(Label(text="Nothing here to use that on."))
        else:
            for target_obj_name in possible_use_targets:
                # Ensure target_obj_name is a string
                obj_name_str = target_obj_name if isinstance(target_obj_name, str) else target_obj_name.get('name', 'Unknown Object')
                btn = self.create_contextual_button(
                    text=obj_name_str.capitalize(),
                    command_tuple=("use", obj_name_str) # action_type is "use", target_name is obj_name_str
                )
                self.contextual_buttons_layout.add_widget(btn)
        
        cancel_btn = self.create_contextual_button(text="Cancel Use", command_tuple=("cancel_use", None))
        self.contextual_buttons_layout.add_widget(cancel_btn)

    def process_command(self, command_str):
            """Central method to process any command, update UI, and check game state."""
            self.update_ui(f"> {color_text(command_str, 'command')}")

            raw_output = self.game_logic.process_player_input(command_str)
            
            # Initialize found_items_list to handle cases where it might not be set
            found_items_list = []

            # Handle enhanced description for movement commands
            # if command_str.lower().startswith("move") or command_str.lower().startswith("go"):
                # It's generally better to update the UI with the room description *after*
                # the main command output has been displayed, or as part of the game_logic's response.
                # However, if this specific timing is intended:
                # enhanced_description = self.enhance_room_description(
                #    self.game_logic.get_room_description(self.game_logic.get_current_location())
                # )
                # This update_ui call might be redundant if the main output_message also contains the room description.
                # Consider if enhance_room_description should be part of what game_logic returns for 'move'.
                # For now, preserving the logic as presented.
                # self.update_ui(enhanced_description)
            
            # Handle evidence recording from achievements system
            if isinstance(raw_output, dict) and raw_output.get("evidence_found"):
                evidence_id = raw_output.get("evidence_found")
                # Assuming game_logic.items refers to the master item definitions
                evidence_name = self.game_logic.items.get(evidence_id, {}).get('name', evidence_id)
                evidence_desc = self.game_logic.items.get(evidence_id, {}).get('description', 'No description available')
                
                if self.achievements_system:
                    # The method seems to be record_evidence in achievements.py, not add_evidence_to_journal
                    self.achievements_system.record_evidence(evidence_id, evidence_name, evidence_desc)
            # else: # This log might be too noisy if not finding evidence is common
                # logging.info("No evidence found in this command's output.")
            
            # Process raw_output for message and found_items
            if isinstance(raw_output, dict):
                output_message = raw_output.get("message", "No message from game logic.")
                # Check for found items specifically from search
                if command_str.lower().startswith("search ") and "found_items" in raw_output:
                    found_items_list = raw_output.get("found_items", []) # Ensure it's a list
            elif isinstance(raw_output, str): # Fallback if game_logic still returns string
                output_message = raw_output
                # Attempt to parse found items from string for "search"
                if command_str.lower().startswith("search ") and "find:" in output_message:
                    try:
                        items_part = output_message.split("find:")[1].strip().rstrip('.')
                        if " and " in items_part:
                            parts = items_part.split(" and ")
                            found_items_list = [item.strip() for item in parts[0].split(",")]
                            found_items_list.append(parts[1].strip())
                        elif items_part and "nothing" not in items_part.lower():
                            found_items_list = [items_part.strip()]
                        else:
                            found_items_list = [] # Explicitly empty if "nothing"
                    except IndexError:
                        found_items_list = []
            else:
                output_message = "An unexpected response was received from the game."
                found_items_list = []

            self.update_ui(output_message) # Display the primary message from the command

            # Populate "take" buttons if items were found from a search, otherwise clear contextual actions
            # Ensure found_items_list is not None and actually contains items before populating.
            if command_str.lower().startswith("search ") and found_items_list: 
                searched_furniture_name = command_str.split(" ", 1)[1] if len(command_str.split(" ", 1)) > 1 else "area"
                self.populate_take_buttons_from_search_results(found_items_list, searched_furniture_name)
            else:
                self.clear_and_display_general_actions()
                self.selected_action = None  # Reset selected primary action

            # Define level_id and other level-specific requirements for endgame check
            # Ensure player and game_logic are valid before accessing attributes
            if self.game_logic and self.game_logic.player:
                level_id = self.game_logic.player.get("current_level", 1) #
                level_req = game_data.LEVEL_REQUIREMENTS.get(level_id, {}) #
                exit_room = level_req.get("exit_room") #
                required_evidence_for_level = set(level_req.get("evidence_needed", [])) #

                # Check for level completion / endgame QTE trigger
                if (self.game_logic.player.get('location') == exit_room and
                        required_evidence_for_level.issubset(set(self.game_logic.player.get('inventory', [])))):
                    if not getattr(self, 'endgame_qte_active', False):
                        self.start_endgame_qte()
                    # Return here to prevent further processing until QTE is resolved
                    # The turn progression should happen as part of the QTE resolution or initial "move" action.
                    return 
            else:
                logging.error("Game logic or player not initialized, cannot check level completion.")
                # Fall through, but this indicates a problem.

            # Auto-save after significant actions 
            auto_save_triggers = ["move", "take", "drop", "use"]
            should_auto_save = any(command_str.lower().startswith(trigger) for trigger in auto_save_triggers)
            
            if should_auto_save and self.game_logic and not self.game_logic.is_game_over:
                self.game_logic.save_game() # Assumes default slot or quicksave logic within save_game

            # Check win/loss conditions and achievements related to game completion
            if self.game_logic and self.game_logic.is_game_over:
                if self.achievements_system:
                    # Assuming check_game_completion_achievements is designed to be called at game over
                    self.achievements_system.check_game_completion_achievements(self.game_logic)
                Clock.schedule_once(lambda dt: self.navigate_to_end_screen(), 0.1)

    def populate_take_buttons_from_search_results(self, found_items_list, searched_furniture_name):
        """Displays buttons for taking items found during a search."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = f"Items found in {color_text(searched_furniture_name, 'special')}:"
        
        if not found_items_list or len(found_items_list) == 0:
            # No items found or empty list
            self.contextual_buttons_layout.add_widget(Label(
                text="Nothing to take.",
                size_hint_y=None,
                height=dp(40)
            ))
        else:
            # Display buttons for each found item
            for item_name in found_items_list:
                btn = self.create_contextual_button(
                    text=f"Take {item_name.capitalize()}",
                    command_tuple=("take", item_name),
                    width_dp=200
                )
                self.contextual_buttons_layout.add_widget(btn)
        
        # Add a "Done" button to return to general actions
        done_btn = self.create_contextual_button(
            text="Done",
            command_tuple=("back", None),
            width_dp=200
        )
        self.contextual_buttons_layout.add_widget(done_btn)

    def enhance_room_description(self, description):
        """Enhances room description with colored keywords."""
        # Color hazard-related words
        hazard_words = ["hazard", "danger", "deadly", "precarious", "unstable", "weak", 
                        "floorboards", "falling", "collapse"]
        fire_words = ["fire", "flames", "burning", "smoldering", "smoke", "ash", "heat"]
        furniture_words = ["chair", "table", "desk", "sofa", "bed", "cabinet", "shelf",
                        "fireplace", "workbench", "bathtub", "sink"]
        
        # Split description into words to preserve spacing and punctuation
        words = []
        current_word = ""
        for char in description:
            if char.isalpha() or char == '-':
                current_word += char
            else:
                if current_word:
                    words.append(current_word)
                    current_word = ""
                words.append(char)
        if current_word:
            words.append(current_word)
        
        # Color words based on type
        colored_description = ""
        for word in words:
            lower_word = word.lower()
            if lower_word in hazard_words:
                colored_description += color_text(word, 'hazard')
            elif lower_word in fire_words:
                colored_description += color_text(word, 'fire')
            elif lower_word in furniture_words:
                colored_description += color_text(word, 'furniture')
            else:
                colored_description += word
        
        return colored_description

    def handle_level_transition(self, response_from_logic):
        logging.info("UI: Handling level transition.")
        level_id = response_from_logic["transition_to_level"]
        start_room = response_from_logic["next_level_start_room"]
        
        # Store pre-transition score if needed for level-specific scoring/achievements
        previous_level_id = self.game_logic.player['current_level'] # before it's updated

        transition_message = self.game_logic.transition_to_new_level(level_id, start_room)
        self.output_label.text = "" # Clear output for new level
        self.update_ui(transition_message) 
        
        if self.achievements_system:
             self.achievements_system.check_level_completion_achievements(self.game_logic, previous_level_id) 
        
        self.update_ui()
        self.update_dynamic_action_buttons()

    def update_ui(self, text=None, append=True):
        """Updates all UI elements reflecting the current game state.
        
        Args:
            text (str, optional): Text to display in the output area. Defaults to None.
            append (bool, optional): Whether to append the text or replace the existing text. Defaults to True.
        """
        if not self.game_logic or not self.game_logic.player: # Ensure game_logic and player are initialized
            return
        
        # Update output text if provided
        if text:
            if append:
                self.output_label.text += f"\n{text}"
                Clock.schedule_once(lambda dt: setattr(self.output_scroll_view, 'scroll_y', 0), 0.01)
            else:
                self.output_label.text = text
                Clock.schedule_once(lambda dt: setattr(self.output_scroll_view, 'scroll_y', 0), 0.01)
        turns_left = self.game_logic.player.get('turns_left', 0)
        self.turns_label.text = f"Actions Left: {color_text(str(turns_left), 'turn')}"
        self.update_map_display()
        score = self.game_logic.player.get('score', 0)
        self.score_label.text = f"Score: {color_text(str(score), 'success')}"
        health = self.game_logic.player.get('health', 0)
        if health < 3:
            color = 'error'      # red
        elif health < 7:
            color = 'warning'    # yellow
        else:
            color = 'success'    # green
        self.health_label.text = f"Health: {color_text(str(health), 'warning' if health < 5 else 'success')}"
        current_room = self.game_logic.get_current_location()
        inventory_list = self.game_logic.player.get('inventory', [])
        if inventory_list:
            colored_items = []
            for item in inventory_list:
                # Color evidence items orange, regular items green
                if self.game_logic.is_evidence_item(item):
                    colored_items.append(color_text(item.capitalize(), 'evidence'))
                else:
                    colored_items.append(color_text(item.capitalize(), 'item'))
            self.inventory_content_label.text = ", ".join(colored_items)
        else:
            self.inventory_content_label.text = "Empty"
        
        # Ensure evidence label is not displayed if it exists
        if hasattr(self, 'evidence_label'):
            if isinstance(self.evidence_label, Label):
                self.evidence_label.opacity = 0  # Hide the label

        if not hasattr(self, '_updating_ui'):
            self._updating_ui = True
            try:
                # Only show room description once
                room_desc = self.game_logic.get_room_description()
                self.update_ui(room_desc)  # Use display_output
            except Exception as e:
                logging.error(f"Error while updating UI: {e}")
            finally:
                self._updating_ui = False
            

    def show_inventory_with_examine(self):
        """Display inventory items with an 'Examine' button for each."""
        self.contextual_buttons_layout.clear_widgets()
        self.contextual_label.text = "Your Inventory:"
        inventory_list = self.game_logic.player.get('inventory', [])
        if not inventory_list:
            self.contextual_buttons_layout.add_widget(Label(text="Inventory is empty."))
        else:
            for item in inventory_list:
                item_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(35), spacing=dp(5))
                item_label = Label(text=color_text(item.capitalize(), 'item'), markup=True, size_hint_x=0.7, halign='left', valign='middle')
                item_label.bind(size=item_label.setter('text_size'))
                examine_btn = Button(
                    text="Examine",
                    size_hint_x=0.3,
                    font_size=dp(12),
                    on_press=lambda btn, item_name=item: self.process_command(f"examine {item_name}")
                )
                item_box.add_widget(item_label)
                item_box.add_widget(examine_btn)
                self.contextual_buttons_layout.add_widget(item_box)
        # Add a back button
        back_btn = self.create_contextual_button(text="Back", command_tuple=("back", None))
        self.contextual_buttons_layout.add_widget(back_btn)

    def update_dynamic_action_buttons(self):
        if not self.game_logic:
            return
        self.dynamic_actions_layout.clear_widgets()
        action_methods = {
            "Examine": self.game_logic.get_examinable_targets_in_room,
            "Take": self.game_logic.get_takeable_items_in_room,
            "Search": self.game_logic.get_searchable_furniture_in_room,
            "Unlock": self.game_logic.get_unlockable_targets,
        }
        buttons_added = 0
        for verb, getter_method in action_methods.items():
            targets = getter_method()
            for target in targets:
                if buttons_added >= 6: break
                btn = Button(text=f"{verb} {target.capitalize()}", font_name=DEFAULT_FONT, size_hint_y=None, height=dp(40))
                btn.bind(on_release=lambda x, cmd=f"{verb.lower()} {target}": self.process_command(cmd))
                self.dynamic_actions_layout.add_widget(btn)
                buttons_added += 1
            if buttons_added >= 6: break

        if buttons_added < 6:
            usable_inventory_items = self.game_logic.get_usable_inventory_items()
            examinable_room_targets = self.game_logic.get_examinable_targets_in_room()
            for item_in_inv in usable_inventory_items:
                if buttons_added >= 6: break
                item_master_data = self.game_logic._get_item_data(item_in_inv)
                if item_master_data and item_master_data.get("use_on"):
                    for use_on_target_name in item_master_data["use_on"]:
                        if buttons_added >= 6: break
                        if any(t.lower() == use_on_target_name.lower() for t in examinable_room_targets):
                            btn_text = f"Use {item_in_inv.capitalize()} on {use_on_target_name.capitalize()}"
                            btn = Button(text=btn_text, font_name=DEFAULT_FONT, size_hint_y=None, height=dp(40))
                            btn.bind(on_release=lambda x, cmd=f"use {item_in_inv} on {use_on_target_name}": self.process_command(cmd))
                            self.dynamic_actions_layout.add_widget(btn)
                            buttons_added += 1
                if buttons_added >= 6: break

        # Set the height of the BoxLayout based on the number of buttons
        num_buttons = len(self.dynamic_actions_layout.children)
        self.dynamic_actions_layout.height = dp(40 * num_buttons + 5 * (num_buttons - 1) if num_buttons > 0 else 0)

    def start_endgame_qte(self):
        """Initiate the endgame QTE for escaping the wrecking ball."""
        self.endgame_qte_active = True
        self.qte_timer = 5.0  # seconds
        self.qte_success = False
        self.update_ui("[color=ff2222][b]A wrecking ball is about to smash through the house! Type 'dodge!' within 5 seconds or be obliterated![/b][/color]")
        self.input_field.hint_text = "Type 'dodge!' NOW!"
        self.input_field.focus = True
        # Start the countdown
        self.qte_event = Clock.schedule_interval(self._endgame_qte_countdown, 0.1)

    def _endgame_qte_countdown(self, dt):
        self.qte_timer -= dt
        if self.qte_timer <= 0:
            self.qte_timer = 0
            self.finish_endgame_qte(success=False)
            return False  # Stop timer
        return True  # Continue timer

    def finish_endgame_qte(self, success):
        """Handle the result of the endgame QTE."""
        self.endgame_qte_active = False
        self.input_field.hint_text = "Enter command..."
        if hasattr(self, 'qte_event'):
            Clock.unschedule(self.qte_event)
            self.qte_event = None
        if success:
            self.update_ui("[color=22ff22][b]You dove out of the way just in time![/b][/color]")
            # Proceed to next level
            level_id = self.player.get("current_level", 1)
            self.handle_level_transition({"transition_to_level": level_id + 1, "next_level_start_room": "start"})
        else:
            self.update_ui("[color=ff2222][b]You hesitated... The wrecking ball obliterates you![/b][/color]")
            # Trigger game over
            self.game_logic.is_game_over = True
            self.game_logic.game_won = False
            self.navigate_to_end_screen()

    def start_qte_timer(self, qte_type, duration):
        self.cancel_qte_timer() # Cancel any existing timer
        self.active_qte_type = qte_type
        self.qte_remaining_time = float(duration)
        self.update_qte_timer_display(self.qte_remaining_time)

        # Schedule the countdown update
        self.qte_timer_event = Clock.schedule_interval(self._qte_countdown, 0.1)
        
        self.disable_action_buttons(True) # Disable normal action buttons
        self.input_field.hint_text = "TYPE YOUR QTE ACTION QUICKLY!"
        logging.info(f"UI: QTE '{qte_type}' started. Duration: {duration}s")

    def _qte_countdown(self, dt):
        self.qte_remaining_time -= dt
        if self.qte_remaining_time <= 0:
            self.qte_remaining_time = 0
            self.update_qte_timer_display(self.qte_remaining_time)
            self.qte_timeout_callback() # Call the timeout function
            return False # Stop the interval scheduling
        self.update_qte_timer_display(self.qte_remaining_time)
        return True # Continue scheduling

    def cancel_qte_timer(self):
        if self.qte_timer_event:
            Clock.unschedule(self.qte_timer_event)
            self.qte_timer_event = None
        self.active_qte_type = None
        self.update_qte_timer_display(0) 
        self.disable_action_buttons(False) # Re-enable action buttons
        self.input_field.hint_text = "Enter command..."
        if self.game_logic and self.game_logic.player: 
             self.game_logic.player['qte_active'] = None 
        logging.info("UI: QTE timer cancelled or finished.")

    def qte_timeout_callback(self, *args): 
        logging.info(f"UI: QTE '{self.active_qte_type}' timed out.")
        if self.active_qte_type: 
            # Send a special command to GameLogic to indicate timeout failure
            self.process_command("INTERNAL_QTE_TIMEOUT_FAILURE_SIGNAL") 
            # cancel_qte_timer will be called within process_command if it was a QTE response
        else:
            logging.info("UI: qte_timeout_callback called but no active_qte_type.")
            self.cancel_qte_timer() # Ensure cleanup if called unexpectedly

    def update_qte_timer_display(self, time_left):
        if self.active_qte_type:
            self.qte_timer_label.text = color_text(f"TIME: {time_left:.1f}s", "error")
        else:
            self.qte_timer_label.text = ""

    def disable_action_buttons(self, disable=True):
        # Iterate through your action buttons and set their disabled property
        # Example:
        if hasattr(self, 'dynamic_actions_layout'): # Assuming you have this layout
             for child_widget in self.dynamic_actions_layout.children:
                if isinstance(child_widget, Button):
                    child_widget.disabled = disable
        # Also consider disabling other static action buttons if necessary

    def disable_action_buttons(self, disable=True):
        for child_widget in self.dynamic_actions_layout.children:
            if isinstance(child_widget, Button): child_widget.disabled = disable
        # Consider disabling other static buttons if needed during QTE
        # self.btn_submit_cmd.disabled = disable # Example for send button

    def navigate_to_end_screen(self):
        app = App.get_running_app()
        if self.game_logic: # Store final stats before clearing game_logic
            app.last_game_score = self.game_logic.player.get('score', 0)
            if not self.game_logic.game_won and hasattr(self.game_logic, 'last_death_message_for_ui'):
                 app.last_death_reason = self.game_logic.last_death_message_for_ui # GameLogic should set this
            elif not self.game_logic.game_won:
                 app.last_death_reason = "An unknown fate claimed you."

        if self.game_logic and self.game_logic.game_won:
            self.manager.current = 'win'
        else:
            self.manager.current = 'lose'
        self.game_logic = None # Clear the game logic for a fresh start next time
        app.current_disaster_details = None 
        app.selected_character_class = None

# --- Win/Lose/Other Screens ---
# (AchievementsScreen, JournalScreen, SaveGameScreen, LoadGameScreen as previously defined,
#  ensuring they use self.manager.get_screen('game').game_logic where appropriate
#  and handle cases where game_logic might be None if accessed from TitleScreen before a game starts)
class WinScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        layout.add_widget(Label(text="[b]YOU SURVIVED... THIS TIME[/b]", markup=True, font_name=DEFAULT_FONT, font_size='30sp'))
        self.score_display = Label(text="Final Score: 0", font_name=DEFAULT_FONT, font_size='20sp')
        layout.add_widget(self.score_display)
        btn_main_menu = Button(text="Main Menu", font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50), on_release=lambda x: self.go_to_screen('title','right'))
        layout.add_widget(btn_main_menu)
        self.add_widget(layout)

    def on_enter(self, *args):
        app = App.get_running_app()
        self.score_display.text = f"Final Score: {getattr(app, 'last_game_score', 0)}"

class LoseScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(50), spacing=dp(20))
        layout.add_widget(Label(text="[b]DEATH FOUND YOU[/b]", markup=True, font_name=DEFAULT_FONT, font_size='30sp', color=get_color_from_hex(COLOR_RED)))
        self.death_reason_label = Label(text="Cause: Unknown", font_name=DEFAULT_FONT, font_size='18sp', markup=True, text_size=(self.width*0.8, None), halign='center')
        layout.add_widget(self.death_reason_label)
        btn_main_menu = Button(text="Main Menu", font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50), on_release=lambda x: self.go_to_screen('title','right'))
        layout.add_widget(btn_main_menu)
        self.add_widget(layout)
    
    def on_enter(self, *args):
        app = App.get_running_app()
        reason = getattr(app, 'last_death_reason', "The design caught up.")
        # The reason might already be colored, or we color it here
        self.death_reason_label.text = f"Cause:\n{reason}"


class AchievementsScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super().__init__(**kwargs)
        self.achievements_system = achievements_system
        layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        layout.add_widget(Label(text="[b]Achievements[/b]", markup=True, font_name=DEFAULT_FONT, size_hint_y=0.1, font_size='24sp'))
        self.scroll_view = ScrollView(size_hint_y=0.8); self.grid_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.grid_layout.bind(minimum_height=self.grid_layout.setter('height')); self.scroll_view.add_widget(self.grid_layout); layout.add_widget(self.scroll_view)
        btn_back = Button(text="Back", font_name=DEFAULT_FONT, size_hint_y=0.1, on_release=lambda x: self.go_to_screen('title', 'right'))
        layout.add_widget(btn_back); self.add_widget(layout)

    def on_enter(self, *args):
        self.grid_layout.clear_widgets()
        if self.achievements_system:
            sorted_achievements = sorted(self.achievements_system.achievements.items(), key=lambda item: (not item[1]['unlocked'], item[1]['name']))
            for ach_id, ach_data in sorted_achievements:
                status_color_tag = 'success' if ach_data['unlocked'] else 'error'
                icon = ach_data.get('icon', '▪') 
                text = f"{icon} [b]{ach_data['name']}[/b] ({color_text('Unlocked' if ach_data['unlocked'] else 'Locked', status_color_tag)})\n   {ach_data['description']}"
                ach_label = Label(text=text, font_name=DEFAULT_FONT, markup=True, size_hint_y=None, height=dp(70), text_size=(self.width*0.9, None), halign='left', valign='top')
                self.grid_layout.add_widget(ach_label)

class JournalScreen(BaseScreen):
    def __init__(self, achievements_system=None, **kwargs):
        super().__init__(**kwargs)
        self.achievements_system = achievements_system
        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        main_layout.add_widget(Label(text="[b]Evidence Journal[/b]", markup=True, font_name=DEFAULT_FONT, size_hint_y=0.1, font_size='24sp'))
        content_layout = BoxLayout(orientation='horizontal', size_hint_y=0.8, spacing=dp(10))
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.4); left_panel.add_widget(Label(text="Collected Evidence:", font_name=DEFAULT_FONT, size_hint_y=0.1))
        self.entry_scroll = ScrollView(); self.entry_list_layout = GridLayout(cols=1, spacing=dp(5), size_hint_y=None)
        self.entry_list_layout.bind(minimum_height=self.entry_list_layout.setter('height')); self.entry_scroll.add_widget(self.entry_list_layout); left_panel.add_widget(self.entry_scroll); content_layout.add_widget(left_panel)
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.6, spacing=dp(5))
        self.details_title = Label(text="Select Evidence", markup=True, font_name=DEFAULT_FONT, font_size='20sp', size_hint_y=0.1)
        self.details_description_scroll = ScrollView(); self.details_description = Label(text="", markup=True, font_name=DEFAULT_FONT, text_size=(None,None), size_hint_y=None, padding=(dp(5),dp(5)), halign='left', valign='top')
        self.details_description.bind(texture_size=self.details_description.setter('size')); self.details_description_scroll.add_widget(self.details_description)
        right_panel.add_widget(self.details_title); right_panel.add_widget(self.details_description_scroll); content_layout.add_widget(right_panel)
        main_layout.add_widget(content_layout)
        btn_back = Button(text="Back to Game", font_name=DEFAULT_FONT, size_hint_y=0.1, on_release=lambda x: self.go_to_screen('game', 'right'))
        main_layout.add_widget(btn_back); self.add_widget(main_layout)

    def on_enter(self, *args):
        self.populate_evidence_list(); self.details_title.text = "Select Evidence"; self.details_description.text = ""

    def populate_evidence_list(self):
        self.entry_list_layout.clear_widgets()
        if not self.achievements_system or not self.achievements_system.evidence_collection:
            self.entry_list_layout.add_widget(Label(text="No evidence collected.", font_name=DEFAULT_FONT, size_hint_y=None, height=dp(40))); return
        sorted_evidence = sorted(self.achievements_system.evidence_collection.items(), key=lambda item: item[1].get('found_date', str(datetime.datetime.min)))
        for ev_id, ev_data in sorted_evidence:
            btn = Button(text=ev_data.get('name', ev_id), font_name=DEFAULT_FONT, size_hint_y=None, height=dp(40))
            btn.bind(on_release=lambda x, eid=ev_id: self.show_evidence_details(eid))
            self.entry_list_layout.add_widget(btn)
            
    def show_evidence_details(self, evidence_id):
        evidence_data = self.achievements_system.evidence_collection.get(evidence_id, {})
        self.details_title.text = color_text(evidence_data.get('name', 'Unknown'), 'evidence')
        self.details_description.text = f"[b]Description:[/b]\n{evidence_data.get('description', 'No details.')}\n\n[size=12sp][color={COLOR_LIGHT_GREY}]Found: {evidence_data.get('found_date', 'Sometime...')}[/color][/size]"
        self.details_description_scroll.scroll_y = 1

class SaveGameScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]Save Game[/b]", markup=True, font_name=DEFAULT_FONT, size_hint_y=0.1, font_size='24sp'))
        self.slots_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=0.7)
        layout.add_widget(self.slots_layout)
        self.status_label = Label(text="", font_name=DEFAULT_FONT, size_hint_y=0.1)
        layout.add_widget(self.status_label)
        btn_back = Button(text="Back to Game", font_name=DEFAULT_FONT, size_hint_y=0.1, on_release=lambda x: self.go_to_screen('game', 'right'))
        layout.add_widget(btn_back); self.add_widget(layout)

    def on_enter(self, *args): self.populate_save_slots(); self.status_label.text = "Select a slot to save or overwrite."
    def populate_save_slots(self):
        self.slots_layout.clear_widgets()
        slots_to_show = ["quicksave", "savegame_1", "savegame_2", "savegame_3"] 
        for slot_name in slots_to_show:
            preview = f"Slot: {slot_name.replace('_', ' ').capitalize()}"
            filepath = os.path.join("saves", f"{slot_name}.json")
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r") as f: info = json.load(f).get("save_info", {})
                    preview += f" - Lvl {info.get('current_level', '?')} {info.get('location', '?')} ({info.get('timestamp', 'No date')})"
                except: preview += color_text(" (Error Reading)", "error")
            else: preview += " (Empty)"
            btn = Button(text=preview, markup=True, font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50))
            btn.bind(on_release=lambda x, s=slot_name: self.confirm_save(s))
            self.slots_layout.add_widget(btn)

    def confirm_save(self, slot_name):
        gs = self.manager.get_screen('game')
        if gs and gs.game_logic:
            # Change from save_game_state to save_game and adapt the response handling
            try:
                # Use save_game method instead of save_game_state
                result = gs.game_logic.save_game(slot_name)
                
                # Handle different return types (dict vs boolean or other)
                if isinstance(result, dict):
                    success = result.get("success", False)
                    message = result.get("message", "Game saved.")
                else:
                    success = bool(result)  # Convert to boolean
                    message = "Game saved successfully." if success else "Failed to save game."
                
                self.status_label.text = message
                if success:
                    self.play_sound("save")
                    self.populate_save_slots()
            except Exception as e:
                self.status_label.text = color_text(f"Save error: {str(e)}", "error")
        else:
            self.status_label.text = color_text("Cannot save: No active game.", "error")

class LoadGameScreen(BaseScreen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        layout.add_widget(Label(text="[b]Load Game[/b]", markup=True, font_name=DEFAULT_FONT, size_hint_y=0.1, font_size='24sp'))
        self.slots_layout = BoxLayout(orientation='vertical', spacing=dp(5), size_hint_y=0.7)
        layout.add_widget(self.slots_layout)
        self.status_label = Label(text="", font_name=DEFAULT_FONT, size_hint_y=0.1)
        layout.add_widget(self.status_label)
        btn_back = Button(text="Back to Title", font_name=DEFAULT_FONT, size_hint_y=0.1, on_release=lambda x: self.go_to_screen('title', 'right'))
        layout.add_widget(btn_back); self.add_widget(layout)

    def on_enter(self, *args): self.populate_load_slots(); self.status_label.text = "Select a slot to load."
    
    def populate_load_slots(self):
        self.slots_layout.clear_widgets()
        slots_to_show = ["quicksave", "savegame_1", "savegame_2", "savegame_3"]
        found_any = False
        for slot_name in slots_to_show:
            preview = f"Slot: {slot_name.replace('_', ' ').capitalize()}"
            filepath = os.path.join("saves", f"{slot_name}.json")
            if os.path.exists(filepath):
                found_any = True
                try:
                    with open(filepath, "r") as f: info = json.load(f).get("save_info", {})
                    preview += f" - Lvl {info.get('current_level', '?')} {info.get('location', '?')} ({info.get('timestamp', 'No date')})"
                    btn = Button(text=preview, markup=True, font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50))
                    btn.bind(on_release=lambda x, s=slot_name: self.load_game_action(s))
                    self.slots_layout.add_widget(btn)
                except: 
                    self.slots_layout.add_widget(Label(text=f"{preview} {color_text('(Error Reading)', 'error')}", markup=True, font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50)))
            else: 
                 self.slots_layout.add_widget(Label(text=f"{preview} (Empty)", markup=True, font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50), color=(0.7,0.7,0.7,1)))
        if not found_any: self.slots_layout.add_widget(Label(text="No save games found.", font_name=DEFAULT_FONT, size_hint_y=None, height=dp(50)))

    def load_game_action(self, slot_name):
        game_screen = self.manager.get_screen('game')
        if game_screen:
            game_screen.start_new_game_session_from_load(load_slot=slot_name) 
            if game_screen.game_logic and game_screen.game_logic.player: # Check if load was successful
                 self.status_label.text = f"Game '{slot_name}' loaded. Transitioning..."
                 self.play_sound("load") 
                 Clock.schedule_once(lambda dt: self.go_to_screen('game', 'left'), 0.2)
            else:
                self.status_label.text = color_text(f"Failed to load game from '{slot_name}'. Save may be corrupted.", "error")
                self.populate_load_slots() # Refresh
        else: self.status_label.text = color_text("Critical Error: Game screen not found.", "error")