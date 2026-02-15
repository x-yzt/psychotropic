from itertools import chain, groupby
from operator import itemgetter

from discord import Interaction
from discord.app_commands import Choice, autocomplete, command
from discord.app_commands import locale_str as _
from discord.app_commands import rename
from discord.ext.commands import Cog

from psychotropic.embeds import ErrorEmbed, send_embed_on_exception
from psychotropic.i18n import get_locale, localize, localize_fmt
from psychotropic.providers import MixturesEmbed
from psychotropic.providers.mixtures import MixturesAPI, format_markdown
from psychotropic.utils import pretty_list, setup_cog, trim_text


class CombosCog(Cog, name="Combos module"):
    def __init__(self, bot):
        self.bot = bot
        # Maps discord locales strings to MixturesAPI instances
        self.mixtures_apis = {
            "en-US": MixturesAPI(session=bot.http_session),
            "fr": MixturesAPI(session=bot.http_session, locale="fr"),
        }

    @property
    def mixtures(self):
        """Get a MixturesAPI instance according to current locale context."""
        if (locale := get_locale()) not in self.mixtures_apis:
            locale = "en-US"

        return self.mixtures_apis[locale]

    async def substance_autocomplete(self, interaction, current: str):
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
            (localize("Risks"), data["risk"], data["risk_reliability"]),
            (localize("Synergy"), data["synergy"], data["effects_reliability"]),
        ):
            value = f"**{param.emoji} {str(param).capitalize()}**"

            # Don't show reliability on unknow (falsy) risk or effect
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

    def make_substance_embed(self, data):
        embed = MixturesEmbed(
            title=localize_fmt("{substance} interactions", substance=data["name"]),
            url=data["site_url"],
            description=format_markdown(data["description"]),
        )

        for key, name in (
            ("risks", localize("☣️ About risks")),
            ("effects", localize("⚡ About effects")),
        ):
            if value := data[key]:
                embed.add_field(name=name, value=value)

        groups = groupby(
            sorted(data["interactions"].values(), key=itemgetter("risk"), reverse=True),
            itemgetter("risk"),
        )

        for risk, interactions in groups:
            embed.add_field(
                name=f"{risk.emoji} {str(risk).capitalize()}",
                value=pretty_list(
                    (
                        (
                            "🚧 *[{name}]({url})* {emoji} *({draft})*"
                            if inter["is_draft"]
                            else "**[{name}]({url})** {emoji}"
                        ).format(
                            name=next(
                                name
                                for name in inter["interactants"]
                                if name != data["name"]
                            ),
                            url=inter["site_url"],
                            emoji=inter["synergy"].emoji,
                            draft=localize("Draft!"),
                        )
                        for inter in sorted(interactions, key=itemgetter("is_draft"))
                    ),
                    capitalize=False,
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
        interaction: Interaction,
        a: str,
        b: str,
        c: str | None = None,
        d: str | None = None,
    ):
        """`/combo` command."""
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

        await interaction.followup.send(
            embeds=[
                self.make_interaction_embed(inter, show_description=len(drugs) == 2)
                for inter in result["interactions"].values()
            ]
        )

    @command(
        name="combos",
        description=_("Show a summary of interactions involving this substance."),
    )
    @autocomplete(substance=substance_autocomplete)
    async def combos(self, interaction: Interaction, substance: str):
        """`/combos` command."""
        await interaction.response.defer()

        try:
            data = await self.mixtures.get_substance_by_alias(substance)
        except KeyError as e:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize_fmt(
                        "Can't find substance {substance}.", substance=e.args[0]
                    )
                )
            )
            return

        await interaction.followup.send(embed=self.make_substance_embed(data))


setup = setup_cog(CombosCog)
