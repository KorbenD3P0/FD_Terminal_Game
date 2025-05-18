# game_data_refactored.py
import random
import logging
import copy

# Items that are fixed and should not be dynamically placed by the general random placement logic
FIXED_ITEMS_DYNAMIC_EXCLUSION = [
    "Newspaper Clipping", 
    "Bludworth's House Key", 
    "Bloody Brick", 
    "toolbelt", 
    "Coroner's Office Key", # Add the key here to ensure its specific placement is respected
    "Radiology Key Card",
    "Morgue Key Card",
    # Medical Director Key Card will be handled by random hospital container logic
]

# --- Existing Constants ---
DEFAULT_ITEM_WEIGHT = 1 #
LIGHT_ITEM_WEIGHT = 0.5 #
HEAVY_ITEM_WEIGHT = 3 #
VERY_HEAVY_ITEM_WEIGHT = 5 #
INITIAL_TURNS = 60 #
STARTING_TURNS = INITIAL_TURNS # # Redundant, can use INITIAL_TURNS directly
HEAVY_PLAYER_THRESHOLD = 15 #
GAS_LEVEL_EXPLOSION_THRESHOLD = 2 #
QTE_DODGE_WRECKING_BALL_DURATION = 5 #
GAS_SPREAD_CHANCE_PER_EXIT_PER_TURN = 0.3 #
GAS_SPREAD_AMOUNT_PER_TICK = 0.2 #
GAS_DECAY_RATE_PER_TURN = 0.1 #
GAS_DECAY_CHANCE_PER_TURN = 0.2 #

# --- NEW: String Literals & Game Identifiers ---

# Player Action Verbs (primarily for internal logic if needed beyond parser aliasing)
ACTION_MOVE = "move"
ACTION_EXAMINE = "examine"
ACTION_BREAK = "break"
ACTION_TAKE = "take"
ACTION_FORCE = "force"
ACTION_SEARCH = "search"
ACTION_USE = "use"
ACTION_DROP = "drop"
ACTION_UNLOCK = "unlock"
ACTION_INVENTORY = "inventory"
ACTION_LIST_ACTIONS = "list"
ACTION_HELP = "help"
ACTION_SAVE = "save"
ACTION_LOAD = "load"
ACTION_QUIT = "quit"
ACTION_NEWGAME = "newgame" # As used in GameLogic.process_player_input for "restart"

# Critical Item Identifiers (add more as needed)
ITEM_LOOSE_BRICK = "loose brick" #
ITEM_BASEMENT_KEY = "Basement Key" #
ITEM_TOOLBELT = "toolbelt" #
ITEM_CORONERS_OFFICE_KEY = "Coroner's Office Key" #

# Critical Room Identifiers (add more as needed)
ROOM_FRONT_PORCH = "Front Porch" #
ROOM_FOYER = "Foyer" #
ROOM_LIVING_ROOM = "Living Room" #
ROOM_ATTIC = "Attic" #
ROOM_KITCHEN = "Kitchen" #
ROOM_HOSPITAL_EMERGENCY_ENTRANCE = "Hospital Emergency Entrance" #
ROOM_MORGUE = "Morgue Autopsy Suite" #
ROOM_MRI_CONTROL_ROOM = "MRI Control Room" #
ROOM_STAIRWELL = "Stairwell" #

# Hazard Type Identifiers (these are keys in the hazards dictionary)
HAZARD_TYPE_WEAK_FLOORBOARDS = "weak_floorboards" #
HAZARD_TYPE_FAULTY_WIRING = "faulty_wiring" #
HAZARD_TYPE_GAS_LEAK = "gas_leak" #
HAZARD_TYPE_WOBBLY_CEILING_FAN = "wobbly_ceiling_fan" #
HAZARD_TYPE_MRI = "mri_machine_hazard" #
HAZARD_TYPE_SPREADING_FIRE = "spreading_fire" #
HAZARD_TYPE_ELECTRICAL_FIRE = "electrical_fire" #

# Hazard State Identifiers (examples if commonly checked)
HAZARD_STATE_COLLAPSING = "collapsing" #
HAZARD_STATE_IGNITED = "ignited" #
HAZARD_STATE_SPARKING = "sparking" #
HAZARD_STATE_LEAKING = "leaking" #
HAZARD_STATE_HEAVY_LEAK = "heavy_leak" #
HAZARD_STATE_BURNT_OUT_HULK = "burnt_out_hulk" #
HAZARD_STATE_SHORTED_OUT = "shorted_out" #

QTE_TYPE_DODGE_WRECKING_BALL = "dodge_wrecking_ball"
QTE_TYPE_GENERIC_DODGE = "dodge"
QTE_TYPE_CLIMB = "climb"
QTE_TYPE_BALANCE = "balance"
QTE_TYPE_RUN = "run"
QTE_TYPE_DIFFUSE = "diffuse" 
QTE_TYPE_DODGE_PROJECTILE = "dodge_projectile"
QTE_TYPE_BUTTON_MASH = "button_mash_qte"
QTE_TYPE_SEQUENCE_INPUT = "sequence_input_qte"
GAME_OVER_MRI_DEATH = "The malfunctioning MRI machine turned the room into a deadly vortex of metal. {object_description} slammed into you with horrific force, {impact_result}. Your attempt to force the door ended in a gruesome demise."
MAX_MRI_QTE_FAILURES = 2 
STAIRWELL_DOOR_FORCE_THRESHOLD = 2 

# QTE Responses (player inputs)
QTE_RESPONSE_DODGE = "dodge" 
QTE_RESPONSE_DODGE_EXCLAMATION = "dodge!" 
QTE_RESPONSE_JUMP = "jump"
QTE_RESPONSE_CLIMB = "climb"
QTE_RESPONSE_PULL = "pull"
QTE_RESPONSE_UP = "up"
QTE_RESPONSE_BALANCE = "balance"
QTE_RESPONSE_STEADY = "steady"
QTE_RESPONSE_STABILIZE = "stabilize"
QTE_RESPONSE_RUN = "run"
QTE_RESPONSE_SPRINT = "sprint"
QTE_RESPONSE_FLEE = "flee"
QTE_RESPONSE_CUT_WIRE = "cut" 
QTE_RESPONSE_SNIP_WIRE = "snip"

QTE_DEFAULT_DURATION = 5 # General default duration in seconds
# QTE_DODGE_WRECKING_BALL_DURATION is already defined

# --- Scoring Constants ---
SCORE_QTE_SUCCESS = 10
SCORE_QTE_COMPLEX_SUCCESS = 15
SCORE_EVIDENCE_FOUND = 20 # Example score for finding a piece of evidence

# --- Achievement IDs (as strings, matching keys in achievements.py) ---
ACHIEVEMENT_FIRST_EVIDENCE = "first_evidence" #
ACHIEVEMENT_COLLECTOR = "collector" #
ACHIEVEMENT_SURVIVOR = "survivor" #
ACHIEVEMENT_HOUSE_ESCAPED = "survived_the_house" #
ACHIEVEMENT_HOSPITAL_SURVIVED = "survived_the_hospital" #
ACHIEVEMENT_SPEEDRUN = "speedrun" #
ACHIEVEMENT_QUICK_REFLEXES = "quick_reflexes" #

# --- Journal Categories ---
JOURNAL_CATEGORY_EVIDENCE = "Evidence" # Matching how AchievementsSystem might categorize
JOURNAL_CATEGORY_EVENTS = "Events"
JOURNAL_CATEGORY_CHARACTERS = "Characters"
JOURNAL_CATEGORY_HAZARDS_ENCOUNTERED = "Hazards Encountered"

# --- Internal Game Signals ---
SIGNAL_QTE_TIMEOUT = "INTERNAL_QTE_TIMEOUT_FAILURE_SIGNAL" #

GAME_OVER_MRI_DEATH = "The malfunctioning MRI machine turned the room into a deadly vortex of metal. {object_description} slams into you with horrific force, {impact_result}. Your attempt to force the door ended in a gruesome demise."
MAX_MRI_QTE_FAILURES = 2 # Player dies on the second failure
STAIRWELL_DOOR_FORCE_THRESHOLD = 2 # Number of force attempts to open the Stairwell door

# Player Action Verbs (ensure ACTION_FORCE is defined if not already)
ACTION_FORCE = "force"
ACTION_BREAK = "break" # Assuming break is also used/defined
QTE_TYPE_DODGE_PROJECTILE = "dodge_projectile" # Ensure this is defined for MRI QTEs

# Hazard Type Identifiers
HAZARD_TYPE_MRI = "mri_machine_hazard" # Ensure this is defined for MRI hazard


# --- UI Screen Names (Mainly for UI logic, but if GameLogic needs to make decisions based on them)
SCREEN_TITLE = "title" #
SCREEN_INTRO = "intro" #
SCREEN_GAME = "game" #
SCREEN_WIN = "win" #
SCREEN_LOSE = "lose" #
SCREEN_ACHIEVEMENTS = "achievements" #
SCREEN_JOURNAL = "journal" #
SCREEN_SAVE_GAME = "save_game" #
SCREEN_LOAD_GAME = "load_game" #
SCREEN_CHARACTER_SELECT = "character_select" #
SCREEN_TUTORIAL = "tutorial" #

# --- Level Configuration ---
LEVEL_REQUIREMENTS = {
    1: { # Formerly Hospital (Level 2 data)
        "name": "Hope River Hospital",
        "evidence_needed": ["Bludworth's House Key"], # Player must find this key to "complete" the hospital
        "entry_room": "Hospital Emergency Entrance",
        "exit_room": "Hospital Morgue Exit", # Player exits here to go to Bludworth's House
        "next_level_id": 2,
        "next_level_start_room": "Front Porch" # Entry point for Bludworth House
    },
    2: { # Formerly Bludworth House (Level 1 data)
        "name": "The Bludworth House",
        # The objective is now to find Bludworth's core research/final clues.
        "evidence_needed": ["Newspaper Clipping", "Bludworth's Final Notes"], # Example, assuming Newspaper Clipping is still relevant
        "entry_room": "Front Porch",
        "exit_room": "Front Porch",  # Example: Player escapes the house once objective met.
                                     # Or could be a new exit like "Hidden Study Exit"
        "next_level_id": None, # This is now the final level in this 2-level setup
        "next_level_start_room": None
    }
}

CHARACTER_CLASSES = {
    "Journalist": {"max_hp": 10, "perception": 1, "intuition": 1, "description": "Balanced. No special bonuses.", "observations": {"inter_level_thought": "I can't shake the feeling that something terrible is about to happen. I need to stay alert."}},
    "EMT": {"max_hp": 14, "perception": 1, "intuition": 1, "description": "More base health.", "observations": {"inter_level_thought": "I can feel the adrenaline coursing through my veins. This is what I was trained for, and now I'll use my skills to keep myself alive."}},
    "Detective": {"max_hp": 10, "perception": 3, "intuition": 1, "description": "Higher perception for finding clues/hazards.", "observations": {"inter_level_thought": "The pattern is becoming clear; I can feel it in my gut. This isn't just a coincidence."}},
    "Medium": {"max_hp": 10, "perception": 1, "intuition": 3, "description": "Higher intuition for hazard warnings.", "observations": {"inter_level_thought": "Why do I feel like I'm being watched? Something's not right here."}}
}

qte_definitions = {
    # ... (existing QTEs like QTE_TYPE_DODGE_WRECKING_BALL if you formalize them here) ...
    QTE_TYPE_DODGE_PROJECTILE: {
        "name": "Dodge Projectile",
        "valid_responses": [QTE_RESPONSE_DODGE, QTE_RESPONSE_DODGE_EXCLAMATION], # e.g., "dodge", "dodge!"
        "default_duration": 3, # Seconds, make it quick
        "score_on_success": SCORE_QTE_SUCCESS, # 10 points
        "success_message_default": "You deftly sidestep the flying object!",
        "failure_message_default": "You're too slow! The object slams into you.",
        "hp_damage_on_failure": 5 # Default damage if not fatal (can be overridden by context)
    },
        QTE_TYPE_DODGE_PROJECTILE: {
        "name": "Dodge Projectile",
        "valid_responses": [QTE_RESPONSE_DODGE, QTE_RESPONSE_DODGE_EXCLAMATION],
        "default_duration": 3,
        "score_on_success": SCORE_QTE_SUCCESS,
        "success_message_default": "You deftly sidestep the flying object!",
        "failure_message_default": "You're too slow! The object slams into you.",
        "hp_damage_on_failure": 5
    },
    QTE_TYPE_BUTTON_MASH: {
        "name": "Rapid Interaction",
        "default_duration": 5.0, # Time to complete the mashing
        "target_mash_count": 10, # How many "mashes" needed
        "score_on_success": SCORE_QTE_SUCCESS,
        "success_message_default": "You managed to interact rapidly enough!",
        "failure_message_default": "Not fast enough!",
        "hp_damage_on_failure": 2
    },
    QTE_TYPE_SEQUENCE_INPUT: {
        "name": "Command Sequence",
        "default_duration": 7.0, # Time to type the sequence
        "score_on_success": SCORE_QTE_COMPLEX_SUCCESS,
        "success_message_default": "Sequence input correct!",
        "failure_message_default": "Incorrect sequence or too slow!",
        "hp_damage_on_failure": 3
    }
}

