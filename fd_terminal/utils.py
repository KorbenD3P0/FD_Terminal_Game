COLOR_RED = "ff0000"
COLOR_GREEN = "00ff00"
COLOR_YELLOW = "ffff00"
COLOR_CYAN = "00ffff"
COLOR_MAGENTA = "ff00ff"
COLOR_WHITE = "ffffff"
COLOR_ORANGE = "ffa500"
COLOR_LIGHT_GREY = "d3d3d3"
COLOR_BLUE = "3399ff"
COLOR_PURPLE = "b266ff"

def color_text(text, text_type):
    """
    Applies Kivy color markup to text based on a predefined category.

    Args:
        text (str): The text to be colored.
        text_type (str): The category of the text, which determines its color.
                         Valid categories include 'room', 'exit', 'evidence', 'item',
                         'hazard', 'fire', 'command', 'furniture', 'success',
                         'error', 'warning', 'special', 'turn', 'default'.

    Returns:
        str: The text string with Kivy color markup, or the original text
             if the text_type is unknown (defaults to white).
    """
    color_map = {
        'room': COLOR_YELLOW,       # Room names
        'exit': COLOR_CYAN,         # Exit directions
        'evidence': COLOR_ORANGE,   # Evidence items
        'item': COLOR_GREEN,        # General items
        'hazard': COLOR_MAGENTA,    # Hazards
        'fire': COLOR_RED,          # Fire or dangerous situations
        'command': COLOR_CYAN,      # User commands
        'furniture': COLOR_BLUE,    # Furniture
        'success': COLOR_GREEN,     # Success messages
        'error': COLOR_RED,         # Error messages
        'warning': COLOR_RED,    # Warning messages (Note: Same as error, consider differentiating if needed)
        'special': COLOR_PURPLE,    # Special elements
        'turn': COLOR_YELLOW,       # Turn counter
        'default': COLOR_WHITE      # Default text color
    }
    
    color = color_map.get(text_type, COLOR_WHITE)  # Default to white if text_type is not found
    return f"[color={color}]{text}[/color]"

# Re-saved to ensure proper encoding and remove hidden null bytes.
