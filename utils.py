from discord import Embed, Colour


class ErrorEmbed(Embed):

    def __init__(self, title='', message='', *args, **kwargs):
        
        if title:
            title = f'Error: {title} :('
        else:
            title = 'Error :('

        super().__init__(
            type = 'rich',
            colour = Colour.red(),
            title = title,
            description = message,
            *args, **kwargs
        )


def pretty_list(items):

    format_item = lambda item: f"     ● {item.capitalize()}"
    return '\n'.join(map(format_item, items))
