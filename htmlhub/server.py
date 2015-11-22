from __future__ import absolute_import, print_function

from ConfigParser import ConfigParser
import logging
import os
import sys

from twisted.internet.defer import maybeDeferred, inlineCallbacks, returnValue
from twisted.web import server
from twisted.web.resource import Resource, NoResource
from twisted.web.util import DeferredResource
from twisted.internet import reactor
from twisted.web.guard import HTTPAuthSessionWrapper, BasicCredentialFactory
from twisted.cred.portal import Portal
from twisted.python import log
from zope.interface import implements

from . import github
from .util import ctype
from .auth import BranchRealm, PasswordDB

logger = logging.getLogger("server")


class HtmlHub(Resource):

    isLeaf = False

    def __init__(self, github_client):
        Resource.__init__(self)
        self.github_client = github_client

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, owner, request):
        return Owner(self.github_client, owner)


class Owner(Resource):

    isLeaf = False

    def __init__(self, github_client, owner):
        Resource.__init__(self)
        self.github_client = github_client
        self.owner = owner

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    def getChild(self, repository, request):
        return Repository(self.github_client, self.owner, repository)


class Repository(Resource):
    isLeaf = False

    def __init__(self, github_client, owner, repository):
        Resource.__init__(self)
        self.github_client = github_client
        self.owner = owner
        self.repository = repository

    def render_GET(self, request):
        return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"

    @inlineCallbacks
    def _getChild(self, branch, request):
        if not branch:
            returnValue(self)
        try:
            git_branch = yield maybeDeferred(self.github_client.get_branch, self.owner,
                                             self.repository, branch)
            resource = Branch(git_branch)
            portal = Portal(BranchRealm(resource), [PasswordDB(git_branch.passwd)])
            credentialFactory = BasicCredentialFactory(branch)
            returnValue(HTTPAuthSessionWrapper(portal, [credentialFactory]))
        except github.BranchNotFound:
            print("Cannot find branch %s" % branch)
            returnValue(NoResource())
        except github.NotFound as e:
            print("Cannot find %s" % e.name)
            returnValue(NoResource())
        except github.GitError:
            print("Git error")
            returnValue(NoResource())

    def getChild(self, branch, request):
        return DeferredResource(self._getChild(branch, request))


class Branch(Resource):

    isLeaf = True

    def __init__(self, git_branch):
        Resource.__init__(self)
        self.git_branch = git_branch

    def render_index(self, request):
        return "Branch " + self.git_branch.branch_name

    def render_GET(self, request):
        if not request.postpath:
            return self.render_index(request)
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
    observer = log.PythonLoggingObserver()
    observer.start()
    logging.basicConfig(stream=sys.stdout, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    parser = ConfigParser({'endpoint': None, 'index-files': 'index.html'})
    parser.read(os.path.join(sys.prefix, "etc", "htmlhub.conf"))
    username = parser.get("github", "username")
    password = parser.get("github", "password")
    endpoint = parser.get("github", "endpoint")
    expiry = int(parser.get("cache", "expiry"))
    index_files = list(map(
        str.strip,
        parser.get('github', 'index-files').splitlines()
        ))
    ghc = github.GitHubClient(
        username,
        password,
        expiry=expiry,
        endpoint=endpoint,
        index_files=index_files,
        )
    site = server.Site(HtmlHub(ghc), logPath="/dev/null")
    reactor.listenTCP(8000, site)
    reactor.run()
