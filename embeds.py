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
   
    def __init__(self, ctx):
        self.ctx = ctx
    
    async def __aenter__(self):
        self.msg = await self.ctx.send(embed=loading_embed)
        return self.msg
    
    async def __aexit__(self, type, value, traceback):
        await self.msg.delete()
