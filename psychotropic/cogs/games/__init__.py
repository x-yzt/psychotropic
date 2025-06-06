import asyncio as aio
import json
import logging
from collections import defaultdict
from datetime import datetime
from functools import partial
from itertools import chain, count, islice
from math import ceil
from operator import itemgetter

from discord import ButtonStyle
from discord.app_commands import Group, Range, command
from discord.ext.commands import Cog
from discord.ext.tasks import loop
from discord.ui import View, button

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.ui import Paginator
from psychotropic.utils import format_user, pretty_list, setup_cog


log = logging.getLogger(__name__)


class ReplayView(View):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @button(label="Play again", style=ButtonStyle.primary, emoji="🏓")
    async def replay(self, interaction, button):
        await self.callback(interaction)


class BaseRunningGame:
    """This base class encapsulates game related, Discord-aware logic."""

    # A registry of all running games. Keys are Discord channels, values are
    # class instances. 
    registry = {}

    def __init__(self, interaction, game, scoreboard):
        self.game = game
        self.scoreboard = scoreboard
        self.owner = interaction.user
        self.channel = interaction.channel
        self.start_time = datetime.now()
        self.tasks = set()
        self.registry[self.channel.id] = self

        log.info(f"Started {self}")

    @property
    def time_since_start(self):
        return datetime.now() - self.start_time

    def can_be_ended(self, interaction):
        """Check if this running game can be ended in a given interaction
        context."""
        return (
            interaction.user == self.owner
            or interaction.permissions.manage_messages
        )

    async def end(self):
        """End a running game. This will cancel all pending tasks."""
        for task in self.tasks:
            task.cancel()
        
        # Only pop the registry value if it actually holds a reference to this
        # instance, as we don't want to remove another instance currently
        # running in the same channel
        if self.registry.get(self.channel.id) is self:
            self.registry.pop(self.channel.id)

        log.info(f"Ended {self}")
    
    async def send_end_message(self, interaction):
        raise NotImplementedError

    async def replay(self, interaction):
        """Create a new instance of this class in a given interaction 
        context by instancing a new underlying game object and using the
        same scoreboard."""
        await type(self).start(interaction, type(self.game)(), self.scoreboard)
    
    def create_task(self, function):
        """Create a new asyncio task tied to this instance. The task must be a
        coroutine, and will be cancelled if the game is ended."""
        task = aio.get_event_loop().create_task(function())
        task.add_done_callback(lambda task: self.tasks.remove(task))

        self.tasks.add(task)

    def __str__(self):
        return f"{self.game} in {self.channel}"

    @classmethod
    def get_from_context(cls, interaction):
        """Get a running game from an interaction context. Return `None`
        if an instance of another `BaseGame` class or if no game are
        running in this context."""
        running_game = cls.registry.get(interaction.channel.id)

        if isinstance(running_game, cls):
            return running_game

    @classmethod
    async def start(cls, interaction, *args, **kwargs):
        """Try to start a new game in a given interaction context and
        return it. Returns `None` if the game can't be created."""
        if BaseRunningGame.get_from_context(interaction):
            await interaction.response.send_message(embed=ErrorEmbed(
                "Another game is running in this channel!",
                "Please end the current game before starting another one."
            ))
            return

        return cls(interaction, *args, **kwargs)


class Scoreboard:
    """This class encapsulated scoreboard related logic."""
    SCORES_PATH = settings.STORAGE_DIR / 'scores.json'

    PAGE_LEN = 15

    def __init__(self):
        self.scores = defaultdict(lambda: 0)
    
    def __setitem__(self, player, score):
        self.scores[player] = score
       
    def __getitem__(self, player):
        return self.scores[player]

    @property
    def page_count(self):
        return ceil(len(self.scores) / self.PAGE_LEN)

    def load(self):
        """Synchronously load scoreboard from filesystem."""
        self.SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.SCORES_PATH.exists():
            with open(self.SCORES_PATH, 'w') as f:
                json.dump({}, f)
        
        with open(self.SCORES_PATH) as f:
            self.scores.update(json.load(f))
        
        log.info(f"Loaded {len(self.scores)} scoreboard entries from FS")
    
    @loop(seconds=60)
    async def save(self):
        """Asynchronously save current scoreboard to filesystem."""
        with open(self.SCORES_PATH, 'w') as f:
            json.dump(self.scores, f)
        
        log.debug(f"Saved {len(self.scores)} scoreboard entries to FS")

    async def make_embed(self, client, page):
        """Generate an embed showing the scoreboard at a given page."""
        bounds = self.PAGE_LEN * (page-1), self.PAGE_LEN * page

        scores = [
            "**{emoji}** - {user} - `{score} 🪙`".format(
                emoji = emoji,
                user = format_user(await client.fetch_user(uid)),
                score = int(score)
            )
            for emoji, (uid, score) in islice(zip(
                chain("🥇🥈🥉", count(4)),
                sorted(
                    self.scores.items(),
                    key = itemgetter(1),
                    reverse = True
                )
            ), *bounds)
        ]

        embed = ErrorEmbed("Empty page")
        if scores:
            embed = DefaultEmbed(
                title = "🏆 Scoreboard",
                description = pretty_list(scores, capitalize=False)
            )

        return embed.add_field(
            name = "📄 Page number",
            value = f"**{page}** / **{self.page_count}**"
        )


games_group = Group(name='game', description="Manage and play games.")


class GamesCog(Cog, name="Games module"):
    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = Scoreboard()
        self.scoreboard.load()
        self.scoreboard.save.start()

    async def start(self, interaction):
        """Obsolete command. Please use `/game structure` instead."""
        await interaction.response.send_message(embed=ErrorEmbed(
            "The `/game start` command is obsolete!",
            "Please use `/game structure` instead.`"
        ))

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
    
    async def end(self, interaction):
        """End a running game. To end a game, you must either own it
        or have permission to manage messages in the current channel.
        """
        running_game = BaseRunningGame.get_from_context(interaction)

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
        
        await running_game.end()
        await running_game.send_end_message(interaction)

    async def cog_load(self):
        # Register some methods as subcommands of the `games_group`
        # shared command group. This workaround is needed to keep
        # matching slash-command signatures.
        for method in ('start', 'scores', 'end'):
            cmd = command()(getattr(self, method))
            games_group.add_command(cmd)

        # Manually add the shared group to the tree
        self.bot.tree.add_command(games_group)

setup = setup_cog(GamesCog)
