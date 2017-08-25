from __future__ import absolute_import, print_function

import logging
import mimetypes


logger = logging.getLogger("util")
types = mimetypes.MimeTypes()

def ctype(filename):
    content_type, _ = types.guess_type(filename, False)
    return content_type or 'text/plain'
