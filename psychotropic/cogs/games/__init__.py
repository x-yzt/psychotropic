import asyncio as aio
import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import partial
from io import BytesIO
from itertools import chain, count, islice
from json import JSONDecoder, JSONEncoder
from math import ceil

from discord import ButtonStyle, Embed, File, Member, User
from discord.app_commands import Group, Range, command
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog
from discord.ext.tasks import loop
from discord.ui import View, button

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.i18n import get_locale, localize, localize_fmt, set_locale
from psychotropic.ui import Paginator
from psychotropic.utils import (
    format_user,
    make_progress_bar,
    memoize_method,
    pretty_list,
    setup_cog,
)

log = logging.getLogger(__name__)


class ReplayView(View):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.locale = get_locale()

    @button(label=localize("Play again"), style=ButtonStyle.primary, emoji="🏓")
    async def replay(self, interaction, button):
        # Callbacks are not executed in the same asyncio context as
        # `bot.global_interaction_check`, hence the locale needs to be manually set
        set_locale(self.locale)

        await self.callback(interaction)


class BaseRunningGame:
    """This base class encapsulates game related, Discord-aware logic."""

    # A registry of all running games. Keys are Discord channels, values are class
    # instances.
    registry = {}

    def __init__(self, interaction, game, scoreboard):
        self.game = game
        self.scoreboard = scoreboard
        self.owner = interaction.user
        self.channel = interaction.channel
        self.locale = str(interaction.locale)
        self.start_time = datetime.now()
        self.tasks = set()
        self.registry[self.channel.id] = self

        log.info(f"Started {self}")

    @property
    def time_since_start(self):
        return datetime.now() - self.start_time

    def can_be_ended(self, interaction):
        """Check if this running game can be ended in a given interaction context."""
        return interaction.user == self.owner or interaction.permissions.manage_messages

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
        """Create a new instance of this class in a given interaction context by
        instancing a new underlying game object and using the same scoreboard."""
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
        """Get a running game from an interaction context. Return `None` if an instance
        of another `BaseGame` class or if no game are running in this context."""
        running_game = cls.registry.get(interaction.channel.id)

        if isinstance(running_game, cls):
            return running_game

    @classmethod
    async def start(cls, interaction, *args, **kwargs):
        """Try to start a new game in a given interaction context and return it. Returns
        `None` if the game can't be created."""
        if BaseRunningGame.get_from_context(interaction):
            await interaction.response.send_message(
                embed=ErrorEmbed(
                    localize("Another game is running in this channel!"),
                    localize(
                        "Please end the current game before starting another one."
                    ),
                )
            )
            return

        return cls(interaction, *args, **kwargs)


@dataclass
class Profile:
    """Represents a player profile data."""

    balance: float = 0
    found_structure_substances: set[str] = field(default_factory=set)
    won_structure_games: int = 0
    won_reagents_games: int = 0

    @property
    def won_games(self):
        return self.won_structure_games + self.won_reagents_games

    @property
    @memoize_method(("balance",))
    def level(self):
        """Current player level."""
        return max(
            filter(lambda lvl: self.balance >= lvl["threshold"], settings.LEVELS),
            key=lambda lvl: lvl["threshold"],
        )

    @property
    @memoize_method(("balance",))
    def next_level(self):
        """Next player level. `None` if the player has outreached the last level
        threshold."""
        try:
            return min(
                filter(
                    lambda lvl: lvl["threshold"] > self.level["threshold"],
                    settings.LEVELS,
                ),
                key=lambda lvl: lvl["threshold"],
            )
        except ValueError:
            return

    @property
    @memoize_method(("balance",))
    def next_level_in(self):
        return (
            self.next_level["threshold"] - self.balance
            if self.next_level
            else float("inf")
        )

    @property
    @memoize_method(("balance",))
    def level_progress(self):
        """Progress beween current and next level as a [0, 1] value."""
        if not self.next_level:
            return 1

        return (self.balance - self.level["threshold"]) / (
            self.next_level["threshold"] - self.level["threshold"]
        )


class ScoreboardJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, Profile):
            return asdict(o) | {"__type__": "Profile"}

        elif isinstance(o, set):
            return list(o)

        return super().default(o)


class ScoreboardJSONDecoder(JSONDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, object_hook=self.object_hook, **kwargs)

    def object_hook(self, obj):
        if obj.pop("__type__", None) == "Profile":
            return Profile(**obj)

        return obj


class Scoreboard:
    """This class encapsulates scoreboard related logic."""

    SCOREBOARD_PATH = settings.STORAGE_DIR / "players.json"

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
            with open(self.SCOREBOARD_PATH, "w") as file:
                json.dump({}, file, cls=ScoreboardJSONEncoder)

        with open(self.SCOREBOARD_PATH) as file:
            self.players.update(json.load(file, cls=ScoreboardJSONDecoder))

        log.info(f"Loaded {len(self.players)} scoreboard entries from FS")

    @loop(seconds=60)
    async def save(self):
        """Asynchronously save current scoreboard to filesystem."""
        with open(self.SCOREBOARD_PATH, "w") as file:
            json.dump(self.players, file, cls=ScoreboardJSONEncoder)

        log.debug(f"Saved {len(self.players)} scoreboard entries to FS")

    def top_players(self):
        """Returns the players by descending balance."""
        return sorted(
            self.players.items(), key=lambda player: player[1].balance, reverse=True
        )

    def rank(self, player):
        """Get the rank of a player. Return 0 if the player is not
        ranked in the scoreboard."""
        if isinstance(player, Member | User):
            player = player.id

        try:
            return (
                next(
                    i
                    for i, (uid, profile) in enumerate(self.top_players())
                    if uid == str(player)
                )
                + 1
            )
        except StopIteration:
            return 0

    async def make_embed(self, client, page):
        """Generate an embed showing the scoreboard at a given page."""
        bounds = self.PAGE_LEN * (page - 1), self.PAGE_LEN * page

        scores = [
            "**{emoji}** - {user} - `{score} 🪙`".format(
                emoji=emoji,
                user=format_user(await client.fetch_user(uid)),
                score=int(profile.balance),
            )
            for emoji, (uid, profile) in islice(
                zip(chain("🥇🥈🥉", count(4)), self.top_players()), *bounds
            )
        ]

        embed = ErrorEmbed(localize("Empty page"))
        if scores:
            embed = DefaultEmbed(
                title=localize("🏆 Scoreboard"),
                description=pretty_list(scores, capitalize=False),
            )

        return embed.add_field(
            name=localize("📄 Page number"),
            value=f"**{page}** / **{self.page_count}**",
        )


