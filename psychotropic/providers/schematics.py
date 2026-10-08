import logging
import re
from random import choice

from aiohttp import ClientError, ClientSession

from psychotropic import settings
from psychotropic.providers.pnwiki import PNWikiApi

log = logging.getLogger(__name__)

# This is where molecules schematics will be downloaded
CACHE_DIR = settings.STORAGE_DIR / "cache" / "schematics"


class UnfetchedRegistryError(RuntimeError):
    def __init__(self, *args):
        super().__init__(
            "SchematicRegistry needs schematics to be cached before they are used. "
            "Please `await` for `fetch_schematics`.",
            *args,
        )


class SchematicRegistry:
    def __init__(self, path):
        path.mkdir(parents=True, exist_ok=True)

        self.path = path
        self.schematics = None

    async def fetch_schematics(self, session: ClientSession):
        """Populate the list of all substances to play the game with from PNWiki."""
        if settings.FETCH_SCHEMATICS:
            log.info("Populating cache with schematics from PNWiki...")

            pnwiki = PNWikiApi(session)

            try:
                # List of substance names
                substances = await pnwiki.list_substances()

                # Maps substance name to schematic image filename
                filenames = await pnwiki.get_schematic_filenames(substances)

                # Maps clean substance name to schematic image filename
                filenames_to_fetch = {}
                for name, filename in filenames.items():
                    clean_name = re.sub(r"\s+\([^)]*\)$", "", name)
                    image_path = self.build_schematic_path(clean_name)

                    # Filter out already-cached substances
                    if image_path.exists():
                        log.debug(f"Skipping substance {clean_name} (cached)")
                    else:
                        filenames_to_fetch[clean_name] = filename

                # Batch-fetch all missing schematics concurrently
                images = await pnwiki.get_images(
                    filenames_to_fetch.values(), width=600, background_color="WHITE"
                )

                for name, filename in filenames_to_fetch.items():
                    if image := images.get(filename):
                        image.save(self.build_schematic_path(name))
                        log.debug(f"Fetched substance {name} ({filename})")
                    else:
                        log.info(f"Skipping substance {name} (schematic fetch failed)")

            except ClientError:
                log.error(
                    "Unable to reach PsychonautWiki API. The schematic cache might be "
                    "empty or incomplete."
                )

        self.schematics = {path.stem: path for path in self.path.glob("*.png")}

        for substance, path in settings.SCHEMATICS_OVERRIDES.items():
            if path is None:
                self.schematics.pop(substance, None)
            else:
                self.schematics[substance] = (
                    settings.BASE_DIR / "data" / "img" / "schematics" / path
                )

        log.info(f"{len(self._schematics)} schematics avalaible in cache")

    @property
    def schematics(self):
        if self._schematics is None:
            raise UnfetchedRegistryError()
        return self._schematics

    @schematics.setter
    def schematics(self, value):
        self._schematics = value

    def pick_substance(self):
        """Pick a random substance name from what is avalaible in the registry."""
        return choice(tuple(self.schematics))

    def build_schematic_path(self, substance):
        """Build the path of a given substance's schematic. There is no guarantee this
        path will actually exist."""
        return self.path / (substance + ".png")

    def __getitem__(self, substance):
        """Get the path of a given substance's schematic, raises an exception if no
        schematic is found for this substance."""
        return self.schematics[substance]


schematic_registry = SchematicRegistry(CACHE_DIR)
