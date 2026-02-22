import asyncio as aio
import logging
import textwrap
from importlib import resources
from io import BytesIO
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
from PIL import Image, ImageColor, ImageDraw, ImageFont

from psychotropic import settings
from psychotropic.cogs.games import BaseRunningGame, ReplayView, Scoreboard, games_group
from psychotropic.embeds import DefaultEmbed
from psychotropic.i18n import localize, localize_fmt, set_locale
from psychotropic.providers import pnwiki
from psychotropic.providers.protest import ReagentsDatabase
from psychotropic.settings import COLOUR
from psychotropic.utils import (
    make_gradient,
    make_transparent,
    setup_cog,
    unformat,
)

log = logging.getLogger(__name__)


Result = tuple[str, str, list[list[int]]]


class ReagentsGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    def __init__(self):
        self.db = ReagentsDatabase()
        self.substance = choice(self.db.get_well_known_substances())
        self.tries = 0

    @property
    def reward(self):
        return 50 if self.tries == 1 else 25

    def get_results(self) -> list[Result]:
        """Return test results of the game substance as a list of `(reagent name,
        color description, [first color, second color, ...])` tuples.

        `KeyError` is raised if no result can be found.
        """
        results = self.db.get_results(self.substance)

        return [
            (
                self.db.get_by_id("reagents", reagent_id)["fullName"],
                result[3],
                list(map(ImageColor.getrgb, self.db.get_result_colors(result))),
            )
            for reagent_id, result in results.items()
        ]

    def is_correct(self, guess: str):
        """Check if a string contains an unformated substring of the right answer and
        increment the tries counter."""
        self.tries += 1
        return unformat(self.substance["commonName"]) in unformat(guess)

    def __str__(self):
        return f"{type(self).__name__} ({self.substance['commonName']})"


class RunningReagentsGame(BaseRunningGame):
    """This class encapsulates reagents game related, Discord-aware logic."""

    TIMEOUT = 10 * 60  # Seconds

    ICON_DIR = settings.BASE_DIR / "data" / "img" / "substances"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.icon = File(choice(list(self.ICON_DIR.iterdir())), "icon.png")

    @property
    def substance_name(self):
        return self.game.substance["commonName"]

    async def check_answer(self, msg: Message):
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
    async def start(
        cls, interaction: Interaction, game: ReagentsGame, scoreboard: Scoreboard
    ):
        self = await super().start(interaction, game, scoreboard)

        if not self:
            return

        view = ReagentsGameStartView(
            user=interaction.user,
            results=game.get_results(),
        )

        await interaction.response.send_message(
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


class ReagentsGameStartView(LayoutView):
    RESULT_SIZE = 512

    def __init__(self, user: User | Member, results: list[Result]):
        super().__init__()

        self.results = self.pick_results(results)

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

    @staticmethod
    def pick_results(results: list[Result]):
        """As Discord allows a maximum of 10 files per message, including one for the
        thumbnail; this picks up to 9 results randomly, prioritysing ones with color
        changes."""
        results.sort(key=lambda r: (bool(len(r[2])), random()), reverse=True)

        return results[:9]

    def make_result_files(self) -> list[File]:
        files = []

        for reagent, description, colors in self.results:
            image = self.draw_result(reagent, description, colors)

            with BytesIO() as buffer:
                image.save(buffer, format="PNG")
                buffer.seek(0)
                files.append(File(fp=buffer, filename=f"{reagent}.png"))

        return files

    def get_gallery_items(self):
        return (
            MediaGalleryItem(
                media=f"attachment://{reagent}.png", description=description
            )
            for reagent, description, _ in self.results
        )

    def draw_result(self, reagent: str, description: str, colors: list[int]):
        size = self.RESULT_SIZE
        title_height = 120

        image = (
            make_gradient(colors, width=size, height=size)
            if colors
            else make_transparent(width=size, height=size)
        )

        with resources.path("psychotropic.data.font", "gg_sans_bold.ttf") as file:
            title_font = ImageFont.truetype(str(file), size=title_height - 40)

        with resources.path("psychotropic.data.font", "gg_sans_semibold.ttf") as file:
            description_font = ImageFont.truetype(str(file), size=50)

        draw = ImageDraw.Draw(image)
        draw.rectangle(
            ((0, 0), (size, title_height)),
            fill=COLOUR.to_rgb(),
        )
        draw.text(
            (size / 2, 25),
            reagent,
            anchor="mt",
            align="center",
            font=title_font,
            fill=(0xFF, 0xFF, 0xFF),
        )
        draw.multiline_text(
            (size / 2, size / 2 + title_height),
            textwrap.fill(description.capitalize(), 20),
            anchor="mm",
            align="center",
            font=description_font,
            fill=(0x0, 0x0, 0x0),
            stroke_width=3,
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
