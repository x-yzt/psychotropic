import asyncio as aio
import logging
from io import BytesIO
from random import choice

from discord import ButtonStyle, File
from discord.app_commands import command
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog
from discord.ui import Button, Select, View
from PIL import ImageColor

from psychotropic import settings
from psychotropic.cogs.games import BaseRunningGame, ReplayView, games_group
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.i18n import localize, localize_fmt, set_locale
from psychotropic.providers import pnwiki
from psychotropic.providers.protest import ReagentsDatabase
from psychotropic.utils import make_gradient, setup_cog, unformat

log = logging.getLogger(__name__)


class ReagentsGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    def __init__(self):
        self.db = ReagentsDatabase()
        self.substance = choice(self.db.get_well_known_substances())
        self.tries = 0
        self.reagents_tried = set()

    @property
    def reward(self):
        return 200 if self.tries == 1 else 100

    def reagent_result(self, reagent):
        """Return a (colors, text) tuple of the results of a given reagent, and add this
        reagent to the tried reagents list.

        `KeyError` is raised if no result can be found.
        """
        self.reagents_tried.add(reagent["id"])

        result = self.db.get_result(self.substance, reagent)

        colors = list(map(ImageColor.getrgb, self.db.get_result_colors(result)))

        return (colors, result[3])

    def is_correct(self, guess):
        """Check if a string contains an unformated substring of the right answer and
        increment the tries counter."""
        self.tries += 1
        return unformat(self.substance["commonName"]) in unformat(guess)

    def __str__(self):
        return f"{type(self).__name__} ({self.substance['commonName']})"


