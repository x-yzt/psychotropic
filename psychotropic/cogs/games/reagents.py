import asyncio as aio
import logging
import textwrap
from importlib import resources
from io import BytesIO
from operator import attrgetter
from random import choice, random

from discord import (
    ButtonStyle,
    File,
    Interaction,
    MediaGalleryItem,
    Member,
    Message,
    User,
)
from discord.app_commands import command
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog
from discord.ui import (
    Button,
    Container,
    LayoutView,
    MediaGallery,
    Section,
    TextDisplay,
    Thumbnail,
)
from PIL import ImageDraw, ImageFont

from psychotropic import settings
from psychotropic.cogs.games import BaseRunningGame, ReplayView, Scoreboard, games_group
from psychotropic.embeds import DefaultEmbed
from psychotropic.i18n import localize, localize_fmt, set_locale
from psychotropic.providers import pnwiki, protest
from psychotropic.providers.protest import Result, Substance
from psychotropic.settings import COLOUR
from psychotropic.utils import (
    make_gradient,
    make_transparent,
    pretty_list,
    setup_cog,
    unformat,
)

log = logging.getLogger(__name__)


class ReagentsGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    def __init__(self):
        self.db = protest.db
        self.substance: Substance = choice(
            list(
                filter(
                    attrgetter("is_popular"),
                    self.db.get_well_known_substances(reactions=9, colored_reactions=3),
                )
            )
        )
        self.clues: list[Result] = self.pick_clues()
        self.tries = 0

    @property
    def reward(self):
        return 50 if self.tries == 1 else 25

    def is_correct(self, guess: str):
        """Check if a string contains an unformated substring of the right answer and
        increment the tries counter."""
        self.tries += 1
        return unformat(str(self.substance)) in unformat(guess)

    def pick_clues(self):
        """As Discord allows a maximum of 10 files per message, including one for the
        thumbnail; this picks up to 9 reagent results randomly, prioritysing ones with
        color changes."""
        results = list(self.substance.results.values())

        results.sort(key=lambda r: (bool(len(r.colors)), random()), reverse=True)

        return sorted(results[:9], key=str)

    def __str__(self):
        return f"{type(self).__name__} ({self.substance})"


class RunningReagentsGame(BaseRunningGame):
    """This class encapsulates reagents game related, Discord-aware logic."""

    TIMEOUT = 10 * 60  # Seconds

    ICON_DIR = settings.BASE_DIR / "data" / "img" / "substances"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = File(choice(list(self.ICON_DIR.iterdir())), "icon.png")

    async def check_answer(self, msg: Message):
        """Check if a message contains the answer and react accordingly."""
        game: ReagentsGame = self.game

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
                        answer=self.game.substance,
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

        elif guess := game.db.search_substance(msg.content):
            embed = DefaultEmbed(
                title=localize_fmt("🔎 Mhh, this is not {substance}", substance=guess),
                description=localize_fmt(
                    "{substance} has the following reagent results", substance=guess
                ),
            )

            similar_results = []
            unalike_results = []

            for clue_result in game.clues:
                try:
                    guess_result = next(
                        filter(
                            lambda r: r.reagent is clue_result.reagent,
                            guess.results.values(),
                        )
                    )
                except StopIteration:
                    continue

                if clue_result.simple_colors == guess_result.simple_colors:
                    similar_results.append(guess_result)
                else:
                    unalike_results.append(guess_result)

            if similar_results:
                embed.add_field(
                    name=localize_fmt(
                        "✅ You're right, {substance} is somewhat alike what we're "
                        "looking at",
                        substance=guess,
                    ),
                    value=pretty_list(
                        f"{res.reagent}: {res.description}" for res in similar_results
                    ),
                )

            if unalike_results:
                embed.add_field(
                    name=localize_fmt("❌ It can't be {substance}", substance=guess),
                    value=pretty_list(
                        f"{res.reagent}: {res.description}" for res in unalike_results
                    ),
                )

            await msg.channel.send(embed=embed)

    async def timeout(self):
        """End the game after a certain time is elapsed."""
        await aio.sleep(self.TIMEOUT)

        await self.channel.send(
            embed=DefaultEmbed(
                title=localize("😔 No one found the solution."),
                description=localize_fmt(
                    "The answer was **{answer}**.", answer=self.game.substance
                ),
            ),
            view=await self.make_end_view(),
        )

        await self.end()

    @classmethod
    async def start(
        cls, interaction: Interaction, game: ReagentsGame, scoreboard: Scoreboard
    ):
        self = await super().start(interaction, game, scoreboard)

        if not self:
            return

        await interaction.response.defer(thinking=True)

        view = ReagentsGameStartView(user=interaction.user, results=game.clues)

        await interaction.followup.send(
            files=[self.icon, *view.make_result_files()],
            view=view,
        )

        self.create_task(self.timeout)

        return self

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
                        answer=self.game.substance,
                    ),
                ).set_thumbnail(url="attachment://icon.png")
            ),
            file=self.icon,
            view=await self.make_end_view(),
        )

    async def make_end_view(self):
        """Return a Discord view used to decorate end game embeds."""
        view = ReplayView(callback=self.replay)

        substance = await pnwiki.get_substance(str(self.game.substance))
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


