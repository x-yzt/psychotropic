from typing import Literal

from psychotropic import settings
from psychotropic.utils import ThrottledAsyncClient


PUG_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"


class AsyncPUGClient(ThrottledAsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            cooldown=settings.HTTP_COOLDOWN,
            timeout=20,  # The API is sometimes *very* slow to handshake
            base_url=PUG_URL,
            **kwargs
        )
    
    async def get_synonyms(self, substance):
        r = await self.get(f"{substance}/synonyms/TXT")
        if r.status_code == 404:
            return []
        return r.text.split('\n')

    async def get_descriptions(self, substance):
        r = await self.get(f"{substance}/description/JSON")
        if r.status_code == 404:
            return []
        return r.json()['InformationList']['Information']

    async def get_properties(self, substance, properties):
        properties = ','.join(properties)
        r = await self.get(f"{substance}/property/{properties}/JSON")
        if r.status_code == 404:
            return {}
        return r.json()['PropertyTable']['Properties'][0]


def get_schematic_url(substance, mode: Literal['2D', '3D'] = '2D'):
    """Get the URL of the schematic of a given substance."""
    return f"{PUG_URL}{substance}/PNG?record_type={mode.lower()}"
