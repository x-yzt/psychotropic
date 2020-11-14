def pretty_list(items, capitalize=True):

    lst, chars = [], 0
    for item in items:
        item = item.strip()
        if not item:
            continue
        if capitalize:
            item = item.capitalize()
        
        chars += len(item)
        if chars > 2040:
            lst.append("● ...")
            break
        lst.append(f"● {item}")
    return '\n'.join(lst)
