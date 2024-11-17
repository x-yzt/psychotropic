import logging
from argparse import ArgumentParser

import discord


parser = ArgumentParser()
parser.add_argument(
    "-l",
    "--log",
    choices=logging._nameToLevel.keys(),
    default="INFO",
    help="Logging level."
)

log_level_name = parser.parse_args().log
log_level = logging._nameToLevel.get(log_level_name)

discord.utils.setup_logging(level=log_level)
