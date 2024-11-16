import asyncio as aio
import re
import unicodedata
from random import sample

import httpx
from mistune.renderers.markdown import MarkdownRenderer


class DiscordMarkdownRenderer(MarkdownRenderer):
    """Convert the Markdown of the Mixtures API, which uses all sort of
    CommonMark features, to the restricted subset Discord uses.
    """
    
    def link(self, token, state):
        """Inline reference-style links."""
        token.pop('label', None)

        return super().link(token, state)

    def render_referrences(self, state):
        """Hide inlined link referrences."""
        return []


def is_deleted(user):
    """Workaround to check if a user account was deleted, as Discord API
    does not provide a proper way to do this."""
    return re.match(r"^deleted_user_[a-z0-9]{12}$", str(user))


def format_user(user):
    """Pretty string representation of an user using Discord-flavored
    markdown."""
    if is_deleted(user):
        return "~~Deleted user~~"
    return f"**{user.display_name}**"


def trim_text(text, limit=1024, url=None):
    text = text.strip()

    if url:
        link = f"\n[**Read more**]({url})"
        limit -= len(link)

    if len(text) > limit:
        text = text[:limit-3] + '...' + (link if url else '')

    return text


def pretty_list(items, capitalize=True):
    lst, chars = [], 0
    for item in items:
        item = item.strip()
        if not item:
            continue
        if capitalize:
            item = item.capitalize()
        
        chars += len(item)
        if chars > 2040:
            lst.append("● ...")
            break
        lst.append(f"● {item}")
    return '\n'.join(lst)


def setup_cog(cog):
    """Helper function to be used in cog modules. Usage:
    setup = setup_cog(MyAwesomeCog)
    """
    return lambda bot: bot.add_cog(cog(bot))


def unaccent(string):
    """Return an unaccented version of a string."""
    return (unicodedata.normalize('NFKD', string)
        .encode('ASCII', 'ignore')
        .decode('utf-8')
    )


def shuffled(collection):
    """Not inplace equivalent to usual random.shuffle."""
    return sample(collection, len(collection))


class ThrottledAsyncClient(httpx.AsyncClient):
    """An `httpx.AsyncClient` with a rate limit on the `get` method."""
    def __init__(self, *args, cooldown=0.1, **kwargs):
        super().__init__(*args, **kwargs)
        self.cooldown = cooldown
        self.semaphore = aio.BoundedSemaphore(1)
    
    async def wait_and_release(self):
        await aio.sleep(self.cooldown)
        self.semaphore.release()

    async def get(self, *args, **kwargs):
        await self.semaphore.acquire()
        
        r = await super().get(*args, **kwargs)
        aio.get_event_loop().create_task(self.wait_and_release())
        return r
