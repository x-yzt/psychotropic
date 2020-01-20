import sys
from discord import Embed, Activity
from discord.ext import commands
from settings import *


bot = commands.Bot(command_prefix='>', description="A bot built for harm reduction.")


@bot.command(name='info', aliases=('psycho', 'psychotropic'))
async def info(ctx):

    """Display various informations about the bot"""

    embed = Embed(
        type = 'rich',
        colour = COLOUR,
        title = "Psychotropic",
    )
    embed.set_image(url=AVATAR_URL)
    embed.add_field(
        name="Help",
        value="Type >help to display help page."
    )
    embed.add_field(
        name="Data providers",
        value=(
            "TripSit (https://tripsit.me/)"
            "\nPubMed (https://www.ncbi.nlm.nih.gov/pmc/)"
        )
    )
    embed.set_footer(
        text="Psychotropic was carefully trained by xyzt_",
        icon_url=AUTHOR_URL
    )
    await ctx.send(embed=embed)


@bot.event
async def on_ready():
    
    print(f"Logged in as {bot.user.name} ({bot.user.id}).")
    await bot.change_presence(activity=Activity(name="Wandering"))


if __name__ == '__main__':
    for extension in EXTENSIONS:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print(f"Failed to load extension {extension}.")
            print(sys.exc_info())

    bot.run(DISCORD_TOKEN)
