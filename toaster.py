import httpx
import json

query = 'lsd'

r = httpx.get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    params={
        'retmode': 'json',
        'db': 'pmc',
        'sort': 'relevance',
        'term': f'{query} AND Open Access[Filter]'
    }
)

print(r.text)

data = json.loads(r.text)['esearchresult']
count = data['count']
ids = data['idlist']

print(count)
print(ids)

r = httpx.get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
    params={
        'retmode': 'json',
        'db': 'pmc',
        'id': ','.join(ids[:2])
    }
)

b = json.loads(r.text)['result']

for key, val in b.items():
    if key != 'uids':
        print(key)
        print(val['source'])
        print(val['pubdate'])
        print(val['title'])

        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{key}/"
        print(url)