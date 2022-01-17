import logging
import sys
from itertools import chain

from discord.ext.commands import command, Cog, is_owner

from psychotropic.utils import setup_cog


log = logging.getLogger(__name__)


def resolve_relative(extension):
    """Resolve an extension package name relative to this admin cog module.
    For instance, '.foo.bar' will be resolved to 'path.to.this.module.foo.bar'.
    """
    if extension.startswith('.'):
        return '.'.join(__name__.split('.')[:-1]) + extension
    return extension


class AdminCog(Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @command(hidden=True)
    @is_owner()
    async def reload(self, ctx, extension: str):
        extension = resolve_relative(extension)

        try:
            self.bot.unload_extension(extension)
            self.bot.load_extension(extension)
        except Exception as e:
            log.error(f"Error while reloading extension {extension}")
            log.error(sys.exc_info())
            await ctx.send(f"Failed to reload {extension}: {type(e).__name__}.")
        else:
            log.info(f"Reloaded extension {extension}")
            await ctx.send(f"The extension {extension} was reloaded.")


setup = setup_cog(AdminCog)
