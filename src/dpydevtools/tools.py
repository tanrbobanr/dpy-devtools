"""The core code.

:copyright: (c) 2022-present Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__author__ = "Tanner B. Corcoran"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022-present Tanner B. Corcoran"

from . import enums
from . import constants
from . import parser
from . import exceptions
from . import utils
from discord import app_commands
from discord.ext import commands
import collections
import subprocess
import functools
import importlib
import datetime
import discord
import logging
import pathlib
import zipfile
import random
import string
import time
import sys
import os
import io


_logger = logging.getLogger(__name__)


class ControlGroups:
    """Container for command control groups.
    
    """
    def __init__(self, __moderators: list[int] = None,
                 __administrators: list[int] = None,
                 __developers: list[int] = None,
                 __cg_defaults: dict[str, enums.ControlGroupOptions] = None
                 ) -> None:
        self._moderators = __moderators or []
        self._administrators = __administrators or []
        self._developers = __developers or []
        self._groups = {"global": enums.ControlGroupOptions.enabled}
        if __cg_defaults:
            self._groups.update(__cg_defaults)
            self._ensure_default_validity()

    def _ensure_default_validity(self) -> None:
        for k, v in self._groups.items():
            utils._ensure_chars_allowed(k)
            if not isinstance(v, enums.ControlGroupOptions):
                raise ValueError(f"\"{v}\" is not a valid control group option")

    def __getitem__(self, __key: str, /) -> enums.ControlGroupOptions | None:
        _logger.debug("acquiring control group %s", __key)
        if __key is None:
            return
        if __key not in self._groups:
            _logger.debug("creating control group %s with default of inherit",
                          __key)
            self._groups[__key] = enums.ControlGroupOptions.inherit
        return self._groups[__key]
    
    def __setitem__(self, __key: str,
                    __value: enums.ControlGroupOptions, /) -> None:
        _logger.debug("setting control group %s to %s", __key, __value)
        if not isinstance(__value, enums.ControlGroupOptions):
            raise ValueError(f"\"{__value}\" is not a valid control group "
                             "option")
        self._groups[__key] = __value
    
    def check(self, __group: str, __userid: int, /) -> bool:
        _logger.debug("initiating control group (%s) check for %s", __group,
                      __userid)
        cgvalue = self[__group]
        if cgvalue == enums.ControlGroupOptions.inherit:
            cgvalue = self["global"]

        if cgvalue == enums.ControlGroupOptions.inherit:
            return True
        if cgvalue == enums.ControlGroupOptions.enabled:
            return True
        if (cgvalue == enums.ControlGroupOptions.modplus and __userid in
            self._moderators + self._administrators + self._developers):
            return True
        if (cgvalue == enums.ControlGroupOptions.adminplus and __userid in
            self._administrators + self._developers):
            return True
        if (cgvalue == enums.ControlGroupOptions.devonly and __userid in
            self._developers):
            return True
        return False


class UserGroups:
    """Container for command user groups (whitelist/blacklist).
    
    """
    def __init__(self, __defaults: dict[str, list[int]] = None) -> None:
        self._groups = __defaults or {}
        if __defaults:
            self._ensure_default_validity()

    def _ensure_default_validity(self) -> None:
        for k, v in self._groups.items():
            utils._ensure_chars_allowed(k)
            for _v in v:
                if not isinstance(_v, int):
                    raise ValueError("\"{_v}\" must be integer parsable")

    def __getitem__(self, __key: str, /) -> list[int]:
        _logger.debug("acquiring user group %s", __key)
        if __key is None:
            return
        if __key not in self._groups:
            _logger.debug("creating user group %s", __key)
            self._groups[__key] = []
        return self._groups[__key]
    
    def check(self, __group: str, __userid: int, /) -> bool:
        if __userid in self[__group]:
            return True
        return False


class TrackingSession:
    """A session created by `Tracker`. Used to track when a user is using a
    command.

    """
    def __init__(self, __tracker: "Tracker", __guildid: int,
                 __userid: int) -> None:
        self._tracker = __tracker
        self._entry = f"{__userid}@{__guildid}"
    
    async def __aenter__(self) -> None:
        _logger.debug("entering tracking session (%s)", self._entry)
        self._tracker._active.append(self._entry)
    
    async def __aexit__(self, exc, exc_type, exc_tb) -> None:
        _logger.debug("exiting tracking session (%s)", self._entry)
        self._tracker._active.remove(self._entry)


class Tracker:
    """A command tracker.
    
    """
    def __init__(self) -> None:
        self._active: list[str] = []
        self._history: collections.deque[str] = collections.deque(maxlen=15)
        self._counts: dict[int, int] = {}
    
    def __call__(self, __guildid: int, __userid: int) -> TrackingSession:
        if __guildid not in self._counts:
            _logger.debug("creating new tracker count for guild %s", __guildid)
            self._counts[__guildid] = 1
        else:
            _logger.debug("incrementing tracker count for guild %s", __guildid)
            self._counts[__guildid] += 1
        datestr = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        self._history.append(f"{__userid}@{datestr}")
        _logger.debug("creating new tracking session")
        return TrackingSession(self, __guildid, __userid)


class TrackerGroups:
    """A container for trackers.
    
    """
    def __init__(self, defaults: dict[str, Tracker] = None) -> None:
        self._groups: dict[str, Tracker] = defaults or {}

    def __getitem__(self, __key: str, /) -> Tracker:
        _logger.debug("acquiring tracker %s", __key)
        if __key is None:
            return
        if __key not in self._groups:
            _logger.debug("creating tracker %s", __key)
            self._groups[__key] = Tracker()
        return self._groups[__key]


class NamedBuffer(io.BufferedReader):
    def __init__(self, name: str, raw: io.RawIOBase) -> None:
        self._name = name
        super().__init__(raw)
    
    @property
    def name(self) -> str:
        return self._name


class DevTools:
    """The main class used to run the control command as well as modify existing
    commands.
    
    """
    def __init__(self, prog: str,
                 controller: commands.Bot | discord.Client,
                 extensions_path: str = None,
                 cg_defaults: dict[str, enums.ControlGroupOptions] = None,
                 cg_moderators: list[int] = None,
                 cg_administrators: list[int] = None,
                 cg_developers: list[int] = None,
                 cw_defaults: dict[str, list[int]] = None,
                 cb_defaults: dict[str, list[int]] = None,
                 tracker_defaults: dict[str, Tracker] = None,
                 files_path: str = None,
                 requirements_path: str = None,
                 log_level: int | str = logging.INFO) -> None:
        """Arguments
        ---------
        prog : str
            The `prog` name for the `argparse.ArgumentParser`.
        controller : Bot or Client
            The bot or client.
        extensions_path : str, optional, default=None
            The path to the extensions/modules.
        cg_defaults : dict of str and ControlGroupOptions, optional,
        default=None
            Control group defaults.
        cg_moderators : list of int, optional, default=None
            List of users who are moderators.
        cg_administrators : list of int, optional, default=None
            List of users who are administrators.
        cg_developers : list of int, optional, default=None
            List of users who are developers.
        cw_defaults : dict of str and list of int, optional, default=None
            Control whitelist defaults.
        cb_defaults : dict of str and list of int, optional, default=None
            Control blacklist defaults.
        tracker_defaults : dict of str and Tracker, optional, default=None
            Command tracker defaults.

        """
        setattr(controller, "__dpy_devtools__", self)
        utils.setup_logging(_logger, log_level)
        self._start_ts = time.time()
        self._prog = prog
        self._controller = controller
        self._control_groups = ControlGroups(cg_moderators, cg_administrators,
                                             cg_developers, cg_defaults)
        self._control_whitelists = UserGroups(cw_defaults)
        self._control_blacklists = UserGroups(cb_defaults)
        self._trackers = TrackerGroups(tracker_defaults)
        self._extensions_path = extensions_path
        self._files_path = files_path
        self._requirements_path = requirements_path
    
    def _check(self, __cg: str, __cw: str, __cb: str, __userid: int) -> bool:
        _logger.debug("beginning check -> cg=%s cw=%s cb=%s userid=%s", __cg,
                      __cw, __cb, __userid)
        if not __cg and not __cw and not __cb:
            return True
        if __cb and self._control_blacklists.check(__cb, __userid):
            return False
        if __cw and self._control_whitelists.check(__cw, __userid):
            return True
        if __cg and self._control_groups.check(__cg, __userid):
            return True
        return False

    @staticmethod
    def get(bot: commands.Bot) -> "DevTools":
        """Get the `DevTools` instance stored in the `commands.Bot` instance.
        Equivalent to: `return bot.__dpy_devtools__`.
        
        """
        dt_inst = getattr(bot, "__dpy_devtools__", None)
        if dt_inst is None:
            raise ValueError("No DevTools instance has been initialized with "
                             "this bot")
        return dt_inst

    def command(self, *, group: str = None, whitelist: str = None,
                blacklist: str = None, tracker: str = None,
                ignore: bool = False):
        """Sets up the decorated command for controlling/tracking. When using
        cogs, group cogs, etc., the `.placeholder` decorator should be used,
        along with the `.resolve_placeholders` method (which should be called
        inside `__init__`).

        Arguments
        ---------
        group : str, default=None
            The control group this command belongs to. If this value is
            provided, but no control group of the given name exists, a new one
            is created with the given name that defaults to `inherit`.
        whitelist : str, default=None
            The user whitelist this command belongs to. If this value is
            provided, but no whitelist of the given name exists, a new (empty)
            one is created.
        blacklist : str, default=None
            The user blacklist this command belongs to. If this value is
            provided, but no blacklist of the given name exists, a new (empty)
            one is created.
        tracker : str, default=None
            The tracker this command belongs to. If this value is provided, but
            no tracker of the given name exists, a new one is created.
        ignore : bool, default=False
            If set to True, no error will be thrown if the user attempts to
            decorate a non-command or non-context-menu function.

        """
        _logger.debug("creating command/menu decorator -> group=%s, "
                           "whitelist=%s, blacklist=%s, tracker=%s, ignore=%s",
                           group, whitelist, blacklist, tracker, ignore)
        self._control_groups[group]
        self._control_whitelists[whitelist]
        self._control_blacklists[blacklist]
        self._trackers[tracker]

        def decorator(cmd):
            if not ignore and not isinstance(cmd, (commands.Command,
                                                   app_commands.Command,
                                                   app_commands.ContextMenu)):
                raise ValueError("The decoration target must be a Command "
                                 "instance")
            _logger.debug("decorating command/menu %s",
                          getattr(cmd, "name", None) or cmd.__name__)
            @functools.wraps(cmd)
            async def wrapper(*args, **kwargs):
                if (group is None and whitelist is None and blacklist is None
                    and tracker is None) or not args:
                    return await cmd(*args, **kwargs)
                utx = utils.get_utx(args)
                userid = utils.get_user_id(utx)
                guildid = utils.get_guild_id(utx)
                sender = utils.get_sender(utx)
                passed = self._check(group, whitelist, blacklist, userid)
                if not passed:
                    embed = utils.make_message._neg(constants.M_COMMAND_LOCKED)
                    await sender(embed=embed)
                    return
                if tracker:
                    async with self._trackers[tracker](guildid, userid) as _:
                        return await cmd(*args, **kwargs)
                return await cmd(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def placeholder(**kwargs: str):
        """Placeholder to be used in classes such as cogs. Same keyword
        arguments as `.command`.
        
        """
        def decorator(cmd):
            if not isinstance(cmd, (commands.Command, app_commands.Command,
                                    app_commands.ContextMenu)):
                raise ValueError("The decoration target must be a Command "
                                 "instance; one fix may be to ensure this "
                                 "decorator is at the top")
            setattr(cmd._callback, "__dpy_devtools_placeholder__", kwargs)
            return cmd
        return decorator
    
    def resolve_placeholders(self, obj: object) -> None:
        """Resolve any placeholders contained in `obj`.
        
        """
        _logger.debug("resolving placeholders for %s",
                      obj.__class__.__name__)
        for name in dir(obj):
            child = getattr(obj, name)

            # skip if child isn't able to be decorated
            # with our decorator anyway
            if not isinstance(child, (commands.Command, app_commands.Command,
                                      app_commands.ContextMenu)):
                continue
            kwargs = getattr(child._callback, "__dpy_devtools_placeholder__",
                             None)
            
            # skip if the given command/menu isn't decorated
            # with a placeholder
            if kwargs is None:
                continue
            _logger.debug("found command/menu instance %s with "
                          "placeholder", name)
            self.add_command(child, **kwargs)

    def add_command(self, cmd: commands.Command | app_commands.Command
                               | app_commands.ContextMenu,
                    **kwargs: str) -> None:
        """Adds a command without the need for a decorator. Same keyword
        arguments as `.command`.
        
        """
        # ignore=True because were using the decorator on the
        # callback function intentionally
        kwargs["ignore"] = True
        _logger.debug("adding command %s to DevTools instance -> %s",
                      getattr(cmd, "name", None) or cmd.__name__,
                      ", ".join(f"{k}={v}" for k, v in kwargs.items()))
        cmd._callback = self.command(**kwargs)(cmd._callback)
        
    async def delegate(self, ctx: commands.Context,
                       *queries: str) -> None:
        """The function to be used as the controller command.
        
        """
        _parser = parser.make_parser(self._prog)
        try:
            parsed = _parser.parse_args(queries)
            func = None
            args = None
            for k, v in vars(parsed).items():
                if v is not None:
                    func = getattr(self, k, None)
                    args = v
                    break
            if not func:
                _parser.parse_args(["-h"])
            await func(_parser, ctx, *args)
        except exceptions.ContainerException as exc:
            embed = utils.make_message._neg("\n".join(exc.messages))
            await ctx.send(embed=embed)
    
    async def _bot__close(self, parser_: parser.CustomParser,
                          ctx: commands.Context) -> None:
        embed = utils.make_message._pos("Bot is being closed...")
        await ctx.send(embed=embed)
        await self._controller.close()

    async def _bot__uptime(self, parser_: parser.CustomParser,
                           ctx: commands.Context) -> None:
        uptime_seconds = int(time.time() - self._start_ts)
        m, s = divmod(uptime_seconds, 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        embed = utils.make_message._def(f"UPTIME: {d}d {h}h {m}m {s}s")
        await ctx.send(embed=embed)

    async def _bot__update_requirements(self, parser_: parser.CustomParser,
                                        ctx: commands.Context) -> None:
        if not self._requirements_path:
            parser_.error("this instance has not be set up with a requirements path")
        await ctx.send(embed=utils.make_message._pos("Updating requirements..."))
        vers = sys.version_info
        args = ("py", f"-{vers.major}.{vers.minor}", "-m", "pip", "install", "-U", "-r",
                self._requirements_path)
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        output = process.communicate()[0]
        if not output:
            await ctx.send(embed=utils.make_message._neg("Requirements path is invalid."))
            return
        await ctx.send(embed=utils.make_message._pos("Requirements updated."))
        await ctx.send(file=discord.File(io.BytesIO(output), "log.txt"))
    
    async def _bot__reload_module(self, parser_: parser.CustomParser, ctx: commands.Context,
                                  module: str) -> None:
        errors: list[tuple[str, str]] = []
        total_found = 0
        current_modules = list(sys.modules.values())
        for m in current_modules:
            if m is None:
                continue
            if m.__name__.startswith(module):
                total_found += 1
                try:
                    importlib.reload(m)
                except Exception as exc:
                    errors.append((m.__name__, str(exc)))
        
        if not errors:
            embed = utils.make_message._pos(f"Reloaded {total_found} of {total_found} module(s).")
            await ctx.send(embed=embed)
            return
        
        formatted_errors = "\n".join([f"Error when reloading '{m}': {e}" for m, e in errors])
        embed = utils.make_message._neg(f"Reloaded {total_found - len(errors)} of {total_found} "
                                        f"module(s).\n\n{formatted_errors}")
        await ctx.send(embed=embed)

    async def _control_groups__list(self, parser_: parser.CustomParser,
                                    ctx: commands.Context) -> None:
        max_key_len = max(len(k) for k in self._control_groups._groups.keys())
        max_val_len = max(len(v.value) for v in
                          self._control_groups._groups.values())
        body = "\n".join(f"{k: <{max_key_len}} -> {v.value: >{max_val_len}}"
                        for k, v in self._control_groups._groups.items())
        embed = utils.make_message._def(body)
        await ctx.send(embed=embed)

    async def _control_groups__edit_all(self, parser_: parser.CustomParser,
                                        ctx: commands.Context,
                                        __value: str) -> None:
        try:
            value = enums.ControlGroupOptions(__value)
        except ValueError:
            parser_.error(f"invalid choice: '{__value}' (choose from "
                           "'disabled', 'enabled', 'inherit', 'modplus', "
                           "'adminplus', 'devonly')")
        for group in self._control_groups._groups:
            self._control_groups[group] = value
        embed = utils.make_message._pos(f"set {len(self._control_groups._groups)} "
                                        f"control groups to {__value}")
        await ctx.send(embed=embed)

    async def _control_groups__edit(self, parser_: parser.CustomParser,
                                    ctx: commands.Context, __group: str,
                                    __value: str) -> None:
        try:
            value = enums.ControlGroupOptions(__value)
        except ValueError:
            parser_.error(f"invalid choice: '{__value}' (choose from "
                           "'disabled', 'enabled', 'inherit', 'modplus', "
                           "'adminplus', 'devonly')")
        if __group not in self._control_groups._groups:
            parser_.error(f"group '{__group}' not found")
        old = self._control_groups._groups[__group].value
        self._control_groups[__group] = value
        embed = utils.make_message._pos(f"edited group '{__group}': value changed "
                                        f"from '{old}' to '{__value}'")
        await ctx.send(embed=embed)

    async def _control_whitelists__list(self, parser_: parser.CustomParser,
                                        ctx: commands.Context) -> None:
        values = list(self._control_whitelists._groups.keys())
        embed = utils.make_message._def(", ".join(values) or "NONE")
        await ctx.send(embed=embed)

    async def _control_whitelists__get(self, parser_: parser.CustomParser,
                                       ctx: commands.Context,
                                       __name: str) -> None:
        if __name not in self._control_whitelists._groups:
            parser_.error(f"whitelist '{__name}' not found")
        whitelist = self._control_whitelists[__name]
        body = ", ".join(str(v) for v in whitelist)
        embed = utils.make_message._def(body or "NONE")
        await ctx.send(embed=embed)

    async def _control_whitelists__add(self, parser_: parser.CustomParser,
                                       ctx: commands.Context, __name: str,
                                       __userid: str) -> None:
        try:
            userid = int(__userid)
        except ValueError:
            parser_.error(f"userid '{__userid}' is not integer parsable")
        if __name not in self._control_whitelists._groups:
            parser_.error(f"whitelist '{__name}' not found")
        if userid in self._control_whitelists[__name]:
            parser_.error(f"whitelist '{__name}' already contains the "
                           f"userid '{__userid}'")
        self._control_whitelists[__name].append(userid)
        embed = utils.make_message._pos(f"userid '{__userid}' added to the whitelist"
                                  f" '{__name}'")
        await ctx.send(embed=embed)

    async def _control_whitelists__remove(self, parser_: parser.CustomParser,
                                          ctx: commands.Context, __name: str,
                                          __userid: str) -> None:
        try:
            userid = int(__userid)
        except ValueError:
            parser_.error(f"userid '{__userid}' is not integer parsable")
        if __name not in self._control_whitelists._groups:
            parser_.error(f"whitelist '{__name}' not found")
        if userid not in self._control_whitelists[__name]:
            parser_.error(f"whitelist '{__name}' does not contains the userid"
                           f" '{__userid}'")
        self._control_whitelists[__name].remove(userid)
        embed = utils.make_message._pos(f"userid '{__userid}' removed from the "
                                  "whitelist '{__name}'")
        await ctx.send(embed=embed)

    async def _control_blacklists__list(self, parser_: parser.CustomParser,
                                        ctx: commands.Context) -> None:
        values = list(self._control_blacklists._groups.keys())
        embed = utils.make_message._def(", ".join(values) or "NONE")
        await ctx.send(embed=embed)

    async def _control_blacklists__get(self, parser_: parser.CustomParser,
                                       ctx: commands.Context,
                                       __name: str) -> None:
        if __name not in self._control_blacklists._groups:
            parser_.error(f"blacklist '{__name}' not found")
        blacklist = self._control_blacklists[__name]
        body = ", ".join(str(v) for v in blacklist)
        embed = utils.make_message._def(body or "NONE")
        await ctx.send(embed=embed)

    async def _control_blacklists__add(self, parser_: parser.CustomParser,
                                       ctx: commands.Context, __name: str,
                                       __userid: str) -> None:
        try:
            userid = int(__userid)
        except ValueError:
            parser_.error(f"userid '{__userid}' is not integer parsable")
        if __name not in self._control_blacklists._groups:
            parser_.error(f"blacklist '{__name}' not found")
        if userid in self._control_blacklists[__name]:
            parser_.error(f"blacklist '{__name}' already contains the userid"
                           f" '{__userid}'")
        self._control_blacklists[__name].append(userid)
        embed = utils.make_message._pos(f"userid '{__userid}' added to the blacklist"
                                  f" '{__name}'")
        await ctx.send(embed=embed)

    async def _control_blacklists__remove(self, parser_: parser.CustomParser,
                                          ctx: commands.Context, __name: str,
                                          __userid: str) -> None:
        try:
            userid = int(__userid)
        except ValueError:
            parser_.error(f"userid '{__userid}' is not integer parsable")
        if __name not in self._control_blacklists._groups:
            parser_.error(f"blacklist '{__name}' not found")
        if userid not in self._control_blacklists[__name]:
            parser_.error(f"blacklist '{__name}' does not contains the userid"
                           f" '{__userid}'")
        self._control_blacklists[__name].remove(userid)
        embed = utils.make_message._pos(f"userid '{__userid}' removed from the "
                                  f"blacklist '{__name}'")
        await ctx.send(embed=embed)

    async def _extensions__list(self, parser_: parser.CustomParser,
                                ctx: commands.Context) -> None:
        if not self._extensions_path:
            parser_.error("this instance is not set up for extension "
                           "manipulation")
        num_extensions, paths = utils._get_extensions(self._extensions_path,
                                                      True)
        embed = utils.make_message._def(", ".join(paths) or "NONE")
        await ctx.send(embed=embed)

    async def _extensions__reload_all(self, parser_: parser.CustomParser,
                                      ctx: commands.Context) -> None:
        num_extensions = len(self._controller.extensions)
        if num_extensions == 0:
            parser_.error("there are no loaded extensions to reload")
        num_succeeded = 0
        ext_paths = list(self._controller.extensions.keys())
        for e in ext_paths:
            try:
                await self._controller.reload_extension(e)
                num_succeeded += 1
            except Exception:
                pass
        embed = utils.make_message._pos(f"extensions reloaded: {num_succeeded}"
                                  f" of {num_extensions}")
        await ctx.send(embed=embed)

    async def _extensions__reload(self, parser_: parser.CustomParser,
                                  ctx: commands.Context, __name: str) -> None:
        if not self._extensions_path:
            parser_.error("individual extension reloading is not possible "
                           "without 'extensions_path' being set in the "
                           "'AdminTools' instance")
        ext_pkg = self._extensions_path.replace("\\", ".")
        ext_path = f"{ext_pkg}.{__name}"
        if ext_path not in self._controller.extensions:
            parser_.error(f"the extension '{ext_path}' is not currently loaded"
                           " and thus cannot be reloaded")
        try:
            await self._controller.reload_extension(ext_path)
        except Exception as exc:
            parser_.error("an error occurred in the extension reloading "
                           f"process: {exc}")
        embed = utils.make_message._pos(f"extension '{ext_path}' has been reloaded")
        await ctx.send(embed=embed)

    async def _extensions__unload_all(self, parser_: parser.CustomParser,
                                      ctx: commands.Context) -> None:
        num_extensions = len(self._controller.extensions)
        if num_extensions == 0:
            parser_.error("there are no loaded extensions to unload")
        num_succeeded = 0
        ext_paths = list(self._controller.extensions.keys())
        for e in ext_paths:
            try:
                await self._controller.unload_extension(e)
                num_succeeded += 1
            except Exception:
                pass
        embed = utils.make_message._pos(f"extensions unloaded: {num_succeeded} of "
                                  f"{num_extensions}")
        await ctx.send(embed=embed)

    async def _extensions__unload(self, parser_: parser.CustomParser,
                                  ctx: commands.Context, __name: str) -> None:
        if not self._extensions_path:
            parser_.error("individual extension unloading is not possible "
                           "without 'extensions_path' being set in the "
                           "'AdminTools' instance")
        ext_pkg = self._extensions_path.replace("\\", ".")
        ext_path = f"{ext_pkg}.{__name}"
        if ext_path not in self._controller.extensions:
            parser_.error(f"the extension '{ext_path}' is not currently loaded"
                           " and thus cannot be unloaded")
        try:
            await self._controller.unload_extension(ext_path)
        except Exception as exc:
            parser_.error("an error occurred in the extension unloading "
                           f"process: {exc}")
        embed = utils.make_message._pos(f"extension '{ext_path}' has been unloaded")
        await ctx.send(embed=embed)

    async def _extensions__load_all(self, parser_: parser.CustomParser,
                                    ctx: commands.Context) -> None:
        if not self._extensions_path:
            parser_.error("extension loading is not possible without "
                           "'extensions_path' being set in the 'AdminTools' "
                           "instance")
        num_extensions, paths = utils._get_extensions(self._extensions_path)
        if not num_extensions:
            parser_.error("no extensions were found")
        num_succeeded = 0
        for p in paths:
            try:
                await self._controller.load_extension(p)
                num_succeeded += 1
            except Exception:
                pass
        embed = utils.make_message._pos(f"extensions loaded: {num_succeeded} of "
                                  f"{num_extensions}")
        await ctx.send(embed=embed)

    async def _extensions__load(self, parser_: parser.CustomParser,
                                ctx: commands.Context, __name: str) -> None:
        if not self._extensions_path:
            parser_.error("individual extension loading is not possible "
                           "without 'extensions_path' being set in the "
                           "'AdminTools' instance")
        num_extensions, paths = utils._get_extensions(self._extensions_path)
        ext_pkg = self._extensions_path.replace("\\", ".")
        ext_path = f"{ext_pkg}.{__name}"
        if ext_path not in paths:
            parser_.error(f"the extension '{ext_path}' does not exist")
        try:
            await self._controller.load_extension(ext_path)
        except Exception as exc:
            parser_.error("an error occurred in the extension loading "
                           f"process: {exc}")
        embed = utils.make_message._pos(f"extension '{ext_path}' has been loaded")
        await ctx.send(embed=embed)

    async def _sync__guilds(self, parser_: parser.CustomParser,
                            ctx: commands.Context,
                            __guilds: tuple[str, ...]) -> None:
        guilds_synced = 0
        for guild_id in __guilds:
            try:
                await self._controller.tree.sync(
                        guild=self._controller.get_guild(int(guild_id)))
            except Exception:
                pass
            else:
                guilds_synced += 1
        embed = utils.make_message._pos(f"synced command tree to {guilds_synced} of "
                                  f"{len(__guilds)} guilds")
        await ctx.send(embed=embed)

    async def _sync__current(self, parser_: parser.CustomParser,
                             ctx: commands.Context) -> None:
        synced = await self._controller.tree.sync(guild=ctx.guild)
        num_synced = len(synced)
        embed = utils.make_message._pos(f"synced {num_synced} commands to the "
                                  "current guild")
        await ctx.send(embed=embed)

    async def _sync__global(self, parser_: parser.CustomParser,
                            ctx: commands.Context) -> None:
        synced = await self._controller.tree.sync()
        num_synced = len(synced)
        embed = utils.make_message._pos(f"synced {num_synced} commands globally")
        await ctx.send(embed=embed)

    async def _sync__copy_global_current(self, parser_: parser.CustomParser,
                                         ctx: commands.Context) -> None:
        self._controller.tree.copy_global_to(ctx.guild)
        embed = utils.make_message._pos("copied global commands to current guild in"
                                  " the local command tree")
        await ctx.send(embed=embed)

    async def _sync__copy_global(self, parser_: parser.CustomParser,
                                 ctx: commands.Context,
                                 __guilds: tuple[str, ...]) -> None:
        guilds_synced = 0
        for guild_id in __guilds:
            try:
                await self._controller.tree.copy_global_to(
                        guild=self._controller.get_guild(int(guild_id)))
            except Exception:
                pass
            else:
                guilds_synced += 1
        embed = utils.make_message._pos(f"copied global commands to {guilds_synced} "
                                  f"of {len(__guilds)} guilds in the local "
                                  "command tree")
        await ctx.send(embed=embed)

    async def _sync__clear_global(self, parser_: parser.CustomParser,
                                  ctx: commands.Context) -> None:
        self._controller.tree.clear_commands(guild=None)
        embed = utils.make_message._pos(f"cleared all global commands from the local"
                                  " command tree")
        await ctx.send(embed=embed)

    async def _sync__clear_current(self, parser_: parser.CustomParser,
                                   ctx: commands.Context) -> None:
        self._controller.tree.clear_commands(guild=ctx.guild)
        embed = utils.make_message._pos(f"cleared the local command tree of the "
                                  "current guild")
        await ctx.send(embed=embed)

    async def _sync__clear_guilds(self, parser_: parser.CustomParser,
                                  ctx: commands.Context,
                                  __guilds: tuple[str, ...]) -> None:
        guilds_synced = 0
        for guild_id in __guilds:
            try:
                await self._controller.tree.clear_commands(
                        guild=self._controller.get_guild(int(guild_id)))
            except Exception:
                pass
            else:
                guilds_synced += 1
        embed = utils.make_message._pos("cleared the local command tree for "
                                  f"{guilds_synced} of {len(__guilds)} guilds")
        await ctx.send(embed=embed)

    async def _git__pull(self, parser_: parser.CustomParser,
                         ctx: commands.Context) -> None:
        process = subprocess.Popen(("git", "pull",
                                    "--allow-unrelated-histories"),
            stdout=subprocess.PIPE)
        output = process.communicate()[0]
        if output is None:
            embed = utils.make_message._neg("already up to date")
        else:
            embed = utils.make_message._pos(output.decode("utf-8"))
        await ctx.send(embed=embed)

    async def _commands__list(self, parser_: parser.CustomParser,
                              ctx: commands.Context) -> None:
        corecmds = [f"core[{i}] -> '{cmd.qualified_name}'@"
                    f"{cmd.callback.__name__}" for i, cmd in
                    enumerate(self._controller.commands)]
        appcmds = [f"app[{i}] -> '{cmd.qualified_name}'@{cmd.callback.__name__}"
                   for i, cmd in
                   enumerate(self._controller.tree.get_commands())]
        embed = utils.make_message._def("\n".join(corecmds+appcmds))
        await ctx.send(embed=embed)

    async def _trackers__list(self, parser_: parser.CustomParser,
                              ctx: commands.Context) -> None:
        embed = utils.make_message._def(", ".join(list(
                self._trackers._groups.keys())) or "NONE")
        await ctx.send(embed=embed)

    async def _trackers__get(self, parser_: parser.CustomParser,
                             ctx: commands.Context, __tracker: str) -> None:
        if __tracker not in self._trackers._groups:
            parser_.error(f"tracker '{__tracker}' does not exist")
        tracker = self._trackers[__tracker]
        current_users = "\n    ".join(tracker._active)
        user_history = "\n    ".join(list(reversed(tracker._history)))
        counts = "\n".join([f"    {k} -> {v}" for k, v in
                            tracker._counts.items()])
        embed = utils.make_message._def(f"CURRENT USERS\n    {current_users}\n\nUSER"
                                  f" HISTORY [15]\n    {user_history}\n\n"
                                  f"COUNTS\n{counts}")
        await ctx.send(embed=embed)

    async def _files__list(self, parser_: parser.CustomParser, ctx: commands.Context,
                           *dir_: str) -> None:
        if not self._files_path:
            parser_.error("the files path has not been defined, and thus all (files | f) "
                          "operations of this command are non-operable")
        
        path = pathlib.Path(self._files_path, *dir_)
        directories = None
        files = None
        for r, d, f in os.walk(path):
            directories = d
            files = f
            break

        lines: list[str] = []
        if directories:
            lines.extend(["DIRECTORIES", ", ".join(directories) + "\n"])
        if files:
            lines.extend(["FILES", ", ".join(files)])
        
        if lines:
            embed = utils.make_message._def("\n".join(lines))
        else:
            embed = utils.make_message._neg("NO FILES OR SUB-DIRECTORIES")
        await ctx.send(embed=embed)
    
    async def _files__download(self, parser_: parser.CustomParser, ctx: commands.Context,
                               *subpath: str) -> None:
        if not self._files_path:
            parser_.error("the files path has not been defined, and thus all (files | f) "
                          "operations of this command are non-operable")

        path = pathlib.Path(self._files_path, *subpath)
        buffer = io.BytesIO()
        if path.is_dir():
            with zipfile.ZipFile(buffer, "a") as zip_file:
                for root, _, files in os.walk(path):
                    for f in files:
                        zip_file.write(pathlib.Path(root, f))
        else:
            with zipfile.ZipFile(buffer, "a") as zip_file:
                zip_file.write(path, path.name)
        buffer.seek(0)
        await ctx.send(file=discord.File(buffer, f"dpy_devtools_zipped_{int(time.time())}.zip"))

    async def _files__upload(self, parser_: parser.CustomParser, ctx: commands.Context,
                             *subpath: str) -> None:
        if not self._files_path:
            parser_.error("the files path has not been defined, and thus all (files | f) "
                          "operations of this command are non-operable")

        # make path and ensure it is not a directory
        path = pathlib.Path(self._files_path, *subpath)
        if path.is_dir():
            parser_.error("the given path is a directory; (-u | --upload) may only be used on "
                          "files")

        # initial embed
        embed = utils.make_message._raw("```\nSend one file or type 'cancel' to cancel.```\n*This"
                                        " dialog will automatically be cancelled"
                                        f"<t:{int(time.time() + 300)}:R>.*",
                                        constants.EMBED_COLOR__POS)
        await ctx.send(embed=embed)
        
        # wait for user response
        def check(message: discord.Message) -> bool:
            return ctx.channel == message.channel and ctx.author == message.author
        msg: discord.Message = await self._controller.wait_for("message", check=check, timeout=300)
        
        # handle cancel
        if msg.content and msg.content.strip().lower() == "cancel":
            embed = utils.make_message._neg("This dialog has been cancelled.")
            await ctx.send(embed=embed)
            return

        # handle attachment saving
        if len(msg.attachments) != 1:
            parser_.error("exactly one attachment must be sent; this dialog has been cancelled")
        await msg.attachments[0].save(path)

        # success embed
        embed = utils.make_message._pos(f"The file '{msg.attachments[0].filename}' has "
                                        f"successfully been saved to '{str(path)}'.")
        await ctx.send(embed=embed)

    async def _files__remove(self, parser_: parser.CustomParser, ctx: commands.Context,
                             *subpath: str) -> None:
        if not self._files_path:
            parser_.error("the files path has not been defined, and thus all (files | f) "
                          "operations of this command are non-operable")

        # make path and get remover (rmdir | unlink)
        path = pathlib.Path(self._files_path, *subpath)
        if not path.exists():
            parser_.error("the given path does not exist")
        if path.is_dir():
            try:
                next(path.iterdir()) # raises StopIteration if there are no files in directory
                embed = utils.make_message._neg("The given directory is not empty.")
                await ctx.send(embed=embed)
                return
            except StopIteration:
                ...
            remover = path.rmdir
        else:
            remover = path.unlink
        
        # confirmation message
        code = "".join(random.sample(string.ascii_letters + string.digits, 25))
        embed = utils.make_message._raw(f"```\nSend the following code to confirm the removal of "
                                        f"'{str(path)}':\n\n{code}```\n*This dialog will "
                                        "automatically be cancelled "
                                        f"<t:{int(time.time() + 300)}:R>.*",
                                        constants.EMBED_COLOR__POS)
        await ctx.send(embed=embed)
        
        # wait for user response
        def check(message: discord.Message) -> bool:
            return ctx.channel == message.channel and ctx.author == message.author
        msg: discord.Message = await self._controller.wait_for("message", check=check, timeout=300)
        if msg.content != code:
            embed = utils.make_message._neg("The code provided does not match. This dialog has "
                                            "been cancelled.")
            await ctx.send(embed=embed)
            return
        
        # remove
        remover()

        # send success message
        embed = utils.make_message._pos(f"'{str(path)}' has successfully been removed.")
        await ctx.send(embed=embed)
