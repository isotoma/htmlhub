from __future__ import absolute_import, print_function

import logging
import mimetypes


logger = logging.getLogger("util")


def ctype(extension):
    return mimetypes.types_map.get(extension, 'text/plain')
