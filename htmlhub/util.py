
from __future__ import absolute_import, print_function

import logging

logger = logging.getLogger("util")

mimetypes_file = '/etc/mime.types'
type_map = {}

def initialise_mimetypes():
    logger.info("Reading mime types from %s" % mimetypes_file)
    for line in open(mimetypes_file):
        if line.startswith("#"):
            continue
        line = line.strip()
        if not line:
            continue
        line = line.replace("\t", " ")
        parts = line.split(" ")
        if len(parts) < 2:
            continue
        mtype = parts[0]
        extensions = [x.strip() for x in  parts[1:] if x.strip()]
        for x in extensions:
            type_map[x] = mtype
    logger.info("%s types read" % len(type_map))

def ctype(extension):
    return type_map.get(extension, 'text/plain')


