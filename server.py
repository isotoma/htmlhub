
from zope.interface import implements

from twisted.web import server, resource
from twisted.web.util import DeferredResource
from twisted.internet import reactor
from twisted.cred.checkers import FilePasswordDB
from twisted.web.guard import HTTPAuthSessionWrapper, DigestCredentialFactory
from twisted.cred.portal import IRealm, Portal
from twisted.cred import credentials

import github

import wingdbstub

username = 'winjer'
password = open("token").read().strip()

def ctype(extension):

    return {
        'css': 'text/css',
        'js': 'application/javascript',
        'html': 'text/html',
    }.get(extension, 'text/plain')

ghc = github.GitHubClient(username, password)
credentialFactory = DigestCredentialFactory("md5", "localhost:8000")

class Root(resource.Resource):

    isLeaf = False

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, owner, request):
        return Owner(owner)

class Owner(resource.Resource):

    isLeaf = False

    def __init__(self, owner):
        resource.Resource.__init__(self)
        self.owner = owner

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, repository, request):
        return Repository(self.owner, repository)


class BranchRealm(object):

    implements(IRealm)

    def __init__(self, branch):
        self.branch = branch

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, branch, lambda: None)
        raise NotImplementedError()

class BranchPasswordDB(FilePasswordDB):

    def __init__(self, branch):
        self.branch = branch
        self.credentialInterfaces = (
            credentials.IUsernamePassword,
        )

    def getUser(self, username):
        if not self.caseSensitive:
            username = username.lower()

        for u, p in self._loadCredentials():
            if u == username:
                return u, p
            raise KeyError(username)

    def _loadCredentials(self):
        for line in self.branch.splitlines():
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

    def __init__(self, owner, repository):
        resource.Resource.__init__(self)
        self.owner = owner
        self.repository = repository

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, branch, request):
        def _(git_branch):
            branch = Branch(git_branch)
            portal = Portal(BranchRealm(branch), [BranchPasswordDB(branch)])
            return HTTPAuthSessionWrapper(portal, [credentialFactory])
        git_branch = ghc.get_branch(self.owner, self.repository, branch)
        return DeferredResource(git_branch.addCallback(_))

class Branch(resource.Resource):

    isLeaf = True

    def __init__(self, git_branch):
        resource.Resource.__init__(self)
        self.git_branch = git_branch

    def render_GET(self, request):
        print self.owner, self.repository, self.branch, request.postpath
        def _(data):
            request.setHeader('Content-Type', ctype(extension))
            request.write(data)
            request.finish()
        self.git_branch.get_html_file(request.postpath).addCallback(_)
        return server.NOT_DONE_YET

site = server.Site(Root())
reactor.listenTCP(8000, site)
reactor.run()

