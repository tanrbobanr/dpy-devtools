"""Utilities used throughout the module.

:copyright: (c) 2022-present Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__author__ = "Tanner B. Corcoran"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022-present Tanner B. Corcoran"

from discord.ext import commands
from . import constants
import pathlib
import logging
import pkgutil
import discord
import typing
import sys
import os

# ADAPTED FROM discord.py
def stream_supports_color(stream: typing.Any) -> bool:
    # Pycharm and Vscode support colour in their inbuilt editors
    if ("PYCHARM_HOSTED" in os.environ or
        os.environ.get("TERM_PROGRAM") == "vscode"):
        return True

    is_a_tty = hasattr(stream, 'isatty') and stream.isatty()
    if sys.platform != "win32":
        return is_a_tty

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return is_a_tty and ("ANSICON" in os.environ or "WT_SESSION" in os.environ)

# ADAPTED FROM discord.py
def setup_logging(logger: logging.Logger, level: int | str):
    handler = logging.StreamHandler()

    if stream_supports_color(handler.stream):
        formatter = _ColourFormatter()
    else:
        dt_fmt = "%Y-%m-%d %H:%M:%S"
        formatter = logging.Formatter("[{asctime}] [{levelname:<8}] {name}: "
                                      "{message}", dt_fmt, style='{')

    handler.setFormatter(formatter)
    logger.setLevel(level)
    logger.addHandler(handler)


def _ensure_chars_allowed(__str: str) -> None:
    if not set(__str).issubset(constants.ALLOWCHARS):
        raise ValueError(f"\"{__str}\" must only include lowercase "
                         "alphanumericals and underscores")


def _get_extensions(path: pathlib.Path, include_prefix: bool = True) -> list[str]:
    if include_prefix:
        return [m.name for m in pkgutil.iter_modules([str(path)], f"{'.'.join(path.parts)}.")]
    return [m.name for m in pkgutil.iter_modules([str(path)])]


class make_message:
    @staticmethod
    def _make(body: str, color: int) -> discord.Embed:
        embed = discord.Embed(color=color, description="```\n" + body + "```")
        embed.set_footer(text=constants.CREATOR_REFERENCE)
        return embed

    @staticmethod
    def _raw(body: str, color: int, **kwargs) -> discord.Embed:
        embed = discord.Embed(color=color, description=body, **kwargs)
        embed.set_footer(text=constants.CREATOR_REFERENCE)
        return embed

    @staticmethod
    def _pos(body: str) -> discord.Embed:
        return make_message._make(body, constants.EMBED_COLOR__POS)
    
    @staticmethod
    def _neg(body: str) -> discord.Embed:
        return make_message._make(body, constants.EMBED_COLOR__NEG)
    
    @staticmethod
    def _def(body: str) -> discord.Embed:
        return make_message._make(body, constants.EMBED_COLOR__DEF)


def get_user_id(utx: commands.Context | discord.Interaction) -> int:
    try:
        id = utx.author.id
        if id:
            return id
    except Exception:
        return utx.user.id


def get_sender(utx: commands.Context | discord.Interaction):
    if isinstance(utx, commands.Context):
        return utx.send
    if utx.response.is_done():
        return utx.followup.send
    return utx.response.send_message


def get_guild_id(utx: commands.Context | discord.Interaction) -> int:
    try:
        return utx.guild.id
    except Exception:
        return

def get_utx(values: typing.Iterable) -> commands.Context | discord.Interaction:
    for v in values:
        if isinstance(v, (commands.Context, discord.Interaction)):
            return v

# ADAPTED FROM discord.py
class _ColourFormatter(logging.Formatter):
    LEVEL_COLORS = [
        (logging.DEBUG, '\x1b[40;1m'),
        (logging.INFO, '\x1b[34;1m'),
        (logging.WARNING, '\x1b[33;1m'),
        (logging.ERROR, '\x1b[31m'),
        (logging.CRITICAL, '\x1b[41m'),
    ]

    FORMATS = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {colour}%(levelname)-8s\x1b[0m "
            "\x1b[35m%(name)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, colour in LEVEL_COLORS
    }

    def format(self, record):
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output