import sys

from discord import Embed, Activity, ActivityType
from discord.ext import commands

import settings
from providers import PROVIDERS


bot = commands.Bot(
    command_prefix = settings.PREFIX,
    description = "A bot built for chemistry and harm reduction."
)


@bot.command(name='info', aliases=('psycho', 'psychotropic'))
async def info(ctx):
    """Display various informations about the bot."""
    embed = Embed(
        type = 'rich',
        colour = settings.COLOUR,
        title = "Psychotropic",
    )
    embed.set_image(url=settings.AVATAR_URL)
    embed.add_field(
        name = "Help",
        value = "Type >help to display help page."
    )
    embed.add_field(
        name = "Data providers",
        value = '\n'.join([
            "{name} ({url})".format(**provider)
            for provider in PROVIDERS.values()
        ])
    )
    embed.set_footer(
        text = "Psychotropic was carefully trained by xyzt_",
        icon_url = settings.AUTHOR_URL
    )
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id}).")
    await bot.change_presence(activity=Activity(
        type = ActivityType.listening,
        name = "Sister Morphine"
    ))


if __name__ == '__main__':
    for extension in settings.EXTENSIONS:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print(f"Failed to load extension {extension}.")
            print(sys.exc_info())

    bot.run(settings.DISCORD_TOKEN)
