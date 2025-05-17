#!/usr/bin/env python3
# Re-saved to ensure proper encoding and remove hidden null bytes.
"""
A tribute screen honoring Tony Todd, who played William Bludworth in the Final Destination series.
This screen appears before the main game begins.
"""

import logging
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import AsyncImage # Consider using Image if the asset is local and bundled
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
# from kivy.core.window import Window # Not directly used here
from kivy.graphics import Color, Rectangle # Used for background, though ModalView has its own bg
from kivy.animation import Animation
from kivy.utils import get_color_from_hex
from kivy.metrics import dp # For consistent sizing

# It's good practice to ensure ui.resource_path or a similar utility is used for assets
# if this file might be run from different contexts or when packaged.
# For now, it assumes 'assets/tony_todd.jpg' is findable relative to execution.
# from .ui import resource_path # Example if you had a central resource_path

# Define default font, consider making this configurable or shared from a central place
DEFAULT_FONT_NAME = "Roboto" # Kivy's default, or replace with your game's default font if registered

class TonyToddTribute(ModalView):
    """A modal tribute screen honoring Tony Todd."""
    
    def __init__(self, on_complete=None, **kwargs):
        super().__init__(
            size_hint=(1, 1),       # Cover the whole screen
            auto_dismiss=False,     # Must be explicitly dismissed or timed out
            background_color=(0, 0, 0, 0.95), # Semi-transparent black background for the ModalView itself
            # background='atlas://data/images/defaulttheme/modalview-background', # Kivy's default, can be overridden
            overlay_color=(0,0,0,0.0), # Make overlay transparent if custom background is drawn for layout
            **kwargs
        )
        
        self.on_complete = on_complete # Callback function when tribute is finished
        
        # Main layout within the ModalView
        # This layout will have its own background to ensure full opacity if desired
        self.layout = BoxLayout(
            orientation='vertical', 
            padding=dp(40), # Use dp for density-independent padding
            spacing=dp(15)  # Use dp for spacing
        )
        
        # Add a background to the layout itself to make it opaque black
        with self.layout.canvas.before:
            Color(0, 0, 0, 1) # Opaque black
            self.layout_rect = Rectangle(size=self.layout.size, pos=self.layout.pos)
        self.layout.bind(size=self._update_layout_rect, pos=self._update_layout_rect)

        # Add image
        try:
            # If 'assets/tony_todd.jpg' is bundled, Image might be more reliable than AsyncImage
            # For local development, AsyncImage is fine.
            # Consider using resource_path if you have one defined in your project.
            image_source = 'assets/tony_todd.jpg' 
            # image_source = resource_path('assets/tony_todd.jpg') # If using a helper
            
            self.portrait = AsyncImage( # Or Image
                source=image_source,
                size_hint=(1, 0.5), # Adjusted size_hint for better balance
                opacity=0, # Start transparent for fade-in
                allow_stretch=True,
                keep_ratio=True
            )
            self.layout.add_widget(self.portrait)
            
            # Start fade-in animation for the image after a short delay
            Clock.schedule_once(lambda dt: Animation(opacity=1, duration=2.0).start(self.portrait), 0.5)
        except Exception as e:
            logging.error(f"TonyToddTribute: Could not load image '{image_source}': {e}")
            # Adjust layout if image fails to load, perhaps add a placeholder Label
            error_label = Label(text="Image not available", font_name=DEFAULT_FONT_NAME, font_size=dp(18))
            self.layout.add_widget(error_label)
            self.layout.padding = dp(60) # Increase padding if no image
            self.layout.spacing = dp(30)
        
        # Memorial text elements
        self.years_label = Label(
            text="1954 - 2024",
            font_name=DEFAULT_FONT_NAME,
            font_size=dp(28), # Use dp
            size_hint=(1, None), height=dp(40), # Set height
            opacity=0,
            color=get_color_from_hex("#CCCCCC") # Light grey
        )
        
        self.name_label = Label(
            text="TONY TODD",
            font_name=DEFAULT_FONT_NAME, # Consider a more impactful font if available
            font_size=dp(50), 
            bold=True,
            size_hint=(1, None), height=dp(70),
            opacity=0,
            color=get_color_from_hex("#FFFFFF")
        )
        
        self.role_label = Label(
            text="William Bludworth, Candyman, and many, many more",
            font_name=DEFAULT_FONT_NAME,
            font_size=dp(22),
            size_hint=(1, None), height=dp(35),
            opacity=0,
            color=get_color_from_hex("#E0E0E0") # Slightly off-white
        )
        
        self.quote_label = Label(
            text='"You all just be careful now."',
            font_name=DEFAULT_FONT_NAME,
            italic=True,
            font_size=dp(20),
            size_hint=(1, None), height=dp(55), # Allow more height for potential wrapping
            opacity=0,
            color=get_color_from_hex("#B0B0B0"), # Dimmer grey
            text_size=(self.width * 0.8, None), # Enable text wrapping
            halign='center'
        )
        self.quote_label.bind(width=lambda instance, value: setattr(instance, 'text_size', (value * 0.8, None)))


        self.tribute_label = Label(
            text="In Loving Memory", # Changed from "In loving memory"
            font_name=DEFAULT_FONT_NAME,
            font_size=dp(24),
            size_hint=(1, None), height=dp(35),
            opacity=0,
            color=get_color_from_hex("#FFFFFF")
        )
        
        # Continue button (initially hidden, appears later)
        self.continue_button = Button(
            text="Continue",
            font_name=DEFAULT_FONT_NAME,
            font_size=dp(18),
            size_hint=(0.5, None), # Centered with 0.5 width
            height=dp(50),
            pos_hint={'center_x': 0.5},
            background_normal='', # Custom background color
            background_color=get_color_from_hex('#333333'), # Darker button
            color=get_color_from_hex("#FFFFFF"), # White text
            opacity=0, # Start transparent
            disabled=True # Start disabled until it fades in
        )
        self.continue_button.bind(on_release=self.on_continue_pressed) # Changed method name
        
        # Add widgets to layout in order
        self.layout.add_widget(self.years_label)
        self.layout.add_widget(self.name_label)
        self.layout.add_widget(self.role_label)
        # Add a small spacer for visual separation before the quote
        spacer = BoxLayout(size_hint_y=None, height=dp(10))
        self.layout.add_widget(spacer)
        self.layout.add_widget(self.quote_label)
        self.layout.add_widget(self.tribute_label)
        
        # Add another spacer before the button
        spacer_button = BoxLayout(size_hint_y=None, height=dp(20))
        self.layout.add_widget(spacer_button)
        self.layout.add_widget(self.continue_button)
        
        self.add_widget(self.layout) # Add the main layout to the ModalView
        
        # Schedule animations for text elements
        Clock.schedule_once(self.animate_text_elements, 2.0) # Start text animations after image fade-in
        
        # Auto-continue after a longer total duration
        self.auto_continue_event = Clock.schedule_once(self.on_continue_pressed, 8.0) # e.g., 8 seconds total
    
    def _update_layout_rect(self, instance, value):
        """Updates the background rectangle of the layout."""
        self.layout_rect.pos = instance.pos
        self.layout_rect.size = instance.size

    def animate_text_elements(self, dt):
        """Animate text elements with sequential fade-ins."""
        anim_duration = 1.0
        delay_step = 0.6

        Animation(opacity=1, duration=anim_duration).start(self.years_label)
        Clock.schedule_once(lambda d: Animation(opacity=1, duration=anim_duration).start(self.name_label), delay_step * 1)
        Clock.schedule_once(lambda d: Animation(opacity=1, duration=anim_duration).start(self.role_label), delay_step * 2)
        Clock.schedule_once(lambda d: Animation(opacity=1, duration=anim_duration).start(self.quote_label), delay_step * 3)
        Clock.schedule_once(lambda d: Animation(opacity=1, duration=anim_duration).start(self.tribute_label), delay_step * 4)
        
        # Animate button appearance and enable it
        def enable_button(animation, widget):
            widget.disabled = False

        button_anim = Animation(opacity=1, duration=anim_duration * 0.8)
        button_anim.bind(on_complete=enable_button)
        Clock.schedule_once(lambda d: button_anim.start(self.continue_button), delay_step * 5)
    
    def on_continue_pressed(self, *args): # Renamed from on_continue
        """Handle continue button press or auto-continue timeout."""
        # Prevent multiple calls if button is pressed close to timeout
        if hasattr(self, 'auto_continue_event') and self.auto_continue_event:
            Clock.unschedule(self.auto_continue_event)
            self.auto_continue_event = None
        
        # Disable button to prevent multiple clicks during fade-out
        self.continue_button.disabled = True
        
        # Fade out the entire tribute modal view
        anim = Animation(opacity=0, duration=1.0) # Faster fade out
        anim.bind(on_complete=self.finish_tribute_sequence) # Renamed callback
        anim.start(self) # Animate the ModalView itself for fade-out
    
    def finish_tribute_sequence(self, *args): # Renamed from finish_tribute
        """Dismisses the modal view and calls the on_complete callback."""
        self.dismiss() # Dismiss the ModalView
        if self.on_complete:
            self.on_complete() # Trigger the callback (e.g., initialize_game_ui)

