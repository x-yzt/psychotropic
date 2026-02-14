from itertools import chain

from discord.app_commands import Choice, autocomplete, command
from discord.app_commands import locale_str as _
from discord.app_commands import rename
from discord.ext.commands import Cog

from psychotropic.embeds import ErrorEmbed, send_embed_on_exception
from psychotropic.i18n import current_locale, localize, localize_fmt, set_locale
from psychotropic.providers import MixturesEmbed
from psychotropic.providers.mixtures import (
    MixturesAPI,
    Reliability,
    Risk,
    Synergy,
    format_markdown,
)
from psychotropic.utils import setup_cog, trim_text


class CombosCog(Cog, name="Combos module"):
    def __init__(self, bot):
        self.bot = bot
        # Maps discord locales strings to MixturesAPI instances
        self.mixtures_apis = {
            "en-US": MixturesAPI(),
            "fr": MixturesAPI(locale="fr"),
        }

    @property
    def mixtures(self):
        """Get a MixturesAPI instance according to current locale context."""
        if (locale := current_locale.get()) not in self.mixtures_apis:
            locale = "en-US"

        return self.mixtures_apis[locale]

    async def substance_autocomplete(self, interaction, current: str):
        set_locale(interaction)

        aliases = await self.mixtures.get_aliases()

        # Slugs of substances already queried in other parameters
        input_slugs = await self.mixtures.get_slugs_from_aliases(
            # Discard the last namespace argument as it is the one the user is
            # currently submitting
            (value for _, value in tuple(interaction.namespace)[:-1]),
            raises=False,
        )

        return sorted(
            (
                Choice(name=alias, value=alias.lower())
                for alias, data in aliases.items()
                if (
                    current.lower() in alias.lower() and data["slug"] not in input_slugs
                )
            ),
            key=lambda choice: choice.value.startswith(current.lower()),
            reverse=True,
        )[:25]

    def make_interaction_embed(self, data, show_description=True):
        title = " + ".join(drug["name"] for drug in data["interactants"].values())
        if data["names"]:
            title += f" ({', '.join(map(str.capitalize, data['names']))})"

        risk, synergy, risk_reliability, effects_reliability = (
            enum(data[key])
            for enum, key in (
                (Risk, "risk"),
                (Synergy, "synergy"),
                (Reliability, "risk_reliability"),
                (Reliability, "effects_reliability"),
            )
        )

        embed = MixturesEmbed(
            title=localize_fmt("Interaction: {title}", title=title),
            url=data["site_url"],
        )

        if data["is_draft"]:
            embed.add_field(
                name=localize("🚧 Warning!"),
                value=localize(
                    "This card is a **draft** and has not been reviewed yet.\n"
                    "It can contain **erroneous** or **misleading** "
                    "information. Use at your own risk."
                ),
                inline=False,
            )

        embed.add_field(
            name=localize("Substances"),
            value="\n".join(
                f"- [{drug['name']}]({drug['site_url']})"
                for drug in data["interactants"].values()
            ),
        )

        for name, param, reliab in (
            (localize("Risks"), risk, risk_reliability),
            (localize("Synergy"), synergy, effects_reliability),
        ):
            value = f"**{param.emoji} {str(param).capitalize()}**"

            if param:
                value += "\n*{reliability} {reliab}.*\n{emoji}".format(
                    reliability=localize("Reliability:"),
                    reliab=str(reliab).lower(),
                    emoji=reliab.emoji,
                )

            embed.add_field(name=name, value=value)

        if show_description:
            for name, key, drug_key in (
                (localize("About risks"), "risk_description", "risks"),
                (localize("About effects"), "effect_description", "effects"),
            ):
                text = trim_text(
                    "\n".join(
                        format_markdown(text)
                        for text in chain(
                            (drug[drug_key] for drug in data["interactants"].values()),
                            (data[key],),
                        )
                    ),
                    url=data["site_url"],
                ) or localize("No data :c")
                embed.add_field(name=name, value=text)
        else:
            embed.add_field(
                name=localize("💡 More info"),
                value=localize_fmt(
                    "[**Read more at Mixtures.info**]({url})", url=data["site_url"]
                ),
                inline=False,
            )

        return embed

    # NoQA on those decorators and function signature, because discord.py does
    # not support *args in application commands. Whoever reading this right
    # now, I feel sorry for you.
    @command(
        name="combo",
        description=_("Show risks and effects of a substance combination."),
    )
    @autocomplete(
        a=substance_autocomplete,
        b=substance_autocomplete,
        c=substance_autocomplete,
        d=substance_autocomplete,
    )
    @rename(
        a=_("first-substance"),
        b=_("second-substance"),
        c=_("third-substance"),
        d=_("fourth-substance"),
    )
    @send_embed_on_exception
    async def combo(
        self,
        interaction,
        a: str,
        b: str,
        c: str | None = None,
        d: str | None = None,
    ):
        """`/combo` command."""
        set_locale(interaction)

        await interaction.response.defer()

        drugs = tuple(filter(None, (a, b, c, d)))

        try:
            slugs = await self.mixtures.get_slugs_from_aliases(drugs)
        except KeyError as e:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize_fmt(
                        "Can't find substance {substance}.", substance=e.args[0]
                    )
                )
            )
            return

        result = await self.mixtures.combine(slugs)

        if unknown := result["unknown_interactions"]:
            await interaction.followup.send(
                embed=MixturesEmbed(
                    title=localize("🚨 Warning!"),
                    description=(
                        localize_fmt(
                            "{count} interactions were not found.", count=unknown
                        )
                        if unknown > 1
                        else localize("An interaction was not found.")
                    ),
                )
            )

        for inter in result["interactions"].values():
            await interaction.followup.send(
                embed=self.make_interaction_embed(
                    inter, show_description=len(drugs) == 2
                )
            )


setup = setup_cog(CombosCog)


setup = setup_cog(CombosCog)
