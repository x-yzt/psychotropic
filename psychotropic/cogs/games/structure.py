import asyncio as aio
import logging
from functools import partial
from random import choice

from discord import ButtonStyle, File
from discord.app_commands import Group, Range
from discord.ext.commands import Cog
from discord.ui import Button

from psychotropic import settings
from psychotropic.cogs.games import ReplayView, BaseRunningGame, Scoreboard
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.providers import pnwiki
from psychotropic.ui import Paginator
from psychotropic.utils import setup_cog, shuffled, unaccent


log = logging.getLogger(__name__)


class SchematicRegistry:
    def __init__(self, path):
        path.mkdir(parents=True, exist_ok=True)

        self.path = path
        self.schematics = []
    
    async def fetch_schematics(self):
        """Populate the list of all substances to play the game with from
        PNWiki."""
        if settings.FETCH_SCHEMATICS:
            log.info("Populating cache with schematics from PNWiki...")

            for substance in await pnwiki.list_substances():
                image_path = self.build_schematic_path(substance)
                if image_path.exists():
                    continue

                image = await pnwiki.get_schematic_image(
                    substance,
                    width=600,
                    background_color='WHITE'
                )
                if image:            
                    image.save(image_path)

        self.schematics = list(self.path.glob('*.png'))

        log.info(f"{len(self.schematics)} schematics avalaible in cache")
    
    @property
    def schematics(cls):
        if not cls._schematics:
            raise cls.UnfetchedRegistryError()
        return cls._schematics
    
    @schematics.setter
    def schematics(self, value):
        self._schematics = value

    def pick_substance(self):
        """Pick a random substance name from what is avalaible in the 
        registry."""
        return choice(self.schematics).stem

    def build_schematic_path(self, substance):
        """Build the path of a given substance's schematic. There is no
        guarantee this path will actually exist."""
        return self.path / (substance + '.png')

    def get_schematic(self, substance):
        """Get the path of a given substance's schematic, raises an
        exception if no schematic is found for this substance."""
        path = self.build_schematic_path(substance)

        if path not in self.schematics:
            raise FileNotFoundError()
        
        return path
    
    class UnfetchedRegistryError(RuntimeError):
        def __init__(self, *args):
            super().__init__(
                "SchematicRegistry needs schematics to be cached before they "
                "are used. Please `await` for `fetch_schematics`.",
                *args
            )


class StructureGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    # This is where molecules schematics will be downloaded
    CACHE_DIR = settings.STORAGE_DIR / 'cache' / 'schematics'

    # Non-word chars often encoutered in substance names
    NON_WORD = '();-, '

    schematic_registry = SchematicRegistry(CACHE_DIR)

    def __init__(self):
        """To populate the substance registry, `prepare_registry` must be
        awaited before instanciation."""
        self.substance = self.schematic_registry.pick_substance()
        self.secret_chars = shuffled([
            i for i, c in enumerate(self.substance)
            if c not in self.NON_WORD
        ])
        self.guess_len = len(self.secret_chars)
        self.tries = 0
    
    @property
    def schematic(self):
        return self.schematic_registry.get_schematic(self.substance)

    @property
    def clue(self):
        return ''.join(
            c if c in self.NON_WORD or i not in self.secret_chars else '_'
            for i, c in enumerate(self.substance)
        )
    
    @property
    def reward(self):
        return len(self.secret_chars) / (1 if self.tries <= 1 else 2)

    def is_correct(self, guess):
        """Check if a string contains an unformated substring of the right
        answer and increment the tries counter."""
        self.tries += 1
        return self.unformat(self.substance) in self.unformat(guess)
    
    def get_clue(self):
        """Generate a new, easier clue and return it."""
        for _ in range(max(1, self.guess_len // 4)):
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

    @staticmethod
    def unformat(string):
        """Return an unformatted version of a string, stripping some special 
        chars. This is used for approximate answer comparsion."""
        return ''.join(
            c for c in unaccent(string.lower())
            if c not in StructureGame.NON_WORD
        )
    

class RunningStructureGame(BaseRunningGame):
    async def make_end_view(self, callback):
        """Return a Discord view used to decorate end game embeds."""
        substance = await pnwiki.get_substance(self.game.substance)

        view = ReplayView(callback)
        view.add_item(Button(
            label="What's that?",
            style=ButtonStyle.url,
            emoji="🌐",
            url=substance['url']
        ))

        return view


class StructureGameCog(Cog, name='Structure Game module'):
    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = Scoreboard()
        self.scoreboard.load()
        self.scoreboard.save.start()
    
    @Cog.listener()
    async def on_ready(self):
        await StructureGame.prepare_registry()
    
    @Cog.listener()
    async def on_message(self, msg):
        if msg.is_system() or msg.author.bot:
            return

        running_game = RunningStructureGame.registry.get(msg.channel.id)
        if not running_game:
            return
        
        game = running_game.game
        
        if game.is_correct(msg.content):
            time = running_game.time_since_start.total_seconds()
            running_game.end()
            self.scoreboard[str(msg.author.id)] += game.reward

            file = File(game.schematic, filename='schematic.png')
            embed = (
                DefaultEmbed(
                    title=f"✅ Correct answer, {msg.author}!",
                    description=f"Well played! The answer was **{game.substance}**."
                )
                .set_thumbnail(url='attachment://schematic.png')
                .add_field(
                    name="⏱️ Elapsed time",
                    value=f"You answered in {time:.2f} seconds."
                )
                .add_field(
                    name="🪙 Reward",
                    value=f"You won **{game.reward} coins**."
                )
            )
            if game.tries == 1:
                embed.add_field(
                    name="🥇 First try bonus!",
                    value="Yay!"
                )
            view = await running_game.make_end_view(
                partial(self.start.callback, self)
            )
            
            await msg.channel.send(embed=embed, file=file, view=view)

    game = Group(name='game', description="Manage structure games.")

    @game.command(name='start')
    async def start(self, interaction):
        """Start a new Structure Game. The bot will pick a random molecule
        schematic, and the first player to write its name in the chat will win.

        A certain number of coins (🪙), corresponding to the number of letters
        guessed will be awarded to the winner.

        Original idea from arli.
        """
        if RunningStructureGame.get_from_context(interaction):
            await interaction.response.send_message(embed=ErrorEmbed(
                "Another game is running in this channel!",
                "Please end the current game before starting another one."
            ))
            return
    
        try:
            game = StructureGame()
        except SchematicRegistry.UnfetchedRegistryError:
            await interaction.response.send_message(embed=ErrorEmbed(
                "The Structure Game is warming up",
                "Please retry in a few moments!"
            ))
            return

        running_game = RunningStructureGame(game, interaction)

        file = File(game.schematic, filename='schematic.png')  
        embed = (
            DefaultEmbed(
                title=f"🚀 {interaction.user} started a new game!",
                description="What substance is this?"
            )
            .set_image(url='attachment://schematic.png')
        )
        await interaction.response.send_message(embed=embed, file=file)

        async def send_clue():
            await aio.sleep(10)
            clue = game.get_clue()
            
            if game.secret_chars:
                await interaction.followup.send(embed=DefaultEmbed(
                    title=f"💡 Here's a bit of help:",
                    description=f"```{clue}```"
                ))
                await send_clue()
            else:
                await interaction.followup.send(
                    embed = DefaultEmbed(
                        title = "😔 No one found the solution.",
                        description = f"The answer was **{game.substance}**."
                    ),
                    view = await running_game.make_end_view(
                        partial(self.start.callback, self)
                    )  
                )
                running_game.end()

        running_game.create_task(send_clue)

    @game.command(name='end')
    async def end(self, interaction):
        """End a running Structure Game. To end a game, you must either own it
        or have permission to manage messages in the current channel.
        """
        running_game = RunningStructureGame.get_from_context(interaction)

        if not running_game:
            await interaction.response.send_message(embed=ErrorEmbed(
                "There is no game running in this channel!",
            ))
            return
        
        if not running_game.can_be_ended(interaction):
            await interaction.response.send_message(embed=ErrorEmbed(
                "You are not allowed to end this game!",
                "You need to own this game or have permission to manage "
                "messages in this channel."
            ))
            return
        
        running_game.end()
        
        await interaction.response.send_message(
            embed = DefaultEmbed(
                title = f"🛑 {interaction.user} ended the game.",
                description = f"The answer was **{running_game.game.substance}**."
            ),
            view = await running_game.make_end_view(
                partial(self.start.callback, self)
            )  
        )
    
    @game.command(name='scores')
    async def scores(self, interaction, page: Range[int, 1] = 1):
        """Show a given page of the scoreboard."""
        await interaction.response.defer(thinking=True)

        await interaction.followup.send(
            embed = await self.scoreboard.make_embed(self.bot, page),
            view = Paginator(
                make_embed = partial(self.scoreboard.make_embed, self.bot),
                page = page,
                last_page = self.scoreboard.page_count
            )
        )


setup = setup_cog(StructureGameCog)
