
from __future__ import absolute_import, print_function
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
from . import github
from .util import ctype
from .auth import BranchRealm, PasswordDB


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

