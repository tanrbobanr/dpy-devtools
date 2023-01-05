"""The enums used by the user for `DevTools` as well as internal
implementations.

:copyright: (c) 2022-present Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__author__ = "Tanner B. Corcoran"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022-present Tanner B. Corcoran"


import enum


class ControlGroupOptions(enum.Enum):
    disabled="disabled"
    enabled="enabled"
    inherit="inherit"
    modplus="modplus"
    adminplus="adminplus"
    devonly="devonly"
