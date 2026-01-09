from functools import partial
from typing import Literal, get_args

from discord import Interaction
from discord.app_commands import command
from discord.app_commands import locale_str as _
from discord.ext.commands import Cog
from discord.ui import Button, Label, Modal, TextDisplay, TextInput, View

from psychotropic import settings
from psychotropic.embeds import ErrorEmbed, send_embed_on_exception
from psychotropic.i18n import localize, localize_fmt, set_locale
from psychotropic.providers import EPAEmbed, PubChemEmbed, dsstox, pubchem
from psychotropic.ui import DefaultEmbed, RetryModalView
from psychotropic.utils import pretty_list, setup_cog, to_float

Mode = Literal["2D", "3D"]


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
        embed.set_image(url=pubchem.get_schematic_url(self.substance, self.mode))

        await interaction.response.edit_message(embed=embed, view=self)


class DilutionModal(Modal):
    def __init__(self, defaults=None, error_message=None):
        # UI items are instance (and not class) attributes so they can be localized and
        # initialized with various values in order to init a pre-fileld modal

        super().__init__(title=localize("🧪 Dilution Calculator"))

        header = localize(
            "A calculator to help with volumetric dosing.\n"
            "Depending on the type of calculation you want to make, fill in two "
            "fields from the three below, and the bot will compute the third."
        )
        if error_message:
            header += "\n\n" + localize_fmt(
                "🛑 **__Error:__ {msg}**", msg=error_message
            )

        footer = localize(
            "*Units are indicated in `mg` and `mL`, but the calculations will be the "
            "same for other units as long as you keep them coherent (eg. if you input "
            "`µg` and `µg/cm³`, the bot will answer in `cm³`).*"
        )

        defaults = defaults or {}

        self.concentration = Label(
            text=localize("Concentration"),
            description=localize("(mg/mL)"),
            component=TextInput(
                placeholder="e.g., 10",
                default=defaults.get("concentration"),
                required=False,
            ),
        )
        self.mass = Label(
            text=localize("Substance mass"),
            description=localize("(mg)"),
            component=TextInput(
                placeholder="e.g., 5",
                default=defaults.get("mass"),
                required=False,
            ),
        )
        self.volume = Label(
            text=localize("Solution volume"),
            description=localize("(mL)"),
            component=TextInput(
                default=defaults.get("volume"),
                required=False,
            ),
        )

        for item in (
            TextDisplay(header),
            self.concentration,
            self.mass,
            self.volume,
            TextDisplay(footer),
        ):
            self.add_item(item)

    def remake_modal(self, **kwargs):
        """Return a new instance where inputs defaults are set from current values.
        Override keyword arguments are supported."""
        return self.__class__(
            defaults={
                var: getattr(self, var).component.value
                for var in ("concentration", "mass", "volume")
            },
            **kwargs,
        )

    @staticmethod
    def validate(label: Label):
        """Checks the component value is empty or a valid positive number."""
        if not label.component.value:
            return None

        try:
            val = to_float(label.component.value)
        except ValueError as err:
            raise ValueError(
                localize_fmt("Enter a valid number for {field}.", field=label.text)
            ) from err

        if val <= 0:
            raise ValueError(
                localize_fmt("{field} must be a positive number.", field=label.text)
            )

        return val

    async def on_submit(self, interaction: Interaction):
        try:
            concentration = self.validate(self.concentration)
            mass = self.validate(self.mass)
            volume = self.validate(self.volume)

            if sum(bool(var) for var in (concentration, mass, volume)) != 2:
                raise ValueError(localize("Please fill exactly two fields."))

        except ValueError as err:
            await interaction.response.send_message(
                embed=ErrorEmbed(str(err)),
                view=RetryModalView(self.remake_modal(error_message=str(err))),
                ephemeral=True,
            )
            return

        if not concentration:
            concentration = mass / volume
            result = f"{concentration:.3g} mg/mL"
            message = localize(
                "Dissolving **{m} mg** of substance in **{v} mL** results in a "
                "concentration of **{c:.3g} mg/mL**."
            )
            formula = "`{c}` = `{m}` / `{v}`"

        if not mass:
            mass = concentration * volume
            result = f"{mass:.3g} mg"
            message = localize(
                "To prepare **{v} mL** of a solution with a concentration of **{c} "
                "mg/mL**, you need **{m:.3g} mg** of substance."
            )
            formula = "`{m}` = `{c}` * `{v}`"

        if not volume:
            volume = mass / concentration
            result = f"{volume:.3g} mL"
            message = localize(
                "To get **{m} mg** of substance from a solution of **{c} mg/mL** of "
                "concentration, you need a volume of **{v:.3g} mL**."
            )
            formula = "`{v}` = `{m}` / `{c}`"

        await interaction.response.send_message(
            content=f"# = {result}",
            embed=DefaultEmbed(title=localize("🧪 Dilution Calculator"))
            .add_field(
                name=localize("🟰 Result"),
                value=message.format(
                    m=mass,
                    v=volume,
                    c=concentration,
                ),
                inline=False,
            )
            .add_field(
                name=localize("📜 Formula"),
                value=formula.format(
                    c=localize("concentration"),
                    m=localize("mass"),
                    v=localize("volume"),
                ),
                inline=False,
            ),
        )