disasters = {
    "a plane whose wing broke off mid-air and": {
        "description": "You were seconds from boarding the flight when {visionary}, their face slick with sweat, seized your arm, their grip like a vice, and rasped, '{warning}' You listen, for some reason, and later watch the plane's wing detach during takeoff, shearing the plane's back half in two. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(50, 180),
        "warnings": [
            "NO! Don't get on! The wing... it's going to SHEAR OFF!",
            "That engine's screaming wrong! It's a death trap, I tell you!",
            "WE'RE ALL GOING TO DIE! Don't you understand?! THIS PLANE IS A COFFIN!",
            "ANY OTHER FLIGHT! For God's sake, that wing is compromised!",
            "Look at the rivets on that wing! They're tearing! Don't board this flying deathtrap!",
            "By all that's sacred, turn back NOW! This flight is doomed!",
            "They're all going to be ripped apart! We're next if we get on!",
            "To hell with this! I'm not dying today. Are you insane enough to board?"
        ],
        "categories": ["transportation_air", "mechanical_failure", "public_transit_hub"]
    },
    "a devastating highway pile-up on Route 42 that": {
        "description": "You were merging onto Route 42 when a battered pickup truck screeching to a halt directly in front of you. You see {visionary} exit the passenger side, screaming, '{warning}' Just moments later, a cacophony of screeching tires, shattering glass, and twisted metal erupted behind you, a devastating chain reaction of mangled metal and crushed bodies. Cars slammed into each other, crumpling like tin cans, their occupants trapped within. Limbs were twisted at unnatural angles, blood splattered across shattered windshields, and the air filled with the metallic tang of carnage. The screams of the dying echoed through the wreckage. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(20, 50),
        "warnings": [
            "DON'T GO ON THE RAMP! It's a slaughterhouse waiting to happen!",
            "That truck... it's going to jackknife! BRAKE, YOU FOOL!",
            "SLAM THE BRAKES! NOW! Or we're part of that wreckage!",
            "GET OFF THE HIGHWAY! It's a demolition derby, and we're the targets!",
            "LOG TRUCK! The chains are snapping! It's going to spill death everywhere!",
            "PULL OVER! DEAR GOD, PULL OVER BEFORE IT'S TOO LATE!",
            "ARE YOU BLIND?! That semi is going to OBLITERATE US!",
            "Those logs... they're coming loose! It's going to be a bloodbath!",
            "This fog isn't just thick, it's a SHROUD! We have to stop or die!",
            "NOT THIS EXIT! It leads straight to HELL!"
        ],
        "categories": ["transportation_road", "vehicle_accident", "public_roadway"]
    },
    "a luxury ferry sinking in Lake Serenity that": {
        "description": "You were on deck of the 'Queen Isabella' when {visionary} stumbled towards you, seizing your hand, pleading, '{warning}' Disembarking just minutes before its departure, you stood on the shore as the ferry tragically succumbed to the depths of Lake Serenity. The elegant vessel was swallowed by the dark, churning water, its lights flickering and then extinguished. The screams of the trapped passengers echoed across the still lake before being silenced forever by the cold, unforgiving water. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(80, 250),
        "warnings": [
            "THE HULL IS BREACHED! We're taking on water fast!",
            "TO THE LIFE RAFTS! NOW! Before we're all dragged to the bottom!",
            "ABANDON SHIP! IT'S GOING DOWN! EVERYONE OFF!",
            "It's sinking! JUMP! For your life, JUMP INTO THE FREEZING WATER!",
            "That list... it's not just a list, it's a goddamn death spiral! GET OFF!",
            "I CAN'T SWIM! Oh God, we're all going to drown in this icy grave!",
            "This rust bucket isn't just old, it's cursed! We should never have boarded!"
        ],
        "categories": ["transportation_water", "structural_failure", "recreational_setting"] #
    },
    "a terrifying rollercoaster derailment at 'Demon's Peak' that": {
        "description": "You stood in the queue for the 'Demon's Peak' coaster when {visionary} suddenly burst through the crowd, yelling, '{warning}' Before you could react, they grabbed your arm, pulling you away. Just as the first car began its ascent, a sickening screech echoed through the park. The coaster lurched violently, its wheels tearing free from the track. The cars twisted and plunged, sending passengers hurtling through the air. Bodies slammed against the twisted metal supports, their screams swallowed by the brutal impact. The air filled with the sickening crunch of bone and the metallic tang of blood. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(15, 40),
        "warnings": [
            "DON'T GET ON THAT RIDE! It's a one-way ticket to oblivion!",
            "THE TRACK IS WARPED! It's going to derail and kill everyone!",
            "STOP THE COASTER! FOR THE LOVE OF GOD, STOP IT!",
            "THE HARNESS IS FAULTY! It won't hold! You'll be thrown out!",
            "IT'S GOING TOO FAST! The G-force will crush us, or the fall will!",
            "HOLD ON TIGHT! PRAY! This ride is about to become a massacre!",
            "This isn't a ride, it's a goddamn guillotine on rails! RUN!",
            "THE BOLTS! THEY'RE SHEARING OFF! The whole structure is compromised!",
            "MAINTAINED?! This thing is held together with spit and bad luck!",
            "I HAVE A TERRIBLE FEELING! This isn't excitement, it's PREMONITION!"
        ],
        "categories": ["public_venue_accident", "mechanical_failure", "entertainment_venue"]
    },
    "an inferno at the 'Crimson Lounge' nightclub that": {
        "description": "You were about to step into the 'Crimson Lounge' when {visionary} blocked your path, choking out, '{warning}' Moments later, screams erupted from inside as the nightclub became an inferno. Flames licked at the windows, their orange glow reflecting in the panicked eyes of those trapped within. The building became a tomb of charred remains, the air thick with smoke and the stench of burning flesh. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(30, 100),
        "warnings": [
            "FIRE! GET OUT NOW! Don't even hesitate!",
            "THE STAGE IS ENGULFED! The sprinklers aren't working!",
            "THE EXIT IS BLOCKED BY FLAMES! We're trapped!",
            "FLASHOVER IMMINENT! THE WHOLE PLACE IS GOING UP! EVERYONE OUT OR BURN!",
            "I SMELL GAS! This isn't just a fire, it's a BOMB waiting to go off!",
            "We're going to be cooked alive in here! Like rats in a furnace!",
            "This place is a tinderbox! One spark and it's an inferno!"
        ],
        "categories": ["public_venue_accident", "fire_related", "structural_hazard", "entertainment_venue"]
    },
    "a collapse of the McKinley Memorial Bridge that": {
        "description": "You were driving onto the McKinley Memorial Bridge when {visionary} ran into the road, waving their arms wildly, shrieking, '{warning}' Trusting your gut, you slammed on the brakes and reversed off just as the bridge buckled and plunged into the river below, a horrifying collapse. The concrete groaned and shattered, sending vehicles and bodies plummeting into the churning water, their screams swallowed by the roar of the collapsing structure. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(40, 120),
        "warnings": [
            "DON'T CROSS! THE BRIDGE IS UNSTABLE! IT'S GOING TO COLLAPSE!",
            "THOSE NOISES! The structure is failing! Metal fatigue!",
            "TURN BACK! NOW! Before we're all at the bottom of the river!",
            "IT'S SHAKING! The bridge is coming apart beneath us!",
            "DRIVE FASTER! OR WE'RE GOING DOWN WITH IT!",
            "GET OFF THE BRIDGE! It's a death trap!",
            "THE CABLES ARE SNAPPING! IT'S OVER! GO, GO, GO!",
            "This bridge isn't just old, it's condemned by fate itself!",
            "I CAN'T DO THIS! IT'S GOING TO PLUMMET! We're all going to die!",
            "WE'RE GOING TO DROWN! Trapped in our cars at the bottom of the river!"
        ],
        "categories": ["structural_collapse", "transportation_road", "infrastructure_failure"]
    },
    "an explosion at the McKinley Chemical Plant that": {
        "description": "You were walking near the McKinley Chemical Plant when {visionary} grabbed your arm, pulling you away, gasping, '{warning}' Barely out of range, you witnessed the devastating explosion that leveled the facility, a cloud of fire and debris erupting into the sky, sending shockwaves through the city. The air filled with the deafening roar of the explosion and the acrid stench of chemicals and burning metal. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(50, 180),
        "warnings": [
            "EVACUATE! CHEMICAL BREACH! The whole plant is unstable!",
            "TOXIC FUMES! It'll sear your lungs! RUN FOR YOUR LIFE!",
            "RUN! DON'T LOOK BACK! It's about to go up like a nuke!",
            "IT'S GONNA BLOW! A CHAIN REACTION! GET THE HELL OUT OF HERE, NOW!",
            "They never fixed that damn leak! Now we all pay the price in blood!",
            "MY LUNGS! I CAN'T BREATHE! The air is poison! We're dead!",
            "This town is a chemical time bomb, and the fuse is lit!"
        ],
        "categories": ["industrial_accident", "explosion_related", "environmental_hazard", "workplace_hazard"]
    },
    # Note: "a wildfire that swept through McKinley National Forest and somehow": was missing from your list but present in game_data.py, so I'll add it here.
    "a wildfire that swept through McKinley National Forest and somehow": {
        "description": "Deep within McKinley National Forest, you paused when {visionary} emerged from the undergrowth, their face etched with worry, rasping, '{warning}' They gestured behind them, where a faint haze of smoke began to curl through the trees. The ground vibrated with the roar of the firestorm, and the sky turned an angry, blood-red as the forest was reduced to a blackened, smoldering wasteland. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(10, 60),
        "warnings": [
            "THE FIRE IS SPREADING TOO FAST! We're cut off!",
            "TO THE RIVER! It's our only chance to survive the inferno!",
            "DON'T GO DEEPER INTO THE WOODS! You'll be burned alive!",
            "IT'S A CROWN FIRE! We're trapped in a furnace of trees!",
            "Those damn campers! Their negligence is going to kill us all!",
            "WE'RE GOING TO BURN ALIVE! I can feel the flesh crisping!",
            "Smells like a crematorium... and we're the next batch."
        ],
        "categories": ["natural_disaster", "environmental_hazard", "fire_related", "outdoor_locations"]
    },
    "a freak storm that flooded downtown McKinley in a matter of minutes and": {
        "description": "You were in downtown McKinley when {visionary} began shouting at the sky, '{warning}'. An inexplicable feeling of unease made you seek higher ground. Minutes later, a freak storm unleashed torrential rain, flooding the streets, turning them into raging rivers that swept away cars and people alike. The air filled with the roar of the storm and the screams of those caught in the flood. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(25, 90),
        "warnings": [
            "GET TO HIGHER GROUND! NOW! Before the streets become rivers!",
            "THE WATER IS RISING TOO QUICKLY! It's a flash flood!",
            "STAY OUT OF THE BASEMENTS! You'll drown like rats!",
            "FLASH FLOOD! RUN FOR YOUR LIVES! The city is going under!",
            "Those storm drains are useless! They're death traps in this deluge!",
            "HELP! I'M BEING SWEPT AWAY! The current is too strong!",
            "This isn't rain, it's a bloody biblical flood! We're finished!"
        ],
        "categories": ["natural_disaster", "weather_event", "urban_disaster", "flood_related"]
    },
    "a high-speed train collision outside McKinley Central Station that": {
        "description": "You were waiting on the platform for the commuter train when {visionary} pushed you back from the edge, screaming, '{warning}' Just then, a freight train collided head-on with your train in a brutal impact, a mangled mess of steel and broken bodies. The air filled with the screech of metal, the shattering of glass, and the screams of the dying. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(60, 200),
        "warnings": [
            "THE SIGNALS ARE DEAD! There's another train on this track!",
            "JUMP! GET OFF THE PLATFORM! NOW!",
            "BRACE FOR IMPACT! THIS IS IT! WE'RE GOING TO BE CRUSHED!",
            "WRONG TRACK! IT'S ON THE WRONG GODDAMN TRACK! OH MY GOD!",
            "They never check these things! We're just meat for their grinder!",
            "We're all going to be torn apart! Twisted metal and flesh!",
            "This isn't a station, it's an abattoir on rails!"
        ],
        "categories": ["transportation_rail", "mechanical_failure", "public_transit_hub", "vehicle_accident"]
    },
    "a ski lift malfunction that": {
        "description": "You were about to hop on the ski lift when {visionary} freaked out and said, '{warning}' A wave of dizziness washed over you, and you instinctively jumped out of the way just as the lift cable snapped, sending chairs plummeting down the slope. The screams of the falling skiers were lost in the wind, their bodies twisting and tumbling down the mountainside. The ones who held onto their seats were slammed into the mountain below when the cable caught and arced the string of seats through the air. There were {killed_count} people killed when the lift malfunctioned. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(5, 25),
        "warnings": [
            "DON'T GET ON THE LIFT! The cable is about to snap!",
            "THE CABLE IS FRAYING! It's unraveling like a cheap sweater!",
            "JUMP NOW! While you still can! Before you plummet to your death!",
            "THAT CABLE! IT'S NOT SECURE! YOU'LL ALL FALL! DON'T DO IT!",
            "The lift is swaying too much! It's going to break free!",
            "That grinding noise... the gears are failing! It's going to drop!",
            "THAT CABLE'S GONNA SNAP! We're all gonna be meat crayons down that slope!",
            "This thing hasn't been inspected since the Mesozoic era! It's a deathtrap!",
            "PLEASE, NO! IT'S NOT SAFE! We're going to die up there, dangling like puppets!",
            "WHAT WAS THAT CRACK?! Oh, God, this is how it ends!"
        ],
        "categories": ["public_venue_accident", "mechanical_failure", "recreational_setting", "height_related_danger"]
    },
    "an apartment collapse that": {
        "description": "You were about to enter your apartment building when {visionary} blocked the doorway, saying, '{warning}' A sudden wave of panic hit you, and you backed away rapidly as the entire structure imploded in a cloud of dust and debris, the screams of the trapped residents swallowed by the collapsing building. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(10, 50),
        "warnings": [
            "GET OUT OF THE BUILDING! NOW! The whole thing is coming down!",
            "THE CEILING IS CRACKING! The load-bearing walls are GONE!",
            "USE THE FIRE ESCAPE! IF IT'S STILL THERE! HURRY!",
            "IT'S COMING DOWN! The entire damn building is IMPLODING!",
            "Shoddy construction! They built this place with paperclips and lies!",
            "WE'RE GOING TO BE BURIED ALIVE! Crushed under tons of rubble! Help us!",
            "Well, there goes the neighborhood... and our lives with it."
        ],
        "categories": ["structural_collapse", "urban_disaster", "construction_failure"]
    },
    "an earthquake in your neighborhood that": {
        "description": "You were walking your garbage out to the street when {visionary} grabbed your hand, yelling, '{warning}' You dove under a sturdy awning just as the earthquake intensified, causing buildings to crumble around you. The air filled with the roar of collapsing structures and the cries of the injured, the ground shaking beneath you. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(25, 30),
        "warnings": [
            "DROP, COVER, AND HOLD ON! PRAY IT'S NOT THE BIG ONE!",
            "GET AWAY FROM WINDOWS! They'll shatter into a million daggers!",
            "WATCH FOR FALLING DEBRIS! Power lines, bricks, everything!",
            "IT'S THE BIG ONE! THE GROUND IS RIPPING APART! RUN FOR YOUR LIFE!",
            "This whole city is built on a damn fault line! We're just waiting to die!",
            "THE GROUND IS OPENING UP! It's swallowing everything whole!",
            "My priceless Ming vase! Oh, the humanity... and the structural integrity!"
        ],
        "categories": ["natural_disaster", "geological_event", "urban_disaster", "structural_collapse"]
    },
    "a typhoon off the coast that": {
        "description": "You were near the coast when {visionary} pointed towards the horizon, saying, '{warning}' An inexplicable fear urged you to seek shelter inland, mere hours before a devastating typhoon made landfall, unleashing its fury on the coastline. The wind howled, the waves crashed, and the rain fell in sheets, tearing apart buildings and flooding entire towns. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(150, 600),
        "warnings": [
            "BOARD UP THE WINDOWS! Or the storm will tear them out and us with them!",
            "SEEK SHELTER! Inland! NOW! This isn't just a storm, it's a monster!",
            "STAY AWAY FROM THE COAST! The storm surge will annihilate everything!",
            "CATEGORY 5! WE'RE ALL GOING TO BE BLOWN TO KINGDOM COME!",
            "They said it would turn north. They always lie until it's too late!",
            "THE WAVES ARE HIGHER THAN THE HOUSES! We're going to be swept out to sea!",
            "My yacht! My beautiful multi-million dollar yacht! It's going to be splinters!"
        ],
        "categories": ["natural_disaster", "weather_event", "coastal_disaster", "flood_related"]
    },
    "a sinkhole that opened under the McKinley business district and": {
        "description": "You were walking across the street on your lunch break to grab a bite when {visionary} tugged at your shirt, crying, '{warning}' You were in shock at this complete stranger having the audacity to insert themselves into your day, but ran as the ground started to open up in front of you, swallowing the area you were just standing on into a massive sinkhole. The ground collapsed like a gaping maw, the earth crumbling and falling into the darkness below. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(5, 30),
        "warnings": [
            "THE GROUND IS COLLAPSING! It's opening up right under us!",
            "WHAT ARE YOU WAITING FOR?! RUN! Or be swallowed by the earth!",
            "GET AWAY FROM THE EDGE! The whole street is caving in!",
            "RUN! IT'S A SINKHOLE! The entire business district is going down!",
            "GET OUT OF THERE! You're standing on your own grave!"
        ],
        "categories": ["natural_disaster", "geological_event", "urban_disaster", "structural_collapse"]
    },
    "a cruise ship that sunk after it was hit by a speedboat. The resulting explosion and lack of lifeboats": {
        "description": "You were enjoying the evening festivities on the cruise ship when {visionary} grabbed your arm, yelling, '{warning}' You grab a life jacket and prepare for the worst, just as the boat struck and flames erupted, engulfing a large section of the vessel. The screams of the burning passengers mingled with the crackling of the fire. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(50, 200),
        "warnings": [
            "THAT BOAT IS COMING AT US WAY TOO FAST!!",
            "PUT ON YOUR LIFE JACKET AND JUMP! NOW!!",
            "LOWER THE LIFEBOATS!! WE'RE GOING TO SINK!",
            "THE WHOLE SHIP'S ABOUT TO EXPLODE! Into the water, now!",
            "THE LIFEBOATS! WHERE ARE THEY?! Oh god, there aren't enough!",
            "And I just renewed my vows... This is one hell of a honeymoon."
        ],
        "categories": ["transportation_water", "explosion_related", "fire_related", "recreational_setting", "vehicle_accident"]
    },
    "a dam break that flooded the nearby Manitou Valley and": {
        "description": "You were picnicking by the river downstream from the massive dam when {visionary} ran towards you, shouting, '{warning}' A primal urge to flee washed over you, and you ran uphill as a wall of water surged towards you, the dam having catastrophically failed. The water roared, a terrifying torrent that swept away everything in its path. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(75, 400),
        "warnings": [
            "HEAD FOR THE HILLS! UPHILL! NOW! Or be swept away!",
            "A WALL OF WATER IS COMING! The dam has burst! RUN!",
            "DON'T STOP! Keep running until you can't see the valley!",
            "THE DAM BROKE! IT'S COMING! A TSUNAMI OF FRESHWATER DEATH!",
            "They said that dam would last a thousand years. It didn't last fifty!",
            "I CAN'T OUTRUN IT! It's too fast! We're all going to be washed away!",
            "My prize-winning petunias! Drowned! Oh, the humanity... and the hydrology!"
        ],
        "categories": ["infrastructure_failure", "flood_related", "man_made_disaster", "environmental_hazard"]
    },
    "a gas pipeline explosion that": {
        "description": "You were driving down a rural road when {visionary} flagged you down, yelling, '{warning}' An overwhelming sense of unease made you accelerate rapidly, narrowly escaping the massive fireball that erupted behind you as a gas pipeline exploded. The shockwave rocked your vehicle, the air filled with the booming roar and the stench of burning gas. Reports indicate there were {killed_count} people who died in the blast. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(10, 40),
        "warnings": [
            "GET AWAY FROM THE PIPELINE! It's about to rupture!",
            "DON'T LIGHT ANYTHING! NOT EVEN A SPARK! Or we're all incinerated!",
            "CALL 911! Tell them the pipeline is compromised! NOW!",
            "IT'S LEAKING GAS! One spark and this whole area becomes a crater!",
            "Pipeline safety? Ha! That's a myth. This was inevitable.",
            "THE PRESSURE! IT'S TOO HIGH! IT'S GONNA BLOW SKY HIGH!",
            "Smells like rotten eggs... and the inside of a furnace."
        ],
        "categories": ["industrial_accident", "explosion_related", "infrastructure_failure", "fire_related"]
    },
    "a factory collapse that": {
        "description": "You were visiting a local factory when {visionary} rushed towards you, stammering, '{warning}' A sudden wave of claustrophobia made you rush towards the exit, just as the building's roof caved in, crushing everything below in a cascade of twisted metal and concrete, the screams of those trapped within echoing through the collapsing structure. Reports indicate there were {killed_count} people killed in this disaster. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(20, 80),
        "warnings": [
            "THE ROOF IS CAVING IN! The whole structure is failing!",
            "RUN FOR THE EXIT! Don't look back, just run!",
            "WATCH OUT FOR MACHINERY! It's all coming down on top of us!",
            "THE SUPPORTS ARE FAILING! GET OUT! GET OUT NOW BEFORE YOU'RE CRUSHED!",
            "OSHA is going to have a field day with what's about to happen.",
            "So much for 'Made in McKinley'. More like 'Buried Alive in McKinley'."
        ],
        "categories": ["industrial_accident", "structural_collapse", "workplace_hazard"]
    },
    "a ferris wheel malfunction that": {
        "description": "The towering Ferris wheel loomed before you. You were about to step into a gondola when {visionary} seized your arm, rasping, '{warning}' They pointed a trembling finger at the central hub. As the wheel began its slow rotation, a sickening grinding sound echoed through the park. Then, with a deafening screech, the central axis snapped. The massive wheel buckled, its gondolas twisting and flinging their occupants into the night air. The cheerful music was replaced by horrifying screams and sickening thuds. Reports indicate there were {killed_count} people killed in this disaster. Afterwards, those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(10, 35),
        "warnings": [
            "STOP THE RIDE! THE AXIS IS SNAPPING! IT'S GOING TO COLLAPSE!",
            "WE'RE GOING TO DIE! Get away from this death machine!",
            "DON'T GET ON! It's a deathtrap waiting to spring!",
            "GET THE FUCK AWAY FROM THERE! Unless you want to be a human pancake!",
            "THE MAIN BEARING IS SHOT! It's tearing itself apart from the inside!",
            "This thing is a relic! It belongs in a scrapyard, not carrying people!",
            "WE'RE GOING TO FALL TO OUR DEATHS! Flung out like ragdolls!",
            "My cotton candy! Oh, and also, we're all about to be splattered across the midway."
        ],
        "categories": ["public_venue_accident", "mechanical_failure", "entertainment_venue", "height_related_danger"]
    },

    # --- NEW THRILLING DISASTERS ---
    "a shopping mall escalator suddenly reversing at high speed that": {
        "description": "You were idly window shopping, about to step onto the escalator to the food court, when {visionary}, perhaps a mall security guard off-duty, hissed, '{warning}' You hesitated, and a moment later, the ascending escalator grotesquely bucked, then reversed direction at terrifying speed. Screams erupted as shoppers were violently flung downwards, a cascade of bodies tumbling over each other, limbs snapping like twigs against the churning metal steps. The bottom of the escalator became a horrifying meat grinder. Reports indicate {killed_count} people were mangled or killed. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(10, 30),
        "warnings": [
            "DON'T STEP ON IT! THE GEARS ARE SHREDDED!",
            "IT'S GOING TO REVERSE! EVERYONE OFF, NOW!",
            "THAT GRINDING NOISE! THE MOTOR'S SHOT! RUN!",
            "THE EMERGENCY STOP ISN'T WORKING! IT'S A TRAP!",
            "Look at the teeth on those steps! They're like a shark's jaw!",
            "My shopping bags! Oh, the humanity... and the velocity!"
        ],
        "categories": ["public_venue_accident", "mechanical_failure", "urban_disaster"]
    },
    "a city-wide blackout during a heatwave causing a cascading hospital failure that": {
        "description": "The city sweltered under a record-breaking heatwave. You were visiting a relative in the overburdened McKinley General when {visionary}, a harried-looking nurse, whispered urgently, '{warning}' Suddenly, the lights flickered and died. The city plunged into darkness. Backup generators sputtered and failed under the strain. Life support machines went silent one by one, monitors faded, and the oppressive heat became a suffocating blanket. Panic turned to despair in the corridors. Reports state {killed_count} critical patients perished. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(40, 150),
        "warnings": [
            "THE GRID'S OVERLOADED! IT'S GOING DOWN! ALL OF IT!",
            "GET OUT OF THE HOSPITAL! THE GENERATORS WON'T HOLD!",
            "LIFE SUPPORT IS FAILING! THEY'RE ALL GOING TO DIE IN THE DARK!",
            "This heat... it's not just weather, it's a prelude to something awful!",
            "No power, no air, no hope! We're cooked!",
            "They said the backup systems were foolproof... fools!"
        ],
        "categories": ["infrastructure_failure", "urban_disaster", "medical_facility_failure", " cascading_disaster"]
    },
    "a high-rise window washer platform collapsing onto a crowded plaza that": {
        "description": "Lunchtime in the bustling downtown plaza. You were about to sit on a bench when {visionary}, a street artist frantically sketching, yelled, '{warning}' and pointed skyward. High above, a window washing platform swung erratically, then with a sickening series of snaps, its cables gave way. The platform, with its occupants, plummeted dozens of stories, exploding like a bomb on impact with the crowded square. Bodies and debris were flung hundreds of feet. The picturesque scene turned into a bloodbath. {killed_count} were killed instantly. Afterwards, those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(25, 70),
        "warnings": [
            "LOOK UP! THE CABLES ARE SNAPPING! IT'S COMING DOWN!",
            "RUN! GET OUT OF THE PLAZA! IT'S NOT SAFE!",
            "THEY'RE FALLING! OH GOD, THEY'RE FALLING!",
            "That winch is screaming! It's about to give!",
            "Move! For the love of God, MOVE!",
            "My artisanal sandwich! And those poor souls..."
        ],
        "categories": ["structural_failure", "public_venue_accident", "height_related_danger", "workplace_hazard_public_impact"]
    },
    "a grain silo explosion at a rural processing plant that": {
        "description": "You were on a scenic drive through farmland, passing by the towering McKinley Grain Co-op, when {visionary}, an old farmer on a tractor, waved you down frantically, shouting '{warning}' Moments later, a deafening boom ripped through the air. One of the massive silos erupted in a colossal fireball, the shockwave flattening nearby structures and sending a rain of burning grain and twisted metal across the fields. The very air seemed to ignite. Reports indicated {killed_count} workers and bystanders were killed. Later, those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(5, 25),
        "warnings": [
            "THE DUST! IT'S TOO THICK! IT'S GONNA BLOW!",
            "GET AWAY FROM THE SILOS! THEY'RE UNSTABLE!",
            "THAT SPARK! NO! IT'LL IGNITE EVERYTHING!",
            "RUN! SHE'S GONNA GO UP LIKE A VOLCANO!",
            "They never cleaned out the conveyors! It's a powder keg!",
            "This isn't just grain, it's a bomb waiting for a spark!"
        ],
        "categories": ["industrial_accident", "explosion_related", "rural_disaster", "workplace_hazard", "fire_related"]
    },
    "a catastrophic theater stage collapse during a live performance that": {
        "description": "You were in the audience, settled in for the premiere of 'McKinley: The Musical!' when {visionary}, perhaps an usher with a look of sheer terror, whispered, '{warning}' Just as the grand finale began, with pyrotechnics and complex hydraulics, the stage rigging above groaned ominously. With a sound like thunder, the entire proscenium arch and tons of equipment collapsed onto the stage, crushing performers and sending the audience into a panicked stampede. The air filled with dust, screams, and the smell of electrical fires. {killed_count} died in the initial collapse or ensuing chaos. Those who initially survived were killed in increasingly bizarre ways, like being {survivor_fates}.",
        "killed_count": random.randint(30, 90),
        "warnings": [
            "THE RIGGING IS FAILING! THE WHOLE STAGE IS COMING DOWN!",
            "GET OUT! EVACUATE THE THEATER, NOW!",
            "THOSE HYDRAULICS ARE OVERLOADED! IT CAN'T HOLD!",
            "PYROTECHNICS NEAR THE CURTAINS?! ARE THEY INSANE?",
            "It's not part of the show! RUN FOR YOUR LIVES!",
            "My signed playbill! And the structural integrity!"
        ],
        "categories": ["public_venue_accident", "structural_collapse", "mechanical_failure", "fire_related", "entertainment_venue"]
    }
}

CATEGORIZED_VISIONARIES = {
    "strangers_distinctive": [
        "a gaunt, wide-eyed stranger", "a woman with wild, tangled hair",
        "a pale, trembling man", "a wiry teenager with haunted eyes",
        "a disheveled, elderly man", "a transient man",
        "an old man with weathered skin", "an elderly woman with wild eyes", # Changed from "serene expression" for more consistency
        "a nervous young man", "a breathless young woman", "the craziest bitch you ever did see",
        "a blind street vendor", "a street performer", "one crazy bastard" # Corrected typo from "basard"
    ],
    "children_youths": [
        "a frantic kid no more than 13 years old", "a frantic teenager",
        "a young child with a look of terror"
    ],
    "family_friends": [ # These might be used for specific narrative setups if desired later
        "a frantic mother", "a frantic father", "a familiar face - your estranged sibling",
        "a familiar face - your estranged parent", "a familiar face - your estranged friend",
        "a familiar face - your estranged lover", "your best friend from childhood"
    ],
    "maintenance_technical": [
        "a maintenance worker with a haunted look", "a nervous engineer"
    ],
    "outdoor_nature_authority": [ # More specific for parks, forests, etc.
        "an old, grizzled park ranger", "an old fisherman" # Fisherman could be near water disasters too
    ],
    "transport_staff": [
        "a frantic steward", "a frantic-looking bus driver", "a frantic-looking taxi driver"
    ],
    "emergency_services": [
        "a frantic-looking police officer", "a frantic-looking firefighter",
        "a frantic-looking paramedic", "a frantic-looking doctor", "a frantic-looking nurse"
    ],
    "service_workers_venue": [ # For places like nightclubs, restaurants, stores
        "a frantic-looking security guard", "a frantic-looking waiter",
        "a frantic-looking waitress", "a frantic-looking bartender", "a carnival worker" # Carnival worker fits here or entertainment
    ],
    "bystanders_general": [ # Good general fallback
        "a frantic-looking pedestrian", "a frantic-looking man",
        "a frantic-looking tourist", "a frantic-looking elderly person",
        "a terrified looking woman"
    ]
    # Add more categories and assign existing visionaries as needed.
}

# Survivor fates for disaster intros
survivor_fates = [
    "impaled by a javelin thrown by a malfunctioning Olympic training robot",
    "crushed by a pallet of cleaning chemicals falling from a poorly secured forklift",
    "electrocuted by a hairdryer pushed into a bathtub by a cat",
    "consumed by a fire that was started by a malfunctioning toaster", 
    "asphyxiated by an over-inflating airbag that deployed randomly due to a bizarre electrical short",
    "dragged off their boat and under the water by an anchor",
    "melted by a sudden surge of molten glass from a shattering furnace at a glassblowing studio",
    "burned alive by a freak explosion of a nearby propane tank",
    "swept overboard on a cruise ship by a freak wave",
    "frozen solid after being accidentally locked in an industrial walk-in freezer when the door handle broke off before a freak electrical surge that super-chilled the unit",
    "swept away during a flash flood",
    "crushed by the sudden collapse of a theater marquee dislodged by a freak hailstorm",
    "impaled by a broken beam from a collapsing building",
    "immolated by a malfunctioning gas grill",
    "trampled by a panicked herd of escaped zoo animals during a city-wide blackout",
    "drowned in an industrial-sized washing machine they fell into while trying to retrieve a dropped phone",
    "suffocated when a grain silo unexpectedly discharged, burying them in corn",
    "decapitated by a rapidly closing automatic barrier arm at a parking garage",
    "mangled in the gears of a drawbridge that unexpectedly activated",
    "torn apart by a runaway snowblower that malfunctioned and chased them down",
    "fatally injured when the floor collapsed beneath them into an abandoned, spike-filled pit",
    "suffered a fatal heart attack after narrowly escaping one near death experience only to see their winning lottery ticket get snatched by the wind and incinerated by a street performer's fire-breathing act",
    "succumbed to a bizarre series of injuries starting with a seemingly harmless papercut",
    "crushed by a falling beam during a freak accident at a construction site",
    "incinerated when a model rocket show went horribly wrong, igniting a cache of fireworks",
    "crushed by falling machinery during a freak accident at a factory",
    "buried alive by accident when a construction crew miscalculated the depth of a trench",
    "decapitated in their vehicle by a jack-knifed semi",
    "sliced apart by a flying piece of metal from a nearby building demolition",
    "crushed beneath a dislodged section of carnival ride seating",
    "crushed beneath a sofa dropped from an apartment balcony by movers",
    "electrocuted by downed power lines after a sudden storm",
    "bisected by a runaway Zamboni at an ice rink",
    "decapitated by a low-flying drone delivering a suspiciously heavy package",
    "sucked into a combine harvester after tripping in a cornfield maze",
    "crushed by a falling church bell during a surprisingly violent wedding",
    "asphyxiated by a malfunctioning automatic car wash brush",
    "impaled by a rogue weather vane during a freak tornado",
    "flattened by a runaway steamroller at a chaotic construction site",
    "fatally perforated by a volley of nails from an exploding nail gun",
    "drowned in a vat of artisanal pickles at a food festival",
    "electrocuted by a giant, sparking bug zapper they mistook for modern art",
    "sliced in half by a rapidly descending automatic parking garage gate",
    "launched into orbit by an over-pressurized porta-potty explosion",
    "pummeled to death by a malfunctioning massage chair set to 'Extreme Measures'",
    "impaled through the skull by a rogue garden gnome launched from a lawnmower",
    "dragged into an industrial wood chipper by their own untied shoelace",
    "crushed by a giant inflatable mascot that suddenly deflated and fell",
    "suffocated inside a rapidly shrinking vacuum storage bag",
    "skewered by multiple umbrellas spontaneously opening inside a packed elevator",
    "fatally entangled in a runaway kite string during a beachfront storm",
    "bisected by a sheet of plate glass falling from a skyscraper during a pigeon scare"
]

# --- Furniture Definitions ---
# Types of furniture for categorization
room_furniture = {
    "general": [
        "dusty table", "floor", "worn armchair", "tattered sofa", "old trunk", "cabinet", "dining table", "cupboard"
    ],
    "bedroom": [
        "four-poster bed", "floor", "nightstand", "large desk", "dresser", "single bed", "cluttered desk"
    ],
    "library": [
        "bookshelves", "floor", "large desk"
    ],
    "kitchen": [
        "kitchen counter", "floor", "shelves", "trash can", "dirty sink"
    ],
    "bathroom": [
        "medicine cabinet", "floor", "stained bathtub", "dirty sink", "toilet"
    ],
    "basement": [
        "workbench", "shelves", "floor", "old trunk", "cabinet"
    ],
    "attic": [
        "crate", "floor", "stack of old boxes", "old trunk"
    ],
    "porch": [
        "broken rocking chair"
    ],
    "front porch": [
        "broken rocking chair"
    ],
    "foyer": [
        "dusty table", "floor", "worn armchair", "tattered sofa", "old trunk", "cabinet", "coat rack"
    ],
    "hallway": [
        "small table", "coat rack"
    ],
    # --- Hospital-specific furniture containers ---
    "hospital": [
        "reception desk",         # Hospital Emergency Entrance
        "low table",              # Waiting Room
        "hospital bed",           # Patient Room 101
        "bedside table",          # Patient Room 101
        "metal shelves",          # Supply Closet
        "control desk",           # MRI Control Room
        "equipment cart",         # MRI Scan Room
        "instrument cabinet",     # Morgue Autopsy Suite
        "mahogany desk",          # Coroner's Office
        "bookshelves"             # Coroner's Office (already in library, but included for hospital context)
    ]
}

# --- Room Name Constants ---
ROOM_MRI_SCAN_ROOM = "MRI Scan Room"
ROOM_MRI_CONTROL_ROOM = "MRI Control Room"
ROOM_RADIOLOGY_WING_ACCESS = "Radiology Wing Access"
ROOM_STAIRWELL = "Stairwell"
ROOM_MORGUE = "Morgue"

