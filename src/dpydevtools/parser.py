"""The parser used for the `DevTools.delegate` command.

:copyright: (c) 2022-present Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__author__ = "Tanner B. Corcoran"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022-present Tanner B. Corcoran"

import argparse
from . import exceptions


class CustomParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        self._messages: list[str] = []
        super().__init__(*args, **kwargs)

    def _print_message(self, message, file=None):
        if message:
            self._messages.append(message)
    
    def exit(self, status=0, message=None):
        if message:
            self._messages.append(message)
        messages = self._messages.copy()
        self._messages = []
        raise exceptions.ContainerException(messages)


class Action__StrInt(argparse.Action):
    def __call__(self, parser: argparse.ArgumentParser,
                 namespace: argparse.Namespace, values: list,
                 option_string: str = None) -> None:
        _str, _int = values
        try:
            _int = int(_int)
        except ValueError:
            raise argparse.ArgumentError(self, f"argument 2 must be an integer")
        setattr(namespace, self.dest, (_str, _int))


def make_parser(prog: str) -> CustomParser:
    PARSER = CustomParser(prog, description="developer and administrator tools for discord.py")
    PARSER__SUBPARSER = PARSER.add_subparsers()

    PARSER_ME = PARSER.add_mutually_exclusive_group()
    PARSER_ME.add_argument("-x", "--close", dest="_bot__close", help="close the bot", action="store_const", const=())
    PARSER_ME.add_argument("-u", "--uptime", dest="_bot__uptime", help="get the uptime of the bot", action="store_const", const=())
    PARSER_ME.add_argument("--update-requirements", dest="_bot__update_requirements", help="update the requirements.txt file", action="store_const", const=())
    PARSER_ME.add_argument("--reload-module", dest="_bot__reload_module", help="reload the given module", nargs=1, metavar=("<module_name_startswith>",))

    CG = PARSER__SUBPARSER.add_parser("control-groups", aliases=["cg"], description="manage control groups", help="manage control groups")
    CG_ME = CG.add_mutually_exclusive_group(required=True)
    CG_ME.add_argument("-l", "--list", dest="_control_groups__list", help="list all control groups and their current values", action="store_const", const=())
    CG_ME.add_argument("-E", "--edit-all", dest="_control_groups__edit_all", help="edit all control groups and set them to <value>", type=str, nargs=1, metavar=("<value>",))
    CG_ME.add_argument("-e", "--edit", dest="_control_groups__edit", help="edit a control group's value", type=str, nargs=2, metavar=("<name>", "<value>"))

    CW = PARSER__SUBPARSER.add_parser("control-whitelists", aliases=["cw"], description="manage whitelists", help="manage whitelists")
    CW_ME = CW.add_mutually_exclusive_group(required=True)
    CW_ME.add_argument("-l", "--list", dest="_control_whitelists__list", help="list all whitelist groups", action="store_const", const=())
    CW_ME.add_argument("-g", "--get", dest="_control_whitelists__get", help="list all users in the given whitelist", nargs=1, metavar=("<name>",))
    CW_ME.add_argument("-a", "--add", dest="_control_whitelists__add", help="add a user to the given whitelist", action=Action__StrInt, nargs=2, metavar=("<name>", "<userid>"))
    CW_ME.add_argument("-r", "--remove", dest="_control_whitelists__remove", help="remove a user from the given whitelist", action=Action__StrInt, nargs=2, metavar=("<name>", "<userid>"))

    CB = PARSER__SUBPARSER.add_parser("control-blacklists", aliases=["cb"], description="manage blacklists", help="manage blacklists")
    CB_ME = CB.add_mutually_exclusive_group(required=True)
    CB_ME.add_argument("-l", "--list", dest="_control_blacklists__list", help="list all blacklist groups", action="store_const", const=())
    CB_ME.add_argument("-g", "--get", dest="_control_blacklists__get", help="list all users in the given blacklist", nargs=1, metavar=("<name>",))
    CB_ME.add_argument("-a", "--add", dest="_control_blacklists__add", help="add a user to the given blacklist", action=Action__StrInt, nargs=2, metavar=("<name>", "<userid>"))
    CB_ME.add_argument("-r", "--remove", dest="_control_blacklists__remove", help="remove a user from the given blacklist", action=Action__StrInt, nargs=2, metavar=("<name>", "<userid>"))

    E = PARSER__SUBPARSER.add_parser("extensions", aliases=["e"], description="load, unload, and reload extensions", help="load, unload, and reload extensions")
    E_ME = E.add_mutually_exclusive_group(required=True)
    E_ME.add_argument("-l", "--list", dest="_extensions__list", help="list all current extensions", action="store_const", const=())
    E_ME.add_argument("-R", "--reload-all", dest="_extensions__reload_all", help="reload all extensions", action="store_const", const=())
    E_ME.add_argument("-r", "--reload", dest="_extensions__reload", help="reload an extension", nargs=1, metavar=("<name>",))
    E_ME.add_argument("-U", "--unload-all", dest="_extensions__unload_all", help="unload all extensions", action="store_const", const=())
    E_ME.add_argument("-u", "--unload", dest="_extensions__unload", help="unload an extension", nargs=1, metavar=("<name>",))
    E_ME.add_argument("-L", "--load-all", dest="_extensions__load_all", help="load all extensions", action="store_const", const=())
    E_ME.add_argument("-d", "--load", dest="_extensions__load", help="load an extension", nargs=1, metavar=("<name>",))

    S = PARSER__SUBPARSER.add_parser("sync", aliases=["s"], description="sync commands", help="sync commands")
    S_ME = S.add_mutually_exclusive_group(required=True)
    S_ME.add_argument("-G", "--guilds", dest="_sync__guilds", help="sync the local command tree to one or more guilds (as guild IDs)", nargs="+", metavar=("<guildid>", "<guildid>"))
    S_ME.add_argument("-c", "--current", dest="_sync__current", help="sync the local command tree to the current guild", action="store_const", const=())
    S_ME.add_argument("-g", "--global", dest="_sync__global", help="sync the local command tree to all guilds", action="store_const", const=())
    S_ME.add_argument("-p", "--copy-global-current", dest="_sync__copy_global_current", help="copy global commands in local command tree to the current guild", action="store_const", const=())
    S_ME.add_argument("-P", "--copy-global", dest="_sync__copy_global", help="copy global commands in local command tree to one or more guilds (as guild IDs)", nargs="+", metavar=("<guildid>", "<guildid>"))
    S_ME.add_argument("-C", "--clear", dest="_sync__clear_global", help="clear all global commands from the local command tree", action="store_const", const=())
    S_ME.add_argument("-x", "--clear-current", dest="_sync__clear_current", help="clear all commands from the local command tree of the current guild", action="store_const", const=())
    S_ME.add_argument("-X", "--clear-guilds", dest="_sync__clear_guilds", help="clear the local command tree for one or more guilds (as guild IDs)", nargs="+", metavar=("<guildid>", "<guildid>"))

    G = PARSER__SUBPARSER.add_parser("git", aliases=["g"], description="run git commands", help="run git commands")
    G_ME = G.add_mutually_exclusive_group(required=True)
    G_ME.add_argument("--pull", dest="_git__pull", help="run git pull", action="store_const", const=())
    
    C = PARSER__SUBPARSER.add_parser("commands", aliases=["c"], description="command information", help="command information")
    C_ME = C.add_mutually_exclusive_group(required=True)
    C_ME.add_argument("-l", "--list", dest="_commands__list", help="list the current commands", action="store_const", const=())

    T = PARSER__SUBPARSER.add_parser("trackers", aliases=["t"], description="get information from command trackers", help="get information from command trackers")
    T_ME = T.add_mutually_exclusive_group(required=True)
    T_ME.add_argument("-l", "--list", dest="_trackers__list", help="list all command trackers", action="store_const", const=())
    T_ME.add_argument("-g", "--get", dest="_trackers__get", help="get information from a command tracker", nargs=1, metavar=("<name>",))
    
    F = PARSER__SUBPARSER.add_parser("files", aliases=["f"], description="navigate, download, or replace files in the designated directory", help="navigate, download, or replace files in the designated directory")
    F_ME = F.add_mutually_exclusive_group(required=True)
    F_ME.add_argument("-l", "--list", dest="_files__list", help="list files and directories in the master path or given subpath", nargs="*", metavar=("<subpath>",))
    F_ME.add_argument("-d", "--download", dest="_files__download", help="download the file or directory specified by the master path or given subpath", nargs="*", metavar=("<subpath>",))
    F_ME.add_argument("-u", "--upload", dest="_files__upload", help="upload the file or directory specified by the master path or given subpath with a file (sent afterwards)", nargs="*", metavar=("<subpath>",))
    F_ME.add_argument("-r", "--remove", dest="_files__remove", help="remove the file or directory specified by the master path or given subpath", nargs="*", metavar=("<subpath>",))
    
    return PARSER
