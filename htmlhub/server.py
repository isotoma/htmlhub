
from zope.interface import implements

from twisted.internet.defer import maybeDeferred
from twisted.web import server, resource
from twisted.web.util import DeferredResource
from twisted.internet import reactor
from twisted.cred.checkers import FilePasswordDB
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.cred.portal import IRealm, Portal
from twisted.cred import credentials

from ConfigParser import ConfigParser
import github
from util import ctype

class HtmlHub(resource.Resource):

    isLeaf = False

    def __init__(self, github_client):
        resource.Resource.__init__(self)
        self.github_client = github_client

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, owner, request):
        return Owner(self.github_client, owner)

class Owner(resource.Resource):

    isLeaf = False

    def __init__(self, github_client, owner):
        resource.Resource.__init__(self)
        self.github_client = github_client
        self.owner = owner

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, repository, request):
        return Repository(self.github_client, self.owner, repository)


class BranchRealm(object):

    implements(IRealm)

    def __init__(self, branch):
        self.branch = branch

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, self.branch, lambda: None)
        raise NotImplementedError()

class PasswordDB(FilePasswordDB):

    def __init__(self, passwd):
        self.passwd = passwd
        FilePasswordDB.__init__(self, None, hash=self.apache_md5)

    def apache_md5(self, username, password, entry_password):
        if entry_password.startswith('$apr1$'):
            salt = entry_password[6:].split('$')[0][:8]
            expected = self.apache_md5crypt(password, salt)
            return expected
        raise NotImplementedError()

    # From: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/325204
    def apache_md5crypt(self, password, salt, magic='$apr1$'):
        # /* The password first, since that is what is most unknown */ /* Then our magic string */ /* Then the raw salt */
        import md5
        m = md5.new()
        m.update(password + magic + salt)

        # /* Then just as many characters of the MD5(pw,salt,pw) */
        mixin = md5.md5(password + salt + password).digest()
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
            m2 = md5.md5()
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
        if not self.caseSensitive:
            username = username.lower()

        for u, p in self._loadCredentials():
            if u == username:
                return u, p
            raise KeyError(username)

    def _loadCredentials(self):
        for line in self.passwd.splitlines():
            line = line.rstrip()
            parts = line.split(self.delim)

            if self.ufield >= len(parts) or self.pfield >= len(parts):
                continue
            if self.caseSensitive:
                yield parts[self.ufield], parts[self.pfield]
            else:
                yield parts[self.ufield].lower(), parts[self.pfield]

class Repository(resource.Resource):
    isLeaf = False

    def __init__(self, github_client, owner, repository):
        resource.Resource.__init__(self)
        self.github_client = github_client
        self.owner = owner
        self.repository = repository

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, branch, request):
        def _(git_branch):
            resource = Branch(git_branch)
            portal = Portal(BranchRealm(resource), [PasswordDB(git_branch.passwd)])
            credentialFactory = BasicCredentialFactory(branch)
            return HTTPAuthSessionWrapper(portal, [credentialFactory])
        git_branch = maybeDeferred(self.github_client.get_branch, self.owner, self.repository, branch)
        return DeferredResource(git_branch.addCallback(_))

class Branch(resource.Resource):

    isLeaf = True

    def __init__(self, git_branch):
        resource.Resource.__init__(self)
        self.git_branch = git_branch

    def render_GET(self, request):
        if request.postpath[-1] == 'passwd':
            return None
        def _(data):
            extension = request.postpath[-1].split(".")[-1]
            request.setHeader('Content-Type', ctype(extension))
            request.write(data)
            request.finish()
        self.git_branch.get_html_file(request.postpath[:]).addCallback(_)
        return server.NOT_DONE_YET

def main():
    parser = ConfigParser()
    parser.read("htmlhub.conf")
    username = parser.get("github", "username")
    password = parser.get("github", "password")
    ghc = github.GitHubClient(username, password)
    site = server.Site(HtmlHub(ghc))
    reactor.listenTCP(8000, site)
    reactor.run()

