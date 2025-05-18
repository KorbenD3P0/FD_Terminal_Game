# Final Destination Terminal

**"Death... doesn't like to be cheated."**

Welcome to **Final Destination Terminal**, a text-based adventure game with a Kivy-powered graphical interface, inspired by the chilling premise of the Final Destination film series. You've narrowly escaped a catastrophe, but Death's design is relentless. Navigate treacherous environments, uncover clues about past victims, and interact with a dynamic world of hazards to find a way to survive... if you can.

## Game Premise

You are a survivor of a recent mass-casualty event. Haunted by the premonition that saved your life, you now find yourself on Death's List simply because you listened and avoided your original fate. The game begins as you accompany the body of the most recent ex-survivor to a place deeply connected with the mysteries of Death – the unsettling Hope River Hospital, and perhaps even the infamous William Bludworth's residence
Your goal is to explore these cursed locations, gather evidence related to past events and victims, and understand the intricate patterns of Death's design, all while trying to stay one step ahead of your own grim fate.

## Key Features

* **Dynamic Hazard System:** Experience a world where the environment itself is your enemy. Hazards can activate, change states, interact with each other, and react to your actions, creating emergent and dangerous situations.
* **Multiple Levels:** Explore distinct, multi-room locations, each with unique items, evidence, and deadly hazards (e.g., Lakeview Hospital, The Bludworth House).
* **Rich Lore & Evidence Collection:** Discover numerous evidence items tied to victims from the Final Destination movies and expanded universe, each with descriptions and potential clues.
* **Character Classes:** Choose from different character archetypes, each with minor statistical differences (HP, Perception, Intuition) influencing gameplay.
* **Interactive Storytelling:** A randomly generated introductory disaster sets the stage for your game session.
* **QTEs (Quick Time Events):** Face sudden dangers that require quick reactions and correct input to survive.
* **Achievements & Journal:** Track your progress with an achievement system and review collected evidence in your journal.
* **Save/Load System:** Save your progress in multiple slots and resume your perilous journey later.
* **Graphical User Interface:** Played through a Kivy-based UI with text output, contextual action buttons, map display, inventory management, and dedicated screens for various game functions.
* **Tony Todd Tribute:** A special tribute screen honors Tony Todd, the iconic William Bludworth.
* **Data-Driven Design:** Game content (rooms, items, hazards, evidence, etc.) is largely defined in `game_data.py`, with a patching system (`hazard_patch.py`) for easy updates and additions.

## How to Play / Controls

* **Interaction:**
    * **Text Input:** Type commands into the input field (e.g., "move north", "examine table", "take key").
    * **Action Buttons:** Use the main action category buttons (Move, Examine, Search, etc.) located on the GameScreen. Selecting an action will often reveal contextual target buttons.
    * **Contextual Buttons:** After selecting a main action or as a result of certain game events (like searching a container), specific target buttons will appear for you to click.
* **Key Commands (Examples):**
    * `list` or `help`: Shows available actions.
    * `examine [target]`: Get details about an object, item, or the room itself.
    * `search [furniture]`: Look inside containers.
    * `take [item]`: Pick up an item.
    * `use [item] on [target]`: Use an item from your inventory.
    * `inventory` or `i`: Check your inventory.
    * `map`: View a textual map of your surroundings.
    * `journal`: Review collected evidence.
    * `break [furniture]`: Attempt to force open or break furniture.
    * `unlock [target]`: Attempt to unlock a door or container, usually with a key.
* **Goal:** Survive each level by finding required evidence and reaching the exit, while managing your Health (HP) and Turns Left. Running out of either means Death has caught up.

## Installation & Setup (Running from Source)

1.  **Prerequisites:**
    * Python 3.x
    * Kivy library and its dependencies. Install Kivy using pip:
        ```bash
        python -m pip install kivy[full]
        # Or follow official Kivy installation instructions for your OS:
        # [https://kivy.org/doc/stable/gettingstarted/installation.html](https://kivy.org/doc/stable/gettingstarted/installation.html)
        ```
2.  **Clone the Repository (Example):**
    ```bash
    git clone [https://github.com/your_username/final-destination-terminal.git](https://github.com/your_username/final-destination-terminal.git)
    cd final-destination-terminal
    ```
