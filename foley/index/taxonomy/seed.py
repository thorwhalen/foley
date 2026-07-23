"""Seed taxonomy data — a representative in-code UCS subset + AudioSet overlap map.

This is the OPEN/CLOSED seam (report 04 §5.3, [11 §3.1]): a small hand-curated
seed lives here in code; the FULL UCS master (82 categories / ~750 subcategories)
and the EnvSound-UCS AudioSet->UCS / FSD50K->UCS tables drop in later as JSON
under ``taxonomy/data/`` and are merged OVER this seed with zero logic change.

Confidence: only ``WEATHRain`` and ``DOORWood`` are treated as authoritative CatIDs;
every other row carries ``confident=False`` (**APPROXIMATE — verify against the UCS
master before shipping as authoritative**). The seed is deliberately partial; it is
NOT the 750-row master.
"""

#: Representative UCS seed. Each row: catid, category, subcategory, synonyms
#: (lowercased), confident. ``confident=False`` => APPROXIMATE CatID.
SEED_UCS_TABLE: list[dict] = [
    # --- DOORS ---
    {
        "catid": "DOORWood",
        "category": "DOORS",
        "subcategory": "Wood",
        "synonyms": [
            "wooden door",
            "oak door",
            "door creak",
            "door open",
            "door close",
            "door slam",
        ],
        "confident": True,
    },
    {
        "catid": "DOORMetal",
        "category": "DOORS",
        "subcategory": "Metal",
        "synonyms": ["metal door", "steel door", "hatch", "cell door"],
        "confident": False,
    },
    {
        "catid": "DOORKnob",
        "category": "DOORS",
        "subcategory": "Knob",
        "synonyms": ["doorknob", "door handle", "latch", "handle turn"],
        "confident": False,
    },
    # --- WEATHER ---
    {
        "catid": "WEATHRain",
        "category": "WEATHER",
        "subcategory": "Rain",
        "synonyms": [
            "rain",
            "rainfall",
            "raining",
            "rain on window",
            "downpour",
            "drizzle",
        ],
        "confident": True,
    },
    {
        "catid": "WEATHWind",
        "category": "WEATHER",
        "subcategory": "Wind",
        "synonyms": ["wind", "gust", "breeze", "howling wind", "windy"],
        "confident": False,
    },
    {
        "catid": "WEATHThunder",
        "category": "WEATHER",
        "subcategory": "Thunder",
        "synonyms": [
            "thunder",
            "thunderclap",
            "thunderstorm",
            "thunder crack",
            "rumble",
        ],
        "confident": False,
    },
    # --- FOOTSTEPS ---
    {
        "catid": "FOOTWood",
        "category": "FOOTSTEPS",
        "subcategory": "Wood",
        "synonyms": ["footsteps wood", "walking wood floor", "footfall wood"],
        "confident": False,
    },
    {
        "catid": "FOOTConc",
        "category": "FOOTSTEPS",
        "subcategory": "Concrete",
        "synonyms": ["footsteps concrete", "walking pavement", "footsteps sidewalk"],
        "confident": False,
    },
    {
        "catid": "FOOTGravel",
        "category": "FOOTSTEPS",
        "subcategory": "Gravel",
        "synonyms": ["footsteps gravel", "walking gravel", "crunch gravel"],
        "confident": False,
    },
    # --- IMPACTS / DESTRUCTION / GLASS ---
    {
        "catid": "IMPTGeneral",
        "category": "IMPACTS",
        "subcategory": "General",
        "synonyms": ["impact", "hit", "thud", "bang", "smash", "crash"],
        "confident": False,
    },
    {
        "catid": "DESTGeneral",
        "category": "DESTRUCTION",
        "subcategory": "General",
        "synonyms": ["destruction", "collapse", "debris", "rubble", "demolition"],
        "confident": False,
    },
    {
        "catid": "GLASBreak",
        "category": "GLASS",
        "subcategory": "Break",
        "synonyms": [
            "glass break",
            "glass shatter",
            "shattering glass",
            "broken glass",
        ],
        "confident": False,
    },
    # --- WATER / LIQUID ---
    {
        "catid": "WATRRun",
        "category": "WATER",
        "subcategory": "Running",
        "synonyms": ["running water", "stream", "faucet", "tap water", "flowing water"],
        "confident": False,
    },
    {
        "catid": "WATRSplash",
        "category": "WATER",
        "subcategory": "Splash",
        "synonyms": ["splash", "splashing", "water splash", "plop"],
        "confident": False,
    },
    {
        "catid": "LIQDPour",
        "category": "LIQUID",
        "subcategory": "Pour",
        "synonyms": ["pour", "pouring", "glug", "liquid pour"],
        "confident": False,
    },
    # --- FIRE ---
    {
        "catid": "FIREGeneral",
        "category": "FIRE",
        "subcategory": "General",
        "synonyms": ["fire", "flames", "campfire", "crackling fire", "burning"],
        "confident": False,
    },
    {
        "catid": "FIREWhoosh",
        "category": "FIRE",
        "subcategory": "Whoosh",
        "synonyms": ["fire whoosh", "flame burst", "fireball", "ignite whoosh"],
        "confident": False,
    },
    # --- VEHICLES ---
    {
        "catid": "VEHCarInt",
        "category": "VEHICLES",
        "subcategory": "Car Interior",
        "synonyms": ["car interior", "in car", "car cabin"],
        "confident": False,
    },
    {
        "catid": "VEHCarExt",
        "category": "VEHICLES",
        "subcategory": "Car Exterior",
        "synonyms": ["car pass by", "car exterior", "car drive by", "engine car"],
        "confident": False,
    },
    {
        "catid": "VEHHorn",
        "category": "VEHICLES",
        "subcategory": "Horn",
        "synonyms": ["car horn", "honk", "vehicle horn", "beep horn"],
        "confident": False,
    },
    # --- AMBIENCE ---
    {
        "catid": "AMBUrban",
        "category": "AMBIENCE",
        "subcategory": "Urban",
        "synonyms": [
            "city ambience",
            "street ambience",
            "urban background",
            "traffic ambience",
        ],
        "confident": False,
    },
    {
        "catid": "AMBNature",
        "category": "AMBIENCE",
        "subcategory": "Nature",
        "synonyms": [
            "nature ambience",
            "forest ambience",
            "outdoor ambience",
            "birdsong bed",
        ],
        "confident": False,
    },
    {
        "catid": "AMBRoom",
        "category": "AMBIENCE",
        "subcategory": "Room Tone",
        "synonyms": ["room tone", "roomtone", "interior ambience", "quiet room"],
        "confident": False,
    },
    # --- USER INTERFACE / DESIGNED ---
    {
        "catid": "GUIBeep",
        "category": "USER INTERFACE",
        "subcategory": "Beep",
        "synonyms": ["ui beep", "button", "menu click", "notification", "ui blip"],
        "confident": False,
    },
    {
        "catid": "GUIWhoosh",
        "category": "USER INTERFACE",
        "subcategory": "Whoosh",
        "synonyms": ["ui whoosh", "swipe", "ui swipe", "transition whoosh"],
        "confident": False,
    },
    # --- ANIMALS ---
    {
        "catid": "ANMLDog",
        "category": "ANIMALS",
        "subcategory": "Dog",
        "synonyms": ["dog", "bark", "dog bark", "growl", "whine dog"],
        "confident": False,
    },
    {
        "catid": "ANMLCat",
        "category": "ANIMALS",
        "subcategory": "Cat",
        "synonyms": ["cat", "meow", "purr", "cat meow"],
        "confident": False,
    },
    {
        "catid": "ANMLBird",
        "category": "ANIMALS",
        "subcategory": "Bird",
        "synonyms": ["bird", "birdsong", "chirp", "tweet", "bird call"],
        "confident": False,
    },
    # --- GUNS / EXPLOSIONS ---
    {
        "catid": "GUNHandgun",
        "category": "GUNS",
        "subcategory": "Handgun",
        "synonyms": ["gunshot", "pistol", "handgun", "gun fire", "shot"],
        "confident": False,
    },
    {
        "catid": "EXPLGeneral",
        "category": "EXPLOSIONS",
        "subcategory": "General",
        "synonyms": ["explosion", "blast", "boom", "detonation", "explode"],
        "confident": False,
    },
    # --- CLOTH / PAPER (foley materials) ---
    {
        "catid": "CLOTHMove",
        "category": "CLOTH",
        "subcategory": "Movement",
        "synonyms": [
            "cloth",
            "cloth movement",
            "fabric",
            "clothing rustle",
            "cloth rustle",
        ],
        "confident": False,
    },
    {
        "catid": "PAPRHandle",
        "category": "PAPER",
        "subcategory": "Handling",
        "synonyms": ["paper", "paper rustle", "page turn", "paper crumple"],
        "confident": False,
    },
    # --- MACHINE / ELECTRICITY / COMMS ---
    {
        "catid": "MACHGeneral",
        "category": "MACHINES",
        "subcategory": "General",
        "synonyms": ["machine", "motor", "mechanism", "machinery", "servo"],
        "confident": False,
    },
    {
        "catid": "ELECBuzz",
        "category": "ELECTRICITY",
        "subcategory": "Buzz",
        "synonyms": ["electric buzz", "spark", "zap", "electricity", "arc"],
        "confident": False,
    },
    {
        "catid": "COMMPhone",
        "category": "COMMUNICATIONS",
        "subcategory": "Phone",
        "synonyms": ["phone ring", "telephone", "ringtone", "cell phone", "dial tone"],
        "confident": False,
    },
]