rooms = {
    1: {
        "Hospital Emergency Entrance": {
            "description": "Automatic doors slide open into a brightly lit, sterile reception area. The smell of antiseptic is overwhelming. Empty chairs line the walls of the waiting room. A large, unattended reception desk sits under a flickering fluorescent light. It's eerily quiet.", 
            "exits": {"north": "ER Hallway", "west": "Waiting Room"}, 
            "floor": 1,
            "objects": ["flickering fluorescent light", "empty chairs"], 
            "furniture": [{"name": "reception desk", "is_container": True, "locked": False, "capacity": 3, "possible_items": ["Radiology Key Card"]}], 
            "items_present": [], 
            "hazards_present": [{"type": "faulty_wiring", "chance": 0.1, "object_name_override": "flickering light fixture", "support_object_override": "ceiling"}], 
            "possible_hazards": [{"type": "short_circuiting_appliance", "chance": 0.05, "object_name_options": ["computer monitor on desk"], "support_object_override": "reception desk"}], 
            "examine_details": {
                "reception desk": "The desk is cluttered with old forms and a dusty computer. Drawers might contain useful items.", 
                "flickering fluorescent light": "The light buzzes and flickers, casting unsettling shadows.", 
                "empty chairs": "Rows of plastic chairs, as if waiting for patients who will never arrive." 
            },
            "first_entry_text": "You heard there was someone here that might be able to help. Look for the Morgue; you need to get past the reception desk.", 
            "locked": False, 
            "unlocks_with": None 
        },
        "Waiting Room": {
            "description": "A large waiting area with rows of uncomfortable plastic chairs. Old magazines are scattered on a low table. A wall-mounted TV displays static. The room feels cold and unwelcoming.", 
            "exits": {"east": "Hospital Emergency Entrance"}, 
            "floor": 1,
            "objects": ["wall-mounted TV showing static", "scattered old magazines"], 
            "furniture": [{"name": "plastic chairs"}, {"name": "low table", "is_container": True, "locked": False, "capacity": 2, "possible_items": ["Radiology Key Card"]}],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "precarious_object", "chance": 0.1, "object_name_options": ["loose ceiling panel"], "support_object_override": "ceiling"}], 
            "examine_details": {
                "wall-mounted TV showing static": "The screen is a mess of 'snow'. The power light is on, though.", 
                "scattered old magazines": "Outdated magazines, their pages yellowed and dog-eared.", 
                "low table": "A simple table, perhaps with something hidden underneath or within its drawers if it has any." 
            },
            "first_entry_text": "The silence in this waiting room is deafening. You feel a prickling sense of being watched.", 
            "locked": False, 
            "unlocks_with": None 
        },
        "ER Hallway": {
            "description": "A long, sterile hallway stretches before you. Doors line either side, labeled with room numbers and department names. The floor is polished linoleum, reflecting the harsh overhead lights. A gurney is parked haphazardly against one wall.", 
            "exits": {"south": "Hospital Emergency Entrance", "north": "Patient Room 101", "east": ROOM_RADIOLOGY_WING_ACCESS, "west": "Supply Closet"},
            "objects": ["gurney"], 
            "furniture": [], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "faulty_wiring", "chance": 0.05, "object_name_options": ["exposed wall socket"], "support_object_override": "wall"}], 
            "examine_details": {
                "gurney": "An empty hospital gurney, stained with something dark." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None 
        },
        "Patient Room 101": {
            "description": "A typical hospital room. A single bed with crisp white sheets sits against one wall, an IV stand beside it. A small bedside table and a chair are the only other furnishings. The window looks out onto a brick wall.", 
            "exits": {"south": "ER Hallway"}, 
            "floor": 1,
            "objects": ["IV stand", "window overlooking brick wall"], 
            "furniture": [{"name": "hospital bed", "is_container": True}, {"name": "bedside table", "is_container": True, "possible_items": ["Radiology Key Card"]}],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "contaminated_waste", "chance": 0.1, "object_name_options": ["sharps container"], "support_object_override": "bedside table"}], 
            "examine_details": {
                "hospital bed": "The bed is neatly made, but feels cold and sterile.", 
                "bedside table": "A small table with a drawer. Might hold personal effects or medical supplies.", 
                "IV stand": "A metal IV stand with empty bags hanging from it." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None 
        },
        "Supply Closet": {
            "description": "A cramped closet filled with shelves stacked high with medical supplies: bandages, syringes, bottles of solution. It smells strongly of disinfectant.", 
            "exits": {"east": "ER Hallway"}, 
            "floor": 1,
            "objects": [], 
            "furniture": [{"name": "metal shelves", "is_container": True, "capacity": 5, "possible_items": ["Radiology Key Card"]}],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "unstable_shelf", "chance": 0.2, "object_name_override": "topmost shelf unit", "support_object_override": "metal shelves"}], 
            "examine_details": {
                "metal shelves": "Packed with all sorts of medical supplies. Some are balanced precariously." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None 
        },
        ROOM_RADIOLOGY_WING_ACCESS: {
            "description": "This area leads to the Radiology department. Heavy, lead-lined doors are visible ahead. Warning signs about radiation are posted on the walls.", 
            "exits": {"south": ROOM_RADIOLOGY_WING_ACCESS, "east": ROOM_MRI_SCAN_ROOM}, "floor": 1,
            "floor": 1,
            "objects": ["lead-lined doors", "radiation warning signs"], 
            "furniture": [{
                "name": "control desk", "is_container": True, "locked": False, "capacity": 2,
                "use_item_interaction": { # Interaction for Radiology Key Card
                    "item_names_required": ["Radiology Key Card", "Medical Director Key Card"], 
                    "action_effect": "activate_mri_hazard", 
                    "message_success": "You swipe the {item_name} through a card reader on the control desk. Lights on the console flash, and you hear the MRI machine in the next room hum to life with a powerful surge!",
                    "message_fail_item": "That key card doesn't seem to do anything with the control desk."
                }
            }],
            "items_present": [], 
            "hazards_present": [{"type": "short_circuiting_appliance", "chance": 0.15, "object_name_options": ["main console"], "support_object_override": "control desk"}],
            "possible_hazards": [], 
            "examine_details": {
                "lead-lined doors": "Thick, heavy doors, presumably to block radiation from imaging equipment.", 
                "radiation warning signs": "Standard trefoil symbols and warnings about magnetic fields and radiation." 
            },
            "first_entry_text": "A palpable sense of unseen energy emanates from this wing.", 
            "locked": False, 
            "unlocks_with": None 
        },
        ROOM_MRI_CONTROL_ROOM: {
            "description": "A room filled with complex machinery and computer consoles, looking through a large observation window into the MRI Scan Room. Various monitors display technical readouts.",
            "exits": {"south": "Radiology Wing Access", "east": "MRI Scan Room"},
            "floor": 1,
            "objects": ["computer consoles", "observation window", "wheelchair", "metallic IV stand", "oxygen tank"],
            "furniture": [
                {
                    "name": "control desk", 
                    "is_container": True, 
                    "locked": False, 
                    "capacity": 2,
                    "use_item_interaction": { # New interaction rule for using items on the desk
                        "item_names_required": ["Radiology Kay Card", "Medical Director Key Card"], # List of valid key cards
                        "action_effect": "activate_mri_hazard", # Custom effect identifier
                        "message_success": "You swipe the {item_name} through a card reader on the control desk. Lights on the console flash, and you hear the MRI machine in the next room hum to life with a powerful surge!",
                        "message_fail_item": "That key card doesn't seem to do anything with the control desk."
                    }
                }
            ],
            "items_present": [], # Key Card - Radiology will be placed here via its definition
            "hazards_present": [{"type": "short_circuiting_appliance", "chance": 0.15, "object_name_options": ["main console"], "support_object_override": "control desk"}],
            "possible_hazards": [],
            "examine_details": {
                "computer consoles": "A bank of computers used to operate the MRI machine. Many screens show error messages. There's a card reader slot on the main console.",
                "observation window": "A large, thick window providing a view into the MRI chamber.",
                "control desk": "The main desk for operating the MRI. Full of buttons and switches, and a prominent card reader."
            },
            "first_entry_text": None,
            "locked": False,
            "unlocks_with": None
        },
        ROOM_MRI_SCAN_ROOM: { 
            "description": "A stark white room dominated by a massive, cylindrical MRI machine. The air hums with latent power. Various medical equipment and metallic objects are scattered around. A heavy door labeled 'MORGUE' is on one wall, and another sturdy door leads to a 'STAIRWELL' on the east wall.",
            "exits": {"west": ROOM_MRI_CONTROL_ROOM, "east": ROOM_STAIRWELL, "south": ROOM_MORGUE}, "floor": 1,
            "objects": ["MRI machine", "metallic IV stand", "oxygen tank", "Morgue Door", "Stairwell Door"],
            "furniture": [{"name": "equipment cart", "is_container": True, "locked": False, "capacity": 1, "possible_items": [ITEM_CORONERS_OFFICE_KEY]}], # Coroner's key spawns here
            "hazards_present": [
                {"type": HAZARD_TYPE_MRI, "object_name_override": "MRI machine", "support_object_override": "center of room"}
            ],
            "items_present": ["Morgue Key Card"],
            "hazards_present": [
                {"type": "mri_machine_hazard", "object_name_override": "MRI machine", "support_object_override": "center of room"}
            ],
            "possible_hazards": [],
            "examine_details": {
                "MRI machine": "The colossal MRI machine. Its powerful magnetic field is a significant danger if it activates unexpectedly.",
                "metallic IV stand": "A standard metal IV stand, dangerously close to the MRI.",
                "oxygen tank": "A green oxygen tank, also metallic and a projectile risk.",
                "equipment cart": "A metal cart with a few drawers. Might contain tools or supplies.",
                "Morgue Door": "A heavy, reinforced door. It looks like it could be forced, but that might be risky in here.",
                "Stairwell Door": "A sturdy metal door, currently jammed shut. It looks like it might yield to repeated, forceful attempts."
            },
            "first_entry_text": "The hum of the MRI machine is unnerving. You feel a strange pull on any metallic items you might be carrying.",
            "locked": False,
            "unlocks_with": None
        },
        ROOM_STAIRWELL: {
            "description": "A cement-lined stairwell running behind the MRI scan room. Debris from the MRI room is scattered here.",
            "floor": 1,
            "locked": True,
            "unlocks_with": {"Radiology Key Card", "Morgue Key Card", "Medical Director Key Card"},
            "exits": {"west": "MRI Scan Room", "downstairs": "Hospital Morgue Hallway"}, 
            "objects": ["scattered debris"]
        },
        "Hospital Morgue Hallway": {
            "description": "A cold, dimly lit hallway. The air is stale and carries a faint chemical odor. A sign on a door at the end reads 'MORGUE - AUTHORIZED PERSONNEL ONLY'. Another door is labeled 'Coroner's Office'.", 
            "exits": {"upstairs": ROOM_RADIOLOGY_WING_ACCESS, "north": "Morgue Autopsy Suite", "east": "Coroner's Office"}, "floor": -1,
            "floor": -1,
            "objects": ["sign - MORGUE", "sign - Coroner's Office"], 
            "furniture": [], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "faulty_wiring", "chance": 0.1, "object_name_options": ["flickering ceiling light"], "support_object_override": "ceiling"}], 
            "examine_details": {
                "sign - MORGUE": "A stark, official sign. No doubt what lies beyond.", 
                "sign - Coroner's Office": "This door is more ornate than the others. It looks important." 
            },
            "first_entry_text": "The temperature drops noticeably here. This part of the hospital feels truly grim.", 
            "locked": False, 
            "unlocks_with": None 
        },
        "Morgue Autopsy Suite": {
            "description": "A cold, sterile room with stainless steel tables and bright overhead lights. Trays of gleaming instruments lie nearby. Several refrigerated body storage units line one wall. The smell of disinfectant and something colder... and older... hangs in the air.", 
            "exits": {"south": "Hospital Morgue Hallway"}, "floor": -1, # Corrected exit
            "objects": ["stainless steel tables", "trays of instruments", "refrigerated body storage units"], 
            "furniture": [{"name": "instrument cabinet", "is_container": True, "locked": False, "capacity": 2}], 
            "items_present": [], 
            "hazards_present": [{"type": "contaminated_waste", "chance": 0.2, "object_name_options": ["biohazard disposal unit"], "support_object_override": "corner"}], 
            "possible_hazards": [], 
            "examine_details": {
                "stainless steel tables": "Cold, gleaming tables designed for one grim purpose.", 
                "trays of instruments": "Scalpels, saws, and other tools of the trade, meticulously arranged.", 
                "refrigerated body storage units": "Silent, cold compartments. Best left undisturbed.", 
                "instrument cabinet": "A glass-fronted cabinet holding more specialized tools and chemicals." 
            },
            "first_entry_text": "There's no mistaking the purpose of this room. A profound sense of death lingers here.", 
            "locked": False, 
            "unlocks_with": None 
        },
        "Coroner's Office": {
            "description": "A surprisingly well-appointed office, a stark contrast to the rest of the hospital. Bookshelves line one wall, a large mahogany desk sits in the center, and framed diplomas adorn the walls. It smells of old books and faint pipe tobacco. This must have been William Bludworth's office.", 
            "exits": {"west": "Morgue Autopsy Suite", "south": "Hospital Morgue Exit"}, 
            "objects": ["framed diplomas"], 
            "furniture": [ 
                {"name": "mahogany desk", "is_container": True, "locked": True, "capacity": 3, "unlocks_with_item": "Desk Drawer Key"}, 
                {"name": "bookshelves", "is_container": True, "locked": False, "capacity": 4} 
            ],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "precarious_object", "chance": 0.1, "object_name_options": ["heavy medical encyclopedia"], "support_object_override": "bookshelves"}], 
            "examine_details": {
                "mahogany desk": "A large, impressive desk. Its drawers are likely locked. There are strange carvings on its surface.", 
                "bookshelves": "Filled with medical texts, anatomy charts, and more esoteric volumes on folklore and mortality.", 
                "framed diplomas": "Various degrees and commendations for a Dr. William Bludworth." 
            },
            "first_entry_text": "This room feels different. More personal. The presence of Bludworth is strong here.", 
            "locked": True, 
            "unlocks_with": ITEM_CORONERS_OFFICE_KEY,
        },
        "Hospital Morgue Exit": { 
            "description": "A heavy steel door at the back of the morgue complex, leading to an exterior loading dock. This seems to be a way out.", 
            "exits": {"north": "Coroner's Office"}, 
            "objects": ["heavy steel door"], 
            "furniture": [], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [], 
            "examine_details": {
                "heavy steel door": "A reinforced door, possibly leading to the outside." 
            },
            "first_entry_text": "This door looks like a way out of this nightmare.", 
            "locked": False, 
            "unlocks_with": None 
            }
        },
    2: {  # Level 2, Bloodworth's Residence
        "Front Porch": {
            "description": "The rotted wooden porch creaks under your feet. The [front door], a heavy oak scarred by time, stands before you. It's firmly shut. A chilling breeze whispers through the overgrown ivy clinging to the decaying facade.", 
            "exits": {"inside": "Foyer"}, # The "Foyer" itself will be locked
            "objects": ["overgrown ivy", "decaying facade", "front door"], # Added "front door"
            "furniture": [{"name": "broken rocking chair", "is_container": False, "locked": False}], # Made not a container for simplicity unless intended
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.2, "object_name": "rotted porch step"}], 
            "examine_details": {
                "broken rocking chair": "A splintered old rocking chair. It sways gently, though there's no wind.",
                "overgrown ivy": "Thick, dark ivy chokes the walls, its tendrils like grasping fingers.", 
                "decaying facade": "The house's exterior is crumbling, paint peeling like sunburnt skin.",
                "front door": "A massive oak door, reinforced with iron bands. It's clearly locked. There's a large, ornate keyhole."
            },
            "first_entry_text": "The air here feels heavy, expectant. Stepping onto the porch feels like crossing a threshold into somewhere truly unwelcoming.", 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, 
            "sink_interactions": 0, 
            "window_interactions": 0, 
            "bookshelves_interactions": 0, 
            "ceiling_fan_interactions": 0, 
            "crate_interactions": 0, 
            "has_newspaper_clipping": False, 
            "stairs_interactions": 0 
        },
        "Foyer": {
            "description": "You step into a grand, yet decaying foyer. Dust motes dance in the slivers of light piercing the grime-coated windows. A massive, tarnished crystal chandelier hangs precariously overhead. A wide staircase, its banister chipped and warped, ascends to the upper floor. To the west, a shadowed archway leads to a living room, and to the east, a formal dining room. A door to the south seems to lead to the basement stairs.", 
            "exits": {"upstairs": "Hallway", "west": "Living Room", "east": "Dining Room", "outside": "Front Porch", "south": "Basement Stairs"}, 
            "objects": ["tarnished chandelier", "grime-coated windows", "wide staircase"], 
            "furniture": [ 
                {"name": "dusty table", "is_container": True, "locked": False, "capacity": 2}, 
                {"name": "coat rack", "is_container": False, "locked": False} 
            ],
            "items_present": [], 
            "hazards_present": [{"type": "precarious_object", "object_name_override": "tarnished chandelier", "support_object_override": "ceiling"}], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.15}], 
            "examine_details": {
                "tarnished chandelier": "This once magnificent chandelier is now coated in grime and sways dangerously with every draft. It looks like it could fall at any moment.", 
                "grime-coated windows": "Years of dirt obscure the view outside, casting the foyer in perpetual twilight.", 
                "wide staircase": "The main staircase looks impressive but parts of its banister are broken, and the wood is warped.", 
                "dusty table": "A heavy wooden table covered in a thick layer of dust. Perfect for hiding small items.", 
                "coat rack": "An old-fashioned coat rack stands empty, save for a few cobwebs." 
            },
            "first_entry_text": "The silence inside is profound, broken only by the creak of the floorboards underfoot. The smell of dust and decay is thick in the air.", 
            "locked": True, # <<< MAKE THE FOYER INITIALLY LOCKED
            "unlocks_with": "Bludworth's House Key",
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Living Room": {
            "description": "Dusty sheets cover most of the furniture...",
            "exits": {"east": "Foyer"}, 
            "objects": ["fireplace", "dusty sheets"],
            "furniture": [ 
                {"name": "worn armchair", "is_container": True, "locked": False, "capacity": 1}, 
                {"name": "tattered sofa", "is_container": True, "locked": False, "capacity": 2},
                # Add the fireplace cavity as searchable furniture:
                {"name": "fireplace cavity", "is_container": True, "locked": False, "capacity": 1, "is_hidden_container": True} 
                # "is_hidden_container": True is a new flag concept. GameLogic needs to handle making this visible/searchable.
                # Alternatively, don't make it 'hidden' and rely on descriptive text from fireplace examine.
            ],
            "hidden_objects": ["loose brick"], # "fireplace cavity" might be removed if handled as furniture visibility
            "items_present": [], # "loose brick" is revealed by examining fireplace
            "hazards_present": [], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.1}, {"type": "precarious_object", "chance": 0.1, "object_name_options": ["unstable stack of books"], "support_object_override": "tattered sofa"}], 
            "examine_details": {
                "fireplace": "A large, cold fireplace, stained black with soot. The hearth is filled with ash.", 
                # The detail about "loose brick" here is fine as an initial observation.
                # The actual reveal of "fireplace cavity" will be handled by GameLogic.
                "dusty sheets": "Old sheets thrown over furniture...",
                "worn armchair": "An old armchair...",
                "tattered sofa": "The sofa has seen better days..."
                # Add examine detail for fireplace cavity if desired, though searching it is the main interaction.
                # "fireplace cavity": "A dark, empty space within the fireplace." (Initial state before key is found)
            },
            # ... other properties ...
            "interaction_flags": { # New suggested structure for tracking states
                "loose_brick_taken": False,
                "fireplace_cavity_revealed": False
            }
        },
        "Dining Room": {
            "description": "A long, mahogany dining table stands as the centerpiece, draped with a moth-eaten lace cloth. Ghostly outlines in the thick dust suggest where plates and silverware once sat. Cobwebs cling to the ornate, empty chairs like macabre decorations. A tall, dark wood cupboard stands against one wall, its doors slightly ajar.", 
            "exits": {"west": "Foyer", "south": "Kitchen"}, 
            "objects": ["dining table", "ornate chairs", "moth-eaten cloth"], 
            "furniture": [
                {
                    "name": "cupboard", "is_container": True, "locked": False, "capacity": 3,
                    # --- NEW ATTRIBUTES for Breakable Interaction ---
                    "is_breakable": True,                         # Can the player attempt to break it?
                    "break_succeeds_on_item_type": ["crowbar", "axe"], # Item types that can break it
                    "break_integrity": 2,                         # How many "force" attempts or hits it can take
                    "break_failure_message": "You kick and heave at the cupboard, but it's sturdy. You might need a tool, or to try again.",
                    "on_break_success_message": "With a splintering crack, the cupboard door shatters!",
                    "on_break_spill_items": [ # Items that appear when broken (not necessarily 'inside' in the normal sense)
                        {"name": "Shattered Porcelain Shard", "quantity": "1d3"}, # Example: 1 to 3 shards
                        {"name": "Dust Cloud Puff", "quantity": 1} # A temporary, non-takeable effect item
                    ],
                    "on_break_trigger_hazard": { # Optional: Trigger or alter a hazard
                        "type": "loose_object", # Type of hazard to trigger/affect
                        "object_name_override": "precariously stacked plates from cupboard",
                        "support_object_override": "floor near cupboard",
                        "initial_state": "falling", # State for the new/affected hazard
                        "chance": 0.7 # Chance of this consequence
                    },
                    "on_break_sound": "wood_splintering" # Sound effect
                    # --- END NEW ATTRIBUTES ---
                }
            ], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "unstable_shelf", "chance": 0.15, "object_name_override": "cupboard shelf", "support_object_override": "cupboard"}, {"type": "weak_floorboards", "chance": 0.1}], 
            "examine_details": {
                "dining table": "The polished surface of the mahogany table is barely visible under the dust. It's set for a meal that never happened.", 
                "ornate chairs": "High-backed chairs, intricately carved but now frail and draped in cobwebs.", 
                "moth-eaten cloth": "A once-fine lace tablecloth, now yellowed and riddled with holes.", 
                "cupboard": "A tall, dark cupboard. Its doors are slightly open, revealing shadowy recesses within. Might contain old silverware or... other things." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Kitchen": {
            "description": "The kitchen is a scene of utter chaos. Broken plates crunch underfoot, and scattered utensils litter the floor. Greasy pots and pans are piled in a stained sink. The back door is heavily boarded up from the inside. A faint, unpleasant smell – gas? – hangs in the air, mingling with the stench of decay. Exposed wires spark near the sink. A grimy trash can sits in the corner.", 
            "exits": {"north": "Dining Room"}, 
            "objects": ["broken plates", "scattered utensils", "boarded window", "boarded back door"], 
            "furniture": [ 
                {"name": "kitchen counter", "is_container": True, "locked": False, "capacity": 2}, 
                {"name": "shelves", "is_container": True, "locked": False, "capacity": 3, "hazard_possible": True, "possible_hazard_types": ["unstable_shelf"]}, 
                {"name": "trash can", "is_container": True, "locked": False, "capacity": 1}, 
                {"name": "dirty sink", "is_container": False, "locked": False} 
            ],
            "items_present": [], 
            "hazards_present": [ 
                {"type": "faulty_wiring", "object_name_override": "exposed wires", "support_object_override": "dirty sink"}, 
                {"type": "gas_leak", "object_name_override": "leaking gas pipe", "support_object_override": "dirty sink"} 
            ], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.1}], 
            "examine_details": {
                "dirty sink": "A grimy, stained sink piled high with dirty dishes. Exposed wires spark dangerously near the faucet. You catch a whiff of gas.", 
                "boarded window": "Heavy wooden planks cover the window frame, nailed securely from the inside. It would take considerable force to break through.", 
                "boarded back door": "The back door is barricaded with thick planks nailed across it. Escape this way seems impossible right now.", 
                "trash can": "An overflowing kitchen trash can, reeking of old food and something faintly metallic. Might be worth a look, if you dare.", 
                "kitchen counter": "Covered in grime and old food stains. Some drawers might still hold secrets.", 
                "shelves": "Rickety wooden shelves, laden with dusty jars and tins. They don't look very stable." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Library": {
            "description": "Towering bookshelves line the walls, filled with crumbling, leather-bound books, many spilling onto the floor. A large, imposing oak desk sits in the center, its surface cluttered with papers and a book left open. The air smells of decaying paper and dust.", 
            "exits": {"west": "Foyer"}, 
            "objects": ["crumbling books", "cluttered papers"], 
            "furniture": [ 
                {"name": "bookshelves", "is_container": True, "locked": False, "capacity": 5, "hazard_possible": True, "possible_hazard_types": ["unstable_shelf"]}, 
                {"name": "large desk", "is_container": True, "locked": False, "capacity": 3} 
            ],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "unstable_shelf", "chance": 0.2, "object_name_override": "topmost bookshelf", "support_object_override": "bookshelves"}, {"type": "weak_floorboards", "chance": 0.1}], 
            "examine_details": {
                "crumbling books": "Ancient tomes, their pages yellowed and brittle. Many look like they haven't been touched in decades.", 
                "cluttered papers": "Scattered notes, journals, and strange diagrams cover the desk and floor. Some might contain valuable information.", 
                "bookshelves": "Floor-to-ceiling bookshelves, packed tightly. Some shelves sag precariously under the weight.", 
                "large desk": "A heavy oak desk, its drawers potentially hiding secrets or useful items." 
            },
            "first_entry_text": "The scent of old paper and forgotten knowledge hangs heavy here. This room feels like the heart of the house's secrets.", 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Hallway": {
            "description": "The upstairs hallway is oppressively silent. Faded, peeling wallpaper depicts unsettling pastoral scenes. Moonlight spills through a grimy window at the far end, illuminating dancing dust motes. Doors lead to several bedrooms and a bathroom. A dark, square opening in the ceiling suggests an attic entrance.", 
            "exits": {"downstairs": "Foyer", "north": "Master Bedroom", "south": "Guest Bedroom", "east": "Guest Bedroom 2", "west": "Bathroom", "up": "Attic Entrance"}, 
            "objects": ["peeling wallpaper", "grimy window"], 
            "furniture": [{"name": "small table", "is_container": True, "locked": False, "capacity": 1}], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.15}], 
            "examine_details": {
                "peeling wallpaper": "The wallpaper is discolored and peeling, revealing dark stains underneath. The pastoral scenes seem to mock the house's decay.", 
                "grimy window": "A tall window at the end of the hall, so dirty that it barely lets in any light.", 
                "small table": "A rickety table, perhaps holding a forgotten trinket." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Master Bedroom": {
            "description": "A massive four-poster bed dominates the room, its velvet curtains ripped and faded, casting long shadows. A thick layer of dust covers everything. An ornate dresser stands against one wall, and a large desk sits near the window. An old ceiling fan hangs motionless overhead, its chains dangling.", 
            "exits": {"south": "Hallway"}, 
            "objects": ["ceiling fan with chains"], 
            "furniture": [ 
                {"name": "four-poster bed", "is_container": True, "locked": False, "capacity": 1}, 
                {"name": "nightstand", "is_container": True, "locked": False, "capacity": 1},  
                {"name": "large desk", "is_container": True, "locked": False, "capacity": 2},  
                {"name": "dresser", "is_container": True, "locked": False, "capacity": 3} 
            ],
            "items_present": [], 
            "hazards_present": [{"type": "wobbly_ceiling_fan", "object_name_override": "ceiling fan with chains", "support_object_override": "ceiling"}], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.1}], 
            "examine_details": {
                "ceiling fan with chains": "An old ceiling fan hangs overhead, coated in dust. Two chains dangle from it. Frayed wiring is visible near its base, and it looks very unsteady. Probably best not to touch it.", 
                "four-poster bed": "A grand bed, though now shrouded in dust. The space underneath is dark and could hide something.", 
                "nightstand": "A small table beside the bed, its drawer slightly ajar.", 
                "large desk": "A writing desk with several drawers, some of which might be locked.", 
                "dresser": "A tall dresser with multiple drawers for clothes... or other things." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Guest Bedroom": { 
            "description": "A small, spartan bedroom. A single metal-frame bed is covered with a stained mattress. The air is stale. A child's toy, a red SUV, sits forlornly on the floor near the window.", 
            "exits": {"north": "Hallway"}, 
            "objects": ["toy red suv"], 
            "furniture": [{"name": "single bed", "is_container": True, "locked": False, "capacity": 1}], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.1}], 
            "examine_details": {
                "toy red suv": "A small, plastic red SUV toy car, scratched and missing a wheel. It looks eerily familiar...", 
                "single bed": "A simple bed with a thin, stained mattress. Not much to see, but something could be hidden underneath." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Guest Bedroom 2": {
            "description": "This room was clearly once a study or office. A large, cluttered desk is covered in yellowed papers and strange, unsettling diagrams. An old camera rests on one corner of the desk. The room feels cold.", 
            "exits": {"west": "Hallway"}, 
            "objects": ["strange diagrams", "camera"], 
            "furniture": [{"name": "cluttered desk", "is_container": True, "locked": False, "capacity": 3}], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "precarious_object", "chance": 0.1, "object_name_options": ["unstable stack of old ledgers"], "support_object_override": "cluttered desk"}], 
            "examine_details": {
                "strange diagrams": "Sheets of paper covered in complex, unsettling diagrams and equations. They seem to depict sequences of events, ending in gruesome outcomes.", 
                "camera": "An older model camera rests on the desk, a layer of dust covering its cracked lens. It might still have photos inside.", 
                "cluttered desk": "Papers, books, and strange instruments are piled high on this desk. A thorough search might yield something." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Bathroom": {
            "description": "The air is thick with the stench of mildew and stagnant water. A cracked mirror hangs precariously above a stained sink. The bathtub is coated in grime. The medicine cabinet hangs slightly open, revealing empty shelves.", 
            "exits": {"east": "Hallway"}, 
            "objects": ["cracked mirror", "stained sink", "grimy bathtub"], 
            "furniture": [ 
                {"name": "medicine cabinet", "is_container": True, "locked": False, "capacity": 2}, 
                {"name": "toilet", "is_container": False, "locked": False} 
            ],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "weak_floorboards", "chance": 0.2}, {"type": "leaking_pipe", "chance": 0.15, "object_name_override": "leaky sink pipe", "support_object_override": "stained sink"}], 
            "examine_details": {
                "cracked mirror": "The mirror is cracked and discolored, reflecting a distorted version of the room... and you.", 
                "stained sink": "The porcelain is stained yellow and brown. A constant drip emanates from the faucet.", 
                "grimy bathtub": "A thick layer of grime coats the tub. You'd rather not touch it.", 
                "medicine cabinet": "Hangs crookedly, its door ajar. Might contain old medication or toiletries." 
            },
            "first_entry_text": None, 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Attic Entrance": {
            "description": "A dark, square opening in the hallway ceiling. A rickety wooden ladder hangs down slightly, disappearing into the oppressive darkness above. It's secured with a heavy-looking padlock near the top.", 
            "exits": {"down": "Hallway"}, 
            "objects": ["padlock", "rickety wooden ladder"], 
            "furniture": [], 
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [], 
            "examine_details": {
                "padlock": "A heavy, rust-covered padlock. It looks very sturdy.", 
                "rickety wooden ladder": "The ladder looks old and unstable. Best to be careful if you manage to get up there." 
            },
            "first_entry_text": None, 
            "locked": True, 
            "unlocks_with": "Attic Key", 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Attic": {
            "description": "The air in the attic is thick with dust and the suffocating smell of old wood and decay. Cobwebs hang like macabre decorations in the gloom. Moonlight filters weakly through cracks in the boarded-up circular window. Stacks of old boxes and forgotten relics are piled everywhere. You see a sturdy wooden crate in one corner with something pinned to it.", 
            "exits": {"down": "Attic Entrance"}, 
            "objects": ["boarded-up window", "cobwebs"], 
            "furniture": [ 
                {"name": "crate", "is_container": True, "locked": False, "capacity": 2}, 
                {"name": "stack of old boxes", "is_container": True, "locked": False, "capacity": 3},  
                {"name": "old trunk", "is_container": True, "locked": True, "capacity": 2, "unlocks_with_item": "Trunk Key"} 
            ],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "precarious_object", "chance": 0.15, "object_name_options": ["unstable stack of boxes"], "support_object_override": "stack of old boxes"}, {"type": "unstable_shelf", "chance": 0.1, "object_name_override": "rotting beam", "support_object_override": "ceiling"}, {"type": "weak_floorboards", "chance": 0.2}], 
            "examine_details": {
                "boarded-up window": "A circular window, heavily boarded from the inside. Only slivers of moonlight penetrate.", 
                "cobwebs": "Thick, dusty cobwebs hang everywhere, brushing against your face as you move.", 
                "crate": "A sturdy wooden crate. Something seems to be pinned to its lid, and it might contain items.", 
                "stack of old boxes": "Piles of cardboard boxes, some collapsing under their own weight. Who knows what's inside?", 
                "old trunk": "A large, dust-covered trunk, possibly locked." 
            },
            "first_entry_text": "The attic is stifling. Every shadow seems to writhe, and the silence is heavy with unspoken secrets.", 
            "locked": False, 
            "unlocks_with": None, 
            "crate_interactions": 0, 
            "has_newspaper_clipping": True, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "stairs_interactions": 0 
        },
        "Basement Stairs": {
            "description": "Steep, narrow wooden stairs descend into pitch darkness. The air grows significantly colder and damper as you peer down. A heavy padlock secures a bolt on the door at the bottom.", 
            "exits": {"up": "Foyer"}, 
            "objects": ["stairs", "padlock on door"], 
            "furniture": [], 
            "items_present": [], 
            "hazards_present": [{"type": "collapsing_stairs", "object_name_override": "rickety stairs", "support_object_override": "stairwell"}], 
            "possible_hazards": [], 
            "examine_details": {
                "stairs": "The wooden steps are slick with damp and look dangerously worn.", 
                "padlock on door": "A sturdy padlock secures the door leading further into the basement." 
            },
            "first_entry_text": None, 
            "locked": True, 
            "unlocks_with": "Basement Key", 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Main Basement Area": {
            "description": "You step onto a cold, damp concrete floor. The air is heavy with the smell of mildew and earth. Pipes groan ominously overhead, dripping water intermittently. A single, bare bulb flickers weakly, casting long, dancing shadows. A sturdy workbench covered in rusty tools stands against one wall. To the south, a warped wooden door leads to a storage room.", 
            "exits": {"up": "Basement Stairs", "south": "Storage Room"}, 
            "objects": ["dripping pipes", "flickering bulb", "rusty tools"], 
            "furniture": [ 
                {"name": "workbench", "is_container": True, "locked": False, "capacity": 3}, 
                {"name": "shelves", "is_container": True, "locked": False, "capacity": 4, "hazard_possible": True, "possible_hazard_types": ["unstable_shelf"]} 
            ],
            "items_present": [], 
            "hazards_present": [ 
                {"type": "faulty_wiring", "object_name_override": "flickering bulb wiring", "support_object_override": "flickering bulb"}, 
                {"type": "weak_floorboards", "object_name_override": "damp concrete patch", "support_object_override": "floor"} 
            ],
            "possible_hazards": [{"type": "precarious_object", "chance": 0.1, "object_name_options": ["loose pipe fitting"], "support_object_override": "dripping pipes"}, {"type": "leaking_pipe", "chance": 0.1, "support_object_override": "dripping pipes"}], 
            "examine_details": {
                "dripping pipes": "Rusty pipes run along the ceiling, weeping water and staining the concrete below.", 
                "flickering bulb": "A single bare bulb, its light stuttering and unreliable. The wiring looks ancient.", 
                "rusty tools": "A collection of old, rusted tools lies scattered on the workbench and floor.", 
                "workbench": "A heavy wooden workbench, stained and scarred from years of use. Its drawers might hold something.", 
                "shelves": "Damp, wooden shelves line one wall, sagging under the weight of forgotten junk." 
            },
            "first_entry_text": "The basement is cold and oppressive. The air is thick with the smell of decay.", 
            "locked": False, 
            "unlocks_with": None, 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        },
        "Storage Room": { 
            "description": "A cramped, windowless storage room. The air is stagnant and smells faintly of chemicals. Wooden shelves line the walls, crammed with dusty jars, forgotten equipment, and cobweb-covered boxes. You feel an intense sense of dread in here. There's a sturdy locked cabinet against the back wall.", 
            "exits": {"north": "Main Basement Area"}, 
            "objects": ["dusty jars"], 
            "furniture": [ 
                {"name": "shelves", "is_container": True, "locked": False, "capacity": 5, "hazard_possible": True, "possible_hazard_types": ["unstable_shelf", "precarious_object"]},  
                {"name": "old trunk", "is_container": True, "locked": True, "capacity": 3, "unlocks_with_item": "Old Trunk Key"}, 
                {"name": "locked cabinet", "is_container": True, "locked": True, "capacity": 2, "unlocks_with_item": "Cabinet Key"} 
            ],
            "items_present": [], 
            "hazards_present": [], 
            "possible_hazards": [{"type": "unstable_shelf", "chance": 0.2}, {"type": "precarious_object", "chance": 0.15, "object_name_options": ["box of old chemicals"], "support_object_override": "shelves"}, {"type": "faulty_wiring", "chance": 0.1, "object_name_options": ["ancient electrical device"], "support_object_override": "shelves"}], 
            "examine_details": {
                "dusty jars": "Rows of jars containing unidentifiable substances, coated in a thick layer of dust.", 
                "shelves": "These shelves are packed to breaking point with miscellaneous junk. They look ready to topple.", 
                "old trunk": "A heavy, old-fashioned trunk, secured with a rusty lock.", 
                "locked cabinet": "A metal cabinet, firmly locked. It might contain something valuable or dangerous." 
            },
            "first_entry_text": "This small room feels suffocating. The silence is unnerving.", 
            "locked": True, 
            "unlocks_with": "Storage Room Key", 
            "fireplace_brick_slot_revealed": False, "sink_interactions": 0, "window_interactions": 0, "bookshelves_interactions": 0, "ceiling_fan_interactions": 0, "crate_interactions": 0, "has_newspaper_clipping": False, "stairs_interactions": 0 
        }
    }
}

