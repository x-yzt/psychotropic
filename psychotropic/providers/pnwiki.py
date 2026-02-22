import asyncio as aio
from io import BytesIO
from operator import itemgetter
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout
from PIL import Image


PNWIKI_URL = 'https://psychonautwiki.org/w/'

PNWIKI_MW_API_URL = 'https://psychonautwiki.org/w/api.php'

PNWIKI_API_URL = 'https://api.psychonautwiki.org/'

GRAPHQL_HEADERS = {
    "accept-type": "application/json",
    "content-type": "application/json",
}


async def list_substances(session: ClientSession):
    query = """
        {
            substances(limit: 1000) {
                name
            }
        }
    """
    async with session.post(
        PNWIKI_API_URL, json={'query': query}, headers=GRAPHQL_HEADERS,
    ) as r:
        data = await r.json()

    return list(map(
        itemgetter('name'),
        data['data']['substances']
    ))


async def get_substance(session: ClientSession, query, **kwargs):
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

    if 'timeout' in kwargs:
        kwargs['timeout'] = ClientTimeout(total=kwargs['timeout'])

    async with session.post(
        PNWIKI_API_URL, json={'query': query}, headers=GRAPHQL_HEADERS,
        **kwargs,
    ) as r:
        data = await r.json()

    substances = data["data"]["substances"]

    return substances[0] if len(substances) else None


async def get_page_images(session: ClientSession, substance_names):
    """Batch-query the MediaWiki API to get the primary image filename
    for each substance page.

    Returns a dict mapping substance name to its SVG filename, or None
    if no page image was found.
    """
    result = {}

    # MediaWiki API supports up to 50 titles per request
    for i in range(0, len(substance_names), 50):
        batch = substance_names[i:i + 50]
        titles = "|".join(batch)

        async with session.get(PNWIKI_MW_API_URL, params={
            "action": "query",
            "titles": titles,
            "prop": "pageimages",
            "format": "json",
        }) as r:
            data = await r.json()

        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            title = page.get("title")
            pageimage = page.get("pageimage")
            if title and pageimage:
                result[title] = pageimage

    return result


def get_schematic_url(filename, width=500):
    return (
        f'{PNWIKI_URL}thumb.php'
        f'?f={quote(filename)}&width={width}'
    )


def _parse_schematic_image(data, background_color=None):
    """Parse raw image bytes into a PIL Image with optional background."""
    image = Image.open(BytesIO(data))

    if background_color:
        background = Image.new("RGB", image.size, background_color)
        background.paste(image, mask=image)
        image = background

    return image


async def get_schematic_image(
    session: ClientSession, filename, width=500, background_color=None,
):
    """Get a PIL `Image` of a substance by fetching its schematic on
    PNWiki. `filename` is the actual SVG filename from the wiki.
    Return `None` if no schematic is found."""
    async with session.get(get_schematic_url(filename, width)) as r:
        if r.status != 200:
            return None
        data = await r.read()

    return _parse_schematic_image(data, background_color)


async def fetch_schematic_images(
    session: ClientSession, svg_map, width=500, background_color=None,
):
    """Batch-fetch schematic images for multiple substances concurrently.

    `svg_map` is a dict mapping substance name to SVG filename.
    Returns a dict mapping substance name to PIL Image (or None on failure).
    """
    sem = aio.Semaphore(20)

    async def _fetch_one(name, filename):
        async with sem:
            try:
                async with session.get(
                    get_schematic_url(filename, width),
                ) as r:
                    if r.status != 200:
                        return name, None
                    data = await r.read()
            except ClientError:
                return name, None
            return name, _parse_schematic_image(data, background_color)

    pairs = await aio.gather(*(
        _fetch_one(name, filename)
        for name, filename in svg_map.items()
    ))

    return dict(pairs)
