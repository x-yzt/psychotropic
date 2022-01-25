import sys

from psychotropic.embeds import provider_embed_factory


module = sys.modules[__name__]


PROVIDERS = {
    'pubmed': {
        'name': "PubMed",
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
    },
    'psychonautwiki': {
        'name': "PsychonautWiki",
        'url': "https://psychonautwiki.org/",
        'icon_url': "https://psychonautwiki.org/eye.png"
    }
}


# Define an Embed subclass for each provider at module level
for provider in PROVIDERS.values():
    class_name = provider['name'] + 'Embed'
    embed_class = provider_embed_factory(provider)

    setattr(module, class_name, embed_class)
