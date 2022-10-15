import json
import logging
from collections import defaultdict
from itertools import chain, count, islice
from math import ceil
from operator import itemgetter

from discord import ButtonStyle
from discord.ext.tasks import loop
from discord.ui import View, button

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed, ErrorEmbed
from psychotropic.utils import format_user, pretty_list


log = logging.getLogger(__name__)


class ReplayView(View):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    @button(label="Play again", style=ButtonStyle.primary, emoji="🏓")
    async def replay(self, interaction, button):
        await self.callback(interaction)


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