# --- Item Definitions (Revamped Structure) ---
keys = {
    # Key found in Hospital (Level 1), unlocks Hospital's Coroner's Office

    # NEW KEY: Found in Hospital's Coroner's Office (Level 1), unlocks Bludworth's House Foyer (Level 2)
    "Bludworth's House Key": {
        "description": "A heavy brass key with 'Bludworth Residence' engraved on it.",
        "examine_description": "This key likely opens the main entrance to the Bludworth house.",
        "is_key": True,
        "takeable": True,
        "unlocks": "Foyer", # Can still be used with "unlock Foyer" if at porch
        "location": "Coroner's Office", 
        "container": "mahogany desk", 
        "is_hidden": True,
        "level": 1,
        "weight": HEAVY_ITEM_WEIGHT,
        "is_evidence": True,
        "use_on": ["front door"], # <<< ADD THIS
        "use_result": { # <<< ADD THIS
            "front door": "You slide the heavy iron key into the lock of the front door. With a resounding *CLUNK*, the tumblers turn. The door is now unlocked."
        }
    },
    # Key found in House (Level 2), unlocks something within the House
    "Bludworth's Study Key": { # Formerly the "Coroner's Office Key" found in the Attic
        "description": "A small, tarnished brass key. An old paper tag attached reads 'W.B. - Private Study'.",
        "takeable": True, "is_key": True,
        "unlocks": "Bludworth's Study Desk", # Example: Unlocks a desk in a new "Study" room or existing room
        "location": "Attic",  # Found in House Attic (Level 2)
        "container": "old trunk", # Assume it's in the attic trunk
        "is_hidden": True,
        "level": 2, # Found in House (Level 2)
        "weight": DEFAULT_ITEM_WEIGHT
    },
    "Attic Key": {
        "description": "A small, tarnished brass key labeled 'Attic'.",
        "takeable": True,
        "is_key": True,
        "unlocks": "Attic Entrance",  # The room or object it unlocks
        "location": None,  # Placed randomly
        "is_hidden": True,
        "level": 2,  # Level where the key is found
        "weight": DEFAULT_ITEM_WEIGHT
    },
    "Basement Key": {
        "description": "A heavy iron key labeled 'Basement'. Feels cold to the touch.",
        "takeable": True,
        "is_key": True,
        "unlocks": "Basement Stairs",
        "location": "Living Room",
        "container": "fireplace cavity",
        "is_hidden": True,
        "level": 2,
        "weight": DEFAULT_ITEM_WEIGHT
    },
    "Storage Room Key": {
        "description": "A rusty, standard-looking key. Might open the basement storage room.",
        "takeable": True,
        "is_key": True,
        "unlocks": "Storage Room",
        "location": None,
        "is_hidden": True,
        "level": 2,
        "weight": DEFAULT_ITEM_WEIGHT
    },
    "Cabinet Key": {
        "description": "A small, intricate brass key. Possibly for a piece of furniture.",
        "takeable": True,
        "is_key": True,
        "unlocks": "locked cabinet",
        "location": None,
        "is_hidden": True,
        "level": 2,
        "weight": DEFAULT_ITEM_WEIGHT
    },

    "Coroner's Office Key": {
        "description": "A small, ornate key with a customized skull-shaped handle. 'Lakeview Hospital - Do Not Copy' is etched on the side. This must have been the key to Bludworth's office, maybe we'll find more answers there.",
        "takeable": True,
        "is_key": True,
        "unlocks": "Coroner's Office", # The room it unlocks
        "location": ROOM_MRI_SCAN_ROOM, # Fixed location
        "container": "equipment cart",  # Placed in the equipment cart in the MRI room
        "is_hidden": True, # Initially hidden in the cart
        "is_metallic": True, # Crucial for MRI interaction
        "level": 1, # Hospital level
        "weight": DEFAULT_ITEM_WEIGHT,
        "triggers_mri_on_pickup": True # Custom flag for GameLogic
    },
    "Radiology Key Card": {
        "description": "A plastic key card labeled 'Radiology'. Grants access to restricted areas in the hospital's radiology wing and can activate certain equipment.",
        "takeable": True,
        "is_key": True,
        "unlocks": [ROOM_RADIOLOGY_WING_ACCESS, ROOM_STAIRWELL], # Can unlock multiple things or be checked for specific interactions
        # Spawn locations: hospital emergency entrance, supply closet, waiting room, patient room 101, or ER hallway
        "spawn_locations": [ # GameLogic will pick one of these
            {"room": "Hospital Emergency Entrance", "container": "reception desk"},
            {"room": "Supply Closet", "container": "metal shelves"},
            {"room": "Waiting Room", "container": "low table"},
            {"room": "Patient Room 101", "container": "bedside table"},
            {"room": "ER Hallway", "container": None} # Placed on floor in ER Hallway
        ],
        "is_hidden": True,
        "level": 1,
        "weight": DEFAULT_ITEM_WEIGHT,
        "activates_mri_via_control_panel": True # Custom flag
    },
    "Morgue Key Card": {
        "description": "A plastic key card labeled 'Morgue'. Used by hospital staff to access the morgue and related areas.",
        "takeable": True,
        "is_key": True,
        "unlocks": [ROOM_MORGUE, ROOM_STAIRWELL, "Hospital Morgue Hallway"], # Unlocks Morgue and Stairwell
        "location": ROOM_MRI_SCAN_ROOM, # Preferred spawn
        "container": None, # Could be on the floor or in a non-specific container if not the Coroner's key cart
        "is_hidden": True, # Or False if it's just lying around after MRI event
        "level": 1,
        "weight": DEFAULT_ITEM_WEIGHT,
        "triggers_mri_on_pickup_if_in_mri_room": True # Custom flag
    },
    "Medical Director Key Card": {
        "description": "A master key card for Lakeview Hospital. Bears the insignia of the Medical Director. Grants access to almost all secure areas.",
        "takeable": True,
        "is_key": True,
        "is_master_key": True, # Custom flag for master key behavior
        "unlocks": "all_hospital_level_1", # Special identifier for GameLogic
        "activates": "all_hospital_level_1", # Special identifier
        # Spawn: Rare spawn in a random container in the hospital
        "is_rare_random_hospital_spawn": True, # Custom flag for placement logic
        "is_hidden": True,
        "level": 1,
        "weight": DEFAULT_ITEM_WEIGHT
    },
}

    # --- Evidence Items (from evidence) ---
