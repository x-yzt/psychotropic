from operator import itemgetter

import httpx


PNWIKI_URL = 'https://psychonautwiki.org/w/'

PNWIKI_API_URL = 'https://api.psychonautwiki.org/'


class PNWikiAPIClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(
            base_url=PNWIKI_API_URL,
            headers={
                "accept-type": "application/json",
                "content-type": "application/json"
            },
            *args, **kwargs
        )
    
    async def post_graphql(self, query, *args, **kwargs):
        return await self.post(
            url='/',
            json={'query': query},
            *args, **kwargs
        )


async def list_substances():
    query = """
        {
            substances(limit: 1000) {
                name
            }
        }
    """
    async with PNWikiAPIClient() as client:
        r = await client.post_graphql(query)
    
    return list(map(
        itemgetter('name'),
        r.json()['data']['substances']
    ))


async def get_substance(query):
    query = """
        {
            substances(query: %s, limit: 1) {
                name
                url
                class {
                    chemical
                    psychoactive
                }
            }
        }
    """ % query
    async with PNWikiAPIClient as client:
        r = await client.post_graphql(query)

    return r.json()

def get_schematic_url(substance, width=500):
    return f'{PNWIKI_URL}thumb.php?f={substance}.svg&width={width}'
