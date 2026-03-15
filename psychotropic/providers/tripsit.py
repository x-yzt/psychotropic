from difflib import get_close_matches

from aiohttp import ClientSession


class TripsitApi:
    API_URL = "https://tripsit.me/api/v1/"

    FACTSHEETS_URL = "https://drugs.tripsit.me/"

    def __init__(self, session: ClientSession):
        self.session = session
        self.aliases: dict[str, str] | None = None

    async def get_aliases(self):
        if self.aliases is None:
            drugs = await self._get_json("getAllDrugs")
            self.aliases = {}

            for name, data in drugs.items():
                self.aliases |= {alias: name for alias in data.get("aliases", [])}

            self.aliases |= {name: name for name in drugs}

        return self.aliases

    async def get_drug(self, alias: str):
        if name := (await self.get_aliases()).get(alias, None):
            return await self._get_json("getDrug/" + name)
        return None

    async def find_aliases(self, query: str, count: int = 25):
        return get_close_matches(query, (await self.get_aliases()).keys(), n=count)

    @classmethod
    def get_factsheet_url(cls, drug_name: str):
        return cls.FACTSHEETS_URL + drug_name

    async def _get_json(self, path):
        async with self.session.get(self.API_URL + path) as resp:
            resp.raise_for_status()

            return (await resp.json())["data"][0]
