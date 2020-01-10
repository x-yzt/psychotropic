import json
import httpx
from discord import Embed
from discord.ext.commands import command, Cog
from utils import ErrorEmbed, pretty_list
from settings import COLOUR


class FactsheetsCog(Cog, name='Factsheets'):
    
    def __init__(self, bot):
        
        self.bot = bot


    @command(name='factsheet', aliases=('facts',))
    async def capcom(self, ctx, drug: str):
        
        """Display a short factsheet concerning a certain drug"""

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "http://tripbot.tripsit.me/api/tripsit/getDrug",
                params={'name': drug.lower()}
            )
        data = json.loads(r.text)
        
        if data['err']:
            embed = ErrorEmbed(f"Can't find drug {drug}")
        
        else:
            data = data['data'][0]
            embed = Embed(
                type = 'rich',
                colour = COLOUR,
                title = "Drug factsheet: " + data['pretty_name'],
                description = data['properties']['summary'],
                url = "http://drugs.tripsit.me/" + drug.lower()
            )
            embed.add_field(
                name="⏲ Duration",
                value=data['properties']['duration'],
                inline=False
            )

            try:
                effects = pretty_list(data['formatted_effects'])
            except KeyError:
                effects = "No data :c"
            embed.add_field(
                name="✨ Effects",
                value=effects
            )

            try:
                categories = pretty_list(data['categories'])
            except KeyError:
                categories = "None"
            embed.add_field(
                name="📚 Categories",
                value=categories
            )

        embed.set_author(
            name="TripSit",
            url="https://tripsit.me/",
            icon_url="https://cdn.discordapp.com/attachments/665208722372427782/665223281032560680/Vojr95_q_400x4001.png"
        )
        await ctx.send(embed=embed)


setup = lambda bot: bot.add_cog(FactsheetsCog(bot))
