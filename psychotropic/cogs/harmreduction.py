from discord import Interaction
from discord.app_commands import autocomplete, command, rename
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog

from psychotropic.providers import TripSitEmbed
from psychotropic.providers.tripsit import TripsitApi
from psychotropic.utils import setup_cog


class HarmReductionCog(Cog, name="Harm reduction module"):
    def __init__(self, bot):
        self.bot = bot
        self.tripsit = TripsitApi(bot.http_session)

    async def alias_autocomplete(self, interaction: Interaction, query: str):
        return await self.tripsit.find_aliases(query)

    @command(
        name="drug",
        description=_(
            "Display common information about a drug, its ROAs, durations and dosages."
        ),
    )
    @autocomplete(drug=alias_autocomplete)
    @rename(drug=_("drug"))
    async def drug(self, interaction: Interaction, drug: str):
        """`\drug` command."""
        data = await self.tripsit.get_drug(drug)

        embed = (
            TripSitEmbed(
                title="Drug factsheet: " + data["pretty_name"],
                description=data["properties"]["summary"],
                url=TripsitApi.get_factsheet_url(drug),
            )
            .add_field(name="⏲ Duration", value=data["properties"]["duration"])
            .add_field(
                name="💡 General advise",
                value=data["properties"].get("general-advice", "None :/"),
            )
            .add_field(name="✨ Effects", value=...)
            .add_field(name="📚 Categories", value=...)
        )

        await interaction.response.send_message(embed=embed)


setup = setup_cog(HarmReductionCog)
