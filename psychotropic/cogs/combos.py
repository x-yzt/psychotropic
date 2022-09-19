from itertools import chain
from typing import Optional

from discord.app_commands import Choice, command, autocomplete, rename
from discord.ext.commands import Cog

from psychotropic.embeds import ErrorEmbed, send_embed_on_exception
from psychotropic.providers import MixturesEmbed
from psychotropic.providers.mixtures import (MixturesAPI, Risk, Synergy,
    Reliability, format_linebreaks)
from psychotropic.utils import setup_cog


class CombosCog(Cog, name="Combos module"):
    def __init__(self, bot):
        self.bot = bot
        self.mixtures = MixturesAPI()
    
    async def substance_autocomplete(self, interaction, current: str):
        aliases = await self.mixtures.get_aliases()
        
        # Slugs of substances already queried in other parameters
        input_slugs = await self.mixtures.get_slugs_from_aliases(
            # Discard the last namespace argument as it is the one the user is
            # currently submitting
            (value for _, value in tuple(interaction.namespace)[:-1]),
            raises=False
        )

        return sorted(
            (
                Choice(name=alias, value=alias.lower())
                for alias, data in aliases.items()
                if (
                    current.lower() in alias.lower()
                    and data['slug'] not in input_slugs
                )
            ),
            key=lambda choice: choice.value.startswith(current.lower()),
            reverse=True
        )[:25]

    def make_interaction_embed(self, data):
        title = ' + '.join(
            drug['name'] for drug in data['interactants'].values()
        )
        if data['names']:
            title += f" ({', '.join(map(str.capitalize, data['names']))})"
        
        risk, synergy, risk_reliability, effects_reliability = (
            enum(data[key]) for enum, key in (
               (Risk,        'risk'),
               (Synergy,     'synergy'),
               (Reliability, 'risk_reliability'),
               (Reliability, 'effects_reliability'),
            )
        )

        risk_text, effects_text = (
            '\n'.join((
                format_linebreaks(text)
                for text in chain(
                    (drug[drug_key] for drug in data['interactants'].values()),
                    (data[key],)
                )
            ))
            for key, drug_key in (
                ('risk_description',   'risks'),
                ('effect_description', 'effects'),
            )
        )

        embed = MixturesEmbed(
            title=f"Interaction: {title}",
            url=data['site_url']
        )

        if data['is_draft']:
            embed.add_field(
                name="🚧 Warning!",
                value=(
                    "This card is a **draft** and has not been reviewed yet.\n"
                    "It can contain **erroneous** or **misleading** "
                    "information. Use at your own risk."
                ),
                inline=False
            )
        
        embed.add_field(
            name="Substances:",
            value='\n'.join((
                f"- [{drug['name']}]({drug['site_url']})"
                for drug in data['interactants'].values()
            ))
        )
        
        for name, param, reliab in (
            ("Risks",   risk,    risk_reliability),
            ("Synergy", synergy, effects_reliability)
        ):
            embed.add_field(
                name=name,
                value=(
                    f"**{param.emoji} {str(param).capitalize()}**\n"
                    f"*Reliability: {str(reliab).lower()}.*\n{reliab.emoji}"
                )
            )

        for name, text in (
            ("About risks", risk_text),
            ("About effects", effects_text)
        ):
            embed.add_field(name=name, value=text[:1024])

        return embed


    # NoQA on those decorators and function signature, because discord.py does
    # not support *args in application commands. Whoever reading this right
    # now, I feel sorry for you.
    @command(name="combo")
    @autocomplete(
        a=substance_autocomplete,
        b=substance_autocomplete,
        c=substance_autocomplete,
        d=substance_autocomplete,
    )
    @rename(
        a="first-substance",
        b="second-substance",
        c="third-substance",
        d="fourth-substance",
    )
    @send_embed_on_exception
    async def combo(
        self, interaction,
        a: str, b: str, c: Optional[str] = None, d: Optional[str] = None
    ):
        """Show risks and effects of a substance combination."""
        await interaction.response.defer()

        drugs = filter(None, (a, b, c, d))
        
        try:
            slugs = await self.mixtures.get_slugs_from_aliases(drugs)
        except KeyError as e:
            await interaction.followup.send(
                embed=ErrorEmbed(f"Can't find substance {e.args[0]}")
            )
            return

        result = await self.mixtures.combine(slugs)

        if unknown := result['unknown_interactions']:
            await interaction.followup.send(embed=MixturesEmbed(
                title="🚨 Warning!",
                description=(
                    f"{unknown} interactions were not found."
                    if unknown > 1 else
                    "An interaction was not found."
                )
            ))

        for inter in result['interactions'].values():
            await interaction.followup.send(
                embed=self.make_interaction_embed(inter)
            )


setup = setup_cog(CombosCog)
