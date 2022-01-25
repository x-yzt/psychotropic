# Psychotropic

A discord bot built for harm reduction.

## Commands

### General

- `>about`

    Show various information about the bot.

- `>help`

    Show help page.

### Science module

- `>substance [substance name]`:

    Display general information about a given chemical substance or compound.

    Aliases names are supported.

- `>schem [substance name] <2d|3d>`:

    Display the shematic of a given chemical substance or compound.

    2D and 3D modes are supported.

- `>solubility [substance name]`:

    Display solubility-related properties about a given substance.

    Multiple sources of experimental and predicted data are averaged to improve
    result accuracy. Result ranges are provided when applicable.

### Factsheets module

- `>factsheet [drug name]`:

    Display a short factsheet concerning a certain drug.

### Structure Game module

The *Structure Game* is a drug chemical structure guessing game. It is a
complete rewrite of a proof of concept from Arli, thanks to them for sharing
it! ✨

- `>game start`:

    Start a new Structure Game. The bot will pick a random molecule schematic,
    and the first player to write its name in the chat will win.

    A certain number of coins (🪙), corresponding to the number of letters
    guessed will be awarded to the winner.

- `>game end`:

    End a running Structure Game. To end a game, you must either own it or have
    permission to manage messages in the current channel.

- `>game scores <page number>`:

    Show a given page of the scoreboard.

## Running your own instance

### Installing

Python 3.6+ is needed to run `psychotropic`.

```bash
$> git clone https://github.com/x-yzt/psychotropic/

$> pip install -r requirements.txt

$> export DISCORD_TOKEN="foobar"
```

### Running

```bash
$> python -m psychotropic.bot
```

*Note:* Persistant storage files will be created and searched in the directory
you invokes the command in, so be sure to `cd` in the directory you actually
want them.
