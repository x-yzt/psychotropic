import json
import httpx
from discord import Embed
from discord.ext.commands import command, Cog
from settings import COLOUR
from utils import pretty_list


class PubMedEmbed(Embed):
    
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.set_author(
            name="NCBI / PubMed",
            url="https://www.ncbi.nlm.nih.gov/pmc/",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/US-NLM-NCBI-Logo.svg/1200px-US-NLM-NCBI-Logo.svg.png"
        )


class ScienceCog(Cog, name='Scientific module'):
    
    def __init__(self, bot):
        
        self.bot = bot

    
    @command(name='articles', aliases=('papers', 'publications'))
    async def articles(self, ctx, *query):

        """Display most revelant scientific publications about a certain drug or substance.
        Additional queries and keywords are supported to refine the search."""

        query = ' '.join(query)

        async with httpx.AsyncClient() as client:
            r = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params={
                    'retmode': 'json',
                    'db': 'pmc',
                    'sort': 'relevance',
                    'term': f'{query} AND Open Access[Filter]'
                }
            )

            data = json.loads(r.text)['esearchresult']
            count = data['count']
            ids = data['idlist']

            r = await client.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
                params={
                    'retmode': 'json',
                    'db': 'pmc',
                    'id': ','.join(ids)
                }
            )

        data = json.loads(r.text)['result']

        articles = []

        for uid, art_data in data.items():
            if uid != 'uids':
                title = art_data['title']
                date = art_data['pubdate']
                source = art_data['source']
                url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{uid}/"
                
                if len(title) > 112:
                    title = title[:110] + '...'

                articles.append(f"*{title}* (🗓 {date})\n🌎 {url}")
        
        embed = PubMedEmbed(
            type = 'rich',
            colour = COLOUR,
            title = "Most revelant articles about " + query,
            description = pretty_list(articles, capitalize=False)
        )

        await ctx.send(embed=embed)


setup = lambda bot: bot.add_cog(ScienceCog(bot))
