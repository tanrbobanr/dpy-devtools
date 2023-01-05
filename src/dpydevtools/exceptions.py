"""The exception used by `parser`.

:copyright: (c) 2022-present Tanner B. Corcoran
:license: MIT, see LICENSE for more details.
"""

__author__ = "Tanner B. Corcoran"
__license__ = "MIT License"
__copyright__ = "Copyright (c) 2022-present Tanner B. Corcoran"


class ContainerException(Exception):
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__()
