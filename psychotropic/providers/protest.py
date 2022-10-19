import json
from importlib import resources


class ReagentsDatabase:
    def __init__(self):
        self.db = json.loads(
            resources.read_text('psychotropic.data', 'reagents.json')
        )
    
    def get_items(self, type_, key, value):
        return list(filter(
            lambda item: item[key] == value,
            self.db[type_].values()
        ))
    
    def get_substance(self, name=None):
        if results := self.get_items('substances', 'commonName', name):
            return results[0]
        
        if results := self.get_items('substances', 'name', name):
            return results[0]

    def get_reagent(self, name):
        if results := self.get_items('reagents', 'fullName', name):
            return results[0]

    def get_result(self, substance, reagent):
        sid, rid = substance['id'], reagent['id']
        return self.db['results'][sid][rid]

    def get_color_code(self, id_):
        return self.db['colors'][id_]['hex']

    def get_well_known_substances(self, reagents_count=10):
        """"Return all substances with `reagents_count` or more reaction
        entries."""
        return [
                self.db['substances'][sid]
                for sid, results in self.db['results'].items()
                if len(results) >= reagents_count
        ]