#: AudioSet label NAME (lowercased) -> UCS CatID. ``mid`` is best-effort (verify
#: against ``audioset/ontology.json`` before trusting). Every ``catid`` here MUST
#: exist in :data:`SEED_UCS_TABLE` — :func:`~foley.index.taxonomy.audioset.load_audioset_ucs_map`
#: asserts this at load time.
SEED_AUDIOSET_UCS_MAP: list[dict] = [
    {"name": "door", "catid": "DOORWood", "mid": "/m/02dgv"},
    {"name": "sliding door", "catid": "DOORMetal", "mid": "/m/02y_763"},
    # NB: 'doorbell' intentionally omitted — the seed has no bell/chime/alert
    # category, and COMMUNICATIONS/Phone (telephony) is a wrong target. Leaving it
    # unresolved is better than mis-filing; add a proper bell CatID with the full
    # UCS drop, then map it here.
    {"name": "rain", "catid": "WEATHRain", "mid": "/m/06mb1"},
    {"name": "raindrop", "catid": "WEATHRain", "mid": "/m/07r10fb"},
    {"name": "thunder", "catid": "WEATHThunder", "mid": "/m/0ngt1"},
    {"name": "thunderstorm", "catid": "WEATHThunder", "mid": "/m/0jb2l"},
    {"name": "wind", "catid": "WEATHWind", "mid": "/m/03m9d0z"},
    {"name": "walk, footsteps", "catid": "FOOTConc", "mid": "/m/07qann"},
    {"name": "fire", "catid": "FIREGeneral", "mid": "/m/0jbk"},
    {"name": "crackle", "catid": "FIREGeneral", "mid": "/m/07pc8k4"},
    {"name": "water", "catid": "WATRRun", "mid": "/m/0838f"},
    {"name": "splash, splatter", "catid": "WATRSplash", "mid": "/m/07qlwh6"},
    {"name": "pour", "catid": "LIQDPour", "mid": "/m/07q0yl5"},
    {"name": "glass", "catid": "GLASBreak", "mid": "/m/039jq"},
    {"name": "shatter", "catid": "GLASBreak", "mid": "/m/07rjwbb"},
    {"name": "explosion", "catid": "EXPLGeneral", "mid": "/m/014zdl"},
    {"name": "gunshot, gunfire", "catid": "GUNHandgun", "mid": "/m/032s66"},
    {"name": "vehicle", "catid": "VEHCarExt", "mid": "/m/07yv9"},
    {"name": "car", "catid": "VEHCarExt", "mid": "/m/0k4j"},
    {"name": "vehicle horn, honk", "catid": "VEHHorn", "mid": "/m/0912c9"},
    {"name": "dog", "catid": "ANMLDog", "mid": "/m/0bt9lr"},
    {"name": "bark", "catid": "ANMLDog", "mid": "/m/05tny_"},
    {"name": "cat", "catid": "ANMLCat", "mid": "/m/01yrx"},
    {"name": "bird", "catid": "ANMLBird", "mid": "/m/015p6"},
    {"name": "telephone", "catid": "COMMPhone", "mid": "/m/07cx4"},
]