evidence = {
    # FD1 Evidence
    "Bloody Brick": {
        "description": "A dirty brick, one corner covered with dried blood, hair and gore. Writing scratched into it reads: 'Alex B. - Didn't see it coming.' Well, shit. ..if HE didn't make it...",
        "takeable": True, "is_evidence": True, "location": False, "is_hidden": True, "weight": HEAVY_ITEM_WEIGHT, "character": "Alex Browning", # <<< ADDED COMMA HERE
        "revealed_by_action": True, # <<< NOW a property of Bloody Brick
        "use_on": ["boarded window", "crate"], # <<< NOW a property of Bloody Brick
        "use_result": { # <<< NOW a property of Bloody Brick
            "boarded window": "With a grunt, you smash the brick against the boards. They splinter and crack, revealing the boarded window frame.",
            "crate": "You bring the brick down hard on the crate. Wood splinters, and the crate breaks open."
        } # <<< Closing brace for use_result
    }, # <<< Closing brace for Bloody Brick item
    "Retractable Clothesline Piece": { # This is a valid item
        "description": "A piece of white, retractable clothesline, slightly frayed. Tod Waggner accidentally hanged himself with one after surviving Flight 180.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Tod Waggner"},
    "Shattered Light Bulb": { 
        "description": "Fragments of a large industrial light bulb, like from a neon sign. Carter Horton was crushed by a falling sign after surviving Flight 180.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Carter Horton"},
    "Miniature Toy Bus": {
        "description": "A small, miniature model of a city bus. Terry Chaney was fatally struck by a bus moments after telling Carter off.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Terry Chaney"},
    "Charred Mug": {
        "description": "A ceramic mug, blackened and cracked by intense heat. Ms. Lewton died in a house fire triggered by a series of 'accidents' involving her computer monitor and vodka.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Valerie Lewton"},
    "Bloody Piece of Metal": {
        "description": "A jagged piece of metal, stained dark brown. Billy Hitchcock was decapitated by shrapnel from a train wreck after Alex intervened and saved Carter Horton from an oncoming train.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Billy Hitchcock"},

    # FD2 Evidence
    "Toy Pigeon": {
        "description": "A small, battered toy pigeon. Tim Carpenter, survived the Route 23 pile-up only to be crushed by falling plate glass window at the dentist. Tim was warned to watch for pigeons just before his death",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Tim Carpenter"},
    "Nipple Ring": {
        "description": "A cheap metal nipple ring. Evan Lewis survived the Route 23 pile-up, then died after a fire escape ladder impaled his eye.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Evan Lewis"},
    "Dirty Hair Tie": {
        "description": "A blue hair tie speckled with brown..or dark red? Nora Carpenter survived the Route 23 pile-up but was decapitated by a malfunctioning elevator.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Nora Carpenter"},
    "Pool Ball Keychain": {
        "description": "An orange striped pool ball keychain. Eugene Dix survived the pile-up but died in a really implausible hospital oxygen explosion along with Clear Rivers.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Eugene Dix"},
    "Clove Cigarette": { 
        "description": "A small bottle of Valium pills. Kat Jennings survived the Route 23 pile-up but was killed when an airbag deployed, impaling her head on a pipe protruding through the headrest.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Kat Jennings"},
    "Fuzzy Red Dice": {
        "description": "A pair of fuzzy red dice, like those Rory Peters hung in his car. He survived the Route 23 pile-up but was sliced apart by barbed wire fencing after Kat's accident.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Rory Peters"},
    "Photo of Officer Burke": {
        "description": "A photo of Officer Thomas Burke. Survived the Route 23 pile-up. Rumored to have met a grisly end involving a wood chipper much later.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Thomas Burke"},
    "Photo of Kimberly Corman": { 
        "description": "A photo of Kimberly Corman. She had the premonition of the Route 23 pile-up and saved a group of people who started dying immediately afterwards. Survived after confronting Death at the lake. She is one of the only people to have found a successful escape from Death. This is who you need to find!!",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Kimberly Corman"},
    "Work Gloves": {
        "description": "A pair of worn leather work gloves. Brian Gibbons survived the Lakeview apartment fire, as well as a run in with a news van on his family's farm, but was later incinerated by an exploding barbecue grill.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Brian Gibbons"},
    "White Rose": {
        "description": "A pressed white rose. Isabella Hudson survived the Route 23 pile-up because she was actually never supposed to die. She was an example of Death using a red herring to keep survivors busy as it cleaned up.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Isabella Hudson"},
     "Newspaper Clipping about Flight 180": {
        "description": "A newspaper clipping detailing the Flight 180 disaster and the subsequent deaths of the survivors. Clear Rivers, a survivor of Flight 180, died trying to help the Route 23 survivors.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Clear Rivers"},

    # FD3 Evidence
    "camera": {
        "description": "An early 2000's digital camera, lens cracked. Wendy Christensen used this camera, capturing photos that predicted the deaths of the Devil's Flight coaster survivors. It wasn't hers, but the yearbook committee didn't care much to have it anymore.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Wendy Christensen"},
    "Navel Piercing with Crystal": {
        "description": "A small navel piercing with a dangling crystal. Belonged to Carrie Dreyer, would-be independent woman, who died in the Devil's Flight roller coaster crash.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Carrie Dreyer"},
    "Photo of Jason on Devil's Flight": {
        "description": "A photo of Jason Wise posing in front of the Devil's Flight roller coaster; the tram of cars caught in time blurring into frame looks as though it's about to bury itself in his head. He died in the initial crash.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Jason Wise"},
    "Photo of the Ashleys": {
        "description": "A photo showing Ashley Freund and Ashlyn Halperin at a carnival game. They survived the coaster but were burned alive in malfunctioning tanning beds (though some say they almost made it out and got electrocuted instead).",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Ashley Freund & Ashlyn Halperin"},
    "Mud Flap Girl Necklace": {
        "description": "A chrome necklace of a mud flap girl silhouette almost as cheap as the person who wore it. Won by Franklin Cheeks; he avoided the Devil's Flight coaster crash, but was killed in a drive-thru when a multi-car accident found its way into his backseat, burying a radiator fan in his skull. Couldn't have happened to a better guy.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Franklin Cheeks"},
    "Photo of Lewis from Ring-The-Bell Game": {
        "description": "A photo of Lewis Romero hitting the bell at a strength tester game. He survived the Devil's Flight coaster crash, but had his head crushed by weights at the gym.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Lewis Romero"},
    "Photo of Ian with Banners": {
        "description": "A photo of Ian McKinley standing near banners that foreshadowed his death. He survived the Devil's Flight coaster crash, but was crushed by a falling cherry picker sign.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Ian McKinley"},
    "Strip of nails": {
        "description": "A strip of collated nails, some missing, faint blood traces. Erin Ulmer survived the Devil's Flight coaster crash, but died after her hand was nailed to her face through the back of her head at the hardware store.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Erin Ulmer"},
    "Overexposed Photo of Kevin": {
        "description": "An overexposed photo showing Kevin Fischer. He survived the Devil's Flight coaster crash, helped Wendy, but died later in a subway crash.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Kevin Fischer"},
     "Photo of Julie giving the finger": {
        "description": "A photo of Julie Christensen giving the finger. Wendy's sister, she survived the Devil's Flight coaster premonition, but coincidentally she died with her sister, and friend, Kevin, in a subway crash months after.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Julie Christensen"},
     "Photo of Perry": {
        "description": "A photo of Perry Malinowski. Survived the Devil's Flight coaster premonition but was impaled by a flagpole at the tricentennial celebration.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Perry Malinowski"},
     "Photo of Amber": {
        "description": "A photo of Amber Regan. Briefly thought to have survived the Devil's Flight coaster premonition. Current status unknown.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Amber Regan"},

    "(Un)Lucky Coin": {
        "description": "A half dollar, covered in what might be dried blood. Associated with Hunt Wynorski's death by internal organ suction removal by a pool filtration system after he lost this coin.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Hunt Wynorski"
    },
    "Can of Hice Pale Ale": {
        "description": "A can of cheap Hice Pale Ale. Carter Daniels was drinking this shortly before he was dragged by his tow truck and then obliterated in the ensuing explosion.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Carter Daniels"
    },
    "Horseshoe Ornament": {
        "description": "A tarnished metal horseshoe ornament, bent out of shape. Carter Daniels had one hanging from his rearview mirror before his tow truck exploded.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Carter Daniels"
    },
    "Safety Goggles": {
        "description": "A pair of cracked safety goggles, typical for auto work. Andy Kewzer, who worked at an auto shop, survived the speedway crash only to be launched through a chain-link fence by a flying CO2 tank.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Andy Kewzer"
    },
    "Hair Clip": {
        "description": "A simple, slightly singed hair clip. Samantha Lane died at a salon when a rock, propelled by a lawnmower, perforated her eye shortly after the speedway disaster. She had moments before put tampons in her children's ears to block the noise at the track.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Samantha Lane"
    },
    "Movie Ticket Stub": {
        "description": "A ticket stub for 'Love Lays Dying in 3D'. Janet Cunningham survived the speedway crash but died after being run over by an 18-wheeler that crashed into the coffee shop she was in.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Janet Cunningham"
    },
    "Confederate Flag Patch": {
        "description": "A small, dirty Confederate flag patch, possibly torn from a piece of clothing. Cynthia Daniels, married to the racist Carter, was bisected by the hood of a race car at the speedway.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Cynthia Daniels"
    },
    "Binocular Flask": {
        "description": "A pair of seemingly ordinary binoculars that cleverly conceals a flask. Nadia Monroy had taken this from Hunt Wynorski before she was gruesomely decapitated by a tire that flew out of the speedway.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Nadia Monroy"
    },
    "Cowboy Hat": { 
        "description": "A slightly crushed cowboy hat. Jonathan Groves, the 'Cowboy', was killed when a hospital bathtub fell through the ceiling and crushed him in his room below.",
        "takeable": True, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Jonathan Groves"
    },
    "Security Guard Flashlight": {
        "description": "A heavy-duty security guard's flashlight, its lens cracked. George Lanter, a security guard and one of the survivors, was later fatally struck by a speeding ambulance.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "George Lanter"
    },
    "Bloody Arm Cast": {
        "description": "A section of a fiberglass arm cast, stained with dried blood. Nick O'Bannon, who had the premonition of the speedway disaster, ultimately had his head smashed into a wall by a semi crashing into a coffee shop.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Nick O'Bannon"
    },
    "Woman's Shoe": {
        "description": "A single woman's tennis shoe, one of the laces badly frayed. Lori Milligan, Nick's girlfriend, died a horrific death, internally decapitated by being crushed between a pillar and a truck.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Lori Milligan"
    },
    # --- FD5 Evidence (Enhanced and New) ---
    "Pair of Glasses": {
        "description": "A black framed pair of glasses, one lens shattered. Olivia Castle survived the North Bay Bridge collapse but, after a mishap during laser eye surgery, fell from a high-rise window, her other eye graphically popping out upon impact with a car windshield below.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Olivia Castle"
    },
    "Rubber Band": { # Description seems fine, matches "Limbs and spine broken after hitting the floor"
        "description": "A broken rubber band, snapped with force. Candice Hooper, a gymnast, survived the bridge collapse but died during practice when a series of unfortunate events led to her landing badly, snapping her spine.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Candice Hooper"
    },
    "Accupuncture Needle": { # Description seems fine
        "description": "A thick, long metal needle used for acupuncture, slightly bent. Isaac Palmer survived the bridge collapse but had his head crushed by a falling Buddha statue in a local spa after a fire started.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Isaac Palmer"
    },
    "Metal Spike": { # Using your provided enhanced description
        "description": "A long metal spike, like from an industrial machine. Roy Carson was impaled by a hook through the chin at the factory where he worked after Death came for Nathan. Nathan took Roy's remaining time, which, unfortunately, was not much longer than Nathan already had.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": HEAVY_ITEM_WEIGHT, "character": "Roy Carson"
    },
    "Chef's Knife": { # Description seems fine, item represents character
        "description": "A sharp chef's knife, surprisingly clean. Dennis Lapman, Sam's boss, survived the bridge collapse but was later killed by a wrench propelled through his head, an accident triggered by Roy Carson's death.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Dennis Lapman"
    },
    "Airplane Ticket (Paris)": { # Description seems fine
        "description": "An airplane ticket for Volée Airlines Flight 180 to Paris. Sam Lawton, Molly Harper, Peter Friedkin, and Nathan Sears all survived the North Bay Bridge collapse, only to tragically die when this flight exploded shortly after takeoff, prequeling the events of the first film.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Sam Lawton, Molly Harper, Peter Friedkin, Nathan Sears" # Updated character list for clarity
    },
    "Damaged Police Badge": { # New for Agent Block
        "description": "A police detective's badge, dented and bearing a bullet hole. Agent Jim Block was investigating the bridge survivors when he was shot in the back and killed by a paranoid Peter Friedkin.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Agent Jim Block"
    },
    "Bent Meat Skewer": { # New for Peter Friedkin
        "description": "A long, heavy-duty meat skewer, bent and bloodied. Peter Friedkin, driven mad by Death's design, was impaled through the back by Sam Lawton with this skewer from Le Café Miro 81's kitchen.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Peter Friedkin"
    },

    # --- FD6: Bloodlines Evidence (New based on synopsis) ---
    # Items for the 1968 Skyview Restaurant Tower Premonition victims (if they are meant to be distinct from the main timeline survivors)
    "Charred Vintage Opera Glasses": { # For Evie Bludworth (Premonition Death)
        "description": "A pair of elegant opera glasses from the late 1960s, warped and partially melted by intense heat. Evie Bludworth would have burned to death in the Skyview Tower explosion premonition.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Evie Bludworth (Premonition)"
    },
    "Bent Elevator Call Button (1960s)": { # For Mr. Fuller (Premonition Death)
        "description": "A brass elevator call button, characteristic of 1960s architecture, severely dented. Mr. Fuller was premonitioned to be crushed in the Skyview Tower's elevator.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Mr. Fuller (Premonition)"
    },
    "Scuffed Dress Shoe (Single, 1960s)": { # For Chet (Premonition Death)
        "description": "A single, scuffed men's dress shoe from the 1960s, its sole nearly detached. Chet was foreseen to fall to his death in the Skyview Tower elevator shaft.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Chet (Premonition)"
    },
    "Broken Ivory Piano Key": { # For Penny Kid (Premonition Death)
        "description": "A broken ivory piano key, with a tiny, faded fingerprint. A young guest, Penny, was envisioned to be crushed by a falling piano during the Skyview Tower disaster.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Penny Kid (Premonition)"
    },

    # Items for the actual deaths in FD6
    "Iris's Book (Death's Omen)": {
        "description": "A leather-bound book filled with chilling handwritten notes, sketches of omens, and names. Iris Campbell, who disrupted Death's design in 1968, was documenting its patterns before being fatally impaled through the mouth by a weather vane.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Iris Campbell"
    },
    "Bloodied Lawn Mower Spark Plug": {
        "description": "A spark plug from a lawnmower, coated in blood and grime. Howard Campbell, Iris's son, received an extremely deep exfoliating facial from a lawnmower during a family barbecue.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Howard Campbell"
    },
    "Torn Sanitation Worker Vest Fragment": { # Representing Julia's death environment
        "description": "A torn fragment of a bright orange sanitation worker's vest, stained and smelling faintly of refuse. Julia Campbell, Howard's daughter, was crushed to death inside a garbage truck.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Julia Campbell"
    },
    "Septum Ring": {
        "description": "A delicate body piercing, violently snapped from its home and bloodied. Erik Campbell's piercings were torn from his body by a malfunctioning MRI machine, leading to his impalement by a wheelchair.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Erik Campbell"
    },
    "Candy Wrapper": { 
        "description": "The wrapper of some peanut butter cups, boasting, 'Now More Nuts!', which you turn over and see is smeared with blood. Bobby Campbell, Erik's brother, was impaled through the forehead by a vending machine dispensing spring.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Bobby Campbell"
    },
    "Cracked RV Side Mirror": {
        "description": "A cracked side mirror from an RV, reflecting a distorted image. Darlene Campbell, Stefani's mother, was bisected by a falling lamp post after their RV crashed during an attempt to get inside Iris' home.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Darlene Campbell"
    },
    "Splintered Log Piece (Stefani)": {
        "description": "A heavy, splintered piece of wood, smelling of pine and recent trauma. Stefani Reyes, who inherited her grandmother's sensitivity to Death's design, was crushed by falling logs from a derailed train.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": HEAVY_ITEM_WEIGHT, "character": "Stefani Reyes"
    },
    "Damaged Prom Corsage": { # For Charlie
        "description": "A prom corsage, its flowers crushed and petals torn, with a faint scent of train oil. Charlie Reyes was killed alongside his sister Stefani by falling logs at his senior prom, moments after they thought they had cheated Death.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Charlie Reyes"
    },
    # Book evidence: Dead Reckoning 
    "Drumstick": { 
        "description": "A drumstick belonging to Jamie. He survived the club collapse but later died after being shot in the chest while saving Eric.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Jamie"},
    "Flask": { 
        "description": "A small hip flask. Ben survived the club collapse but later died after falling down an open manhole.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Ben"}, # Empty flask is default, full might be heavy
    "Macy's Name Tag": { 
        "description": "A 'Club Kitty' name tag. Macy survived the club collapse but was later sliced in half by a fallen metal pane.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Macy"},
    "Officer Hewlett's Badge": { 
        "description": "A police officer's badge. Officer Marina Hewlett survived the club collapse but later died after being bitten by a black widow.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Officer Marina Hewlett"},
    "Charlie Delgado's Car Keys": { 
        "description": "A set of car keys. Charlie Delgado survived the club collapse but was later crushed when an elevator fell on him.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Charlie Delgado"},
    "Compact": { 
        "description": "A small makeup compact. Amber survived the club collapse but was later run over by Charlie's out of control car.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Amber"},
    "Cigarette Lighter": { 
        "description": "A heavy cigarette lighter. Sebastian Lebecque survived the club collapse but was killed when his motorcycle exploded from a thrown-away cigar.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Sebastian Lebecque"},

    # Book Evidence: Destination Zero
    "Locket": {
        "description": "A small, tarnished locket. Juliet Collins survived the Mornington Crescent explosion but later drowned after being thrown into the River Thames, though she was revived.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Juliet Collins"},
    "Bill Sangster's Knife": { 
        "description": "A sharp, well-maintained knife. Bill Sangster survived the Mornington Crescent explosion but was later crushed inside the gears of a drawbridge.",
        "takeable": True,"level": 2,  "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Bill Sangster"},
    "Scalpel": { 
        "description": "A small, sterile scalpel. Stewart Tubbs survived the Mornington Crescent explosion but was later autopsied alive by his co-worker.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Stewart Tubbs"},
    "Cobra Totem": { 
        "description": "A small wooden totem carved in the shape of a cobra. Andrew Caine survived the Mornington Crescent explosion but was later blinded and bitten repeatedly by cobras.",
        "takeable": True,"level": 2,  "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Andrew Caine"},
    "Brooch": { 
        "description": "An ornate silver brooch. Jane Stanley survived the Mornington Crescent explosion but was later bitten on the tongue by a poisonous cobra.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Jane Stanley"},
    "Magnifying Glass": { 
        "description": "A small, portable magnifying glass. Hector Barnes survived the Mornington Crescent explosion but was later bitten on the wrist by a poisonous cobra.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Hector Barnes"},
    "Ink Pen": { 
        "description": "A heavy fountain pen, stained with ink. Matthew Upton survived the Mornington Crescent explosion but was later impaled in the stomach by a chemical-coated pipe.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Matthew Upton"},
    "Press Pass": { 
        "description": "A laminated press pass for 'Borderlands Patrol'. Patricia 'Patti' Fuller survived the train bombing but later died of an intentional overdose of anesthesia, though she was revived.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Patricia 'Patti' Fuller"},
    "Circuit City Name Tag": { 
        "description": "A plastic name tag with the Circuit City logo. Will Sax survived the train bombing but was later decapitated by a flying CD.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Will Sax"},
    "Business Card": { 
        "description": "A glossy business card for a talent agent. Al Kinsey survived the train bombing but was later beheaded by a dislodged hubcap.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Al Kinsey"},
    "Wrench": { 
        "description": "A small, greasy wrench. Susan Fries survived the train bombing but later had her chest incinerated by thermite.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": HEAVY_ITEM_WEIGHT, "character": "Susan Fries"},
    "Construction Pin": { 
        "description": "A metal pin shaped like a miniature hard hat. Zack Halloran survived the train bombing but was later vertically severed in half by a falling glass pane.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Zack Halloran"},
    "Demolition Derby Ticket Stub": { 
        "description": "A soggy ticket stub from a demolition derby event. Hal Ward survived the train bombing but later drowned during a flash-flood.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Hal Ward"},

    # Book Evidence: End of the Line 
    "Bicycle Brake Handle": {
        "description": "A severely damaged handbrake (usually) found on mountain bikes. Danny King survived a train crash after a premonition but was later accidentally killed by his sister being unknowingly used as a servant of Death.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Danny King"},
    "Hairpin": {
        "description": "A simple hairpin, used for picking locks. Louise King survived the train crash with her twin Danny but was later attacked and survived alongside him.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Louise King"},
    "Broken Train Handhold": { 
        "description": "A piece of a broken handhold from the train. James Barker survived the train crash but later seemingly died after being flung into a department store and impaled by umbrellas.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "James Barker"},
    "Turquoise Charm": {
        "description": "A small turquoise charm. Bodil Raden survived the train crash but later seemingly died after being flung into a department store and impaled by umbrellas.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Bodil Raden"},
    "Skeleton Figurine": {
        "description": "A small plastic skeleton figurine from a hotel desk. Mary-Beth Bradbury survived the train crash but was later brutally decapitated by a flailing chainsaw.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Mary-Beth Bradbury"},
    "Tattered Book": {
        "description": "A worn copy of 'Murder on the Orient Express'. Peter Hoffman survived the train crash but later died after being impaled through his torso by the horns of a gazelle.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Peter Hoffman"},
    "Floral Hair Decoration": {
        "description": "A floral hair decoration. Rinoka Aratsu survived the train crash (despite a vision of her death) but was severely burned and later crushed by an overflowing bathtub.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Rinoka Aratsu"},
    "Used Syringe": { 
        "description": "A used syringe. Kate Shelley had visions related to Death's design after surviving a Sux Racing incident at her college, and subsequently became a servant of Death; she ultimately died by suicide via syringe. Dont poke yourself!",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Kate Shelley"},
    "Patient Wristband": {
        "description": "A hospital patient wristband. Andrew Williams was a patient in the hospital whose overflowing bathtub broke through the hospital floor and crushed Rinoka Aratsu beneath it.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Andrew Williams"},
    "Corkscrew": { 
        "description": "A small corkscrew. Jack Cohen, a 99-year-old man, survived the train crash but later died after falling on a corkscrew that impaled his eye.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Jack Cohen"},

    # Book Evidence: Dead Man's Hand 
    "iPod": {
        "description": "An iPod with white earphones. Aldis Escobar survived a near-fatal casino elevator incident, but his ribcage was later crushed by his steering wheel in a car crash that same afternoon.",
        "takeable": True, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Aldis Escobar"},
    "Female Wedding Band": {
        "description": "A plain wedding band. Allie Gaines survived the casino elevator crash but later died from being drenched in contaminated blood when a traffic light fell on the vehicle carrying the survivors, absolutely obliterating the driver she was sat behind. Months later, she was informed she had contracted not just HIV but the most aggressive case of full blown AIDS the doctor had ever seen, save for one Isabella Montoya, who had just been in their office.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Allie Gaines"},
    "Male Wedding Band": {
        "description": "A plain wedding band. Tom survived the casino elevator crash but was later hit by a speeding truck while changing a tire.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Tom"},
    "Poker Chip": {
        "description": "A well-worn poker chip. Arlen Ploog survived the casino elevator crash, but had his penis bitten off by a startled prostitute and succumbed to blood loss.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Arlen Ploog"},
    "Costume Feather": {
        "description": "A single feather from a stage costume. Shawna Engels survived the casino elevator crash but was later driven backwards into a slot machine and impaled through the back of her head by the coin dispenser, turning her into a ghoulish Pez dispenser.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Shawna Engels"},
    "Detective Badge": {
        "description": "A gold detective's badge. Warren Ackerman survived the casino elevator crash but was later electrocuted by damaged cables while pursuing a suspect.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Warren Ackerman"},
    "Detective Notepad": { 
        "description": "A small police notepad. Detective Isabelle Montoya survived the casino elevator crash but survived the casino elevator crash but later died from being drenched in contaminated blood when a traffic light fell on the vehicle carrying the survivors, absolutely obliterating the driver she was sat next to. Months later, she was informed she had contracted not just HIV but the most aggressive case of full blown AIDS the doctor had ever seen, save for one Allie Gaines, who had just been in their office.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Detective Isabelle Montoya"},

    # Book Evidence: Looks Could Kill (Reconciled)
    "Sherry's Cellphone": {
        "description": "A cellphone with the name 'DEATH' on the 'recent calls' caller ID. Stephanie 'Sherry' Pulaski survived the yacht foundering but was later run over by a bus after a phone call from Death distracted her.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Stephanie 'Sherry' Pulaski"},
    "Camera Lens Cap": { 
        "description": "A plastic camera lens cap. Gunter Nonhoff survived the yacht foundering but was later slowly severed in half by an unattended delivery truck.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Gunter Nonhoff"},
    "Small Mirror": { 
        "description": "A small handheld mirror. William 'Brut' Simms survived the yacht foundering and being swept away in a sewer flood, but was later run over when he was left suspended by his belt in a subway tunnel.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "William 'Brut' Simms"},
    "Compact Mirror": { 
        "description": "A small makeup compact. Rosemarie 'Rose' Dupree survived the yacht foundering but later had (most of) her internal organs pumped out during liposuction.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Rosemarie 'Rose' Dupree"},
    "'Chardonnay''s Lighter": { 
        "description": "A well-used lighter. Darla 'Chardonnay' survived the yacht foundering but later drowned in her hottub after being knocked unconscious by the lid falling on her.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Darla 'Chardonnay'"},
    "'Shiraz' Edelstein's Braid": { 
        "description": "A single, stylish braided hair extension. Shirelle 'Shiraz' Edelstein survived the yacht foundering but was later internally decapitated on the set of a music video after her hair got caught in the spokes of a spinning prop car's tire.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Shirelle 'Shiraz' Edelstein"},
    "'Chablis''s Cat Toy": { 
        "description": "A small, fluffy cat toy. Ruby 'Chablis' survived the yacht foundering but later died from cyanide gas exposure, biting off her tongue.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Ruby 'Chablis'"},

    # Book Evidence: Death of the Senses (Reconciled)
    "Small Football Trophy": {
        "description": "A small, tarnished football trophy. Jack Curtis foresaw 'John Doe's' murder spree based on the five senses, prevented it, and survived the subsequent attempts on his life, only to be shot to death by a jealous police officer. Truly a shame to have lost this one; he could have been a lot of help.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Jack Curtis"},
    "Metal Sculpture Piece": { 
        "description": "A small, sharp piece from a metal sculpture. Officer Amy Tom survived a near-fatal encounter but later bled to death after being impaled by her own art.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Officer Amy Tom"},
    "Earbud": { 
        "description": "A single earbud. Joshua Cornell III, the representative of hearing, survived multiple attempts on his life in his home, but later had his head cut off by a platinum record.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Joshua Cornell III"},
    "Small Microphone": { 
        "description": "A small, lapel microphone. Katie Astin, the representative of touch, survived but was later blinded and impaled by a lighting rig.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Katie Astin"},
    "Wine Bottle Stopper": { 
        "description": "An ornate wine bottle stopper. Dominique Swann, the representative of taste, survived but later died of asphyxiation on a glass shard from an exploding bottle.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Dominique Swann"},
    "Miniature Garbage Truck": { 
        "description": "A small toy garbage truck. Dawson Donahue, the representative of smell, survived but was later crushed against a wall when his car exploded.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Dawson Donahue"},
    "Eyedrops": { 
        "description": "A small bottle of eyedrops. Chelsea Cox, the representative of sight, survived but was later impaled through the eyes by icicles.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Chelsea Cox"},

    # Comic Book Evidence: Sacrifice
    "Suicide Note": {
        "description": "A crumpled piece of paper, a suicide note. It details the visions of a tormented narrator: a bus crash killing his best friend Jim and 56 others after his warning was ignored, then a factory explosion killing at least 20 more. He believed sacrificing himself was the only way to save his family from a foreseen fiery gas station explosion.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "John Doe (Narrator)"},
    "Picket Fence Splinter": {
        "description": "A sharp splinter of wood, possibly from a picket fence. One of the factory workers who heeded the narrator's warning about the explosion later died by accidental impalement on a fence post after his ladder broke.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Unnamed Factory Worker (Fence)"},
    "Rubber Ducky": {
        "description": "A small, yellow rubber ducky. A female factory worker survived the explosion thanks to the narrator's warning, only to be electrocuted to death when her radio fell into her bathtub.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Unnamed Factory Worker (Bathing)"},
    "Lawnmower Blade Piece": {
        "description": "A jagged piece of a metal blade. Another factory worker who escaped the explosion due to the protagonist's vision was later killed when his legs were shredded by his own lawnmower.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Unnamed Factory Worker (Lawnmower)"},
    "Train Ticket": {
        "description": "A creased train ticket stub. The fourth factory worker who believed the narrator's premonition about the factory explosion was later run over by a speeding train while fleeing, as the protagonist had become a pariah.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Unnamed Factory Worker (Train)"},

    # Comic Book Evidence: Spring Break
    "Carly Hagan's Notebook": {
        "description": "A small notebook filled with notes and theories about Death. Carly Hagan, who had the premonition of the hotel fire and explosion, tried to save her friends. Despite her efforts, she never managed to save a single one and was supposedly the last to die, vanishing into thin air.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Carly Hagan"},
    "Spanish Phrasebook": {
        "description": "A small, well-worn Spanish phrasebook. Bryan, a tough but calm college student who flirted with Carly, was fluent in Spanish. He survived the hotel explosion but was later suffocated inside a trapped coffin.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Bryan"},
    "Sunglasses": {
        "description": "A pair of broken sunglasses. Jake, Carly's arrogant party-hard boyfriend who dismissed her theories, survived the hotel explosion but was later shredded by helicopter blades.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Jake"},
    "Fireworks Wrapper": {
        "description": "A piece of a colorful fireworks wrapper. Matt, Amanda's relaxed boyfriend who didn't worry about 'Death's rules,' survived the hotel explosion but was later incinerated by fireworks, which deeply upset him after Amanda's death.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Matt"},
    "Swimsuit Piece": {
        "description": "A small piece of swimsuit fabric. Amanda, admired for her good looks and initially skeptical of Carly's theories, became increasingly paranoid. She survived the hotel explosion but was later trapped and drowned in a pool.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Amanda"},
    "Bridge Piece": {
        "description": "A small, splintered piece of wood from a bridge. Jeremy, part of the mean group who only survived after hearing theories of other premonitions, seemed surprisingly calm about being hunted by Death. He survived the hotel explosion but later had his neck snapped in a bridge collapse.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": DEFAULT_ITEM_WEIGHT, "character": "Jeremy"},
    "Dreena's Necklace": {
        "description": "A broken necklace. Dreena, also part of the mean group, seemed scared but unwilling to help Carly's group escape, yet stayed close. She survived the hotel explosion but later had her neck snapped in a bridge collapse alongside Jeremy.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Dreena"},
    "Glass Shard": {
        "description": "A sharp shard of glass. Gino, the smart one from the mean group who started to believe Carly after Katie's death and even explored Mayan ruins for clues, survived the hotel explosion but was later impaled through the mouth by a glass shard.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Gino"},
    "Display Skeleton Piece": {
        "description": "A small, plastic piece from a medical display skeleton. Katie, Kris's devoted girlfriend and one of the nicest in the group, was in such shock after Kris's death she was hospitalized. She survived the hotel explosion but was later impaled on the ribs of a medical display skeleton.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": LIGHT_ITEM_WEIGHT, "character": "Katie"},
    "Propeller Blade": {
        "description": "A jagged piece of metal from a boat propeller. Kris, Katie's daredevil boyfriend who seemed ready to help, was the first of the Spring Break survivors to die after the hotel explosion, eviscerated by a boat propeller in an accident largely his own fault.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "weight": HEAVY_ITEM_WEIGHT, "character": "Kris"},

    # Book Evidence: Final Destination: Wipeout (Unreleased - Fictionalized Deaths)
    "Surf Wax (Black)": { 
        "description": "A chunk of black surf wax, smelling faintly of coconut and something metallic... like blood. Ravyn survived the beach plane crash but was later impaled by her own surfboard after a freak wave caused by a minor tremor slammed it into her during a night surf session.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Ravyn Blackthorne", "weight": DEFAULT_ITEM_WEIGHT
    },
    "Seashell Necklace Fragment": { 
        "description": "Part of a broken seashell necklace, sharp edges stained dark. Kim survived the plane crashing into the beach with Ravyn, but was later decapitated by a boat propeller while trying to retrieve Ravyn's board after the tremor-wave incident.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Kim Rachelle", "weight": LIGHT_ITEM_WEIGHT
    },
    "Rusty Fishing Hook": { 
        "description": "A large, rusty fishing hook, barbed and bent. Karl survived the plane crashing into the beach, but later tripped over a loose net on his boat during a storm, falling onto a gaff hook that pierced his eye and skull.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Karl Windsor", "weight": DEFAULT_ITEM_WEIGHT
    },
    "Tacky Souvenir T-Shirt": { 
        "description": "A brightly colored, tacky tourist t-shirt ('I Got Leid in Hawaii!'), ripped and burned. Brett survived the plane crashing into the beach but was later incinerated when a propane tank for a luau barbecue exploded unexpectedly.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Brett O'Connel", "weight": LIGHT_ITEM_WEIGHT
    },
    "Ukulele String": { 
        "description": "A snapped ukulele string. Drew survived the plane crashing into the beach but was later strangled when her scarf got caught in the gears of a sugar cane harvester she got too close to.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Drew Perkin", "weight": LIGHT_ITEM_WEIGHT
    },
    "Skateboard Wheel": { 
        "description": "A single skateboard wheel, cracked and gritty with sand. Bobby survived the plane crashing into the beach, but later fell from a hotel balcony, landing on decorative spiked railings below, after being startled by Mandy.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Bobby Fraider", "weight": DEFAULT_ITEM_WEIGHT
    },
    "Temporary Tattoo Sheet": { 
        "description": "A sheet of cheap, glittery temporary tattoos, one partially used. Mandy survived the plane crashing into the beach, but was later electrocuted in a hotel hot tub when a faulty underwater light fixture short-circuited after Bobby's fall caused a power surge.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Mandy Robertson", "weight": LIGHT_ITEM_WEIGHT
    },
    "Crushed Beer Can": { 
        "description": "A crushed aluminum beer can. Corey survived the plane crashing into the beach, but was later crushed by a falling vending machine that tipped over when he kicked it in frustration.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Corey Micheals", "weight": LIGHT_ITEM_WEIGHT
    },
     "Military Dog Tag": { 
        "description": "A dented military dog tag. Corbin Wainright, the soldier hunting the survivors, wasn't part of the plane crash premonition but had his own brush with Death. His fate after encountering Ravyn's group is unknown, but this suggests he didn't make it either.",
        "takeable": True, "level": 2, "is_evidence": True, "location": None, "is_hidden": True, "character": "Corbin Wainright", "weight": LIGHT_ITEM_WEIGHT
        },
    # Other/Ambiguous Evidence Items from original lists (keeping some for variety)
     "Newspaper Clipping": { # Generic clipping, placed specifically
        "description": "A faded newspaper clipping lies inside the crate with a key on top of it. The headline screams about the horrific disaster you survived; scattered papers underneath show the other survivors, or rather, recount their strange deaths.\nReading it sends a chill down your spine as it dawns on you: everything led to this moment right now. The disaster, the other survivors dying, you coming here of all places ..you're.. you're in danger! Grab the Coroner's Office Key and get out of here before something happens to you!",
        "takeable": True,
        "is_evidence": True,
        "level": 2, # Level 2 for House
        "location": "Attic", # Fixed location in the attic
        "is_hidden": True, # Initially hidden inside the crate
        "container": "crate", # Specifies it's in the crate
        "weight": LIGHT_ITEM_WEIGHT, # Newspaper is light
        "character": "You"
    },
        "Morgue Log Excerpt": {
        "description": "A torn page from an old morgue log. An entry reads: 'Victim: Howard Campbell, dead of acute facial/cranial trauma. Cause: Bizarre facial decapitation by falling in front of an active lawn mower. Patterns align with J.B.'s theories on pre-emptive design. His insights are... unsettlingly accurate.'",
        "takeable": True, "is_evidence": True, "level": 1, # Hospital
        "location": "Coroner's Office", # Assuming Coroner's Office is in level 1 (Hospital)
        "container": "mahogany desk", # Player needs to unlock and search the desk
        "is_hidden": True,
        "weight": 0.1, "character": "William Bludworth (referenced)",
        "narrative_flag_on_collect": "found_bludworth_connection_in_hospital"
    },
        "Bludworth's Note": { 
        "description": "A hospital note from 'JB' regarding anomalous patterns in 'accidental' deaths over the years. An address is written at the bottom, 'for anybody who might need it'.",
        "takeable": True, "is_evidence": True, "level": 1, 
        "location": "Coroner's Office", "container": "mahogany desk", "is_hidden": True,
        "weight": 0.1, "character": "William Bludworth",
        "narrative_flag_on_collect": "found_bludworth_consult_note", 
        "narrative_snippet_on_collect": "The chilling consultation note from Bludworth himself confirms your fears: these aren't accidents."
        },
    }

items = {
    # Update existing House items to level 2
    "loose brick": {
        "description": "A brick that feels loose in the fireplace cavity. It's heavy and rough.",
        "takeable": True, "location": "Living Room", "is_hidden": True, "revealed_by_action": True,
        "use_on": ["boarded window", "crate"],
        "use_result": {
            "boarded window": "With a grunt, you smash the brick against the boards...",
            "crate": "You bring the brick down hard on the crate..."
        },
        "transforms_into_on_examine": "Bloody Brick", # Corrected key from previous discussion
        "use_destroys_target": False,
        "weight": HEAVY_ITEM_WEIGHT,
        "level": 2 # Now Level 2
    },
    "toolbelt": {
        "description": "A worn leather toolbelt containing various tools, including a rubber mallet.",
        "takeable": True, "location": "Main Basement Area", "is_hidden": False,
        "use_on": ["fireplace cavity"],
        "use_result": {
            "fireplace cavity": "You use the rubber mallet from the toolbelt to carefully tap it..."
        },
        "use_destroys_target": False,
        "weight": HEAVY_ITEM_WEIGHT,
        "level": 2 # Now Level 2
    },
    "Shattered Porcelain Shard": {
        "description": "A sharp piece of broken porcelain. Looks dangerous if stepped on.",
        "takeable": True, # Or False if it's just an environmental detail players avoid
        "weight": 0.1,
        "is_evidence": False,
        "level": "all", # Can appear on any level if dynamically created
        "is_floor_hazard": True, # New flag
        "floor_hazard_effect": { # Effects if stepped on (checked by HazardEngine during/after move)
            "status_effect": {"name": "bleeding", "duration": 2, "hp_damage": 1},
            "message": "You step on a sharp porcelain shard, cutting your foot!",
            "chance": 0.25 # Chance to trigger effect when moving into/within room with it on floor
        }
    },
    "Dust Cloud Puff": { # Example of a non-takeable effect item
        "description": "A puff of dust briefly hangs in the air.",
        "takeable": False,
        "duration_in_room_turns": 1 # How long the "effect" is noted
        }
    }



# --- Hazard Master Data ---
# Hazard definitions are global. Their placement is level-specific via room data.
hazards = {
    "weak_floorboards": {
        "name": "Weak Floorboards",
        "initial_state": "creaking",
        "placement_object": ["floorboards", "rotted wood patch", "section of flooring"],
        "object_name_options": ["creaky floorboard", "rotted plank", "unstable section of floor"],
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.1,
                "target_state": "cracking",
                "message": "The {object_name} groans ominously under your scrutiny."
            },
            "jump": {
                "chance_to_trigger": 0.8,
                "target_state": "collapsing",
                "message": "As you jump on the {object_name}, it gives way beneath your weight with a terrible crack!"
            },
            "jump_on": {
                "chance_to_trigger": 0.8,
                "target_state": "collapsing",
                "message": "You foolishly jump on the {object_name} and it immediately gives way!"
            }
        },
        "states": {
            "creaking": {"description": "The {object_name} near the {support_object} creaks ominously when weight is applied."},
            "cracking": {"description": "Visible cracks spread across the {object_name} on the {support_object}. It feels very unstable.", "chance_to_progress": 0.3, "next_state": "collapsing"},
            "collapsing": {
                "description": "With a sharp crack, the {object_name} on the {support_object} gives way!",
                "autonomous_action": "check_fall_through", # HazardEngine handles this
                "fall_outcome_message": "You plummet through the collapsing floor!",
                "fall_damage": 3,
                "fall_target_room_override": None, # Can be set by room_specific_outcomes
                "is_fatal_if_no_target": False # If no target room, player just takes damage and stays (or specific message)
            },
            "tripping_on_porch": { # Specific for House Endgame
                "description": "The overloaded porch groans and a section gives way under your feet, sending you sprawling!",
                "status_effect": {"name": "stumbled", "duration": 1},
                "is_fatal": False,
                "message": "You hit the deck hard as the wood splinters! That was close!"
            },
            "hole": {"description": "A gaping hole remains where the {object_name} on the {support_object} used to be."}
        },
        "room_specific_outcomes": { # Maps room name to a target state or a target room for 'collapsing' state
            "Front Porch": "tripping_on_porch", # Player trips, doesn't fall through for endgame
            "Attic": "Staircase Landing" # Example: Falling from Attic lands you on Staircase Landing
        }
    },
    "faulty_wiring": {
        "name": "Faulty Wiring",
        "initial_state": "exposed",
        "placement_object": ["wall panel", "junction box", "ceiling fan", "dirty sink"],
        "object_name_options": ["exposed wires", "frayed cable", "sparking outlet"],
        "movement_logic": None,
        "player_seek_chance": 0.0,
        "player_proximity_trigger": {
            "state_requirements": ["sparking"],
            "condition_player_has_metal_items": True,
            "chance_to_escalate": 0.3,
            "aggression_influence_on_chance": 0.1,
            "escalation_logic": [
                {"message": "The {object_name} near you arcs violently due to your metallic items!", "to_state": "arcing"}
            ]
        },
        "states": {
            "exposed": {
                "description": "Some wires look dangerously exposed near the {support_object}.",
                "chance_to_progress": 0.1,
                "next_state": "sparking",
                "environmental_effect": {}
            },
            "sparking": {
                "description": "The {object_name} on the {support_object} are emitting dangerous sparks!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+1"},
                "chance_to_progress": 0.05,
                "next_state": "arcing",
                "chance_to_revert": 0.2,
                "revert_state": "exposed",
                "hazard_interaction": {
                    "gas_leak": {
                        "requires_target_hazard_state": ["leaking", "heavy_leak"],
                        "chance": 0.9,
                        "message": "The sparks from {source_hazard_object} ignite the gas from the {target_hazard_object}!",
                        "target_state": "ignited",
                        "source_target_state": "shorted_out"
                    },
                    "water_puddle": {
                        "requires_target_hazard_state": "present",
                        "chance": 0.8,
                        "message": "Sparks from the {source_hazard_object} electrify the {target_hazard_object}!",
                        "target_state": "electrified",
                        "source_target_state": "shorted_out"
                    }
                },
                "contact_status_effect": {"name": "stunned", "duration": 1, "hp_damage": 2},
                "causes_effect_on_contact": True,
            },
            "arcing": {
                "description": "The {object_name} is arcing violently!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                "instant_death_if_hit": True,
                "death_message": "You're struck by a powerful electrical arc from the {object_name}!",
                "triggers_hazard_on_state_change": [
                    {"type": "spreading_fire", "chance": 0.3, "target_object": "{support_object}", "initial_state": "smoldering"}
                ]
            },
            "shorted_out": {
                "description": "The {object_name} on the {support_object} looks dead and smoking slightly.",
                "environmental_effect": {"is_sparking": False}
            }
        },
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.2,
                "target_state": "sparking",
                "message": "As you examine the {object_name}, it suddenly starts sparking!"
            },
            "use": {
                # Accept either a specific item or any item of a given type
                # "required_item": "rubber_gloves",  # (legacy, still supported)
                "item_used_type": "protective_gear",  # New: any item with type "protective_gear" works
                "chance_to_trigger": 0.9,
                "target_state": "shorted_out",
                "message": "You manage to safely insulate the {object_name} with your protective gear."
            },
            "touch": {
                "chance_to_trigger": 0.8,
                "effect": "electrocution",
                "message": "You foolishly touch the {object_name}!"
            }
        }
    },
    "gas_leak": {
        "name": "Gas Leak",
        "initial_state": "faint_smell",
        "placement_object": ["gas pipe", "stove knob", "furnace valve"],
        "object_name_options": ["corroded gas pipe", "loose stove knob", "faulty furnace valve"],
        "player_interaction": {
            "examine": {"chance_to_trigger": 0.15, "target_state": "hissing_leak", "message": "You investigate the {object_name}. The smell of gas intensifies, and you hear a faint hiss."},
            "use_tool_on_valve": {"required_item": "wrench", "target_state": "sealed_leak", "message": "You manage to tighten the {object_name}, and the hissing stops. The smell of gas lessens."}
        },
        "states": {
            "faint_smell": {"description": "There's a faint, sweet smell of gas near the {object_name} on the {support_object}.", "environmental_effect": {"gas_level": "+0.5"}},
            "hissing_leak": {
                "description": "A steady hiss comes from the {object_name} on the {support_object}, and the smell of gas is stronger.",
                "environmental_effect": {"gas_level": "+1", "noise_level": "+1"},
                "chance_to_progress": 0.2, "next_state": "heavy_leak"
            },
            "heavy_leak": {
                "description": "The smell of gas from the {object_name} on the {support_object} is overpowering. The air feels thick with it.",
                "environmental_effect": {"gas_level": "+2", "noise_level": "+1"},
                "status_effect_on_room_entry": {"name": "dizzy", "duration": 2} # Player gets dizzy just by being in room
            },
            "ignited": { # Triggered by sparks or fire
                "description": "The leaking gas from the {object_name} on the {support_object} ignites with a terrifying WHOOSH!",
                "instant_death_in_room": True, # If player is in room when it ignites
                "death_message": "The room erupts in a fireball as the gas ignites! You're instantly incinerated.",
                "environmental_effect": {"is_on_fire": True, "gas_level": "0", "noise_level": "+5", "visibility": "dense_smoke"},
                "sets_room_on_fire": True
            },
            "sealed_leak": {"description": "The {object_name} on the {support_object} appears to be sealed. The smell of gas is fading.", "environmental_effect": {"gas_level": "-1"}} # Reduces gas level
        }
    },
    "wobbly_ceiling_fan": { # From previous iteration, assuming it's for level 1
        "level_id": 1, # Mark as level 1 specific hazard placement contextually if needed
        "name": "Wobbly Ceiling Fan",
        "initial_state": "stable",
        "placement_object": ["ceiling fan fixture"],
        "object_name_options": ["old ceiling fan", "rickety ceiling fan", "heavy ceiling fan"],
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.2, "target_state": "wobbling", "aggression_modifier": 0.1,
                "message": "You look up at the {object_name}. It sways slightly more than it should.",
                "message_already_wobbling": "The {object_name} is definitely unsteady. Best not to linger underneath."
            },
            "use": {
                "chance_to_trigger": 0.4, "target_state": "sparking_wobble", "aggression_modifier": 0.2,
                "message": "You try to operate the {object_name}. It lurches, sparks fly from its base, and it begins to wobble violently!",
                "message_already_sparking": "Messing with the sparking, wobbling {object_name} seems like a death wish!"
            }
        },
        "states": {
            "stable": {
                "description": "An {object_name} hangs overhead, its blades still. Frayed wiring is visible near its base.",
                "chance_to_progress": 0.02, "next_state": "wobbling",
                "aggression_influence": {"chance_to_progress_boost": 0.03}
            },
            "wobbling": {
                "description": "The {object_name} overhead creaks and wobbles precariously!",
                "environmental_effect": {"noise_level": "+1"},
                "chance_to_progress": 0.3, "next_state": "sparking_wobble",
                "aggression_influence": {"chance_to_progress_boost": 0.15},
                "chance_to_fall_if_wobbling_too_long": 0.1,
                "next_state_if_fall": "falling"
            },
            "sparking_wobble": {
                "description": "Sparks erupt from the base of the {object_name} as it sways dangerously!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                "chance_to_progress": 0.5, "next_state": "falling",
                "aggression_influence": {"chance_to_progress_boost": 0.25},
                "hazard_interaction": {
                    "gas_leak": {
                        "target_state": "ignited", "chance": 0.7, "aggression_influence_on_chance": 0.15,
                        "requires_target_hazard_state": ["leaking", "heavy_leak"],
                        "message": "A spark from the wildly swinging {source_hazard_object} ignites the gas!"
                    }
                }
            },
            "falling": {
                "description": "With a horrifying shriek of tearing metal, the {object_name} breaks loose from the ceiling and plummets!",
                "autonomous_action": "check_hit_player",
                "environmental_effect": {"noise_level": "+3"},
                "instant_death_if_hit": True,
                "death_message": "The heavy {object_name} crashes down on you, silencing your investigation permanently.",
                "chance_to_progress": 1.0, "next_state": "fallen"
            },
            "fallen": {
                "description": "The wreckage of the {object_name} lies shattered on the floor. The ceiling above is damaged.",
                "triggers_hazard_on_state_change": [{
                        "type": "loose_object", "target_object": "ceiling_damage_area",
                        "object_name_options": ["cloud of dust", "splintered wood", "piece of plaster"],
                        "initial_state": "falling", "chance": 0.4, "condition": "player_in_room",
                        "aggression_influence_on_chance": 0.1,
                        "trigger_message": "The impact of the {source_name} shakes dust and debris from the damaged ceiling!"
                }]
            }
        }
    },

    "contaminated_waste": {
        "name": "Contaminated Waste Bin",
        "initial_state": "sealed",
        "placement_object": ["medical waste bin", "biohazard container"],
        "object_name_options": ["red biohazard bin", "overflowing sharps container"],
        "player_interaction": {
            "examine": {
                "message": "A {object_name}, clearly marked with biohazard symbols. It seems sealed... mostly."
            },
            "search": { # Trying to search it
                "chance_to_trigger": 0.3, "target_state": "leaking_fumes", "aggression_modifier": 0.1,
                "message": "You try to pry open the {object_name}. A puff of noxious gas escapes!",
                "status_effect_on_trigger": {"name": "poisoned", "duration": 2, "hp_damage": 1}
            }
        },
        "states": {
            "sealed": {
                "description": "A {object_name} sits in the corner, seemingly secure."
            },
            "leaking_fumes": {
                "description": "The {object_name} is clearly damaged, and a foul, irritating gas seeps out.",
                "environmental_effect": {"gas_level": "+0.5"}, # Slower, more localized gas
                "status_effect_on_room_entry": {"name": "disoriented", "duration": 1}, # If player enters room with this active
                "chance_to_progress": 0.05, "next_state": "spilled", # Can get knocked over
                "aggression_influence": {"chance_to_progress_boost": 0.1}
            },
            "spilled": {
                "description": "The {object_name} has been knocked over, its hazardous contents spilling onto the floor!",
                "environmental_effect": {"is_wet": True, "gas_level": "+1"}, # Creates a "wet" (contaminated) area
                "contact_status_effect": {"name": "poisoned", "duration": 3, "hp_damage": 2}, # If player steps in it
                "death_message": "You slip in the spilled contaminated waste, and a searing pain shoots through you as the toxins enter your system. It's a slow, agonizing end."
                # This state could also interact with "water_puddle" to make it a "contaminated_puddle"
            }
        }
    },
    "robot_vacuum_malfunctioning": {
        "name": "Malfunctioning Robot Vacuum",
        "initial_state": "docked",
        "can_move_between_rooms": True,
        "object_name_options": ["erratic robot vacuum", "whirring floor cleaner", "rogue Roomba"],
        "movement_logic": "seek_target_type_then_player", # New or enhanced logic in HazardEngine
        "seekable_target_types": ["gas_leak_source"], # What it actively looks for first
        "player_seek_chance_if_no_primary_target": 0.2, # Chance to seek player if no gas leak found
        "aggression_influence": { # How global aggression affects this hazard
            "player_seek_chance_boost": 0.1, # e.g., agg_factor * 0.1 added to seek chance
            "chance_to_start_sparking_boost": 0.05, # More likely to become dangerous
            "collision_player_chance_multiplier": 1.2 # More likely to cause issues on collision
        },
        "collision_targets": ["player", "loose_object", "spillable_container", "unstable_shelf_support"],
        "collision_effects": {
            "player": {"chance": 0.15, "effect": "trip", "status_effect": {"name": "tripped", "duration": 1}, "message": "The {object_name} careens into your legs, making you stumble!"},
            "loose_object": {"chance": 0.3, "effect": "knock_over", "target_hazard_type":"loose_object", "target_hazard_state": "wobbling", "message": "The {object_name} bumps the {target_object_name}, sending it wobbling!"}
            # Add more for "spillable_container" (e.g. trigger a spill), "unstable_shelf_support" (e.g. change shelf state)
        },
        "states": {
            "docked": {
                "description": "A {object_name} sits quietly on its charging dock.",
                "environmental_effect": {"noise_level": "+0"},
                "chance_to_progress": 0.1, # Chance to activate each turn
                "next_state": "patrolling",
                "aggression_influence": {"chance_to_progress_boost": 0.1}
            },
            "patrolling": {
                "autonomous_action": "move_and_interact", # Changed from "move_and_interact"
                "can_move_randomly_if_not_seeking": True, # Used by _move_and_interact
                "description": "The {object_name} hums as it randomly patrols the area.",
                "environmental_effect": {"noise_level": "+1"},
                "chance_to_progress": 0.05, # Chance to detect something or malfunction
                "next_state": "seeking_gas_leak", # Could also go to "sparking_randomly"
                "player_seek_chance": 0.05 # Low chance to bother player while just patrolling
            },
            "seeking_gas_leak": {
                "autonomous_action": "move_and_interact",
                "target_type_to_seek": "gas_leak", # Changed from "gas_leak_source" to actual hazard type
                "on_target_found_next_state": "approaching_gas_source",
                "description": "The {object_name} beeps erratically, its sensors scanning. It seems to be hunting for something.",
                "environmental_effect": {"noise_level": "+1"},
                "chance_to_progress_if_target_not_found": 0.1, # Chance to give up or change behavior
                "next_state_if_target_not_found": "sparking_randomly" # Or back to patrolling
            },
            "approaching_gas_source": {
                "description": "The {object_name} locks onto a target and moves purposefully towards the source of a suspected gas leak!",
                "environmental_effect": {"noise_level": "+2"},
                "autonomous_action": "move_and_interact", # Continues moving towards target
                "proximity_to_target_next_state": "near_gas_sparking", # State when it reaches target
                "proximity_threshold": 1, # e.g., when in the same room as the gas_leak_source
            },
            "near_gas_sparking": {
                "description": "The {object_name} is dangerously close to a gas source and starts to emit sparks from its damaged motor!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                "hazard_interaction": {
                    "gas_leak": { # Interacts with a "gas_leak" type hazard
                        "requires_target_hazard_state": ["hissing_leak", "heavy_leak"], # Gas leak must be active
                        "chance": 0.85, # High chance to ignite
                        "message": "Sparks from the {source_hazard_object} fly towards the {target_hazard_object}...",
                        "target_state": "ignited", # Tells the gas_leak hazard to go to its "ignited" state
                        "source_target_state": "broken_after_explosion" # What happens to the vacuum
                    }
                },
                "chance_to_progress": 0.1, # Chance to break down even if no explosion
                "next_state": "broken_malfunctioning"
            },
            "sparking_randomly": {
                "description": "The {object_name} malfunctions, erratically zipping around and emitting dangerous sparks!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                "autonomous_action": "move_and_interact", # Moves randomly while sparking
                "can_move_randomly_if_not_seeking": True,
                "hazard_interaction": { # Can still ignite gas if it randomly enters a gassy room
                    "gas_leak": {
                        "requires_target_hazard_state": ["hissing_leak", "heavy_leak"],
                        "chance": 0.4, # Lower chance if just randomly encountering
                        "message": "The randomly sparking {source_hazard_object} ignites gas from {target_hazard_object}!",
                        "target_state": "ignited",
                        "source_target_state": "broken_after_explosion"
                    }
                },
                "chance_to_progress": 0.2, # Chance to break down
                "next_state": "broken_malfunctioning"
            },
            "broken_after_explosion": {
                "description": "The {object_name} is a charred, twisted wreck after the explosion it caused.",
                "environmental_effect": {"is_sparking": False, "noise_level": "+0"}
            },
            "broken_malfunctioning": {
                "description": "The {object_name} sputters and dies, its casing cracked and smoking faintly.",
                "environmental_effect": {"is_sparking": False, "noise_level": "+0"}
            }
        }
    },

    "water_puddle": {
        "name": "Water Puddle",
        "initial_state": "small",
        "placement_object": ["sink", "toilet", "bathtub", "shower", "water pipes"],
        "object_name_options": ["puddle of water", "wet spot", "slippery area"],
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.0,
                "message": "You see a {object_name} on the floor by the {support_object}."
            },
            "step_in": {
                "chance_to_trigger": 0.4,
                "target_state": "slip_hazard",
                "message": "You step in the {object_name} and nearly slip!"
            }
        },
        "states": {
            "small": {
                "description": "There's a {object_name} around the {support_object}.",
                "chance_to_progress": 0.2,
                "next_state": "growing",
                "environmental_effect": {
                    "is_wet": True
                }
            },
            "growing": {
                "description": "The {object_name} has grown larger around the {support_object}.",
                "chance_to_progress": 0.3,
                "next_state": "slip_hazard",
                "environmental_effect": {
                    "is_wet": True
                }
            },
            "slip_hazard": {
                "description": "There's a large, dangerous {object_name} spreading from the {support_object}.",
                "autonomous_action": "check_player_slip",
                "slip_damage": 1,
                "slip_message": "You slip on the wet floor and fall painfully!",
                "is_fatal": False,
                "environmental_effect": {
                    "is_wet": True
                }
            }
        }
    },
    "loose_object": {
        "name": "Loose Object",
        "object_name_options": ["heavy book", "ceramic vase", "loose ceiling tile", "precariously stacked cans", "unstable toolkit", "antique music box", "dusty trophy"],
        "initial_state": "precarious",
        "placement_object": ["shelf", "table", "mantlepiece", "top_of_cabinet", "ceiling", "workbench_top", "windowsill", "bookcase_top"],
        "death_message": "The falling {object_name} strikes you with deadly force!",
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.05, "target_state": "wobbling", "aggression_modifier": 0.1,
                "message": "As you examine the {object_name}, it shifts alarmingly."
            },
            "take": {
                "chance_to_trigger": 0.3, "target_state": "falling", "aggression_modifier": 0.15,
                "message": "You try to grab the {object_name}, but it slips from your grasp and begins to fall!"
            }
        },
        "affected_by": { # External triggers affecting the *support_object* or general area
            "player_bump_support": {"chance": 0.2, "target_state": "wobbling", "aggression_modifier": 0.1},
            "robot_vacuum_collision": {"chance": 0.3, "target_state": "wobbling", "aggression_modifier": 0.15},
            "weak_floorboards_trigger_nearby": {"chance": 0.4, "target_state": "wobbling", "aggression_modifier": 0.1},
            "loud_noise_nearby": {"chance": 0.15, "target_state": "wobbling", "aggression_modifier": 0.1},
            "explosion_nearby": {"chance": 0.7, "target_state": "falling", "aggression_modifier": 0.1}
        },
        "player_proximity_trigger": { # If player is just in the room, very low chance
            "state_requirements": ["precarious"],
            "chance_to_escalate": 0.01,
            "escalation_logic": [{"to_state": "wobbling", "message": "A slight tremor passes through the room, and the {object_name} on the {support_object} shifts slightly."}],
            "aggression_influence_on_chance": 0.02
        },
        "states": {
            "precarious": {
                "description": (
                    "A {object_name} rests precariously on the {support_object}."
                    if "{support_object}" not in ["ceiling", "nearby", None, ""] else
                    "Something heavy ({object_name}) is precariously positioned overhead."
                ),
                "chance_to_progress": 0.03, "next_state": "wobbling", # Naturally gets less stable over time
                "aggression_influence": {"chance_to_progress_boost": 0.05}
            },
            "wobbling": {
                "description": "The {object_name} on the {support_object} wobbles dangerously!",
                "chance_to_progress": 0.6, "next_state": "falling",
                "environmental_effect": {"noise_level": "+0"}, # Typically silent
                "aggression_influence": {"chance_to_progress_boost": 0.2}
            },
            "falling": {
                "description": "The {object_name} suddenly topples from the {support_object} and plummets!",
                "autonomous_action": "check_hit_player", # Engine checks if player is in hazard's location
                "environmental_effect": {"noise_level": "+1"},
                "instant_death_if_hit": True, # Handled by engine's autonomous_action
                "chance_to_progress": 1.0, "next_state": "fallen"
            },
            "fallen": {
                "description": "The {object_name} lies shattered or dented on the floor near the {support_object}.",
                "triggers_hazard_on_state_change": [
                    {
                        "type": "startle_player", "chance": 0.3, "condition": "player_in_room",
                        "aggression_influence_on_chance": 0.15,
                        "trigger_message": "The crash of the {source_name} makes you jump!"
                    },
                    { # If it was a container (e.g. "jar of marbles", "pot of paint")
                        "type": "water_puddle", # Generic "spill" hazard
                        "target_object" : "{support_object}", # Spills near where it fell
                        "initial_state": "small",
                        "chance": 0.2, "condition_property_on_object_name": "spillable", # If object_name was defined as spillable
                        "aggression_influence_on_chance": 0.1,
                        "trigger_message": "When the {source_name} hit the floor, its contents spilled out!"
                    }
                ]
            }
        }
    },
    "unstable_shelf": {
        "name": "Unstable Shelf",
        "initial_state": "stable",
        "placement_object": ["bookshelves", "shelves", "cupboard", "wall_mounted_shelf"],
        "player_interaction": {
            "examine": {
                "chance_to_reveal": 0.7, "target_state": "wobbling", "aggression_modifier": 0.1,
                "message": "The {object} groans under its own weight as you look at it."
            },
            "search": {"chance_to_trigger": 0.1, "target_state": "collapsing", "aggression_modifier": 0.2},
            "take_item_from": {"chance_to_trigger": 0.15, "target_state": "collapsing", "aggression_modifier": 0.15}
        },
        "affected_by": {
            "loud_noise_nearby": {"chance": 0.2, "target_state": "wobbling", "aggression_modifier": 0.1},
            "robot_vacuum_collision": {"chance": 0.4, "target_state": "wobbling", "aggression_modifier": 0.1},
            "explosion_nearby": {"chance": 0.8, "target_state": "collapsing", "aggression_modifier": 0.1}
        },
        "states": {
            "stable": {"description": "The {object} seems sturdy enough."},
            "wobbling": {
                "description": "The {object} looks overloaded and precarious, wobbling slightly.",
                "chance_to_progress": 0.2, "next_state": "collapsing",
                "aggression_influence": {"chance_to_progress_boost": 0.2}
            },
            "collapsing": {
                "description": "With a terrible groan, the {object} gives way!",
                "instant_death": True, # If player is under/near it (HazardEngine checks this)
                "death_message": "The {object} gives way! Heavy items and splintered wood crash down, burying you.",
                "environmental_effect": {"noise_level": "+2"},
                "triggers_hazard_on_state_change": [
                     {"type": "loose_object", "target_object": "floor_near_{object}", "object_name_options": ["heavy book", "shattered knick-knack", "cloud of dust"], "initial_state": "fallen", "chance": 1.0, "trigger_message": "Contents of the {source_name} scatter everywhere!"}
                ],
                 "chance_to_progress": 1.0, "next_state": "collapsed"
            },
            "collapsed": {
                "description": "The {object} lies in a heap of broken wood and scattered contents on the floor."
            }
        }
    },
    "mri_machine_hazard": {
        "name": "Magnetic Resonance Imager",
        "initial_state": "powered_down",
        "placement_object": ["MRI machine"], # Should be defined in MRI Scan Room's hazards_present
        "object_name_options": ["MRI machine"],
        "player_interaction": {
            "examine": {"chance_to_trigger": 0.05, "target_state": "flickering_power", "message": "The massive MRI machine hums faintly. A loose panel sparks when you touch it.", "aggression_modifier": 0.1},
            "use_tool": {"chance_to_trigger": 0.3, "target_state": "power_surge", "message": "You mess with a control panel. Lights flash and the humming intensifies dangerously!", "aggression_modifier": 0.2}
        },
        "states": {
            "powered_down": {
                "description": "The {object_name} is silent and dark.",
                "chance_to_progress": 0.02, "next_state": "flickering_power",
                "aggression_influence": {"chance_to_progress_boost": 0.05}
            },
            "flickering_power": {
                "description": "Lights on the {object_name} control panel flicker erratically. A low hum is audible.",
                "environmental_effect": {"noise_level": "+1"},
                "chance_to_progress": 0.1, "next_state": "power_surge",
                "aggression_influence": {"chance_to_progress_boost": 0.1}
            },
            "power_surge": { # Can be triggered by Radiology Key Card
                "description": "The {object_name} emits a loud whine and sparks fly from its casing! The magnetic field feels stronger.",
                "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                "chance_to_progress": 0.4, "next_state": "active_scan_pull", # Default progression
                "aggression_influence": {"chance_to_progress_boost": 0.2}
                # This state could also check if Coroner's Key is in room and transition to QTE sequence
            },
            "active_scan_pull": { # General active state, might pull loose items
                "description": "The {object_name} is fully active, its powerful magnetic field yanking at anything metallic!",
                "environmental_effect": {"noise_level": "+3"},
                "autonomous_action": "mri_pull_objects", # Generic pull
                "item_pull_damage": 2, # Less than QTE projectiles
                "item_pull_message": "{pulled_item_name} is ripped from your grasp and flies into the MRI!",
                "chance_to_progress": 0.05, "next_state": "catastrophic_failure",
            },
            # --- Coroner's Key QTE Sequence States ---
            "coroners_key_qte_initiate_pull": {
                "description": "The {object_name} ROARS to life! The Coroner's Key is ripped from your grasp by an irresistible force, slamming against the machine's housing!",
                "environmental_effect": {"noise_level": "+4", "is_sparking": True},
                "on_state_entry_special_action": "handle_coroners_key_magnetize", # GameLogic handles this
                "chance_to_progress": 1.0, # Immediately progresses
                "next_state": "qte_metal_shower_stage1",
                "instant_hp_damage": 0 # The shock is the effect
            },
            "qte_metal_shower_stage1": {
                "description": "Metallic objects in the room begin to rattle violently! Suddenly, a tray of scalpels and clamps rips from a nearby cart and flies towards your head!",
                "autonomous_action": "_mri_qte_projectile_action", # HazardEngine handles this
                "qte_projectile_name": "a tray of sharp medical instruments",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 3.0,
                "damage_on_qte_fail": 4,
                "next_state_after_qte": "qte_metal_shower_stage2", # Progresses on QTE resolution (success/fail)
                "environmental_effect": {"noise_level": "+3"}
            },
            "qte_metal_shower_stage2": {
                "description": "Before you can recover, a heavy oxygen tank tears loose from the wall, tumbling erratically towards you!",
                "autonomous_action": "_mri_qte_projectile_action",
                "qte_projectile_name": "a heavy oxygen tank",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 2.5,
                "damage_on_qte_fail": 6,
                "next_state_after_qte": "qte_metal_shower_stage3",
                "environmental_effect": {"noise_level": "+4"}
            },
            "qte_metal_shower_stage3": {
                "description": "The {object_name} shrieks! An entire metal gurney careens across the room, aimed straight for you!",
                "autonomous_action": "_mri_qte_projectile_action",
                "qte_projectile_name": "a metal gurney",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 2.0,
                "damage_on_qte_fail": 10, # More damaging
                "next_state_after_qte": "mri_overload_sequence_complete", # If player survives all stages
                "environmental_effect": {"noise_level": "+5", "visibility": "patchy_smoke"}
            },
            "mri_overload_sequence_complete": {
                "description": "The {object_name} shudders violently, sparks cascading from its panels. The magnetic field fluctuates wildly, then with a deafening CLANG and a shower of sparks, it dies. Smoke pours from the machine.",
                "environmental_effect": {"noise_level": "+1", "is_sparking": False, "visibility": "dense_smoke"},
                "on_state_entry_special_action": "handle_coroners_key_release", # GameLogic handles this
                "chance_to_progress": 1.0,
                "next_state": "mri_deactivated_key_released", # Final state for this path
                "on_state_entry_unlock_room": "Morgue" # Unlocks Morgue door as part of sequence end
            },
            "mri_deactivated_key_released":{
                "description": "The {object_name} is a smoking, sputtering wreck. The Coroner's Key lies on the floor nearby, released from the dead machine. The Morgue door is now accessible.",
                "environmental_effect": {"noise_level": "0", "visibility": "dense_smoke"}
                # Key is made takeable by GameLogic via on_state_entry_special_action of previous state
            },
            # --- End Coroner's Key QTE ---
            "catastrophic_failure": { # General failure state if not Coroner's Key sequence
                "description": "The {object_name} begins to shake violently, the magnetic coils creating a deafening noise as they overload!",
                "environmental_effect": {"noise_level": "+4", "visibility":"patchy_smoke"},
                "autonomous_action": "_mri_explosion_countdown", # Existing action
                "countdown_turns": 2,
                "explosion_death_message": "The MRI machine explodes catastrophically! The blast tears through the room, leaving nothing but destruction in its wake.",
                "chance_to_progress": 1.0, "next_state": "exploded"
            },
            "exploded": {
                "description": "What remains of the {object_name} is a smoking, twisted wreck. The explosion has destroyed much of the room.",
                "environmental_effect": {"noise_level": "0", "visibility":"dense_smoke"}
            },
            "shorted_out": { # General safe state
                "description": "With a final pop and a puff of acrid smoke, the {object_name} goes silent. The magnetic field is gone.",
                "environmental_effect": {"noise_level": "0", "visibility":"normal"}
            }
            # Note: The door_force_attempt_reaction states are specific to forcing the Morgue door,
            # which is a separate interaction path from finding the Coroner's Key.
            # If finding Coroner's Key also unlocks Morgue door, that happens at the end of its QTE sequence.
        }
    },
    "precarious_object": {
        "name": "Precarious Object",
        "initial_state": "unstable",
        "placement_object": ["heavy bookcase", "wall cabinet", "trophy case", "medicine cabinet", "large mirror"],
        "object_name_options": ["unstable object", "teetering item", "wobbly fixture"],
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.1,
                "target_state": "very_unstable",
                "message": "The {object_name} wobbles ominously as you look at it."
            },
            "touch": {
                "chance_to_trigger": 0.6,
                "target_state": "falling",
                "message": "You touch the {object_name} and it begins to topple!"
            }
        },
        "states": {
            "unstable": {
                "description": "The {object_name} near the {support_object} looks unsteady, as if it might fall.",
                "chance_to_progress": 0.05,
                "next_state": "very_unstable"
            },
            "very_unstable": {
                "description": "The {object_name} on the {support_object} wobbles precariously at the slightest movement.",
                "chance_to_progress": 0.2,
                "next_state": "falling"
            },
            "falling": {
                "description": "The {object_name} on the {support_object} tips over and crashes down!",
                "autonomous_action": "check_hit_player",
                "hit_damage": 2,
                "is_fatal_if_direct_hit": False,
                "chance_to_progress": 1.0,
                "next_state": "fallen",
                "hit_message": "The falling {object_name} strikes you, causing injury!"
            },
            "fallen": {
                "description": "The {object_name}, which had fallen from the {support_object}, now lies shattered or dented on the floor.",
                "triggers_hazard_on_state_change": [
                    {
                        "type": "startle_player", "chance": 0.3, "condition": "player_in_room",
                        "aggression_influence_on_chance": 0.15,
                        "trigger_message": "The crash of the {source_name} makes you jump!"
                    },
                    { 
                        "type": "water_puddle", # Generic "spill" hazard
                        "target_object" : "{support_object}", # Spills near where it fell
                        "initial_state": "small",
                        "chance": 0.2, "condition_property_on_object_name": "spillable", 
                        "aggression_influence_on_chance": 0.1,
                        "trigger_message": "When the {source_name} hit the floor, its contents spilled out!"
                    }
                ]
            }
        }
    },
    "collapsing_stairs": {
        "name": "Collapsing Stairs",
        "initial_state": "stable",
        "placement_object": ["stairs"],
        "trigger_action": ["move", "examine"],
        "base_trigger_chance_on_move": 0.15, # Base chance when moving onto them
        "base_trigger_chance_on_examine": 0.05, # Base chance when examining
        "weight_factor": 0.1, # Player weight influence
        "interaction_factor": 1.5, # Multiplier per examination count
        "aggression_influence_on_trigger": 0.15, # Additive boost from agg_factor
        "reveal_on_examine": {"chance": 0.9, "target_state": "creaking", "aggression_modifier": 0.05},
        "states": {
            "stable": {"description": "The {object} look old but seem to hold."},
            "creaking": {
                "description": "The wooden {object} groan and shift under the slightest weight. They look ready to collapse.",
                "chance_to_progress": 0.1, "next_state": "collapsing",
                "aggression_influence": {"chance_to_progress_boost": 0.2}
            },
            "collapsing": {
                "description": "With a sickening crack, the {object} give way beneath you!",
                "instant_death": True,
                "death_message": "You tumble violently downwards as the {object} collapse, the fall breaking your neck.",
                "environmental_effect": {"noise_level": "+3"},
                "triggers_hazard_on_state_change": [
                    {"type": "loose_object", "target_object": "nearby_wall_or_ceiling", "object_name_options": ["dislodged beam", "cloud of splinters", "heavy light fixture"], "initial_state": "falling", "chance": 0.5, "trigger_message": "The violent collapse of the stairs shakes loose other parts of the structure!"}
                ],
                "chance_to_progress": 1.0, "next_state": "collapsed"
            },
            "collapsed": {
                "description": "The {object} are now a pile of broken timbers, blocking the way."
                }
            }
        },
        "mri_machine_hazard": {
            "name": "Magnetic Resonance Imager",
            "initial_state": "powered_down",  # Default initial state
            "placement_object": ["MRI machine"],
            "object_name_options": ["MRI machine"],
            "player_interaction": {
                "examine": {
                    "chance_to_trigger": 0.05, "target_state": "flickering_power",
                    "message": "The massive MRI machine hums faintly. A loose panel sparks when you touch it.",
                    "aggression_modifier": 0.1
                },
                "use_tool": {
                    "chance_to_trigger": 0.3, "target_state": "power_surge",
                    "message": "You mess with a control panel. Lights flash and the humming intensifies dangerously!",
                    "aggression_modifier": 0.2
                }
            },
            "player_proximity_trigger": {
                "state_requirements": ["flickering_power", "power_surge", "active_scan_pull"],
                "chance_to_escalate": 0.2,
                "condition_player_has_metal_items": True,
                "escalation_logic": [
                    {"from_state": "flickering_power", "to_state": "active_scan_pull", "message": "As you get closer, metallic items on you VIOLENTLY tug towards the MRI!"},
                    {"from_state": "power_surge", "to_state": "active_scan_pull", "message": "The surging MRI machine suddenly unleashes a powerful magnetic pulse!"}
                ],
                "aggression_influence_on_chance": 0.15
            },
            "states": {
                "powered_down": {
                    "description": "The {object_name} is silent and dark.",
                    "chance_to_progress": 0.02, "next_state": "flickering_power",
                    "aggression_influence": {"chance_to_progress_boost": 0.05}
                },
                "flickering_power": {
                    "description": "Lights on the {object_name} control panel flicker erratically. A low hum is audible.",
                    "environmental_effect": {"noise_level": "+1"},
                    "chance_to_progress": 0.1, "next_state": "power_surge",
                    "aggression_influence": {"chance_to_progress_boost": 0.1}
                },
                "power_surge": {
                    "description": "The {object_name} emits a loud whine and sparks fly from its casing! The magnetic field feels stronger.",
                    "environmental_effect": {"is_sparking": True, "noise_level": "+2"},
                    "chance_to_progress": 0.4, "next_state": "active_scan_pull",
                    "aggression_influence": {"chance_to_progress_boost": 0.2},
                    "hazard_interaction": {
                        "water_puddle": {"target_state": "electrified", "chance": 0.6, "aggression_influence_on_chance": 0.1, "message":"Sparks from the surging MRI arc into a nearby water puddle!"}
                    }
                },
                "active_scan_pull": {
                    "description": "The {object_name} is fully active, its powerful magnetic field yanking at anything metallic with terrifying force!",
                    "environmental_effect": {"noise_level": "+3"},
                    "autonomous_action": "mri_pull_objects",
                    "instant_death_if_player_has_large_metal": True,
                    "death_message_large_metal": "A large metallic object you're carrying is violently ripped from your grasp and slams into you as it's pulled into the {object_name}!",
                    "room_metal_objects": ["Oxygen Tank", "IV Pole", "Metal Wheelchair", "Steel Equipment Cart"],
                    "room_metal_object_death_chance": 0.7,
                    "room_metal_object_death_message": "The {pulled_object} is suddenly yanked across the room by the powerful magnetic field! It slams into you with devastating force, crushing you against the MRI machine.",
                    "item_pull_damage": 5,
                    "item_pull_message": "{pulled_item_name} is ripped from your grasp and flies into the MRI, striking you on the way!",
                    "chance_to_progress": 0.05, "next_state": "catastrophic_failure",
                    "aggression_influence": {"chance_to_progress_boost": 0.1}
                },
                "catastrophic_failure": {
                    "description": "The {object_name} begins to shake violently, the magnetic coils creating a deafening noise as they overload!",
                    "environmental_effect": {"noise_level": "+4", "visibility":"patchy_smoke"},
                    "autonomous_action": "mri_explosion_countdown",
                    "countdown_turns": 2,
                    "countdown_message": "The MRI machine is going to explode! You need to get out NOW!",
                    "explosion_radius_rooms": 1,
                    "explosion_death_message": "The MRI machine explodes in a catastrophic failure! The blast tears through the room, leaving nothing but destruction in its wake.",
                    "chance_to_progress": 1.0, "next_state": "exploded"
                },
                "exploded": {
                    "description": "What remains of the {object_name} is a smoking, twisted wreck. The explosion has destroyed much of the room.",
                    "environmental_effect": {"noise_level": "0", "visibility":"dense_smoke"}
                },
                "shorted_out": {
                    "description": "With a final pop and a puff of acrid smoke, the {object_name} goes silent. The magnetic field is gone.",
                    "environmental_effect": {"noise_level": "0", "visibility":"normal"}
                },


            # --- NEW MRI QTE SEQUENCE STATES ---
            "mri_qte_sequence_start_and_lock_doors": {
                "description": "The {object_name} ROARS to life with terrifying power! The doors to the Morgue and Stairwell SLAM SHUT and lock with a heavy thud. Sparks fly from the control panel! What? The magnetic force seems to be messing with the locks!",
                "environmental_effect": {"noise_level": "+5", "is_sparking": True, "visibility": "patchy_smoke"},
                "on_state_entry_special_action": "mri_lock_doors_and_initiate_qtes", # GameLogic will handle this
                "chance_to_progress": 1.0, # Immediately progresses to first QTE challenge logic
                "next_state": "mri_qte_challenge_1_button_mash_setup" # Setup state for the first QTE
            },
            "mri_qte_challenge_1_button_mash_setup": {
                "description": "A console near the emergency stop is flickering wildly! You might be able to override the surge if you're fast enough!",
                "autonomous_action": "_trigger_mri_qte_stage", # HazardEngine action to call GameLogic.trigger_qte
                "qte_stage_context": {
                    "qte_type": QTE_TYPE_BUTTON_MASH,
                    "duration": 5.0,
                    "ui_prompt_message": "RAPIDLY HIT THE OVERRIDE! (Mash the button/key shown in popup!)",
                    "expected_input_word": "mash_success", # Internal signal UI will send on success
                    "input_type": "button_mash", # New type for QTEPopup
                    "target_mash_count": 10,
                    "success_message": "You slammed the override! The machine shudders!",
                    "failure_message": "Too slow on the override! The MRI's power fluctuates dangerously!",
                    "hp_damage_on_failure": 3,
                    "is_fatal_on_failure": False,
                    "next_state_after_qte_success": "mri_qte_challenge_2_type_word_setup",
                    "next_state_after_qte_failure": "mri_qte_failure_damage_1" # Go to a damage state
                }
            },
            "mri_qte_challenge_2_type_word_setup": {
                "description": "The main console flashes a critical system alert: 'MANUAL INPUT REQUIRED'. A prompt appears: EMERGENCY SHUNT.",
                "autonomous_action": "_trigger_mri_qte_stage",
                "qte_stage_context": {
                    "qte_type": QTE_TYPE_SEQUENCE_INPUT, # Or just use existing word for one word
                    "duration": 6.0,
                    "ui_prompt_message": "Type 'SHUNT' to reroute power!",
                    "expected_input_word": "shunt", # The word to type
                    "input_type": "word",
                    "success_message": "Power rerouted! The machine groans, still unstable!",
                    "failure_message": "Wrong command! The MRI sparks violently!",
                    "hp_damage_on_failure": 4,
                    "is_fatal_on_failure": False,
                    "next_state_after_qte_success": "mri_qte_challenge_3_sequence_input_setup",
                    "next_state_after_qte_failure": "mri_qte_failure_damage_2"
                }
            },
            "mri_qte_challenge_3_sequence_input_setup": {
                "description": "System override needed! The console displays: 'Initiate Magnetic Field Collapse Sequence: D V P'",
                "autonomous_action": "_trigger_mri_qte_stage",
                "qte_stage_context": {
                    "qte_type": QTE_TYPE_SEQUENCE_INPUT,
                    "duration": 8.0,
                    "ui_prompt_message": "Enter Emergency Sequence: D V P (e.g., type 'DVP')",
                    "expected_input_word": "dvp", # The sequence to type (no spaces for simplicity)
                    "input_type": "word", # QTEPopup handles single word input
                    "success_message": "Sequence Accepted! The magnetic field is destabilizing!",
                    "failure_message": "Incorrect Sequence! Catastrophic overload imminent!",
                    "hp_damage_on_failure": 5,
                    "is_fatal_on_failure": True, # Failure here could be fatal
                    "next_state_after_qte_success": "mri_field_collapsing_qte_success",
                    "next_state_after_qte_failure": "catastrophic_failure" # Leads to explosion
                }
            },
            "mri_qte_failure_damage_1": { # State after failing QTE 1
                "description": "The MRI machine surges, zapping you with raw energy!",
                "on_state_entry_apply_damage": 3, # Handled by HazardEngine
                "chance_to_progress": 1.0,
                "next_state": "mri_qte_challenge_2_type_word_setup" # Player gets another chance but is weaker
            },
             "mri_qte_failure_damage_2": { # State after failing QTE 2
                "description": "Another powerful surge from the MRI rocks the room, and you're thrown against a console!",
                "on_state_entry_apply_damage": 4,
                "chance_to_progress": 1.0,
                "next_state": "mri_qte_challenge_3_sequence_input_setup"
            },
            "mri_field_collapsing_qte_success": {
                "description": "With a deafening screech and a final shower of sparks, the {object_name} groans. The intense magnetic pull lessens, and the room trembles. Smoke pours from the machine. The door locks disengage with a CLUNK!",
                "environmental_effect": {"noise_level": "+1", "is_sparking": False, "visibility": "dense_smoke"},
                "on_state_entry_special_action": "mri_unlock_doors_and_breakdown", # GameLogic will handle this
                "chance_to_progress": 1.0,
                "next_state": "mri_broken_doors_open_qte_path"
            },
            "mri_broken_doors_open_qte_path": {
                "description": "The {object_name} is a smoking, sputtering wreck. The doors to the Morgue and Stairwell are now accessible.",
                "environmental_effect": {"noise_level": "0", "visibility": "dense_smoke"}
            },
            # --- End NEW MRI QTE SEQUENCE ---

            # Existing states like coroner's key pull, metal shower, etc.
            # These might become alternate paths or be partially integrated if desired.
            # For now, the new QTE sequence is a distinct path triggered by "mri_qte_sequence_start_and_lock_doors"
            "coroners_key_qte_initiate_pull": { # ... existing, this could lead to mri_qte_sequence_start_and_lock_doors
                "description": "The {object_name} ROARS to life! The Coroner's Key is ripped from your grasp by an irresistible force, slamming against the machine's housing!",
                "environmental_effect": {"noise_level": "+4", "is_sparking": True},
                "on_state_entry_special_action": "handle_coroners_key_magnetize",
                "chance_to_progress": 1.0,
                "next_state": "mri_qte_sequence_start_and_lock_doors" # <<< MODIFIED to start new sequence
            },
            # qte_metal_shower_stage1,2,3 might be removed if the above sequence replaces it entirely
            # or they could be a different type of MRI malfunction.
            # For clarity, let's assume the new sequence above is the primary one for door locking.

            "catastrophic_failure": { # ... existing ...
                "description": "The {object_name} begins to shake violently, the magnetic coils creating a deafening noise as they overload!",
                "environmental_effect": {"noise_level": "+4", "visibility":"patchy_smoke"},
                "autonomous_action": "_mri_explosion_countdown",
                "countdown_turns": 2,
                "explosion_death_message": "The MRI machine explodes catastrophically! The blast tears through the room, leaving nothing but destruction in its wake.",
                "chance_to_progress": 1.0, "next_state": "exploded"
            },
            "exploded": { # ... existing ...
                "description": "What remains of the {object_name} is a smoking, twisted wreck. The explosion has destroyed much of the room.",
                "environmental_effect": {"noise_level": "0", "visibility":"dense_smoke"}
            },
            "shorted_out": { # General safe state
                "description": "With a final pop and a puff of acrid smoke, the {object_name} goes silent. The magnetic field is gone.",
                "environmental_effect": {"noise_level": "0", "visibility":"normal"}
            },
            # Remove the old door_force_attempt_reaction states if this new sequence replaces that logic.
    
                # --- DOOR FORCE SEQUENCE ---
            "door_force_attempt_reaction": {
                "description": "As you strain against the Morgue door, the {object_name} behind you groans ominously. Lights flicker wildly, and a powerful hum fills the room. Metal objects in the room begin to rattle!",
                "environmental_effect": {"noise_level": "+2", "is_sparking": True},
                "chance_to_progress": 1.0,
                "next_state": "qte_metal_shower_1",
                "instant_hp_damage": 0
            },
            "qte_metal_shower_1": {
                "description": "Suddenly, a tray of scalpels and clamps rips from a nearby cart and flies towards your head!",
                "autonomous_action": "_mri_qte_projectile_action",
                "qte_projectile_name": "a tray of sharp medical instruments",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 3.0,
                "damage_on_qte_fail": 4,
                "next_state_after_qte": "qte_metal_shower_2",
                "environmental_effect": {"noise_level": "+3"}
            },
            "qte_metal_shower_2": {
                "description": "Before you can recover, a heavy oxygen tank tears loose from the wall, tumbling erratically towards you!",
                "autonomous_action": "_mri_qte_projectile_action",
                "qte_projectile_name": "a heavy oxygen tank",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 2.5,
                "damage_on_qte_fail": 6,
                "next_state_after_qte": "qte_metal_shower_3",
                "environmental_effect": {"noise_level": "+4"}
            },
            "qte_metal_shower_3": {
                "description": "The {object_name} shrieks! An entire metal gurney careens across the room, aimed straight for you!",
                "autonomous_action": "_mri_qte_projectile_action",
                "qte_projectile_name": "a metal gurney",
                "qte_type": QTE_TYPE_DODGE_PROJECTILE,
                "qte_duration": 2.0,
                "damage_on_qte_fail": 10,
                "next_state_after_qte": "mri_field_collapsing_after_force",
                "environmental_effect": {"noise_level": "+5", "visibility": "patchy_smoke"}
            },
            "mri_field_collapsing_after_force": {
                "description": "With a final, violent shudder and a shower of sparks, the {object_name} groans and the intense magnetic pull lessens. The air crackles, and then... an eerie quiet. Smoke pours from the machine.",
                "environmental_effect": {"noise_level": "+1", "is_sparking": False, "visibility": "dense_smoke"},
                "chance_to_progress": 1.0,
                "next_state": "mri_broken_door_open",
                "on_state_entry_unlock_room": "Morgue"
            },
            "mri_broken_door_open": {
                "description": "The {object_name} is a smoking, sputtering wreck. The Morgue door, perhaps damaged by the chaos or the strain, now stands slightly ajar.",
                "environmental_effect": {"noise_level": "0", "visibility": "dense_smoke"}
                }
            }
        },
    "leaking_pipe": {
        "name": "Leaking Pipe",
        "initial_state": "dripping",
        "placement_object": ["exposed pipes", "sink drain", "radiator", "water heater"],
        "object_name_options": ["leaking pipe", "water drip", "pipe leak"],
        "player_interaction": {
            "examine": {
                "chance_to_trigger": 0.0,
                "message": "You see a {object_name} near the {support_object}."
            },
            "repair": {
                "chance_to_trigger": 0.2,
                "target_state": "fixed",
                "message": "You manage to temporarily stop the {object_name}."
            }
        },
        "states": {
            "dripping": {
                "description": "There's a {object_name} near the {support_object}, slowly dripping water.",
                "chance_to_progress": 0.2,
                "next_state": "flowing",
                "environmental_effect": {
                    "is_wet": True
                },
                "triggers_hazard_on_state_change": [{
                    "type": "water_puddle",
                    "probability": 0.8
                }]
            },
            "flowing": {
                "description": "The {object_name} at the {support_object} is flowing steadily now, creating a puddle.",
                "chance_to_progress": 0.1,
                "next_state": "burst",
                "environmental_effect": {
                    "is_wet": True
                },
                "triggers_hazard_on_state_change": [{
                    "type": "water_puddle",
                    "probability": 1.0
                }]
            },
            "burst": {
                "description": "The {object_name} has burst, spraying water everywhere around the {support_object}!",
                "environmental_effect": {
                    "is_wet": True,
                    "visibility": "reduced"
                },
                "triggers_hazard_on_state_change": [{
                    "type": "water_puddle",
                    "probability": 1.0
                }],
                "status_effect": {
                    "name": "soaked",
                    "duration": 3
                }
            },
            "fixed": {
                "description": "The {object_name} at the {support_object} has been temporarily fixed, though it might start leaking again."
            }
        }
    },
    "spreading_fire": {
        "name": "Spreading Fire",
        "states": {
            "smoldering": {
                "description": "The {object_name} is smoldering, wisps of smoke curling upwards.",
                "environmental_effect": {"visibility": "hazy", "temperature": "+1"},
                "chance_to_progress": 0.3,
                "next_state": "burning_low",
                "aggression_influence": {"chance_to_progress": 0.1}
            },
            "burning_low": {
                "description": "Small flames lick at the {object_name}, growing steadily.",
                "environmental_effect": {"is_on_fire": True, "visibility": "smoky", "temperature": "+2", "noise_level": "+1"},
                "chance_to_progress": 0.4,
                "next_state": "burning_high",
                "spreads_to_adjacent_combustible": True, # Can spread to nearby furniture/objects
                "aggression_influence": {"chance_to_progress": 0.15, "spread_effectiveness": 1.3}
            },
            "burning_high": {
                "description": "The {object_name} is now engulfed in roaring flames! The heat is intense.",
                "environmental_effect": {"is_on_fire": True, "visibility": "very_smoky", "temperature": "+3", "noise_level": "+2"},
                "instant_death_on_entry": True, # If player enters room with this
                "death_message": "You are instantly consumed by the inferno!",
                "spreads_to_adjacent_combustible": True,
                "spreads_to_adjacent_room_chance": 0.1, # Chance to spread to next room via open exit
                "aggression_influence": {"spread_to_room_chance": 0.05}
            },
            "burnt_out": {
                "description": "Only charred remains of the {object_name} are left. The air is thick with smoke.",
                "environmental_effect": {"is_on_fire": False, "visibility": "very_smoky", "temperature": "+1"}
            }
        },
        "initial_state": "smoldering",
        "placement_object": ["trash can", "tattered sofa", "stack of old boxes", "curtains"], # Combustible items
        "can_spread": True, # The fire itself can spread
        "vulnerable_to": ["water_puddle_large", "fire_extinguisher_item"], # What can put it out
        "affected_by": {
            "water_puddle_large": {"target_state": "burnt_out", "message": "The water douses the flames."},
            "use_item_fire_extinguisher": {"target_state": "burnt_out", "message": "You manage to extinguish the fire!"}
        },
        "autonomous_decay_to_burnt_out": {"chance": 0.05} # Chance to burn out on its own if not spreading
    },
    "short_circuiting_appliance": { # Copied from previous response, fits well
        "name": "Short-Circuiting Appliance",
        "initial_state": "off",
        "placement_object": ["old_radio", "table_lamp", "ancient_television", "kitchen_mixer", "electric_heater", "window_ac_unit", "computer_monitor"],
        "object_name_options": ["old radio", "table lamp", "ancient television", "kitchen mixer", "electric heater", "window AC unit", "CRT computer monitor"],
        "player_interaction": {
            "examine": {
                "chance_to_reveal": 0.3, "target_state": "flickering", "aggression_modifier": 0.1,
                "message": "The {object_name} looks old and dusty. You notice its power cord is frayed."
            },
            "use": { # Player tries to turn it on
                "chance_to_trigger": 0.4, "target_state": "malfunctioning", "aggression_modifier": 0.2,
                "message": "You try to use the {object_name}. It sputters and sparks ominously!"
            }
        },
        "affected_by": {
            "water_puddle_contact": {"target_state": "broken_electrified", "chance": 0.7, "aggression_modifier": 0.1},
            "power_surge_event": {"target_state": "malfunctioning", "chance": 0.5, "aggression_modifier": 0.15} # External event
        },
        "states": {
            "off": {
                "description": "An {object_name} sits innocuously on the {support_object}.",
                "chance_to_progress": 0.02, "next_state": "flickering", "aggression_influence": {"chance_to_progress_boost": 0.05}
            },
            "flickering": {
                "description": "The {object_name} on the {support_object} flickers erratically, making a faint buzzing sound.",
                "environmental_effect": {"noise_level": "+0"},
                "chance_to_progress": 0.2, "next_state": "malfunctioning", "aggression_influence": {"chance_to_progress_boost": 0.15}
            },
            "malfunctioning": {
                "description": "The {object_name} on the {support_object} is smoking and sparking violently, letting out loud crackles!",
                "environmental_effect": {"is_sparking": True, "noise_level": "+1", "visibility": "patchy_smoke"},
                "contact_status_effect": {"name": "stunned", "duration": 1, "hp_damage": 2},
                "hazard_interaction": {
                    "gas_leak": {"target_state": "ignited", "chance": 0.6, "aggression_influence_on_chance": 0.2},
                    "water_puddle": {"target_state": "electrified", "chance": 0.7, "aggression_influence_on_chance": 0.15}
                },
                "chance_to_progress": 0.15, "next_state": "burst_into_flames", "aggression_influence": {"chance_to_progress_boost": 0.2},
                "chance_to_revert": 0.05, "revert_state": "flickering", "aggression_influence": {"revert_chance_multiplier": 0.3}
            },
            "burst_into_flames": {
                "description": "The malfunctioning {object_name} on the {support_object} suddenly bursts into aggressive flames!",
                "environmental_effect": {"is_on_fire": True, "is_sparking": False, "noise_level": "+2"},
                "instant_death_if_too_close": True, # HazardEngine handles proximity
                "death_message": "You're caught in the sudden inferno as the {object_name} explodes in fire!",
                "triggers_hazard_on_state_change": [
                    {"type": "spreading_fire", "target_object": "{object_name}", "initial_state": "burning_high", "chance": 1.0}
                ],
                "chance_to_progress": 1.0, "next_state": "burnt_out_hulk"
            },
            "broken_electrified": {
                "description": "The {object_name} on the {support_object} is a sizzling, sparking mess, surrounded by electrified water.",
                "environmental_effect": {"is_sparking": True, "is_wet": True, "noise_level": "+1"},
                "instant_death_on_contact_with_appliance_or_water": True,
                "death_message": "You make contact with the electrified {object_name} or the charged water around it. The shock is instantly fatal.",
                "creates_hazard_on_floor": {"type": "water_puddle", "initial_state": "electrified", "target_object": "{support_object}"}
            },
            "burnt_out_hulk": {
                "description": "The {object_name} on the {support_object} is now a blackened, melted husk."
                }
            }
        }
    }

    # Other existing hazards like leaking_pipe, short_circuiting_appliance, precarious_object, loose_object should be reviewed
    # to ensure their definitions are robust and don't implicitly assume a single level.



