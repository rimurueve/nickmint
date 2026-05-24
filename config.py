import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "8330904314"))
WEBAPP_URL: str = os.getenv("WEBAPP_URL", "https://your-project.onrender.com")
DATABASE_URL: str = os.getenv("DATABASE_URL", "nickmint.db")

# Slot configuration
BASE_SLOTS: int = 50
MAX_SLOTS: int = 100
STARS_PER_PACK: int = 10
SLOTS_PER_PACK: int = 5

# Username generation
USERNAME_ADJECTIVES = [
    "cool", "dark", "fast", "gold", "iron", "mega", "nano", "neon",
    "nova", "pixel", "pro", "sky", "slim", "snap", "star", "sync",
    "tech", "turbo", "ultra", "void", "wave", "zero", "apex", "byte",
    "chip", "core", "data", "echo", "flux", "gear", "hack", "hyper",
    "ion", "jade", "keen", "live", "mode", "myth", "node", "onyx",
    "peak", "qbit", "rare", "sage", "true", "unit", "vibe", "wild",
]

USERNAME_NOUNS = [
    "ace", "arc", "arm", "art", "ash", "axe", "bay", "bit", "box",
    "bug", "cat", "cod", "cog", "cop", "cow", "cry", "cub", "dag",
    "dam", "den", "dex", "dig", "dim", "dip", "dot", "dub", "elf",
    "elk", "eve", "eye", "fan", "far", "fat", "fin", "fit", "fix",
    "fly", "fog", "fox", "fun", "gap", "gem", "god", "guy", "gym",
]
