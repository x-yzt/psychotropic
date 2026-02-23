import json
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from operator import contains, eq
from typing import Any

from PIL import ImageColor

from psychotropic.utils import is_in, unformat


@dataclass
class Color:
    id: int
    name: str
    hex: str
    is_simple: bool
    _simple_color_id: int

    @property
    def simple(self) -> "Color":
        return db.colors[self._simple_color_id]

    def to_rgb(self) -> tuple[int, ...]:
        return ImageColor.getrgb(self.hex)

    def __str__(self):
        return self.name


@dataclass
class Substance:
    id: int
    name: str
    full_name: str
    is_popular: bool
    classes: list[str]

    @property
    def results(self) -> dict[int, "Result"]:
        return db.results[self.id]

    def __str__(self):
        return self.name


@dataclass
class Reagent:
    id: int
    name: str

    def __str__(self):
        return self.name


@dataclass
class Result:
    substance: Substance
    reagent: Reagent
    description: str
    colors: list[Color]
    simple_colors: list[Color]

    def __str__(self):
        return self.description


class ReagentsDatabase:
    def __init__(self):
        data = json.loads(resources.read_text("psychotropic.data", "reagents.json"))

        self.colors: dict[int, Color] = {
            int(cid): Color(
                id=int(cid),
                name=color["name"],
                hex=color["hex"],
                is_simple=color["simple"],
                _simple_color_id=color["simpleColorId"],
            )
            for cid, color in data["colors"].items()
        }

        self.substances: dict[int, Substance] = {
            int(sid): Substance(
                id=int(sid),
                name=substance["commonName"],
                full_name=substance["name"],
                is_popular=substance["isPopular"],
                classes=substance["classes"],
            )
            for sid, substance in data["substances"].items()
        }

        self.reagents: dict[int, Reagent] = {
            int(rid): Reagent(
                id=int(rid),
                name=reagent["fullName"],
            )
            for rid, reagent in data["reagents"].items()
        }

        self.results: dict[int, dict[int, Result]] = {
            int(sid): {
                int(rid): Result(
                    substance=self.substances[int(sid)],
                    reagent=self.reagents[int(rid)],
                    description=result[0][3],
                    colors=[self.colors[int(cid)] for cid in result[0][0]],
                    simple_colors=[self.colors[int(cid)] for cid in result[0][1]],
                )
                for rid, result in results.items()
            }
            for sid, results in data["results"].items()
        }

    def lookup(
        self,
        type_: str,
        attr: str,
        value: Any,
        *,
        operator: Callable[[Any, Any], bool] = eq,
        transform: Callable[[Any], Any] | None = None,
    ) -> list:
        transform = transform or (lambda x: x)

        return list(
            filter(
                lambda item: operator(transform(getattr(item, attr)), transform(value)),
                getattr(self, type_).values(),
            )
        )

    def search_substance(self, name: str) -> Substance | None:
        # Checks if a whole substance name is included in query string
        if results := self.lookup(
            "substances", "name", name, operator=is_in, transform=unformat
        ):
            return results[0]

        # Checks if query string is included in full substance name, containing aliases
        if results := self.lookup(
            "substances", "full_name", name, operator=contains, transform=unformat
        ):
            return results[0]

    def get_well_known_substances(
        self, reactions: int = 0, colored_reactions: int = 0
    ) -> list[Substance]:
        """Return all substances with `reactions` or more reaction entries and
        `colored_reactions` or more reactions whose result is not "no color change"."""
        return [
            self.substances[sid]
            for sid, results in self.results.items()
            if len(results) >= reactions
            and sum(1 for result in results.values() if len(result.colors))
            >= colored_reactions
        ]


db = ReagentsDatabase()
