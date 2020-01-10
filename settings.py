from discord import Colour
from os import getenv


EXTENSIONS = [
    'cogs.factsheets'
]

COLOUR = Colour.from_rgb(86, 126, 255)

AVATAR_URL = "https://cdn.discordapp.com/avatars/665177975053877259/0532c68773e3b586d503498a6a670f7b.png?size=512"

AUTHOR_URL = "https://cdn.discordapp.com/avatars/663909261688176661/e27879e77a73620846530e54a7cf4aac.png?size=256"

DISCORD_TOKEN = getenv('DISCORD_TOKEN')


try:
    from localsettings import *
    print("Local settings module found, overriding production settings.")
except ImportError:
    print("Using production settings.")
