import httpx
import json
from bs4 import BeautifulSoup


DSSTOX_URL = "https://comptox.epa.gov/dashboard/dsstoxdb/"

PHYSICAL_PROPERTIES = [
    'density',
    'mv', # Molar volume
    'mp', # Melting point
    'bp', # Boiling point
    'fp', # Flash point
    'wsol',
    'logkow',
    'logkoa',
    'polarizability',
    'thermalconductivity',
    'surface tension', 
    'viscosity',
    'ior', # Index of refraction
    'mr', # Molar refractivity
    'vp', # Vapor pressure
    'hlc', # Henry's law constant
]


async def get_properties(query):

    async with httpx.AsyncClient(base_url=DSSTOX_URL, timeout=30) as client:
        r = await client.get('results', params={'search': query})
    
    # The data to get is contained in this tag:
    # <div id="single_results" data-result="HTML ESCAPED JSON DATA"></div>
    soup = BeautifulSoup(r.text, 'html.parser')
    tag = soup.find(id='single_results')
    
    if not tag:
        return
    return json.loads(tag.get('data-result'))
