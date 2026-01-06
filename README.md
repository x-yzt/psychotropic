# Psychotropic

*A discord bot built for harm reduction and chemistry.*

![Psychotropic logo][1]

## Getting started

Just [invite the bot to your own server][2], and see what it can do!

## Commands

Psychotropic has a comprehensive help system.

- `/about`

    Show various information about the bot.

- `/help`

    Display help page. All commands will be listed there ✨

## Credits

The *Structure game* is a complete rewrite of a proof of concept from arli,
thanks to them for sharing it!

## Running your own instance

### Installing

Python 3.10+ is needed to run `psychotropic`.

```bash
$> git clone https://github.com/x-yzt/psychotropic/

$> cd psychotropic

$> pip install .

$> export DISCORD_TOKEN="foobar"
```

### Running

```bash
$> python -m psychotropic.bot
```

*Note:* Persistant storage files will be created and searched in the directory
you invokes the command in, so be sure to `cd` in the directory you actually
want them.

### Converting scores from V1

The `scores.json` file was removed in favor of a more permissive `players.json`
file. This little script can help converting between the old and new format.

```py
import json

from psychotropic.cogs.games import Profile, ScoreboardJSONEncoder
from psychotropic.settings import STORAGE_DIR


with open(STORAGE_DIR / 'scores.json') as file:
    data = {
        uid: Profile(balance=max((0, balance)))
        for uid, balance in json.load(file).items()
    }

with open(STORAGE_DIR / 'players.json', 'w') as file:
    json.dump(data, file, cls=ScoreboardJSONEncoder)

print(f"Converted {len(data)} scoreboard entries.")
```

## Translations

Psychotropic uses `Babel` for localization, and leverages a common `GNU/gettext`
infrastructure.

- To add a translation catalog for a new language, eg. for Spanish (`es`):
```shell
uv run pybabel extract -F pyproject.toml -k _ -k localize -k localize_fmt -o messages.pot .
uv run pybabel init -i messages.pot -d ./psychotropic/locales/ -l es
```

- To update translations catalogs from source code:
```shell
uv run pybabel extract -F pyproject.toml -k _ -k localize -k localize_fmt -o messages.pot .
pybabel update -i ./messages.pot -d ./psychotropic/locales/
```

- To compile `.po` files into `.mo` after changing them:
```shell
pybabel compile -d ./psychotropic/locales/
```

[1]: https://raw.githubusercontent.com/x-yzt/psychotropic/master/res/psychotropic.png

[2]: https://discord.com/oauth2/authorize?client_id=665177975053877259&scope=bot+applications.commands&permissions=277025442880
