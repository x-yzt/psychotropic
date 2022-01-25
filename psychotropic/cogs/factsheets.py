from discord.ext.commands import command, Cog

from psychotropic.embeds import ErrorEmbed
from psychotropic.providers import tripsit, TripSitEmbed
from psychotropic.utils import pretty_list, setup_cog


class FactsheetsCog(Cog, name='Drug factsheets module'):
    def __init__(self, bot):
        self.bot = bot
    
    @command(name='factsheet', aliases=('facts', 'drug'))
    async def factsheet(self, ctx, drug: str):
        """Display a short factsheet concerning a certain drug."""
        data = await tripsit.get_drug(drug)
        
        if data['err']:
            embed = ErrorEmbed(f"Can't find drug {drug}")
        
        else:
            data = data['data'][0]
            embed = TripSitEmbed(
                title = "Drug factsheet: " + data['pretty_name'],
                description = data['properties']['summary'],
                url = tripsit.get_drug_url(drug)
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
