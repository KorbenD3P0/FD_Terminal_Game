import os
import sys

# Add the root directory of your project to the Python path
# This allows importing fd_terminal
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    # Import your main Kivy application class from your package
    from fd_terminal.main import FinalDestinationApp

    if __name__ == '__main__':
        FinalDestinationApp().run()
except ImportError as e:
    print(f"Error importing your application: {e}")
    print("Please ensure your project structure is correct and 'fd_terminal' is a valid package.")
except Exception as e:
    print(f"An error occurred while running the application: {e}")