games_group = Group(name="game", description=_("Manage and play games."))


class GamesCog(Cog, name="Games module"):
    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = Scoreboard()
        self.scoreboard.load()
        self.scoreboard.save.start()

    # Descriptions have to be explicit strings so they can be extracted for localization
    # See comment in cog_load method below to get why command decorators are not used

    async def start(self, interaction):
        """`/game start` command"""
        await interaction.response.send_message(
            embed=ErrorEmbed(
                localize("The `/game start` command is obsolete!"),
                localize("Please use `/game structure` instead.`"),
            )
        )

    start.description = _("Obsolete command. Please use `/game structure` instead.")

    async def scores(self, interaction, page: Range[int, 1] = 1):
        """`/game scores` command"""
        await interaction.response.defer(thinking=True)

        await interaction.followup.send(
            embed=await self.scoreboard.make_embed(self.bot, page),
            view=Paginator(
                make_embed=partial(self.scoreboard.make_embed, self.bot),
                page=page,
                last_page=self.scoreboard.page_count,
            ),
        )

    scores.description = _("Show a given page of the scoreboard.")

    async def profile(self, interaction, member: Member | None = None):
        """`/game profile` command"""
        member = member or interaction.user

        profile = self.scoreboard[member]
        rank = self.scoreboard.rank(member)
        ratio = profile.balance / profile.won_games if profile.won_games else 0

        progress_bar = make_progress_bar(
            profile.level_progress,
            color=profile.level["color"].to_rgb(),
            width=600,
            height=40,
        )

        embed = (
            Embed(
                title=localize_fmt("👤 {user}'s profile", user=member),
                colour=profile.level["color"],
            )
            .add_field(
                name=localize("⚖️ Balance"),
                value=localize_fmt(
                    "You own **{balance} 🪙**.", balance=profile.balance
                ),
                inline=False,
            )
            .add_field(
                name=localize("🎚️ Level"),
                value=localize_fmt(
                    "You're currently at the **{lvl}** level.",
                    lvl=profile.level["name"],
                ),
                inline=False,
            )
            .add_field(
                name=localize("🏆 Rank"),
                value=(
                    localize_fmt(
                        "You're ranked **{rank}** out of {total} players.",
                        # Small magic trick here: 0 corresponds to an
                        # unranked player
                        rank="🚫🥇🥈🥉"[rank] if rank <= 3 else rank,
                        total=len(self.scoreboard),
                    )
                ),
                inline=False,
            )
            .add_field(
                name=localize("🎮 Won games"),
                value=localize_fmt(
                    "- __Structure games:__ {structure_games}\n"
                    "- __Reagents games:__ {reagents_games}\n"
                    "*({ratio:.2f} 🪙 / game)*",
                    structure_games=profile.won_structure_games,
                    reagents_games=profile.won_reagents_games,
                    ratio=ratio,
                ),
            )
            .set_image(url="attachment://progress.png")
            .set_thumbnail(url=member.display_avatar.url)
        )

        if profile.next_level_in != float("inf"):
            embed.set_footer(
                text=localize_fmt(
                    "⏫ Next level in {amount} 🪙", amount=profile.next_level_in
                )
            )

        with BytesIO() as buffer:
            progress_bar.save(buffer, format="PNG")
            buffer.seek(0)
            file = File(fp=buffer, filename="progress.png")

            await interaction.response.send_message(embed=embed, file=file)

    profile.description = _(
        "Display profile information and game statistics about yourself or another "
        "player."
    )

    async def end(self, interaction):
        """`/game end` command"""
        running_game = BaseRunningGame.get_from_context(interaction)

        if not running_game:
            await interaction.response.send_message(
                embed=ErrorEmbed(
                    localize("There is no game running in this channel!"),
                )
            )
            return

        if not running_game.can_be_ended(interaction):
            await interaction.response.send_message(
                embed=ErrorEmbed(
                    localize("You are not allowed to end this game!"),
                    localize(
                        "You need to own this game or have permission to manage "
                        "messages in this channel."
                    ),
                )
            )
            return

        await running_game.end()
        await running_game.send_end_message(interaction)

    end.description = _(
        "End a running game. You must either own it or have permission to manage "
        "messages in this channel."
    )

    async def cog_load(self):
        # Register some methods as subcommands of the `games_group` shared command
        # group. This workaround is needed to keep matching slash-command signatures.
        for method in ("start", "scores", "profile", "end"):
            method = getattr(self, method)
            cmd = command(description=method.description)(method)
            games_group.add_command(cmd)

        # Manually add the shared group to the tree
        self.bot.tree.add_command(games_group)


setup = setup_cog(GamesCog)
setup = setup_cog(GamesCog)
