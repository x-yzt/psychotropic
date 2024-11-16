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

[1]: https://raw.githubusercontent.com/x-yzt/psychotropic/master/res/psychotropic.png

[2]: https://discord.com/oauth2/authorize?client_id=665177975053877259&scope=bot+applications.commands&permissions=277025442880
