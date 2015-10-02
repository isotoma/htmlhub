from __future__ import absolute_import, print_function

import base64
import crypt
import hashlib

from zope.interface import implements
from twisted.web import resource
from twisted.cred import portal
from twisted.cred import checkers

import logging

logger = logging.getLogger("auth")

class BranchRealm(object):

    implements(portal.IRealm)

    def __init__(self, branch):
        self.branch = branch

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self.branch, lambda: None)
        raise NotImplementedError()

class PasswordDB(checkers.FilePasswordDB):

    def __init__(self, passwd):
        self.passwd = passwd
        self.cred_cache = None
        checkers.FilePasswordDB.__init__(self, None, hash=self.apache)

    def apache(self, username, password, entry_password):
        if entry_password.startswith('$apr1$'):
            salt = entry_password[6:].split('$')[0][:8]
            expected = self.apache_md5crypt(password, salt)
            return expected
        elif entry_password.startswith('{SHA}'):
            expected = '{SHA}' + base64.b64encode(hashlib.sha1(password).digest())
            return expected
        salt = entry_password[:2]
        expected = crypt.crypt(password, salt)
        return expected

    # From: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/325204
    def apache_md5crypt(self, password, salt, magic='$apr1$'):
        # /* The password first, since that is what is most unknown */ /* Then our magic string */ /* Then the raw salt */
        m = hashlib.md5()
        m.update(password + magic + salt)

        # /* Then just as many characters of the MD5(pw,salt,pw) */
        mixin = hashlib.md5(password + salt + password).digest()
        for i in range(0, len(password)):
            m.update(mixin[i % 16])

        # /* Then something really weird... */
        # Also really broken, as far as I can tell.  -m
        i = len(password)
        while i:
            if i & 1:
                m.update('\x00')
            else:
                m.update(password[0])
            i >>= 1

        final = m.digest()

        # /* and now, just to make sure things don't run too fast */
        for i in range(1000):
            m2 = hashlib.md5()
            if i & 1:
                m2.update(password)
            else:
                m2.update(final)

            if i % 3:
                m2.update(salt)

            if i % 7:
                m2.update(password)

            if i & 1:
                m2.update(final)
            else:
                m2.update(password)

            final = m2.digest()

        # This is the bit that uses to64() in the original code.

        itoa64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

        rearranged = ''
        for a, b, c in ((0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)):
            v = ord(final[a]) << 16 | ord(final[b]) << 8 | ord(final[c])
            for i in range(4):
                rearranged += itoa64[v & 0x3f]; v >>= 6

        v = ord(final[11])
        for i in range(2):
            rearranged += itoa64[v & 0x3f]; v >>= 6

        return magic + salt + '$' + rearranged

    def getUser(self, username):
        return username, self.passwd[username]