class RunningReagentsGame(BaseRunningGame):
    """This class encapsulates reagents game related, Discord-aware logic."""

    TIMEOUT = 10 * 60  # Seconds

    COST = 5  # Coins per reagent

    ICON_DIR = settings.BASE_DIR / "data" / "img" / "substances"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = File(choice(list(self.ICON_DIR.iterdir())), "icon.png")

    @property
    def substance_name(self):
        return self.game.substance["commonName"]

    async def check_answer(self, msg):
        """Check if a message contains the answer and react accordingly."""
        game = self.game

        if game.is_correct(msg.content):
            time = self.time_since_start.total_seconds()

            await self.end()
            self.scoreboard[msg.author].balance += game.reward
            self.scoreboard[msg.author].won_structure_games += 1

            embed = (
                DefaultEmbed(
                    title=localize_fmt("✅ Correct answer, {user}!", user=msg.author),
                    description=localize_fmt(
                        "Well played! The answer was **{answer}**.",
                        answer=self.substance_name,
                    ),
                )
                .set_thumbnail(url="attachment://icon.png")
                .add_field(
                    name=localize("⏱️ Elapsed time"),
                    value=localize_fmt(
                        "You answered in {time:.2f} seconds.", time=time
                    ),
                )
                .add_field(
                    name=localize("🪙 Reward"),
                    value=localize_fmt(
                        "You won **{amount} coins**.", amount=game.reward
                    ),
                )
            )
            if game.tries == 1:
                embed.add_field(
                    name=localize("🥇 First try bonus!"),
                    value=localize("Yay!"),
                )

            view = await self.make_end_view()

            await msg.channel.send(embed=embed, file=self.icon, view=view)

    async def timeout(self):
        """End the game after a certain time is elapsed."""
        await aio.sleep(self.TIMEOUT)

        await self.channel.send(
            embed=DefaultEmbed(
                title=localize("😔 No one found the solution."),
                description=localize_fmt(
                    "The answer was **{answer}**.", answer=self.substance_name
                ),
            ),
            view=await self.make_end_view(),
        )

        await self.end()

    @classmethod
    async def start(cls, interaction, game, scoreboard):
        self = await super().start(interaction, game, scoreboard)

        if not self:
            return

        embed = (
            DefaultEmbed(
                title=(
                    localize_fmt(
                        "🚀 {user} found a strange chemical in its pockets...",
                        user=interaction.user,
                    )
                ),
                description=localize("Can you find what this is?"),
            )
            .set_thumbnail(url="attachment://icon.png")
            .set_footer(text=localize("Wow, shady stuff..."))
        )
        await interaction.response.send_message(
            embed=embed, file=self.icon, view=self.make_reagent_select_view()
        )

        self.create_task(self.timeout)

        return self

    async def test_reagent(self, interaction):
        try:
            reagent_id = interaction.data["values"][0]
        except IndexError:
            return

        reagent = self.game.db.get_by_id("reagents", reagent_id)
        try:
            colors, text = self.game.reagent_result(reagent)
        except KeyError:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize("Reaction error 💣"),
                    localize_fmt(
                        "Sadly I can't perform a {reagent} test on this mysterious "
                        "substance.",
                        reagent=reagent["fullName"],
                    ),
                ),
                view=self.make_reagent_select_view(),
            )
            return

        embed = (
            DefaultEmbed(
                title=localize_fmt(
                    "⚗️ {reagent} test results", reagent=reagent["fullName"]
                )
            )
            .add_field(
                name=localize("🔎 Observed results"),
                value=f"**{text.capitalize()}**",
            )
            .set_footer(text=localize("Mhh..."))
        )

        if self.scoreboard[interaction.user].balance < self.COST:
            embed.add_field(
                name=localize("🎁 I'll treat you!"),
                value=localize_fmt(
                    "{user} was low on 🪙, I gave them a reagent.",
                    user=interaction.user,
                ),
            )
        else:
            self.scoreboard[interaction.user].balance -= self.COST
            embed.add_field(
                name=localize("💸 Thank you!"),
                value=localize_fmt(
                    "{user} paid {cost} 🪙 for the reagent.",
                    user=interaction.user,
                    cost=self.COST,
                ),
            )

        if colors:
            image = make_gradient(colors, 600, 100)

            with BytesIO() as buffer:
                image.save(buffer, format="PNG")
                buffer.seek(0)
                file = File(fp=buffer, filename="gradient.png")

                embed.set_image(url="attachment://gradient.png")

                await interaction.followup.send(
                    embed=embed, file=file, view=self.make_reagent_select_view()
                )

        else:
            # No color change, special patterns...
            await interaction.followup.send(
                embed=embed, view=self.make_reagent_select_view()
            )

    def make_reagent_select_view(self):
        view = View(timeout=self.TIMEOUT)
        select = Select(placeholder=localize("Buy and use a reagent..."))

        async def callback(interaction):
            # Disable the select dropdown as soon as a choice have been made
            select.disabled = True
            await interaction.response.edit_message(view=view)

            await self.test_reagent(interaction)

        select.callback = callback

        for reagent in self.game.db.get_reagents():
            if reagent["id"] not in self.game.reagents_tried:
                select.add_option(
                    label=localize_fmt("{reagent} test", reagent=reagent["fullName"]),
                    description=localize_fmt(
                        "Buy and use this test for {cost} 🪙", cost=self.COST
                    ),
                    value=reagent["id"],
                )

        # Don't add the select to the view if no items are avalaible
        # because selection without options are not allowed by Discord
        if select.options:
            view.add_item(select)

        return view

    async def send_end_message(self, interaction):
        await interaction.response.send_message(
            embed=(
                DefaultEmbed(
                    title=localize_fmt(
                        "🛑 {user} ended the game.",
                        user=interaction.user,
                    ),
                    description=localize_fmt(
                        "The answer was **{answer}**.",
                        answer=self.game.substance["commonName"],
                    ),
                ).set_thumbnail(url="attachment://icon.png")
            ),
            file=self.icon,
            view=await self.make_end_view(),
        )

    async def make_end_view(self):
        """Return a Discord view used to decorate end game embeds."""
        view = ReplayView(callback=self.replay)

        substance = await pnwiki.get_substance(self.game.substance["commonName"])
        # The substance might not be found on PNW
        if substance:
            view.add_item(
                Button(
                    label=localize("What's that?"),
                    style=ButtonStyle.url,
                    emoji="🌐",
                    url=substance["url"],
                )
            )

        return view


class ReagentsGameCog(Cog, name="Reagents game module"):
    def __init__(self, bot):
        self.bot = bot

    @property
    def scoreboard(self):
        return self.bot.get_cog("Games module").scoreboard

    @Cog.listener()
    async def on_message(self, msg):
        if (
            msg.is_system()
            or msg.author.bot
            or not (running_game := RunningReagentsGame.get_from_context(msg))
        ):
            return

        set_locale(running_game.locale)

        await running_game.check_answer(msg)

    # See comment in cog_load method below to get why command decorators are not used
    async def reagents(self, interaction):
        """`/game reagents` command"""
        await RunningReagentsGame.start(interaction, ReagentsGame(), self.scoreboard)

    reagents.description = _(
        "Start a new Reagents Game. The first player who guess the substance in the "
        "chat wins."
    )
    reagents.extras = {
        "long_description": _(
            "Start a new Reagents Game. The bot will pick a random substance, and "
            "players can use reagents to identify it. The first player who guess the "
            "substance in the chat will win.\n\n"
            "Performing the testing takes some coins (🪙), but finding the answer will "
            "be rewarded!"
        )
    }

    async def cog_load(self):
        # Register the method as a subcommand of the `games_group` shared command group.
        # This workaround is needed to keep matching slash-command signatures.
        cmd = command(
            description=self.reagents.description,
            extras=self.reagents.extras,
        )(self.reagents)
        games_group.add_command(cmd)

        # Update the shared command group in the command tree
        self.bot.tree.add_command(games_group, override=True)


setup = setup_cog(ReagentsGameCog)
