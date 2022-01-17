import logging
import os

from discord import Colour


log = logging.getLogger(__name__)


# General

EXTENSIONS = [
    'psychotropic.cogs.factsheets',
    'psychotropic.cogs.science'
]

PREFIX = '>'

HTTP_COOLDOWN = .2 # Delay between HTTP requests in seconds

COLOUR = Colour.from_rgb(86, 126, 255)

AVATAR_URL = "https://cdn.discordapp.com/avatars/665177975053877259/0532c68773e3b586d503498a6a670f7b.png?size=512"

AUTHOR_URL = "https://avatars.githubusercontent.com/u/62727704"

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')


# Science cog

COMPOUNDS_DESCRIPTION_PROVIDERS = (
    "NCI Thesaurus",
    "CAMEO Chemicals"
)

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
