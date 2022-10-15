import logging
import sys

from discord import Activity, ActivityType, Intents, Permissions
from discord.app_commands import Command
from discord.ext.commands import Bot
from discord.ui import Button, View
from discord.utils import oauth_url

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed
from psychotropic.providers import PROVIDERS


log = logging.getLogger(__name__)


class PsychotropicBot(Bot):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True

        activity = Activity(
            type=ActivityType.listening, name="Sister Morphine"
        )

        super().__init__(
            command_prefix=settings.PREFIX,
            help_command=None,
            intents=intents,
            activity=activity,
            description="A Discord bot built for harm reduction and chemistry."
        )
    
    @property
    def oauth_url(self):
        return oauth_url(
            self.user.id,
            scopes=('bot', 'applications.commands'),
            permissions=Permissions(**{
                perm: True for perm in (
                    'read_messages',
                    'send_messages',
                    'send_messages_in_threads',
                    'embed_links',
                    'attach_files',
                    'add_reactions',
                    'use_application_commands',
                )
            })
        )
    
    async def load_extensions(self):
        """Load all extensions configured in settings."""
        for extension in settings.EXTENSIONS:
            try:
                await self.load_extension(extension)
                log.debug(f"Loaded extension {extension}.")
            except Exception:
                log.error(f"Failed to load extension {extension}.")
                log.error(sys.exc_info())

    async def sync_tree(self):
        """Sync the app commands tree."""
        self.tree.copy_global_to(guild=settings.TEST_GUILD)

        await self.tree.sync(guild=settings.TEST_GUILD)
        await self.tree.sync()

    async def setup_hook(self):
        log.info(f"OAuth URL: {self.oauth_url}")

        await self.load_extensions()
        await self.sync_tree()

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} ({self.user.id}).")
        

class InviteView(View):
    def __init__(self):
        super().__init__()
        self.add_item(
            Button(
                label = "Invite me to your guild!",
                url = bot.oauth_url,
                emoji = "✨"
            )
        )


bot = PsychotropicBot()


@bot.tree.command(name='psycho')
async def info(interaction):
    """Display various informations about the Psychotropic bot."""
    await interaction.response.send_message(
        embed = (
            DefaultEmbed(
                title = "🧪 Psychotropic",
                description = bot.description
            )
            .set_image(url=settings.AVATAR_URL)
            .add_field(
                name = "💡 Help",
                value = "Use `/help` to display help page."
            )
            .add_field(
                name = "🛠️ Source code & issues",
                value = "[See them on GitHub](https://github.com/x-yzt/psychotropic)"
            )
            .add_field(
                name = "📈 Stats",
                value = f"Currently in **{len(bot.guilds)}** guilds."
            )
            .add_field(
                name = "📄 Data providers",
                value = '\n'.join([
                    "[{name}]({url})".format(**provider)
                    for provider in PROVIDERS.values()
                ])
            )
            .set_footer(
                text = "Psychotropic was carefully trained by xyzt_",
                icon_url = settings.AUTHOR_AVATAR_URL
            )
        ),
        view = InviteView()
    )


@bot.tree.command(name='help')
async def help(interaction):
    """Display Psychotropic help."""
    embed = (
        DefaultEmbed(
            title = "💡 Psychotropic help",
            description = bot.description
        )
        .set_thumbnail(url=settings.AVATAR_URL)
    )

    for cmd in bot.tree.walk_commands():
        if not isinstance(cmd, Command):
            continue
        
        params = ''
        if cmd.parameters:
            params += "**Parameters:**\n"
            
            for param in cmd.parameters:
                params += f"- `{param.display_name}`"

                if param.choices:
                    params += f" [{'|'.join(c.name for c in param.choices)}]"

                if param.description != '…':
                    params += f": *{param.description}*"
                
                params += '\n'
        
        embed.add_field(
            name = f"⌨️  /{cmd.qualified_name}",
            value = '\n'.join((
                cmd.callback.__doc__.strip().replace('\n', ' '),
                params
            )),
            inline = False
        )

    await interaction.response.send_message(embed=embed)


if __name__ == '__main__':
    # Log handler is configured in __init__.py
    bot.run(settings.DISCORD_TOKEN, log_handler=None)
