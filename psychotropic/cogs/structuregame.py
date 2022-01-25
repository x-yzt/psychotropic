import asyncio as aio
import json
import logging
from collections import defaultdict
from datetime import datetime
from itertools import chain, count, islice
from operator import itemgetter
from random import choice

from discord.ext.commands import Cog, group
from discord.ext.tasks import loop

from psychotropic.embeds import (DefaultEmbed, ErrorEmbed,
    LoadingEmbedContextManager)
from psychotropic.providers import pnwiki
from psychotropic.utils import (pretty_list, setup_cog, classproperty,
    unaccent, shuffled)


log = logging.getLogger(__name__)


class StructureGame:
    """This Discord-agnostic class encapsulates bare game-related logic."""

    # Blacklisted substances that will not be picked
    BLACKLIST = {
        '25H-NBOMe',
        'Antihistamine',
        'Ayahuasca', 
        'Barbiturates',
        'Cannabinoid',
        'Entactogens',
        'Experience: I-Doser (\'audio-drug\') and meditation',
        'MiPLA',
        'Morning glory',
        'Orphenadrine',
        'Stimulants',
    }

    # Non-word chars often encoutered in substance names
    NON_WORD = '();-, '

    # A list of all substances to play the game with
    _substances = []

    def __init__(self):
        self.substance = choice(tuple(self.substances))
        self.secret_chars = shuffled([
            i for i, c in enumerate(self.substance)
            if c not in self.NON_WORD
        ])
        self.guess_len = len(self.secret_chars)
        self.tries = 0
    
    @property
    def schematic_url(self):
        return pnwiki.get_schematic_url(self.substance)
    
    @property
    def clue(self):
        return ''.join(
            c if c in self.NON_WORD or i not in self.secret_chars else '_'
            for i, c in enumerate(self.substance)
        )
    
    @property
    def reward(self):
        return len(self.secret_chars) / (1 if self.tries <= 1 else 2)
    
    @classproperty
    def substances(cls):
        if not cls._substances:
            raise RuntimeError(
                "Substances need to be fetched before a game is created. "
                "Please `await` for `StructureGame.fetch_substances` before "
                "instanciating this class."
            )
        return cls._substances

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
    async def fetch_substances(cls):
        """Populate the list of all substances to play the game with from
        PNWiki."""
        cls._substances = set(await pnwiki.list_substances()) - cls.BLACKLIST

        log.info(f"Fetched {len(cls.substances)} substances from PNWiki")

    @staticmethod
    def unformat(string):
        """Return an unformatted version of a string, stripping some special 
        chars. This is used for approximate answer comparsion."""
        return ''.join(
            c for c in unaccent(string.lower())
            if c not in StructureGame.NON_WORD
        )
    

class RunningGame:
    """This class encapsulates game related, Discord-aware logic."""

    # A registry of all running games. Keys are Discord channels, values are
    # class instances. 
    registry = {}

    def __init__(self, game, ctx):
        self.game = game
        self.owner = ctx.author
        self.channel = ctx.channel
        self.start_time = datetime.now()
        self.tasks = set()
        self.registry[ctx.channel] = self

        log.info(f"Started {self}")
    
    @property
    def time_since_start(self):
        return datetime.now() - self.start_time

    def can_be_ended(self, ctx):
        """Check if a this running game can be ended in a given context."""
        return (
            ctx.author == self.owner
            or ctx.author.permissions_in(ctx.channel).manage_messages
        )
    
    def end(self):
        """End a running game. This will cancel all pending tasks."""
        for task in self.tasks:
            task.cancel()
        self.registry.pop(self.channel, None)

        log.info(f"Ended {self}")
    
    def create_task(self, function):
        """Create a new asyncio task tied to this instance. The task must be a
        coroutine, and will be cancelled if the game is ended."""
        task = aio.get_event_loop().create_task(function())
        task.add_done_callback(lambda task: self.tasks.remove(task))
        
        self.tasks.add(task)
    
    def __del__(self):
        self.end()
    
    def __str__(self):
        return f"{self.game} in {self.channel}"


