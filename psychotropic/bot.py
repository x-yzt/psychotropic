import logging
import sys

from aiohttp import ClientSession
from discord import Activity, ActivityType, Intents, Interaction, Permissions
from discord.app_commands import Command
from discord.app_commands import locale_str as _
from discord.ext.commands import Bot
from discord.ui import Button, View
from discord.utils import oauth_url

from psychotropic import settings
from psychotropic.embeds import DefaultEmbed
from psychotropic.i18n import localize, localize_fmt, set_locale, translator
from psychotropic.providers import PROVIDERS

log = logging.getLogger(__name__)


class PsychotropicBot(Bot):
    def __init__(self):
        intents = Intents.default()
        intents.message_content = True

        activity = Activity(type=ActivityType.listening, name="Sister Morphine")

        super().__init__(
            command_prefix=settings.PREFIX,
            help_command=None,
            intents=intents,
            activity=activity,
        )

    @property
    def oauth_url(self):
        return oauth_url(
            self.user.id,
            scopes=("bot", "applications.commands"),
            permissions=Permissions(
                **{
                    perm: True
                    for perm in (
                        "read_messages",
                        "send_messages",
                        "send_messages_in_threads",
                        "embed_links",
                        "attach_files",
                        "add_reactions",
                        "use_application_commands",
                    )
                }
            ),
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
        if settings.SYNC_GLOBAL_TREE:
            await self.tree.sync()
        else:
            self.tree.clear_commands(guild=settings.TEST_GUILD)
            self.tree.copy_global_to(guild=settings.TEST_GUILD)
            await self.tree.sync(guild=settings.TEST_GUILD)

    async def global_interaction_check(self, interaction: Interaction):
        """Pre-checks triggered upon each interaction event."""
        set_locale(interaction)
        return True

    async def setup_hook(self):
        log.info(f"OAuth URL: {self.oauth_url}")

        self.http_session = ClientSession()

        await self.load_extensions()
        await self.tree.set_translator(translator)
        self.tree.interaction_check = self.global_interaction_check
        await self.sync_tree()

    async def on_ready(self):
        log.info(f"Logged in as {self.user.name} ({self.user.id}).")


class InviteView(View):
    def __init__(self):
        super().__init__()
        self.add_item(
            Button(
                label=localize("Invite me to your guild!"),
                url=bot.oauth_url,
                emoji="✨",
            )
        )


bot = PsychotropicBot()


@bot.tree.command(
    name="psycho",
    description=_("Display various informations about the Psychotropic bot."),
)
async def info(interaction: Interaction):
    """`/pycho` command"""

    await interaction.response.send_message(
        embed=(
            DefaultEmbed(
                title="🧪 Psychotropic",
                description=localize(
                    "A Discord bot built for harm reduction and chemistry."
                ),
            )
            .set_image(url=settings.AVATAR_URL)
            .add_field(
                name=localize("💡 Help"),
                value=localize("Use `/help` to display help page."),
            )
            .add_field(
                name=localize("🛠️ Source code & issues"),
                value=localize_fmt(
                    "[See them on GitHub]({url})",
                    url="https://github.com/x-yzt/psychotropic",
                ),
            )
            .add_field(
                name=localize("📈 Stats"),
                value=localize_fmt(
                    "Currently in **{len}** guilds.", len=len(bot.guilds)
                ),
            )
            .add_field(
                name=localize("📄 Data providers"),
                value="\n".join(
                    [
                        "[{name}]({url})".format(**provider)
                        for provider in PROVIDERS.values()
                    ]
                ),
            )
            .set_footer(
                text=localize("Psychotropic was carefully trained by xyzt_"),
                icon_url=settings.AUTHOR_AVATAR_URL,
            )
        ),
        view=InviteView(),
    )


@bot.tree.command(
    name="help", description=_("Display help about Psychotropic commands.")
)
async def help(interaction: Interaction):
    """`/help` command"""

    embed = DefaultEmbed(
        title=localize("💡 Psychotropic help"),
        description=localize("A Discord bot built for harm reduction and chemistry."),
    ).set_thumbnail(url=settings.AVATAR_URL)

    for cmd in bot.tree.walk_commands():
        if not isinstance(cmd, Command):
            continue

        params = ""
        if cmd.parameters:
            params += localize("**Parameters:**") + "\n"

            # TODO: I18n for parameters choices and descriptions
            for param in cmd.parameters:
                params += "- `{p}`".format(p=localize(param.display_name))

                if param.choices:
                    params += f" [{'|'.join(c.name for c in param.choices)}]"

                if param.description != "…":
                    params += ": *{d}*".format(d=localize(param.description))

                params += "\n"

        embed.add_field(
            name=f"⌨️  /{cmd.qualified_name}",
            value="\n".join(
                (
                    # Description are extracted to translation catalogs from command
                    # decorators, so it's safe to use dynamic lookup here.
                    localize(cmd.extras.get("long_description") or cmd.description)
                    .strip()
                    .replace("\n", " "),
                    params,
                )
            ),
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


if __name__ == "__main__":
    # Log handler is configured in __init__.py
    bot.run(settings.DISCORD_TOKEN, log_handler=None)
