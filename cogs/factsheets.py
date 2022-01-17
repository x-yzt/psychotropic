import json

import httpx
from discord.ext.commands import command, Cog

from embeds import ErrorEmbed
from providers import TripSitEmbed
from utils import pretty_list, setup_cog


class FactsheetsCog(Cog, name='Drug factsheets module'):
    def __init__(self, bot):
        self.bot = bot
    
    async def load_ts_data(self, drug: str):
        async with httpx.AsyncClient() as client:
            r = await client.get(
                "http://tripbot.tripsit.me/api/tripsit/getDrug",
                params = {'name': drug.lower()}
            )
        return json.loads(r.text)

    @command(name='factsheet', aliases=('facts', 'drug'))
    async def factsheet(self, ctx, drug: str):
        """Display a short factsheet concerning a certain drug."""
        data = await self.load_ts_data(drug)
        
        if data['err']:
            embed = ErrorEmbed(f"Can't find drug {drug}")
        
        else:
            data = data['data'][0]
            embed = TripSitEmbed(
                title = "Drug factsheet: " + data['pretty_name'],
                description = data['properties']['summary'],
                url = "http://drugs.tripsit.me/" + drug.lower()
            )
            embed.add_field(
                name = "⏲ Duration",
                value = data['properties']['duration'],
                inline = False
            )

            try:
                effects = pretty_list(data['formatted_effects'])
            except KeyError:
                effects = "No data :c"
            embed.add_field(
                name = "✨ Effects",
                value = effects
            )

            try:
                categories = pretty_list(data['categories'])
            except KeyError:
                categories = "None"
            embed.add_field(
                name = "📚 Categories",
                value = categories
            )

        await ctx.send(embed=embed)


setup = setup_cog(FactsheetsCog)
