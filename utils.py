from discord import Embed, Colour


class ErrorEmbed(Embed):

    def __init__(self, title='', message='', *args, **kwargs):
        
        if title:
            title = f'Error: {title} :('
        else:
            title = 'Error :('

        super().__init__(
            type='rich',
            colour=Colour.red(),
            title=title,
            description=message,
            *args, **kwargs
        )


def pretty_list(items, capitalize=True):

    if capitalize:
        format_item = lambda item: f"● {item.capitalize()}"
    else:
        format_item = lambda item: f"● {item}"
    
    items = map(format_item, items)
    lst = ''
    for item in items:
        if len(lst) + len(item) > 2040:
            lst += '\n ● ...'
            break
        lst += '\n' + item
    return lst
