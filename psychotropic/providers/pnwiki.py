from io import BytesIO
from operator import itemgetter

import httpx
from PIL import Image


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
    # Temporary workaround to exclude substance id 192 which makes the
    # PNWiki API timeout
    query = """
        {
            a: substances(limit:192) {
                name
            },
            b: substances(offset:193 limit:1000) {
                name
            }
        }
    """
    async with PNWikiAPIClient() as client:
        r = await client.post_graphql(query)
    
    return list(map(
        itemgetter('name'),
        r.json()['data']['a'] + r.json()['data']['b']
    ))


async def get_substance(query, **kwargs):
    query = """
        {
            substances(query: "%s", limit: 1) {
                name
                url
                class {
                    chemical
                    psychoactive
                }
            }
        }
    """ % query

    async with PNWikiAPIClient() as client:
        r = await client.post_graphql(query, **kwargs)

    substances = r.json()["data"]["substances"]

    return substances[0] if len(substances) else None


def get_schematic_url(substance, width=500):
    return f'{PNWIKI_URL}thumb.php?f={substance}.svg&width={width}'


async def get_schematic_image(substance, width=500, background_color=None):
    """Get a PIL `Image` of a given substance by fetching its schematic on
    PNWiki. Return `None` if no schematic is found."""
    async with httpx.AsyncClient() as client:
        r = await client.get(get_schematic_url(substance, width))

    if r.status_code != 200:
        return None

    image = Image.open(BytesIO(r.content))

    if background_color:
        background = Image.new("RGB", image.size, background_color)
        background.paste(image, mask=image)
        image = background

    return image