class StructureGameCog(Cog, name='Structure Game module'):
    PAGE_LEN = 15

    def __init__(self, bot):
        self.bot = bot
        self.scoreboard = defaultdict(lambda: 0)
        self.load_scoreboard()
        self.save_scoreboard.start()
    
    def load_scoreboard(self):
        """Synchronously load scoreboard from filesystem."""
        with open('scores.json') as f:
            self.scoreboard.update(json.load(f))
        
        log.info(f"Loaded {len(self.scoreboard)} scoreboard entries from FS")

    @loop(seconds=60)
    async def save_scoreboard(self):
        """Asynchronously save current scoreboard to filesystem."""
        with open('scores.json', 'w') as f:
            json.dump(self.scoreboard, f)
        
        log.debug(f"Saved {len(self.scoreboard)} scoreboard entries to FS")
    
    @Cog.listener()
    async def on_ready(self):
        await StructureGame.fetch_substances()
    
    @Cog.listener()
    async def on_message(self, msg):
        ctx = await self.bot.get_context(msg)
        if msg.is_system() or msg.author.bot or ctx.valid:
            return
        
        running_game = RunningGame.registry.get(msg.channel)
        if not running_game:
            return
        
        game = running_game.game
        
        if game.is_correct(msg.content):
            time = running_game.time_since_start.total_seconds()
            running_game.end()
            self.scoreboard[msg.author.id] += game.reward

            embed = DefaultEmbed(
                title=f"✅ Correct answer, {msg.author}!",
                description=f"Well played! The answer was **{game.substance}**."
            )
            embed.set_thumbnail(url=game.schematic_url)
            embed.add_field(
                name="⏱️ Elapsed time",
                value=f"You answered in {time:.2f} seconds."
            )
            embed.add_field(
                name="🪙 Reward",
                value=f"You won **{game.reward} coins**."
            )
            if game.tries == 1:
                embed.add_field(
                    name="🥇 First try bonus!",
                    value="Yay!"
                )
            
            await msg.channel.send(embed=embed)
    
    @group()
    async def game(self, ctx):
        """Structure Game command group."""
        ctx.running_game = RunningGame.registry.get(ctx.channel)

    @game.command(aliases=('begin',))
    async def start(self, ctx):
        """Start a new Structure Game. The bot will pick a random molecule
        schematic, and the first player to write its name in the chat will win.

        A certain number of coins (🪙), corresponding to the number of letters
        guessed will be awarded to the winner.
        """
        if ctx.running_game:
            await ctx.send(embed=ErrorEmbed(
                "Another game is running in this channel!",
                "Please end the current game before starting another one."
            ))
            return

        game = StructureGame()
        running_game = RunningGame(game, ctx)

        embed = DefaultEmbed(
            title=f"🚀 {ctx.author} started a new game!",
            description="What substance is this?"
        )
        embed.set_image(url=game.schematic_url)
        await ctx.send(embed=embed)

        async def send_clue():
            await aio.sleep(10)
            clue = game.get_clue()
            
            if game.secret_chars:
                await ctx.send(embed=DefaultEmbed(
                    title=f"💡 Here's a bit of help:",
                    description=f"```{clue}```"
                ))
                await send_clue()
            else:
                await ctx.send(embed=DefaultEmbed(
                    title="😔 No one found the solution.",
                    description=f"The answer was **{game.substance}**."
                ))
                running_game.end()

        running_game.create_task(send_clue)

    @game.command(aliases=('stop', 'quit'))
    async def end(self, ctx):
        """End a running Structure Game. To end a game, you must either own it
        or have permission to manage messages in the current channel.
        """
        if not ctx.running_game:
            await ctx.send(embed=ErrorEmbed(
                "There is no game running in this channel!",
            ))
            return
        
        if not ctx.running_game.can_be_ended(ctx):
            await ctx.send(embed=ErrorEmbed(
                "You are not allowed to end this game!",
                "You need to own this game or have permission to manage "
                "messages in this channel."
            ))
            return
        
        ctx.running_game.end()
        
        ans = ctx.running_game.game.substance
        await ctx.send(embed=DefaultEmbed(
            title=f"🛑 {ctx.author} ended the game.",
            description=f"The answer was **{ans}**."
        ))
    
    @game.command(aliases=('scoreboard', 'board'))
    async def scores(self, ctx, page: int=1):
        """Show a given page of the scoreboard."""
        bounds = self.PAGE_LEN * (page-1), self.PAGE_LEN * page

        async with LoadingEmbedContextManager(ctx):
            scores = [
                "**{emoji} - {user}:** {score} 🪙".format(
                    emoji=emoji,
                    user=await self.bot.fetch_user(uid),
                    score=score
                )
                for emoji, (uid, score) in islice(zip(
                    chain("🥇🥈🥉", count(4)),
                    sorted(
                        self.scoreboard.items(),
                        key=itemgetter(1),
                        reverse=True
                    )
                ), *bounds)
            ]

        if not scores:
            await ctx.send(embed=ErrorEmbed("No such page"))
            return

        embed = DefaultEmbed(
            title="🏆 Scoreboard",
            description=pretty_list(scores, capitalize=False)
        )
        await ctx.send(embed=embed)
    

setup = setup_cog(StructureGameCog)
