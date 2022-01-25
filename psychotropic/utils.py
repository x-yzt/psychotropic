import unicodedata
from random import sample


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


def setup_cog(cog):
    """Helper function to be used in cog modules. Usage:
    setup = setup_cog(MyAwesomeCog)
    """
    return lambda bot: bot.add_cog(cog(bot))


class classproperty(property):
    """This decorator works on classes as `@properties` does on instances. This
    is needed because Python < 3.9 does not support decorating a method with
    both @classmethod and @property.
    """
    def __get__(self, obj, type_=None):
        return super().__get__(type_)

    def __set__(self, obj, value):
        super().__set__(type(obj), value)

    def __delete__(self, obj):
        super().__delete__(type(obj))


def unaccent(string):
    """Return an unaccented version of a string."""
    return (unicodedata.normalize('NFKD', string)
        .encode('ASCII', 'ignore')
        .decode('utf-8')
    )

def shuffled(collection):
    """Not inplace equivalent to usual random.shuffle."""
    return sample(collection, len(collection))
