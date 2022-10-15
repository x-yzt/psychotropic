from functools import partial
from typing import Literal, get_args

from discord.app_commands import command
from discord.ext.commands import Cog
from discord.ui import Button, View

from psychotropic import settings
from psychotropic.embeds import ErrorEmbed, send_embed_on_exception
from psychotropic.providers import EPAEmbed, PubChemEmbed, dsstox, pubchem
from psychotropic.utils import pretty_list, setup_cog


Mode = Literal['2D', '3D']


class SchematicView(View):
    def __init__(self, substance: str, mode: Mode):
        super().__init__()
        self.substance = substance
        self.mode = mode

        for label in get_args(Mode):
            button = Button(label=label, disabled=label == self.mode)
            button.callback = partial(self.toggle_mode, button)
            self.add_item(button)

    async def toggle_mode(self, button, interaction):
        self.mode = button.label

        for children in self.children:
            children.disabled = children.label == self.mode
        
        embed = interaction.message.embeds[0]
        embed.set_image(
            url = pubchem.get_schematic_url(self.substance, self.mode)
        )

        await interaction.response.edit_message(embed=embed, view=self)


class ScienceCog(Cog, name="Scientific module"):
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
    
    @command(name='substance')
    @send_embed_on_exception
    async def substance(self, interaction, substance: str):
        """Display general information about a given chemical substance or
        compound. Aliases names are supported.
        """
        await interaction.response.defer(thinking=True)

        async with pubchem.AsyncPUGClient() as client:
            synonyms = await client.get_synonyms(substance)
            descriptions = await client.get_descriptions(substance)
            properties = await client.get_properties(
                substance, self.DEFAULT_PROPERTIES
            )

        if not synonyms:
            await interaction.followup.send(embed=ErrorEmbed(
                f"Can't find substance {substance}"
            ))
            return
        
        try:
            description = descriptions[1]['Description']  # Default value
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
        
        await interaction.followup.send(
            embed = PubChemEmbed(
                title = "Substance information: " + synonyms[0].capitalize(),
                description = description
            )
            .set_thumbnail(url=schem_url)
            .add_field(
                name = "🔬 IUPAC Name",
                value = iupac_name.capitalize(),
                inline = False
            )
            .add_field(
                name = "🏷 Synonyms",
                value = pretty_list(synonyms[1:7])
            )
            .add_field(
                name = "🧪 Formula",
                value = f"**{formula}**",
            )
            .add_field(
                name = "🏋 Molar mass",
                value = f"{weight} g/mol",
            )
            .add_field(
                name = "🔗 Hydrogen bonds",
                value = f"Donors: {h_bond_donors}\nAcceptors: {h_bond_acceptors}",
            )
            .add_field(
                name = "🌀 Molecular complexity",
                value = complexity,
            )
        )

    @command(name='schematic')
    @send_embed_on_exception
    async def schematic(self, interaction, substance: str, mode: Mode = '2D'):
        """Display the shematic of a given chemical substance or compound. 2D
        and 3D modes are supported.
        """
        await interaction.response.defer(thinking=True)

        async with pubchem.AsyncPUGClient() as client:
            synonyms = await client.get_synonyms(substance)
            properties = await client.get_properties(
                substance, ('MolecularFormula', 'IUPACName')
            )
        
        if not synonyms:
            await interaction.followup.send(embed=ErrorEmbed(
                f"Can't find substance {substance}"
            ))
            return
        
        formula = properties['MolecularFormula']
        iupac_name = properties['IUPACName']

        schem_url = pubchem.get_schematic_url(substance, mode)
        
        await interaction.followup.send(
            embed = (
                PubChemEmbed(
                    title = "Substance schematic: " + synonyms[0].capitalize(),
                )
                .add_field(
                    name = "🔬 IUPAC Name",
                    value = iupac_name.capitalize(),
                    inline = False
                )
                .add_field(
                    name = "🧪 Formula",
                    value = f"**{formula}**",
                )
                .set_image(url=schem_url)
            ),
            view = SchematicView(substance, mode)
        )
    
    @command(name='solubility')
    @send_embed_on_exception
    async def solubility(self, interaction, substance: str):
        """Display solubility-related properties about a given substance.
        Multiple sources of experimental and predicted data are averaged to
        improve result accuracy. Result ranges are provided when applicable.
        """
        await interaction.response.defer(thinking=True)

        match = await dsstox.get_substance(substance)
        if not match:
            await interaction.followup.send(
                embed = ErrorEmbed(f"Can't find substance {substance}")
            )
            return
        
        dsstox_id = match['dtxsid']
        name = match['searchWord']
        props = await dsstox.get_properties(dsstox_id)

        embed = EPAEmbed(title=f"Solubility information: {name}")

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

        await interaction.followup.send(embed=embed)


setup = setup_cog(ScienceCog)
