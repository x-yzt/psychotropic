import json
from enum import Enum

from aiohttp import ClientSession
from mistune import create_markdown

from psychotropic.i18n import localize
from psychotropic.utils import DiscordMarkdownRenderer


def format_markdown(text):
    text = text.replace("\\r\\n", "\n")
    render = create_markdown(renderer=DiscordMarkdownRenderer())

    return render(text)


class MixturesDecoder(json.JSONDecoder):
    def __init__(self):
        super().__init__(object_hook=self.object_hook)

    def object_hook(self, obj):
        for key, enum in (
            ("risk", Risk),
            ("synergy", Synergy),
            ("risk_reliability", Reliability),
            ("effects_reliability", Reliability),
        ):
            if key in obj:
                obj[key] = enum(obj[key])

        return obj


class MixturesEnum(Enum):
    def __str__(self):
        return self.name

    def __bool__(self):
        return bool(self.value)

    @property
    def emoji(self):
        return self._emojis[self.value]


class Risk(MixturesEnum):
    UNKNOWN = 0
    NEUTRAL = 1
    CAUTION = 2
    UNSAFE = 3
    DANGEROUS = 4

    def __str__(self):
        # Explicit strings are needed here for i18n extraction by gettext
        return [
            localize("unknown"),
            localize("neutral"),
            localize("caution"),
            localize("unsafe"),
            localize("dangerous"),
        ][self.value]

    def __lt__(self, other):
        if isinstance(other, Risk):
            return self.value < other.value

        return NotImplemented

    @property
    def _emojis(self):
        return "❔", "⏺️", "⚠️", "🛑", "⛔"


class Synergy(MixturesEnum):
    UNKNOWN = 0
    NEUTRAL = 1
    DECREASE = 2
    INCREASE = 3
    MIXED = 4
    ADDITIVE = 5

    def __str__(self):
        # Explicit strings are needed here for i18n extraction by gettext
        return [
            localize("unknown"),
            localize("neutral"),
            localize("decrease"),
            localize("increase"),
            localize("mixed"),
            localize("additive"),
        ][self.value]

    @property
    def _emojis(self):
        return "❔", "⏺️", "⏬", "⏫", "🔀", "➡️"


class Reliability(MixturesEnum):
    UNKNOWN = 0
    HYPOTHETICAL = 1
    INFERRED = 2
    PROVEN = 3

    def __str__(self):
        # Explicit strings are needed here for i18n extraction by gettext
        return [
            localize("unknown"),
            localize("hypothetical"),
            localize("inferred"),
            localize("proven"),
        ][self.value]

    @property
    def _emojis(self):
        return "", "◉⭘⭘", "◉◉⭘", "◉◉◉"


class MixturesAPI:
    API_URL = "https://mixtures.info/{locale}/api/v1/"

    def __init__(self, session: ClientSession, locale="en"):
        self.locale = locale
        self.session = session
        self._aliases = {}
        self._catalogue = {}

    @property
    def api_url(self):
        return self.API_URL.format(locale=self.locale)

    @property
    async def catalogue(self):
        """The catalogue is mapping lowercase aliases to slugs."""
        if not self._catalogue:
            self._catalogue = {
                alias.lower(): data["slug"]
                for alias, data in (await self.get_aliases()).items()
            }

        return self._catalogue

    async def get_aliases(self):
        if not self._aliases:
            self._aliases = await self.get_json("aliases/")
            self._catalogue = {}  # Invalidate catalogue

        return self._aliases

    async def get_substance(self, slug):
        return await self.get_json("substance/" + slug)

    async def get_substance_by_alias(self, alias):
        slug = (await self.catalogue)[alias.lower()]

        return await self.get_substance(slug)

    async def combine(self, slugs):
        return await self.get_json("combo/" + "+".join(slugs))

    async def get_slugs_from_aliases(self, aliases, raises=True):
        catalogue = await self.catalogue

        if raises:
            return {catalogue[alias.lower()] for alias in aliases}

        return {slug for alias in aliases if (slug := catalogue.get(alias.lower()))}

    async def get_json(self, path, **kwargs):
        async with self.session.get(self.api_url + path, **kwargs) as resp:
            resp.raise_for_status()

            return await resp.json(loads=lambda s: json.loads(s, cls=MixturesDecoder))
