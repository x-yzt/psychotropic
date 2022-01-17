import httpx


COMPTOX_URL = "https://comptox.epa.gov/dashboard-api/"


async def search_substances(query):
    """Return a list of substances from the CompTox database that match the
    query string.
    """
    query = query.lower()

    async with httpx.AsyncClient(base_url=COMPTOX_URL, timeout=30) as client:
        r = await client.get('ccdapp1/search/chemical/start-with/' + query)

    return r.json()


async def get_substance(query):
    """Query the CompTox database and return the best match."""
    matches = await search_substances(query)
    matches.sort(
        key=lambda x: (x['rank'], x['searchWord'].lower() == query),
        reverse=True
    )
    return matches[0] if len(matches) else None


async def get_properties(dsstox_id):
    """Query the CompTox database and return the DSSTox chemical properties of
    a substance, given its DSSTox identifier.
    """
    async with httpx.AsyncClient(base_url=COMPTOX_URL, timeout=30) as client:
        r = await client.get(
            'ccdapp2/chemical-property/search/by-dtxsid',
            params={'id': dsstox_id}
        )
    return r.json()


def format_units(string):
    """Replace ASCII exponents with Unicode chars."""
    return (string
        .replace('^2', '²')
        .replace('^3', '³')
        if string else ''
    )