class ScienceCog(Cog, name="Scientific module"):
    # PUG properties that will be shown in substance information embeds
    DEFAULT_PROPERTIES = (
        "MolecularFormula",
        "MolecularWeight",
        "IUPACName",
        "HBondDonorCount",
        "HBondAcceptorCount",
        "Complexity",
    )

    # DSSTox propetries names that will be shown in solubility embeds
    DSSTOX_PROPERTIES = (
        "Water Solubility",
        "LogKoa: Octanol-Air",
        "LogKow: Octanol-Water",
        "Melting Point",
        "Molar Volume",
        "Density",
        "Molar Refractivity",
        "Viscosity",
        "Polarizability",
    )

    def __init__(self, bot):
        self.bot = bot

    @command(
        name="substance",
        description=_("Display information about a chemical substance or compound."),
    )
    @send_embed_on_exception
    async def substance(self, interaction, substance: str):
        """`/substance` command"""
        set_locale(interaction)

        await interaction.response.defer(thinking=True)

        async with pubchem.AsyncPUGClient() as client:
            synonyms = await client.get_synonyms(substance)
            descriptions = await client.get_descriptions(substance)
            properties = await client.get_properties(substance, self.DEFAULT_PROPERTIES)

        if not synonyms:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize_fmt(
                        "Can't find substance {substance}", substance=substance
                    )
                )
            )
            return

        try:
            description = descriptions[1]["Description"]  # Default value
        except IndexError:
            description = localize("No description avalaible 🤔")
        for provider in settings.COMPOUNDS_DESCRIPTION_PROVIDERS:
            for desc in descriptions:
                try:
                    if provider.lower() in desc["DescriptionSourceName"].lower():
                        description = desc["Description"]
                        break
                except KeyError:
                    pass

        formula = properties["MolecularFormula"]
        weight = properties["MolecularWeight"]
        iupac_name = properties["IUPACName"]
        h_bond_donors = properties["HBondDonorCount"]
        h_bond_acceptors = properties["HBondAcceptorCount"]
        complexity = properties["Complexity"]

        schem_url = pubchem.get_schematic_url(substance)

        await interaction.followup.send(
            embed=PubChemEmbed(
                title=localize("Substance information: ") + synonyms[0].capitalize(),
                description=description,
            )
            .set_thumbnail(url=schem_url)
            .add_field(
                name=localize("🔬 IUPAC Name"),
                value=iupac_name.capitalize(),
                inline=False,
            )
            .add_field(name=localize("🏷 Synonyms"), value=pretty_list(synonyms[1:7]))
            .add_field(
                name=localize("🧪 Formula"),
                value=f"**{formula}**",
            )
            .add_field(
                name=localize("🏋 Molar mass"),
                value=f"{weight} g/mol",
            )
            .add_field(
                name=localize("🔗 Hydrogen bonds"),
                value=localize_fmt(
                    "Donors: {donors}\nAcceptors: {acceptors}",
                    donors=h_bond_donors,
                    acceptors=h_bond_acceptors,
                ),
            )
            .add_field(
                name=localize("🌀 Molecular complexity"),
                value=complexity,
            )
        )

    @command(
        name="schematic",
        description=_(
            "Display the shematic of a given chemical substance or compound. 2D and 3D "
            "modes are supported."
        ),
    )
    @send_embed_on_exception
    async def schematic(self, interaction, substance: str, mode: Mode = "2D"):
        """`/schematic` command"""
        set_locale(interaction)

        await interaction.response.defer(thinking=True)

        async with pubchem.AsyncPUGClient() as client:
            synonyms = await client.get_synonyms(substance)
            properties = await client.get_properties(
                substance, ("MolecularFormula", "IUPACName")
            )

        if not synonyms:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize_fmt(
                        "Can't find substance {substance}", substance=substance
                    )
                )
            )
            return

        formula = properties["MolecularFormula"]
        iupac_name = properties["IUPACName"]

        schem_url = pubchem.get_schematic_url(substance, mode)

        await interaction.followup.send(
            embed=(
                PubChemEmbed(
                    title=localize("Substance schematic: ") + synonyms[0].capitalize(),
                )
                .add_field(
                    name=localize("🔬 IUPAC Name"),
                    value=iupac_name.capitalize(),
                    inline=False,
                )
                .add_field(
                    name=localize("🧪 Formula"),
                    value=f"**{formula}**",
                )
                .set_image(url=schem_url)
            ),
            view=SchematicView(substance, mode),
        )

    @command(
        name="solubility",
        description=_(
            "Display solubility information about a substance. Multiple sources of "
            "data are averaged."
        ),
        extras={
            "long_description": _(
                "Display solubility information about a substance. Multiple sources of "
                "experimental and predicted data are averaged to improve result "
                "accuracy. Result ranges are provided when applicable."
            )
        },
    )
    @send_embed_on_exception
    async def solubility(self, interaction, substance: str):
        """`/solubility` command"""
        set_locale(interaction)

        await interaction.response.defer(thinking=True)

        match = await dsstox.get_substance(substance)
        if not match:
            await interaction.followup.send(
                embed=ErrorEmbed(
                    localize_fmt(
                        "Can't find substance {substance}", substance=substance
                    )
                )
            )
            return

        dsstox_id = match["dtxsid"]
        name = match["searchWord"]
        props = await dsstox.get_properties(dsstox_id)

        embed = EPAEmbed(
            title=localize_fmt("Solubility information: {name}", name=name)
        )

        props = props["data"]
        for prop in props:
            prop_name = prop["name"]
            if prop_name not in self.DSSTOX_PROPERTIES:
                continue

            unit = dsstox.format_units(prop["unit"])

            prop_text = ""
            for method in ("predicted", "experimental"):
                results = prop[method]
                if not results:
                    continue

                vals = [
                    r["value"]
                    for r in results["rawData"]
                    if r.get("modelName") not in settings.DSSTOX_EXCLUDED_MODELS
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
                    prop_text += f", {low:.3n}\xa0~\xa0{up:.3n}\n" + localize_fmt(
                        "*({method}, {count} sources)*\n", method=method, count=count
                    )

            if prop_text:
                embed.add_field(name=prop_name, value=prop_text.strip(), inline=True)

        await interaction.followup.send(embed=embed)

    @command(
        name="dilution",
        description=_("A small dilution calculator to help with volumetric dosing."),
    )
    @send_embed_on_exception
    async def dilution(self, interaction: Interaction):
        """`/dilution` command"""
        set_locale(interaction)

        await interaction.response.send_modal(DilutionModal())


setup = setup_cog(ScienceCog)