3.  **Project Structure:**
    The game is organized into several Python files within a package structure (e.g., an `fd_terminal` directory):
    * `main.py`: Main application entry point.
    * `ui.py`: Defines all Kivy screens and UI elements.
    * `game_logic.py`: Core game mechanics, player state, command processing.
    * `hazard_engine.py`: Manages environmental hazards and their interactions.
    * `game_data.py`: Contains all game content (rooms, items, evidence, hazard definitions, etc.).
    * `achievements.py`: Handles the achievement system and evidence logging.
    * `utils.py`: Utility functions, like text coloring.
    * `tony_todd_tribute.py`: The tribute screen logic.
    * `hazard_patch.py`: Allows for patching new data into `game_data.py` at runtime.
    * `assets/`: Directory containing fonts, images, etc. (Ensure this path is correct for `resource_path` in `ui.py`).
4.  **Run the Game:**
    Navigate to the directory containing `main.py` (or its parent if `main.py` is inside the package) and run:
    ```bash
    python main.py
    # Or, if your main.py is inside a package like 'fd_terminal':
    # python -m fd_terminal.main 
    ```
    The specific command might vary slightly based on your exact project layout and how you've structured it as a Python package. The provided `main.py` uses relative imports like `from . import hazard_patch`, suggesting it's intended to be run as part of a package.

## Game Mechanics Overview

### Character Classes
Before starting a new game, you can select a character class. Each class has slightly different starting HP, Perception (affecting finding hidden things), and Intuition (affecting hazard warnings or sensing danger).

### Levels & Progression
The game is divided into levels, each with a unique setting (e.g., Lakeview Hospital, Bludworth House). To complete a level and progress, you typically need to find specific pieces of evidence and reach the designated exit. An Inter-Level screen summarizes your performance before you proceed.

### Hazards & Environment
The environment is highly dynamic and dangerous:
* **Active Hazards:** Objects and situations can become active hazards with various states (e.g., faulty wiring sparking, gas leaks, unstable objects).
* **Environmental State:** Rooms have environmental properties like gas level, wetness, fire, sparks, noise, and visibility, which are affected by hazards and player actions.
* **Chain Reactions:** Hazards can interact with each other (e.g., sparks igniting gas) or be triggered by player actions or other environmental changes. Fire can spread from objects to the room and even to adjacent rooms.
* **Mobile Hazards:** Some hazards, like the "robot_vacuum_malfunctioning," can move between rooms and interact with the player or other objects upon collision.
* **Temporary Effects:** Actions like breaking certain furniture can cause temporary environmental effects, such as a "Dust Cloud Puff" reducing visibility for a short duration.
* **Floor Hazards:** Items like "Shattered Porcelain Shard" on the floor can pose a risk when moving into or within a room.

### Quick Time Events (QTEs)
At critical moments, a QTE may be triggered, requiring you to type a specific command (e.g., "DODGE") within a short time limit to avoid damage or death. The MRI machine, for instance, can trigger a sequence of QTEs as it pulls objects towards the control room.

### Evidence, Journal & Achievements
* **Evidence:** Collect evidence items scattered throughout the game. These items are crucial for understanding the story, completing levels, and are logged in your journal.
* **Journal:** Access your journal (`journal` command or button) to review details of collected evidence, including names, descriptions, and when they were found.
* **Achievements:** Unlock achievements for accomplishing various milestones, such as finding your first piece of evidence, surviving levels, or reacting quickly to danger. Achievements are saved and loaded across game sessions.

### Saving and Loading
You can save your game progress at almost any time (outside of active QTEs) using the "save" command or UI button, choosing from several slots including a "quicksave". Load a previously saved game from the main menu or in-game. The game state, including player status, inventory, revealed items, interaction counters, current level room states, and active hazard states (including temporary effects), is saved.

## Customization & Data

The game is designed to be data-driven:
* **`game_data.py`:** This file is the central repository for all static game content, including room layouts, item properties, evidence details, character class stats, detailed hazard definitions (with states, interactions, and environmental effects), QTE parameters, disaster intros, and more.
* **`hazard_patch.py`:** This module allows for adding new items and hazards (or theoretically updating existing ones, though current logic skips existing keys) to the game data at runtime when the application starts. This makes it easier to expand the game content without directly modifying `game_data.py` every time.

## Credits & Acknowledgements

Based on the "Final Destination" film, book and comic series

Developed with love by: [KorbenD3P0] people associated with the IP officially, this was just a hobby project made to be informative for people interested in the lesser known, wider "FDU"

This game would not have been possible without TheInnsersect
(Hi, Mom!)

---

Enjoy your brush with Death, and try not to end up on its list permanently. Good luck.
### Troubleshooting

- If you encounter issues with missing modules, ensure you are using the correct Python version and that all dependencies are installed in your virtual environment.
- For Android builds, make sure all system dependencies for Buildozer are installed (see Kivy/Buildozer docs).

---

## Version History

v1.0.0 - Initial release
- Two complete levels: The Bludworth House and Lakeview Hospital
- Achievement system
- Save/Load functionality