# --- Initial Environmental Conditions for Rooms ---

initial_environmental_conditions = {
    "gas_level": 0,      # 0: none, 1: noticeable, 2: heavy, 3: explosive
    "is_wet": False,     # For electrical hazards, slipping
    "is_on_fire": False, # If the room itself is on fire
    "is_sparking": False, # If there are active electrical sparks in the room (not just an object)
    "noise_level": 0,    # 0: silent, 1: quiet, 2: noisy, 3: very loud
    "visibility": "normal" # normal, dim, dark, very_dark, patchy_smoke, dense_smoke
}

# --- Status Effect Definitions ---
status_effects_definitions = {
    "bleeding": {"duration": 3, "hp_change_per_turn": -1, "message_on_tick": "You are bleeding steadily.", "message_on_wear_off": "The bleeding has stopped."},
    "poisoned": {"duration": 4, "hp_change_per_turn": -1, "message_on_tick": "You feel a wave of nausea from the poison.", "message_on_wear_off": "The poison seems to have run its course."},
    "stunned": {"duration": 1, "prevents_action": True, "message_on_tick": "You are stunned and can't act!", "message_on_wear_off": "You shake off the daze."},
    "dizzy": {"duration": 2, "effects": {"action_failure_chance": 0.3}, "message_on_tick": "You feel dizzy and unsteady.", "message_on_wear_off": "Your head clears."},
    "burned": {"duration": 2, "hp_change_per_turn": -2, "message_on_tick": "Your burns sear with pain.", "message_on_wear_off": "The worst of the burn pain subsides."},
    "stumbled": {"duration": 1, "prevents_action": False, "message_on_tick": "You quickly regain your footing.", "message_on_wear_off": ""} # Short, minor effect
}


