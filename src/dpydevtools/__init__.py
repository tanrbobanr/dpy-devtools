"""A set of useful administrator and developer tools for discord.py.

:copyright: (c) 2022 Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__title__ = "dpy-devtools"
__author__ = "Tanner B. Corcoran"
__email__ = "tannerbcorcoran@gmail.com"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022 Tanner B. Corcoran"
__version__ = "0.0.2"
__description__ = "A set of useful administrator and developer tools for discord.py"
__url__ = "https://github.com/tanrbobanr/dpy-devtools"
__download_url__ = "https://pypi.org/project/dpy-devtools/"


__all__ = (
    "DevTools",
    "ControlGroupOptions"
)


from .tools import DevTools
from .enums import ControlGroupOptions
