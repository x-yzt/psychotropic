from enum import Enum

import httpx


def format_linebreaks(text):
    return text.replace('\\r\\n', '\n')


class MixturesEnum(Enum):
    def __str__(self):
        return self.name
    
    @property
    def emoji(self):
        return self._emojis[self.value]


class Risk(MixturesEnum):
    UNKNOWN = 0
    NEUTRAL = 1
    CAUTION = 2
    UNSAFE = 3
    DANGEROUS = 4

    @property
    def _emojis(self):
        return '❔', '⏺️', '⚠️', '🛑', '⛔'
    

class Synergy(MixturesEnum):
    UNKNOWN = 0
    NEUTRAL = 1
    DECREASE = 2
    INCREASE = 3
    MIXED = 4
    ADDITIVE = 5
    
    @property
    def _emojis(self):
        return '❔', '⏺️', '⏬', '⏫', '🔀', '➡️'


class Reliability(MixturesEnum):
    UNKNOWN = 0
    HYPOTHETICAL = 1
    INFERRED = 2
    PROVEN = 3
    
    @property
    def _emojis(self):
        return '', '◉⭘⭘', '◉◉⭘', '◉◉◉'


class MixturesAPI:
    API_URL = 'https://mixtures.info/en/api/v1/'

    def __init__(self):
        self._aliases = {}
        self._catalogue = {}
    
    async def get_aliases(self):
        if not self._aliases:
            await self._fetch_aliases()
        return self._aliases
    
    async def get_substance(self, slug):
        return (await self.get('substance/' + slug)).json()
    
    async def combine(self, slugs):
        return (await self.get('combo/' + '+'.join(slugs))).json()
    
    async def get_slugs_from_aliases(self, aliases, raises=True):
        # The catalogue is mapping lowercase aliases to slugs
        if not self._catalogue:
            self._catalogue = {
                alias.lower(): data['slug']
                for alias, data in (await self.get_aliases()).items()
            }
        
        return set(filter(None, (
            self._catalogue[alias.lower()] if raises
            else self._catalogue.get(alias.lower())
            for alias in aliases
        )))

    async def get(self, *args, **kwargs):
        async with httpx.AsyncClient(
            base_url=self.API_URL,
            follow_redirects=True
        ) as client:
            return await client.get(*args, **kwargs)

    async def _fetch_aliases(self):
        self._aliases = (await self.get('aliases')).json()
        self._catalogue = {}  # Invalidate catalogue