# --- Initial Item Placement Logic (Helper functions, may be moved to GameLogic or a LevelManager later) ---
# This section is a bit more complex and tightly coupled with global modification.
# For a refactor, this logic would ideally be managed by GameLogic or a dedicated LevelLoader,
# operating on level-specific data.
# For now, these are stubs to indicate where this logic existed.
# The actual implementation will be in GameLogic which will take filtered data.

def _get_available_container_slots(target_rooms_data, target_items_data):
    """
    Helper to get all available 'slots' in containers within specified rooms.
    A slot is a tuple: (room_name, furniture_name, item_name_if_already_there_or_None).
    
    Args:
        target_rooms_data (dict): Dictionary of room data keyed by room name
        target_items_data (dict): Dictionary of item data keyed by item name
        
    Returns:
        list: List of tuples representing available container slots
    """
    logging.debug("Getting available container slots for placement...")
    slots = []
    
    # Create a mapping of items to their containers and rooms
    items_by_location = {}
    for item_name, item_data in target_items_data.items():
        if "container" in item_data and item_data["container"]:
            room = item_data.get("location")
            container = item_data.get("container")
            if room and container:
                if (room, container) not in items_by_location:
                    items_by_location[(room, container)] = []
                items_by_location[(room, container)].append(item_name)
    
    # Process each room and find containers
    for room_name, room_data in target_rooms_data.items():
        # Check if the room has furniture
        if "furniture" in room_data:
            for furniture in room_data["furniture"]:
                if furniture.get("container", False):
                    furniture_name = furniture["name"]
                    
                    # Skip locked containers unless specifically needed
                    if furniture.get("locked", False):
                        continue
                    
                    # Check how many items are already in this container
                    items_in_container = items_by_location.get((room_name, furniture_name), [])
                    
                    # Determine capacity - default to 1 for small containers, more for large ones
                    capacity = 1
                    if "large" in furniture_name.lower() or "chest" in furniture_name.lower():
                        capacity = 3
                    elif "cabinet" in furniture_name.lower() or "shelf" in furniture_name.lower():
                        capacity = 2
                        
                    # Add empty slots
                    empty_slots_to_add = capacity - len(items_in_container)
                    for _ in range(max(0, empty_slots_to_add)):
                        slots.append((room_name, furniture_name, None))
                    
                    # Also include slots with items, as they might be relevant for some operations
                    for item_name in items_in_container:
                        slots.append((room_name, furniture_name, item_name))
    
    random.shuffle(slots)  # Randomize the order to avoid predictable placements
    logging.debug(f"Found {len(slots)} total container slots across {len(target_rooms_data)} rooms")
    return slots

