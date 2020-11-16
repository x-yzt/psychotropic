from embeds import DefaultEmbed


PROVIDERS = {
    'pubmed': {
        'name': "PubMed / NCBI",
        'url': "https://www.ncbi.nlm.nih.gov/pmc/",
        'icon_url': "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/US-NLM-NCBI-Logo.svg/1200px-US-NLM-NCBI-Logo.svg.png"
    },
    'pubchem': {
        'name': "PubChem",
        'url': "https://pubchem.ncbi.nlm.nih.gov/",
        'icon_url': "https://pubchemblog.files.wordpress.com/2019/12/pubchem_splash.png?:200"
    },
    'epa': {
        'name': "EPA",
        'url': "https://www.epa.gov/",
        'icon_url': "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Seal_of_the_United_States_Environmental_Protection_Agency.svg/320px-Seal_of_the_United_States_Environmental_Protection_Agency.svg.png"
    },
    'tripsit': {
        'name': "TripSit",
        'url': "https://tripsit.me/",
        'icon_url': "https://cdn.discordapp.com/attachments/665208722372427782/665223281032560680/Vojr95_q_400x4001.png"
    }
}


def provider_embed_factory(provider_id):
    """Factory method intended to generate provider embed classes."""
    class ProviderEmbed(DefaultEmbed):
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            provider_data = PROVIDERS[provider_id]
            self.set_author(**provider_data)
    
    return ProviderEmbed


PubMedEmbed = provider_embed_factory('pubmed')
PubChemEmbed = provider_embed_factory('pubchem')
EPAEmbed = provider_embed_factory('epa')
TripSitEmbed = provider_embed_factory('tripsit')
