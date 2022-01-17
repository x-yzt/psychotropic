import httpx
from discord import Embed, Colour

import settings


class DefaultEmbed(Embed):
    def __init__(self, **kwargs):
        super().__init__(
            type = 'rich',
            colour = settings.COLOUR,
            **kwargs
        )


class ErrorEmbed(Embed):
    def __init__(self, msg=None, info=None, **kwargs):
        msg = msg or "Something went wrong"
        super().__init__(
            type = 'rich',
            colour = Colour.red(),
            title = f"Error: {msg} :(",
            description = info,
            **kwargs
        )


loading_embed = DefaultEmbed(
    title = "Computing...",
    description = "Relax, it will just take a year or two"
)


class LoadingEmbedContextManager:
    """Context manager to display a loading embed while inner code executes.
    The loading embed will be removed as soon as the inner block finishes, even
    if it raises an exception.
    """
    def __init__(self, ctx):
        self.ctx = ctx
    
    async def __aenter__(self):
        self.msg = await self.ctx.send(embed=loading_embed)
        return self.msg
    
    async def __aexit__(self, type, value, traceback):
        await self.msg.delete()


def send_embed_on_exception(func):
    """Decorator to send an embed if errors occurs during command
    processing. Exceptions are still raised after the embed is sent.
    """
    async def inner(self, ctx, *args, **kwargs):
        try:
            return await func(self, ctx, *args, **kwargs)
        except httpx.RequestError:
            await ctx.send(embed=ErrorEmbed(
                "Can't connect to external server",
                "Maybe you should retry later?")
            )
            raise
        except Exception:
            await ctx.send(embed=ErrorEmbed())
            raise
    return inner
