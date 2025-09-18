import asyncio as aio
import re
import unicodedata
from itertools import pairwise
from random import sample

import httpx
from mistune.renderers.markdown import MarkdownRenderer
from PIL import Image


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


def unformat(string, non_word='();-_, '):
    """Return an unformatted version of a string, stripping some special 
    chars. This is used for approximate answer comparsion."""
    return ''.join(
        c for c in unaccent(string.lower()) if c not in non_word
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


def make_gradient(colors, width=256, height=256):
    """Creates a horizontal gradient with n color stops."""
    assert len(colors)

    if len(colors) == 1:
        colors.append(colors[0])

    image = Image.new("RGB", (width, height))

    segments = list(pairwise(colors))
    segment_width = width / len(segments)

    for i, (start_color, end_color) in enumerate(segments):
        start_x = int(i * segment_width)
        end_x = int((i + 1) * segment_width)

        for x in range(start_x, end_x):
            t = (x - start_x) / segment_width
            r = int(start_color[0] * (1 - t) + end_color[0] * t)
            g = int(start_color[1] * (1 - t) + end_color[1] * t)
            b = int(start_color[2] * (1 - t) + end_color[2] * t)

            for y in range(height):
                image.putpixel((x, y), (r, g, b))

    return image
