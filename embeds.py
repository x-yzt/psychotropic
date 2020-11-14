from discord import Embed, Colour
import settings


class DefaultEmbed(Embed):

    def __init__(self, **kwargs):

        super().__init__(
            type = 'rich',
            colour = settings.COLOUR,
            **kwargs
        )


class ErrorEmbed(Embed):

    def __init__(self, msg=None, info=None, **kwargs):

        msg = msg or "Something went wrong"
        super().__init__(
            type = 'rich',
            colour = Colour.red(),
            title = f"Error: {msg} :(",
            description = info,
            **kwargs
        )
