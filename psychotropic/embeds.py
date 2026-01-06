import functools

import httpx
from discord import Colour, Embed

from psychotropic import settings
from psychotropic.i18n import localize, localize_fmt


class DefaultEmbed(Embed):
    def __init__(self, **kwargs):
        super().__init__(
            type = 'rich',
            colour = settings.COLOUR,
            **kwargs
        )


class ErrorEmbed(Embed):
    def __init__(self, msg=None, info=None, **kwargs):
        msg = msg or localize("Something went wrong")
        super().__init__(
            type = 'rich',
            colour = Colour.red(),
            title = localize_fmt("Error: {msg} :(", msg=msg),
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
            await interaction.followup.send(embed=ErrorEmbed(
                localize("Can't connect to external server"),
                localize("Maybe you should retry later?"))
            )
            raise
        except Exception:
            await interaction.followup.send(embed=ErrorEmbed())
            raise
    return inner