def _place_dynamic_items(item_names_to_place, available_slots, all_items_dict, rooms_dict, item_type_for_log="Item"):
    """
    Helper to place a list of items into available container slots.
    Modifies all_items_dict with location and container.
    
    Args:
        item_names_to_place (list): List of item names to place in containers
        available_slots (list): List of slots (room_name, furniture_name, item_name_or_None)
        all_items_dict (dict): Dictionary of all items to modify
        rooms_dict (dict): Dictionary of rooms data
        item_type_for_log (str): Type of item for logging purposes
        
    Returns:
        int: Number of items successfully placed
    """
    if not item_names_to_place or not available_slots:
        logging.warning(f"No {item_type_for_log}s to place or no available slots")
        return 0
    
    # Filter to only empty slots
    empty_slots = [slot for slot in available_slots if slot[2] is None]
    
    if not empty_slots:
        logging.warning(f"No empty slots available for {item_type_for_log} placement")
        return 0
        
    items_to_place = item_names_to_place.copy()
    random.shuffle(items_to_place)  # Randomize placement order
    
    placed_count = 0
    
    # Try to place items in available slots
    for item_name in items_to_place:
        if not empty_slots:
            logging.warning(f"Ran out of empty slots while placing {item_type_for_log}s")
            break
            
        # Get the next available slot
        slot = empty_slots.pop(0)
        room_name, furniture_name, _ = slot
        
        if item_name not in all_items_dict:
            logging.warning(f"Item '{item_name}' not found in items dictionary")
            continue
            
        # Update the item's location and container
        all_items_dict[item_name]["location"] = room_name
        all_items_dict[item_name]["container"] = furniture_name
        all_items_dict[item_name]["hidden"] = True  # Hidden until container is searched
        
        placed_count += 1
        logging.info(f"Placed {item_type_for_log} '{item_name}' in {furniture_name} in {room_name}")
            
    logging.info(f"Successfully placed {placed_count}/{len(item_names_to_place)} {item_type_for_log}s")
    return placed_count

def get_initial_player_state(character_class="Journalist"):
    """Return a fresh player state dict for the given character class."""
    stats = CHARACTER_CLASSES.get(character_class, CHARACTER_CLASSES["Journalist"])
    return {
        "location": LEVEL_REQUIREMENTS[1]["entry_room"],
        "inventory": [],
        "hp": stats["max_hp"],
        "max_hp": stats["max_hp"],
        "perception": stats["perception"],
        "intuition": stats["intuition"],
        "status_effects": {},
        "score": 0,
        "turns_left": STARTING_TURNS,
        "actions_taken": 0,
        "visited_rooms": {LEVEL_REQUIREMENTS[1]["entry_room"]},
        "current_level": 1,
        "qte_active": None,
        "qte_duration": 0,
        "last_hazard_type": None,
        "last_hazard_object_name": None,
        "character_class": character_class
    }

def initialize_dynamic_game_elements_globally(rooms_global, items_global, evidence_global, keys_global):
    """
    This global initializer will be replaced by GameLogic._initialize_level_data(level_id).
    It's kept here as a reference to the original logic.
    
    If you need to initialize game elements, please use:
    - game_logic._initialize_level_data(level_id)
    - game_logic._place_dynamic_elements_for_level(level_id)
    
    Args:
        rooms_global (dict): Dictionary of all rooms
        items_global (dict): Dictionary of all items
        evidence_global (dict): Dictionary of all evidence items
        keys_global (dict): Dictionary of all keys
    """
    logging.warning("DEPRECATED: initialize_dynamic_game_elements_globally should no longer be called directly. Logic moved to GameLogic._initialize_level_data.")
    
    # For backward compatibility: show how the function used to work
    logging.debug("Original functionality: This would have collected all containers, assigned items to slots")
    logging.debug("Original functionality: It would distribute regular items, evidence items, and keys")
    
    # If somehow this is still being called by old code, we'll give basic functionality
    # by delegating to the appropriate methods in GameLogic
    from game_logic import GameLogic
    import inspect
    
    # Find what called this function
    caller_frame = inspect.currentframe().f_back
    caller_info = inspect.getframeinfo(caller_frame)
    logging.warning(f"Called from {caller_info.filename}:{caller_info.lineno}")
    
    logging.info("For reference, initialize_dynamic_game_elements_globally is a legacy method.")
    logging.info("Use GameLogic._initialize_level_data(level_id) instead.")
    
    return
# --- Disaster Intro Elements (Can remain global as it's for game start) ---
