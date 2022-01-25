from discord.ext.commands import command, Cog

from psychotropic import settings
from psychotropic.embeds import (ErrorEmbed, LoadingEmbedContextManager,
    send_embed_on_exception)
from psychotropic.providers import dsstox, pubchem, PubChemEmbed, EPAEmbed
from psychotropic.utils import pretty_list, setup_cog


class ScienceCog(Cog, name='Scientific module'):
    # PUG properties that will be shown in substance information embeds
    DEFAULT_PROPERTIES = (
        'MolecularFormula',
        'MolecularWeight',
        'IUPACName',
        'HBondDonorCount',
        'HBondAcceptorCount',
        'Complexity',
    )

    # DSSTox propetries names that will be shown in solubility embeds    
    DSSTOX_PROPERTIES = (
        'Water Solubility',
        'LogKoa: Octanol-Air',
        'LogKow: Octanol-Water',
        'Melting Point',
        'Molar Volume',
        'Density',
        'Molar Refractivity',
        'Viscosity',
        'Polarizability',
    )
    
    def __init__(self, bot):
        self.bot = bot
        self.pug_client = pubchem.AsyncPUGClient()
    
    @command(name='substance', aliases=('compound',))
    @send_embed_on_exception
    async def substance(self, ctx, substance: str):
        """Display general information about a given chemical substance or
        compound. Aliases names are supported.
        """
        async with self.pug_client as client:
            synonyms = await client.get_synonyms(substance)
            descriptions = await client.get_descriptions(substance)
            properties = await client.get_properties(substance, self.DEFAULT_PROPERTIES)

        if not synonyms:
            await ctx.send(embed=ErrorEmbed(
                f"Can't find substance {substance}"
            ))
        
        try:
            description = descriptions[1]['Description'] # Default value
        except IndexError:
            description = "No description avalaible 🤔"
        for provider in settings.COMPOUNDS_DESCRIPTION_PROVIDERS:
            for desc in descriptions:
                try:
                    if provider.lower() in desc['DescriptionSourceName'].lower():
                        description = desc['Description']
                        break
                except KeyError:
                    pass
        
        formula = properties['MolecularFormula']
        weight = properties['MolecularWeight']
        iupac_name = properties['IUPACName']
        h_bond_donors = properties['HBondDonorCount']
        h_bond_acceptors = properties['HBondAcceptorCount']
        complexity = properties['Complexity']

        schem_url = pubchem.get_schematic_url(substance)
        
        embed = PubChemEmbed(
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

    @command(name='schem', aliases=('schematic', 'draw'))
    @send_embed_on_exception
    async def schem(self, ctx, substance: str, mode: str='2d'):
        """Display the shematic of a given chemical substance or compound.
        2D and 3D modes are supported.
        """
        mode = mode.lower()

        if mode not in ('2d', '3d'):
            await ctx.send(embed=ErrorEmbed(
                f"Invalid mode {mode}", "Try with `2d` or `3d`."
            ))
            return
        
        async with self.pug_client as client:
            synonyms = await client.get_synonyms(substance)
            properties = await client.get_properties(
                substance, ('MolecularFormula','IUPACName')
            )
        
        if not synonyms:
            await ctx.send(embed=ErrorEmbed(
                f"Can't find substance {substance}"
            ))
            return
        
        formula = properties['MolecularFormula']
        iupac_name = properties['IUPACName']

        schem_url = pubchem.get_schematic_url(substance, mode)
        
        embed = PubChemEmbed(
            title = "Substance schematic: " + synonyms[0].capitalize(),
        )
        embed.add_field(
            name = "🔬 IUPAC Name",
            value = iupac_name.capitalize(),
            inline = False
        )
        embed.add_field(
            name = "🧪 Formula",
            value = f"**{formula}**",
        )
        embed.set_image(url=schem_url)

        await ctx.send(embed=embed)
    
    @command(name='solubility', aliases=('solub',))
    @send_embed_on_exception
    async def solubility(self, ctx, substance: str):
        """Display solubility-related properties about a given substance.
        Multiple sources of experimental and predicted data are averaged to
        improve result accuracy. Result ranges are provided when applicable.
        """
        async with LoadingEmbedContextManager(ctx):
            match = await dsstox.get_substance(substance)
            if not match:
                await ctx.send(embed=ErrorEmbed(
                    f"Can't find substance {substance}"
                ))
                return
        
            dsstox_id = match['dtxsid']
            name = match['searchWord']
            props = await dsstox.get_properties(dsstox_id)

        embed = EPAEmbed(title = f"Solubility information: {name}")

        props = props['data']
        for prop in props:
            prop_name = prop['name']
            if prop_name not in self.DSSTOX_PROPERTIES:
                continue
                
            unit = dsstox.format_units(prop['unit'])

            prop_text = ''
            for method in ('predicted', 'experimental'):
                results = prop[method]
                if not results:
                    continue
                
                vals = [
                    r['value'] for r in results['rawData']
                    if r.get('modelName') not in settings.DSSTOX_EXCLUDED_MODELS
                ]
                if not vals:
                    continue
                
                count = len(vals)
                avg = sum(vals) / count
                low, up = min(vals), max(vals)
                
                prop_text += f"**{avg:.3n} {unit}**"
                if count == 1:
                    prop_text += f"\n*({method})*\n"
                else:
                    prop_text += f", {low:.3n}\xa0~\xa0{up:.3n}\n*({method}, {count} sources)*\n"
            
            if prop_text:
                embed.add_field(
                    name = prop_name,
                    value = prop_text.strip(),
                    inline = True
                )

        await ctx.send(embed=embed)


setup = setup_cog(ScienceCog)
