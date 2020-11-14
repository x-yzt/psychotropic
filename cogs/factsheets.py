import json
import httpx
from itertools import chain
from discord import Embed
from discord.ext.commands import command, Cog
from embeds import ErrorEmbed
from utils import pretty_list
from settings import COLOUR


class TripSitEmbed(Embed):
    
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.set_author(
            name="TripSit",
            url="https://tripsit.me/",
            icon_url="https://cdn.discordapp.com/attachments/665208722372427782/665223281032560680/Vojr95_q_400x4001.png"
        )


class FactsheetsCog(Cog, name='Drug factsheets module'):
    
    def __init__(self, bot):
        
        self.bot = bot
    

    async def load_ts_data(self, drug: str):

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "http://tripbot.tripsit.me/api/tripsit/getDrug",
                params={'name': drug.lower()}
            )
        return json.loads(r.text)

    
    @command(name='factsheet', aliases=('facts', 'drug'))
    async def factsheet(self, ctx, drug: str):
        
        """Display a short factsheet concerning a certain drug"""

        data = await self.load_ts_data(drug)
        
        if data['err']:
            embed = ErrorEmbed(f"Can't find drug {drug}")
        
        else:
            data = data['data'][0]
            embed = TripSitEmbed(
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

        await ctx.send(embed=embed)


setup = lambda bot: bot.add_cog(FactsheetsCog(bot))
