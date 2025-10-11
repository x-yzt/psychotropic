import asyncio as aio
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from functools import partial
from io import BytesIO
from itertools import chain, count, islice
from json import JSONDecoder, JSONEncoder
from math import ceil
from typing import Optional

from discord import ButtonStyle, Embed, File, Member, User
from discord.app_commands import Group, Range, command
from discord.ext.commands import Cog
from discord.ext.tasks import loop
from discord.ui import View, button

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.ui import Paginator
from psychotropic.utils import (
    format_user, make_progress_bar, memoize_method, pretty_list, setup_cog)


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


@dataclass
class Profile:
    """Represents a player profile data."""
    balance: float = 0
    won_structure_games: int = 0
    won_reagents_games: int = 0

    @property
    def won_games(self):
        return self.won_structure_games + self.won_reagents_games

    @property
    @memoize_method(('balance',))
    def level(self):
        """Current player level."""
        return max(
            filter(
                lambda lvl: self.balance >= lvl['threshold'],
                settings.LEVELS
            ),
            key=lambda lvl: lvl['threshold']
        )

    @property
    @memoize_method(('balance',))
    def next_level(self):
        """Next player level. `None` if the player has outreached the
        last level threshold."""
        try:
            return min(
                filter(
                    lambda lvl: lvl['threshold'] > self.level['threshold'],
                    settings.LEVELS
                ),
                key=lambda lvl: lvl['threshold']
            )
        except ValueError:
            return
    
    @property
    @memoize_method(('balance',))
    def next_level_in(self):
        return (
            self.next_level['threshold'] - self.balance
            if self.next_level
            else float('inf')
        )

    @property
    @memoize_method(('balance',))
    def level_progress(self):
        """Progress beween current and next level as a [0, 1] value."""
        if not self.next_level:
            return 1
    
        return (
            (self.balance - self.level['threshold'])
            / (self.next_level['threshold'] - self.level['threshold'])
        )


class ScoreboardJSONEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Profile):
            return asdict(obj) | {'__type__': 'Profile'}

        return super().default(obj)


class ScoreboardJSONDecoder(JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj):
        if obj.pop('__type__', None) == 'Profile':
            return Profile(**obj)
        
        return obj


class Scoreboard:
    """This class encapsulates scoreboard related logic."""
    SCOREBOARD_PATH = settings.STORAGE_DIR / 'players.json'

    PAGE_LEN = 15

    def __init__(self):
        self.players = defaultdict(lambda: Profile())

    def __len__(self):
        return len(self.players)

    def __setitem__(self, player, profile):
        assert isinstance(profile, Profile)

        if isinstance(player, Member | User):
            player = player.id
        
        self.players[str(player)] = profile
       
    def __getitem__(self, player):
        if isinstance(player, Member | User):
            player = player.id
        
        return self.players[str(player)]

    @property
    def page_count(self):
        return ceil(len(self.players) / self.PAGE_LEN)

    def load(self):
        """Synchronously load scoreboard from filesystem."""
        self.SCOREBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.SCOREBOARD_PATH.exists():
            with open(self.SCOREBOARD_PATH, 'w') as file:
                json.dump({}, file, cls=ScoreboardJSONEncoder)
        
        with open(self.SCOREBOARD_PATH) as file:
            self.players.update(json.load(file, cls=ScoreboardJSONDecoder))
        
        log.info(f"Loaded {len(self.players)} scoreboard entries from FS")
    
    @loop(seconds=60)
    async def save(self):
        """Asynchronously save current scoreboard to filesystem."""
        with open(self.SCOREBOARD_PATH, 'w') as file:
            json.dump(self.players, file, cls=ScoreboardJSONEncoder)

        log.debug(f"Saved {len(self.players)} scoreboard entries to FS")

    def top_players(self):
        """Returns the players by descending balance."""
        return sorted(
            self.players.items(),
            key=lambda player: player[1].balance,
            reverse=True
        )

    def rank(self, player):
        """Get the rank of a player. Return 0 if the player is not
        ranked in the scoreboard."""
        if isinstance(player, Member | User):
            player = player.id

        try:
            return next(
                i for i, (uid, profile) in enumerate(self.top_players())
                if uid == str(player)
            ) + 1
        except StopIteration:
            return 0

    async def make_embed(self, client, page):
        """Generate an embed showing the scoreboard at a given page."""
        bounds = self.PAGE_LEN * (page-1), self.PAGE_LEN * page

        scores = [
            "**{emoji}** - {user} - `{score} 🪙`".format(
                emoji = emoji,
                user = format_user(await client.fetch_user(uid)),
                score = int(profile.balance)
            )
            for emoji, (uid, profile) in islice(
                zip(chain("🥇🥈🥉", count(4)), self.top_players()),
                *bounds
            )
        ]

        embed = ErrorEmbed("Empty page")
        if scores:
            embed = DefaultEmbed(
                title="🏆 Scoreboard",
                description=pretty_list(scores, capitalize=False)
            )

        return embed.add_field(
            name="📄 Page number",
            value=f"**{page}** / **{self.page_count}**"
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

    async def profile(self, interaction, member: Optional[Member] = None):
        """Display profile information and game statistics for a player.
        If no player is provided, your information will be displayed.
        """
        member = member or interaction.user

        profile = self.scoreboard[member]
        rank = self.scoreboard.rank(member)
        ratio = (
            profile.balance / profile.won_games
            if profile.won_games else 0
        )

        progress_bar = make_progress_bar(
            profile.level_progress,
            color=profile.level['color'].to_rgb(),
            width=600,
            height=40
        )

        embed = (
            Embed(
                title=f"👤 {member}'s profile",
                colour=profile.level['color']
            )
            .add_field(
                name="⚖️ Balance",
                value=f"You own **{profile.balance} 🪙**.",
                inline=False
            )
            .add_field(
                name="🎚️ Level",
                value=(
                    f"You're currently at the **{profile.level['name']}** "
                    "level."
                ),
                inline=False
            )
            .add_field(
                name="🏆 Rank",
                value=(
                    "You're ranked **{rank}** out of {total} players."
                    .format(
                        # Small magic trick here: 0 corresponds to an
                        # unranked player
                        rank='🚫🥇🥈🥉'[rank] if rank <= 3 else rank,
                        total=len(self.scoreboard)
                    )
                ),
                inline=False
            )
            .add_field(
                name="🎮 Won games",
                value=(
                    f"- __Structure games:__ {profile.won_structure_games}\n"
                    f"- __Reagents games:__ {profile.won_reagents_games}\n"
                    f"*({ratio:.2f} 🪙 / game)*"
                )
            )
            .set_image(url="attachment://progress.png")
            .set_thumbnail(url=member.display_avatar.url)
        )

        if profile.next_level_in != float('inf'):
            embed.set_footer(
                text=f"⏫ Next level in {profile.next_level_in} 🪙"
            )
        
        with BytesIO() as buffer:
            progress_bar.save(buffer, format="PNG")
            buffer.seek(0)
            file = File(fp=buffer, filename="progress.png")

            await interaction.response.send_message(embed=embed, file=file)

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
        for method in ('start', 'scores', 'profile', 'end'):
            cmd = command()(getattr(self, method))
            games_group.add_command(cmd)

        # Manually add the shared group to the tree
        self.bot.tree.add_command(games_group)

setup = setup_cog(GamesCog)
