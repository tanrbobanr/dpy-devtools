# Install
`pip install dpy-devtools`
# Docs
PENDING...
Until then, here is some implementation code:
```py
from discord.ext import commands
import discord
from dpydevtools import DevTools, ControlGroupOptions


bot = commands.Bot(...)
tools = DevTools(
    "!bot",
    bot,
    cg_defaults={
        "global": ControlGroupOptions.disabled,
        "example_group_0": ControlGroupOptions.adminplus},
    cw_defaults={"example_whitelist_0": [12345678901234567890]})


@bot.command(name="bot")
async def cmd(ctx: commands.Context, *queries: str) -> None:
    return await tools.delegate(ctx, *queries)


@bot.command(name="test")
@tools.command(
    group="example_group_0",
    whitelist="example_whitelist_0",
    tracker="example_tracker_0"
)
async def test_command(...): ...


bot.run(...)
```
*When using extensions, you must use `.placeholder` in combination with `resolve_placeholders`:*
```py
from dpydevtools import DevTools
from discord.ext import commands


class mycog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = commands.Bot
        DevTools.get(bot).resolve_placeholders(self)

    # make sure the placeholder is at the very top (or
    # more specifically, make sure it happens *after*
    # the command is created)
    @DevTools.placeholder(group=..., ...) 
    @commands.command(name="test")
    async def test_command(...): ...


async def setup(...):...
```

The available commands can be accessed by running `<prefix><commandname> -h`. This uses `argparse`, and is navigatable in a similar way through discord.