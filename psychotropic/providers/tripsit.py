import httpx


TRIPSIT_URL = "http://drugs.tripsit.me/"

TRIPSIT_API_URL = "http://tripbot.tripsit.me/api/tripsit/"


async def get_drug(drug):
    async with httpx.AsyncClient(base_url=TRIPSIT_API_URL) as client:
        r = await client.get(
            "getDrug",
            params = {'name': drug.lower()}
        )
    return r.json()


def get_drug_url(drug):
    return TRIPSIT_URL + drug.lower()
