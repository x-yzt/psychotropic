import logging
import os
from pathlib import Path

from discord import Colour, Object


log = logging.getLogger(__name__)


# General

EXTENSIONS = [
    'psychotropic.cogs.admin',
    'psychotropic.cogs.factsheets',
    'psychotropic.cogs.science',
    'psychotropic.cogs.games',
    'psychotropic.cogs.games.structure',
    'psychotropic.cogs.games.reagents',
    'psychotropic.cogs.combos',
]

BASE_DIR = Path(__file__).parent

STORAGE_DIR = Path('storage')

PREFIX = '>'

HTTP_COOLDOWN = .2  # Delay between HTTP requests in seconds

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

TEST_GUILD = Object(id=353885439331008512)

SYNC_GLOBAL_TREE = True  # Only sync to test guild otherwise


# Cosmetics

COLOUR = Colour.from_rgb(86, 126, 255)

AVATAR_URL = "https://cdn.discordapp.com/avatars/665177975053877259/0532c68773e3b586d503498a6a670f7b.png?size=512"

AUTHOR_AVATAR_URL = "https://avatars.githubusercontent.com/u/62727704"


# Science cog

COMPOUNDS_DESCRIPTION_PROVIDERS = (
    "NCI Thesaurus",
    "CAMEO Chemicals",
)


# Games cog

LEVELS = (
    {
        'threshold': 0,
        'name': "Beginner 🧑‍🎓",
        'color': COLOUR,
    },
    {
        'threshold': 420,
        'name': "420 chemist 🥽",
        'color': Colour(0x00FFFF),
    },
    {
        'threshold': 1_000,
        'name': "1k chemist 🧪",
        'color': Colour(0x7CFC00),
    },
    {
        'threshold': 5_000,
        'name': "5k chemist 🧬",
        'color': Colour(0xFFC107),
    },
    {
        'threshold': 10_000,
        'name': "10k chemist 🧑‍🔬",
        'color': Colour(0x001F3F),
    },
    {
        'threshold': 20_000,
        'name': "Walter White 👑",
        'color': Colour(0xFF0000),
    },
)


# Structure game cog

FETCH_SCHEMATICS = True  # Fetch schematics from PNWiki on each bot start


# Entries to be excluded from the DSSTox results.
# This is matched against the `model_name` field DSSTox provides.
DSSTOX_EXCLUDED_MODELS = (
    'ACD_Sol',
)


try:
    from psychotropic.localsettings import *
    log.info("Local settings module found, overriding production settings.")
except ImportError:
    log.info("Using production settings.")
