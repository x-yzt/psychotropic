import json
from importlib import resources


class ReagentsDatabase:
    def __init__(self):
        self.db = json.loads(resources.read_text("psychotropic.data", "reagents.json"))

    def get_items(self, type_, key, value):
        return list(filter(lambda item: item[key] == value, self.db[type_].values()))

    def get_by_id(self, type_, id_):
        return self.db[type_][str(id_)]

    def get_substance(self, name=None):
        if results := self.get_items("substances", "commonName", name):
            return results[0]

        if results := self.get_items("substances", "name", name):
            return results[0]

    def get_reagent(self, name):
        if results := self.get_items("reagents", "fullName", name):
            return results[0]

    def get_reagents(self):
        return list(self.db["reagents"].values())

    def get_result(self, substance, reagent):
        sid, rid = substance["id"], reagent["id"]
        return self.db["results"][str(sid)][str(rid)][0]

    def get_results(self, substance):
        sid = substance["id"]
        return {rid: result[0] for rid, result in self.db["results"][str(sid)].items()}

    def get_result_colors(self, result):
        return (self.get_color_code(cid) for cid in result[0])

    def get_color_code(self, cid):
        return self.db["colors"][str(cid)]["hex"]

    def get_well_known_substances(self, reactions: int = 0, colored_reactions: int = 0):
        """Return all substances with `reactions` or more reaction entries and
        `colored_reactions` or more reactions whose result is not "no color change"."""
        return [
            self.db["substances"][sid]
            for sid, results in self.db["results"].items()
            if len(results) >= reactions
            and sum(1 for r in results.values() if len(r[0][0])) >= colored_reactions
        ]
