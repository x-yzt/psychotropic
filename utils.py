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