class ReagentsGameStartView(LayoutView):
    RESULT_SIZE = 512

    TITLE_HEIGHT = 120

    with resources.path("psychotropic.data.font", "gg_sans_bold.ttf") as file:
        TITLE_FONT = ImageFont.truetype(str(file), size=TITLE_HEIGHT - 40)

    with resources.path("psychotropic.data.font", "gg_sans_semibold.ttf") as file:
        TEXT_FONT = ImageFont.truetype(str(file), size=50)

    def __init__(self, user: User | Member, results: list[Result]):
        super().__init__()

        self.results = results

        self.add_item(
            Container(
                TextDisplay(
                    localize_fmt(
                        "# 🚀 {user} found a strange chemical in its pockets...",
                        user=user,
                    )
                ),
                Section(
                    TextDisplay(
                        localize(
                            "Let's try a few reagents on it. Can you find what it is?"
                        )
                    ),
                    accessory=Thumbnail(media="attachment://icon.png"),
                ),
                MediaGallery(*(self.get_gallery_items())),
                TextDisplay(localize("*Wow, shady stuff...*")),
                accent_color=COLOUR,
            ),
        )

    def make_result_files(self) -> list[File]:
        files = []

        for result in self.results:
            image = self.draw_result(result)

            with BytesIO() as buffer:
                image.save(buffer, format="PNG")
                buffer.seek(0)
                files.append(File(fp=buffer, filename=f"{result.reagent}.png"))

        return files

    def get_gallery_items(self):
        return (
            MediaGalleryItem(
                media=f"attachment://{result.reagent}.png",
                description=result.description,
            )
            for result in self.results
        )

    def draw_result(self, result: Result):
        size = self.RESULT_SIZE
        title_height = self.TITLE_HEIGHT

        image = (
            make_gradient(
                [color.to_rgb() for color in result.colors], width=size, height=size
            )
            if result.colors
            else make_transparent(width=size, height=size)
        )

        draw = ImageDraw.Draw(image)
        draw.rectangle(
            ((0, 0), (size, title_height)),
            fill=COLOUR.to_rgb(),
        )
        draw.text(
            (size / 2, 25),
            str(result.reagent),
            anchor="mt",
            align="center",
            font=self.TITLE_FONT,
            fill=(0xFF, 0xFF, 0xFF),
        )
        draw.multiline_text(
            (size / 2, size / 2 + title_height),
            textwrap.fill(result.description.capitalize(), 20),
            anchor="mm",
            align="center",
            font=self.TEXT_FONT,
            fill=(0x0, 0x0, 0x0),
            stroke_width=6,
            stroke_fill=(0xFF, 0xFF, 0xFF, 0x80),
        )

        return image


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
