import asyncio as aio
from collections.abc import Iterable
from io import BytesIO
from operator import itemgetter
from urllib.parse import quote

from aiohttp import ClientError, ClientSession, ClientTimeout
from PIL import Image

from psychotropic.utils import batched

PILColor = float | tuple[float, ...] | str | None


class PNWikiApi:
    PNWIKI_URL = "https://psychonautwiki.org/w/"

    PNWIKI_API_URL = "https://api.psychonautwiki.org/"

    PNWIKI_MW_API_URL = "https://psychonautwiki.org/w/api.php"

    GRAPHQL_HEADERS = {
        "accept-type": "application/json",
        "content-type": "application/json",
    }

    def __init__(self, session: ClientSession):
        self.session = session

    async def _post_graphql(self, query: str, **kwargs):
        """Post a GraphQL query to Bitfrost, the PNWiki API."""

        if isinstance(timeout := kwargs.get("timeout"), float):
            kwargs["timeout"] = ClientTimeout(total=timeout)

        async with self.session.post(
            self.PNWIKI_API_URL,
            json={"query": query},
            headers=self.GRAPHQL_HEADERS,
            **kwargs,
        ) as r:
            return await r.json()

    async def list_substances(self, **kwargs):
        data = await self._post_graphql("""
            {
                substances(limit: 1000) {
                    name
                }
            }
        """)

        return list(map(itemgetter("name"), data["data"]["substances"]))

    async def get_substance(self, query: str, **kwargs):
        query = (
            """
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
            """
            % query
        )
        data = await self._post_graphql(query, **kwargs)
        substances = data["data"]["substances"]

        return substances[0] if len(substances) else None

    async def get_schematic_filenames(self, substances_names: Iterable[str]):
        """Batch-query the MediaWiki API to get the primary image filename for each
        substance page.

        Returns a dict mapping substance name to its schematic filename. If no
        schematic is found, entries will not be present in the output dict.
        """
        filenames = {}

        # MediaWiki API supports up to 50 titles per request
        for batch in batched(substances_names, 50):
            async with self.session.get(
                self.PNWIKI_MW_API_URL,
                params={
                    "action": "query",
                    "titles": "|".join(batch),
                    "prop": "pageimages",
                    "format": "json",
                },
            ) as r:
                data = await r.json()

            pages = data.get("query", {}).get("pages", {})

            for page in pages.values():
                title = page.get("title")
                pageimage = page.get("pageimage")

                # Filter out non-svg filenames are we're only interested in schematics
                if title and pageimage and pageimage.lower().endswith(".svg"):
                    filenames[title] = pageimage

        return filenames

    def get_image_url(self, filename: str, width: int = 500):
        """Get an image absolute URL from its filename."""
        return f"{self.PNWIKI_URL}thumb.php?f={quote(filename)}&width={width}"

    async def get_image(
        self,
        filename: str,
        width: int = 500,
        background_color: PILColor = None,
    ):
        """Get a PIL `Image` from an image filename by fetching it from PNWiki. Return
        `None` if no image is found."""
        async with self.session.get(self.get_image_url(filename, width)) as r:
            if r.status != 200:
                return None

            data = await r.read()

        return self._parse_image(data, background_color)

    async def get_images(
        self,
        filenames: Iterable[str],
        width: int = 500,
        background_color: PILColor = None,
    ):
        """Batch-fetch images for multiple substances filenames concurrently.

        Returns a dict mapping filename to PIL `Image`, or `None` on failure.
        """

        async def fetch_one(filename):
            async with aio.Semaphore(20):
                try:
                    return await self.get_image(filename, width, background_color)
                except ClientError:
                    return None

        images = await aio.gather(*map(fetch_one, filenames))

        return dict(zip(filenames, images))

    @staticmethod
    def _parse_image(data, background_color: PILColor = None):
        """Parse raw image bytes into a PIL Image with optional background."""
        image = Image.open(BytesIO(data))

        if background_color:
            background = Image.new("RGB", image.size, background_color)
            background.paste(image, mask=image)
            image = background

        return image
