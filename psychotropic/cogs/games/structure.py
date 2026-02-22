import asyncio as aio
import logging
from random import choice

from discord import ButtonStyle, File
from discord.app_commands import command
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog
from discord.ui import Button
from httpx import TimeoutException

from psychotropic import settings
from psychotropic.cogs.games import BaseRunningGame, ReplayView, games_group
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.i18n import localize, localize_fmt, set_locale
from psychotropic.providers import pnwiki
from psychotropic.utils import setup_cog, shuffled, unformat

log = logging.getLogger(__name__)


class SchematicRegistry:
    def __init__(self, path):
        path.mkdir(parents=True, exist_ok=True)

        self.path = path
        self.schematics = []

    async def fetch_schematics(self):
        """Populate the list of all substances to play the game with from PNWiki."""
        if settings.FETCH_SCHEMATICS:
            log.info("Populating cache with schematics from PNWiki...")

            try:
                for substance in await pnwiki.list_substances():
                    image_path = self.build_schematic_path(substance)
                    if image_path.exists():
                        continue

                    image = await pnwiki.get_schematic_image(
                        substance, width=600, background_color="WHITE"
                    )
                    if image:
                        image.save(image_path)

            except TimeoutException:
                log.error(
                    "Unable to reach PsychonautWiki API. The schematic cache might be "
                    "empty or incomplete."
                )

        self.schematics = list(self.path.glob("*.png"))

        log.info(f"{len(self._schematics)} schematics avalaible in cache")

    @property
    def schematics(cls):
        if not cls._schematics:
            raise cls.UnfetchedRegistryError()
        return cls._schematics

    @schematics.setter
    def schematics(self, value):
        self._schematics = value

    def pick_substance(self):
        """Pick a random substance name from what is avalaible in the registry."""
        return choice(self.schematics).stem

    def build_schematic_path(self, substance):
        """Build the path of a given substance's schematic. There is no guarantee this
        path will actually exist."""
        return self.path / (substance + ".png")

    def get_schematic(self, substance):
        """Get the path of a given substance's schematic, raises an exception if no
        schematic is found for this substance."""
        path = self.build_schematic_path(substance)

        if path not in self.schematics:
            raise FileNotFoundError()

        return path

    class UnfetchedRegistryError(RuntimeError):
        def __init__(self, *args):
            super().__init__(
                "SchematicRegistry needs schematics to be cached before they "
                "are used. Please `await` for `fetch_schematics`.",
                *args,
            )


class StructureGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    # This is where molecules schematics will be downloaded
    CACHE_DIR = settings.STORAGE_DIR / "cache" / "schematics"

    # Non-word chars often encoutered in substance names
    NON_WORD = "();-, "

    schematic_registry = SchematicRegistry(CACHE_DIR)

    def __init__(self):
        """To populate the substance registry, `prepare_registry` must be awaited before
        instanciation."""
        self.substance = self.schematic_registry.pick_substance()
        self.secret_chars = shuffled(
            [i for i, c in enumerate(self.substance) if c not in self.NON_WORD]
        )
        self.guess_len = len(self.secret_chars)
        self.tries = 0

    @property
    def schematic(self):
        return self.schematic_registry.get_schematic(self.substance)

    @property
    def clue(self):
        return "".join(
            c if c in self.NON_WORD or i not in self.secret_chars else "_"
            for i, c in enumerate(self.substance)
        )

    @property
    def reward(self):
        return len(self.secret_chars) / (1 if self.tries <= 1 else 2)

    def is_correct(self, guess):
        """Check if a string contains an unformated substring of the right answer and
        increment the tries counter."""
        self.tries += 1
        return unformat(self.substance, self.NON_WORD) in unformat(guess, self.NON_WORD)

    def get_clue(self):
        """Generate a new, easier clue and return it."""
        for __ in range(max(1, self.guess_len // 4)):
            try:
                self.secret_chars.pop()
            except IndexError:
                break

        return self.clue

    def __str__(self):
        return f"{type(self).__name__} ({self.substance})"

    @classmethod
    async def prepare_registry(cls):
        """Prepare the registry of all substances to play the game with."""
        await cls.schematic_registry.fetch_schematics()


class RunningStructureGame(BaseRunningGame):
    """This class encapsulates structure game related, Discord-aware logic."""

    async def check_answer(self, msg):
        """Check if a message contains the answer and react accordingly."""
        game = self.game

        if game.is_correct(msg.content):
            time = self.time_since_start.total_seconds()

            await self.end()
            self.scoreboard[msg.author].balance += game.reward
            self.scoreboard[msg.author].won_structure_games += 1
            self.scoreboard[msg.author].found_structure_substances.add(game.substance)

            file = File(game.schematic, filename="schematic.png")
            embed = (
                DefaultEmbed(
                    title=localize_fmt("✅ Correct answer, {user}!", user=msg.author),
                    description=(
                        localize_fmt(
                            "Well played! The answer was **{answer}**.",
                            answer=game.substance,
                        )
                    ),
                )
                .set_thumbnail(url="attachment://schematic.png")
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

            await msg.channel.send(embed=embed, file=file, view=view)

    async def send_clue(self):
        """Periodically send clues by showing some more letters."""
        await aio.sleep(10)

        game = self.game
        clue = game.get_clue()

        if game.secret_chars:
            await self.channel.send(
                embed=DefaultEmbed(
                    title=localize("💡 Here's a bit of help:"),
                    description=f"```{clue}```",
                )
            )
            await self.send_clue()
        else:
            await self.channel.send(
                embed=DefaultEmbed(
                    title=localize("😔 No one found the solution."),
                    description=localize_fmt(
                        "The answer was **{answer}**.", answer=game.substance
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

        file = File(game.schematic, filename="schematic.png")

        embed = DefaultEmbed(
            title=localize_fmt("🚀 {user} started a new game!", user=interaction.user),
            description=localize("What substance is this?"),
        ).set_image(url="attachment://schematic.png")

        await interaction.response.send_message(embed=embed, file=file)

        self.create_task(self.send_clue)

        return self

    async def send_end_message(self, interaction):
        await interaction.response.send_message(
            embed=DefaultEmbed(
                title=localize_fmt("🛑 {user} ended the game.", user=interaction.user),
                description=localize_fmt(
                    "The answer was **{answer}**.", answer=self.game.substance
                ),
            ),
            view=await self.make_end_view(),
        )

    async def make_end_view(self):
        """Return a Discord view used to decorate end game embeds."""
        view = ReplayView(callback=self.replay)

        substance = None

        try:
            # Short timeout because the "what's that?" button is not mandatory, plus a
            # response is needed in less than 3 seconds when triggered by the game end
            # application command
            substance = await pnwiki.get_substance(self.game.substance, timeout=2)
        except TimeoutException:
            log.warning("Unable to reach PsychonautWiki API")

        # The PNW API might not return data if the substance is a draft
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


class StructureGameCog(Cog, name="Structure game module"):
    def __init__(self, bot):
        self.bot = bot

    @property
    def scoreboard(self):
        return self.bot.get_cog("Games module").scoreboard

    @Cog.listener()
    async def on_ready(self):
        await StructureGame.prepare_registry()

    @Cog.listener()
    async def on_message(self, msg):
        if (
            msg.is_system()
            or msg.author.bot
            or not (running_game := RunningStructureGame.get_from_context(msg))
        ):
            return

        set_locale(running_game.locale)

        await running_game.check_answer(msg)

    # See comment in cog_load method below to get why command decorators are not used
    async def structure(self, interaction):
        """`/game structure` command"""
        try:
            game = StructureGame()
        except SchematicRegistry.UnfetchedRegistryError:
            await interaction.response.send_message(
                embed=ErrorEmbed(
                    localize("The Structure Game is warming up"),
                    localize("Please retry in a few moments!"),
                )
            )
            return

        await RunningStructureGame.start(interaction, game, self.scoreboard)

    structure.description = _(
        "Start a new Structure Game. The first player to guess the molecule in the "
        "chat wins."
    )
    structure.extras = {
        "long_description": _(
            "Start a new Structure Game. The bot will pick a random molecule "
            "schematic, and the first player to write its name in the chat wins.\n\n"
            "A certain number of coins (🪙), corresponding to the number of letters "
            "guessed, will be awarded to the winner.\n\n"
            "Original idea from arli."
        )
    }

    async def cog_load(self):
        # Register the method as a subcommand of the `games_group` shared command group.
        # This workaround is needed to keep matching slash-command signatures.
        cmd = command(
            description=self.structure.description,
            extras=self.structure.extras,
        )(self.structure)
        games_group.add_command(cmd)

        # Update the shared command group in the command tree
        self.bot.tree.add_command(games_group, override=True)


setup = setup_cog(StructureGameCog)
