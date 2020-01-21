import json
import httpx
import asyncio
from discord import Embed
from discord.ext.commands import command, Cog
from settings import COLOUR, COMPOUNDS_DESCRIPTION_PROVIDERS, HTTP_COOLDOWN
from utils import pretty_list, ErrorEmbed


class PubMedEmbed(Embed):
    
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.set_author(
            name="NCBI / PubMed",
            url="https://www.ncbi.nlm.nih.gov/pmc/",
            icon_url="https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/US-NLM-NCBI-Logo.svg/1200px-US-NLM-NCBI-Logo.svg.png"
        )


class PubChemEmbed(Embed):
    
    def __init__(self, *args, **kwargs):
        
        super().__init__(*args, **kwargs)
        self.set_author(
            name="PubChem",
            url="https://pubchem.ncbi.nlm.nih.gov/",
            icon_url=""
        )


class ScienceCog(Cog, name='Scientific module'):
    
    def __init__(self, bot):
        
        self.bot = bot

    
    @command(name='articles', aliases=('papers', 'publications'))
    async def articles(self, ctx, *query):

        """Display most revelant scientific publications about a certain drug or substance.
        Additional queries and keywords are supported to refine the search."""

        query = ' '.join(query)

        try:
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
                await asyncio.sleep(HTTP_COOLDOWN)

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
        
        except httpx.exceptions.ConnectionClosed:
            await ctx.send(embed=ErrorEmbed("Can't connect to PubChem servers"))
            return

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
    
    	
    @command(name='substance', aliases=('compound',))
    async def substance(self, ctx, substance: str):

        """Display general information about a given chemical substance or compound.
        Aliases names are supported."""

        try:
            async with httpx.AsyncClient() as client:
                url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{substance}"

                r_syn = await client.get(url + "/synonyms/TXT")
                await asyncio.sleep(.1)
                r_desc = await client.get(url + "/description/JSON")
                await asyncio.sleep(.1)
                r_prop = await client.get(url + "/property/MolecularFormula,MolecularWeight,IUPACName,HBondDonorCount,HBondAcceptorCount,Complexity/JSON")

        except httpx.exceptions.ConnectionClosed:
            await ctx.send(embed=ErrorEmbed("Can't connect to PubChem servers"))
            return
        
        if r_syn.status_code == 404:
            await ctx.send(embed=ErrorEmbed(f"Can't find substance {substance}"))
            return
        
        synonyms = r_syn.text.split('\n')

        descriptions = json.loads(r_desc.text)['InformationList']['Information']
        try:
            description = descriptions[1]['Description'] # Default value
        except IndexError:
            description = "No description avalaible 🤔"
        for provider in COMPOUNDS_DESCRIPTION_PROVIDERS:
            for desc in descriptions:
                try:
                    if provider.lower() in desc['DescriptionSourceName'].lower():
                        description = desc['Description']
                        break
                except KeyError:
                    pass
        
        properties = json.loads(r_prop.text)['PropertyTable']['Properties'][0]
        formula = properties['MolecularFormula']
        weight = properties['MolecularWeight']
        iupac_name = properties['IUPACName']
        h_bond_donors = properties['HBondDonorCount']
        h_bond_acceptors = properties['HBondAcceptorCount']
        complexity = properties['Complexity']

        schem_url = url + "/PNG"
        
        embed = PubChemEmbed(
            type = 'rich',
            colour = COLOUR,
            title = "Substance information: " + synonyms[0].capitalize(),
            description = description
        )
        embed.set_thumbnail(url=schem_url)
        embed.add_field(
            name = "🔬 IUPAC Name",
            value = iupac_name.capitalize(),
            inline = False
        )
        embed.add_field(
            name = "🏷 Synonyms",
            value = pretty_list(synonyms[1:7])
        )
        embed.add_field(
            name = "🧪 Formula",
            value = f"**{formula}**",
        )
        embed.add_field(
            name = "🏋 Molar mass",
            value = f"{weight} g/mol",
        )
        embed.add_field(
            name = "🔗 Hydrogen bonds",
            value = f"Donors: {h_bond_donors}\nAcceptors: {h_bond_acceptors}",
        )
        embed.add_field(
            name = "🌀 Molecular complexity",
            value = complexity,
        )

        await ctx.send(embed=embed)


setup = lambda bot: bot.add_cog(ScienceCog(bot))
