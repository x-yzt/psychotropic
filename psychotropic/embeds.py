import functools
import httpx
from discord import Embed, Colour

from psychotropic import settings


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


def provider_embed_factory(provider):
    """Factory method intended to generate provider embed classes."""
    class ProviderEmbed(DefaultEmbed):    
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.set_author(**provider)
    
    return ProviderEmbed


def send_embed_on_exception(func):
    """Decorator to send an embed if errors occurs during command
    processing. Exceptions are still raised after the embed is sent.
    """
    @functools.wraps(func)
    async def inner(self, interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)
        except httpx.RequestError:
            await interaction.response.send_message(embed=ErrorEmbed(
                "Can't connect to external server",
                "Maybe you should retry later?")
            )
            raise
        except Exception:
            await interaction.response.send_message(embed=ErrorEmbed())
            raise
    return inner
