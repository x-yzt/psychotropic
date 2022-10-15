from discord.app_commands import command
from discord.ext.commands import Cog

from psychotropic.embeds import ErrorEmbed
from psychotropic.providers import TripSitEmbed, tripsit
from psychotropic.utils import pretty_list, setup_cog


class FactsheetsCog(Cog, name='Drug factsheets module'):
    def __init__(self, bot):
        self.bot = bot

    @command(name='factsheet')
    async def factsheet(self, interaction, drug: str):
        """Display a short factsheet concerning a certain drug."""
        data = await tripsit.get_drug(drug)

        if data['err']:
            embed = ErrorEmbed(f"Can't find drug {drug}")

        else:
            data = data['data'][0]

            try:
                effects = pretty_list(data['formatted_effects'])
            except KeyError:
                effects = "No data :c"

            try:
                categories = pretty_list(data['categories'])
            except KeyError:
                categories = "None"

            embed = (
                TripSitEmbed(
                    title = "Drug factsheet: " + data['pretty_name'],
                    description = data['properties']['summary'],
                    url = tripsit.get_drug_url(drug)
                )
                .add_field(
                    name = "⏲ Duration",
                    value = data['properties']['duration']
                )
                .add_field(
                    name = "💡 General advise",
                    value = data['properties'].get('general-advice', "None :/"),
                )
                .add_field(
                    name = "✨ Effects",
                    value = effects
                )
                .add_field(
                    name = "📚 Categories",
                    value = categories
                )
            )

        await interaction.response.send_message(embed=embed)


setup = setup_cog(FactsheetsCog)
