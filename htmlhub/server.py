from __future__ import absolute_import, print_function

from ConfigParser import ConfigParser
import logging
import os.path
import sys

from twisted.internet.defer import maybeDeferred, inlineCallbacks, returnValue
from twisted.web import server, http
from twisted.web.resource import Resource, NoResource as BaseResource
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

class NoResource(BaseResource):
    template = unicode("""
    <html>
    <head>
        <title>404 - We can't find that</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: sans-serif;
                padding: 0 20px;
            }
            h1 {
                display: inline-block;
                width: 99px;
                height: 60px;
                text-indent: -999em;
                background-image: url('data:image/svg+xml;utf8,<svg viewBox="0 0 372.69 226.91" xmlns="http://www.w3.org/2000/svg"><path d="m0 185.74v41.17h225.02v-41.04h-13.5v27.62h-198.1v-27.75z" fill="#46bbc8"/><path d="m0 0v111.49h13.27v-98l198.21-.16.01 98 13.53.16v-111.49z" fill="#46bbc8"/><g fill="#000"><path d="m.05 124.51h13.38v48.43h-13.38z"/><path d="m118.77 148.87v-.14c0-7-5-13.08-12.36-13.08s-12.15 6-12.15 12.94v.14c0 7 5 13.08 12.28 13.08s12.22-6 12.22-12.94m-38.16 0v-.14c0-13.91 11.12-25.19 25.94-25.19s25.8 11.15 25.8 25.05v.14c0 13.91-11.11 25.18-25.94 25.18s-25.8-11.14-25.8-25"/><path d="m230.41 148.87v-.14c0-7-5-13.08-12.35-13.08s-12.15 6-12.15 12.94v.14c0 7 5 13.08 12.28 13.08s12.21-6 12.21-12.94m-38.15 0v-.14c0-13.91 11.11-25.19 25.94-25.19s25.81 11.15 25.81 25.05v.14c0 13.91-11.11 25.18-25.94 25.18s-25.8-11.14-25.8-25"/><path d="m255.5 124.51h17.69l7.84 18.75 8.03-18.75h17.5v48.44h-13.24v-27.82l-8.08 19.22h-8.62l-8.08-19.08v27.68h-13.04z"/><path d="m35.32 156.83a24.65 24.65 0 0 0 15.58 5.81c3.57 0 5.49-1.25 5.49-3.33v-.14c0-2-1.58-3.11-8.09-4.63-10.23-2.36-18.12-5.26-18.12-15.22v-.14c0-9 7.07-15.5 18.6-15.5 7.14 0 12.93 1.69 17.75 4.94l-4.64 11a24 24 0 0 0 -13.45-4.77c-3.22 0-4.8 1.38-4.8 3.11v.14c0 2.22 1.65 3.19 8.3 4.71 11 2.42 17.91 6 17.91 15.09v.1c0 9.89-7.76 15.78-19.42 15.78a34.45 34.45 0 0 1 -19.76-5.84z"/><path d="m157.61 136.28h-14.4v-11.76h41.81l-4.96 11.76h-9.13v36.67h-13.32z"/><path d="m337.7 124.34-20.45 48.78h12.8l13.96-32.87 4.65 11.14h-3.54l-4.96 11.76h13.41l4.19 10.03h14.93l-21.18-48.84z"/></g></svg>');
                background-repeat: no-repeat;
                background-size: 100%%;
            }
            h2 {
                font-size: 2.25rem;
                font-weight: normal;
            }
            .container {
                position: relative;
                width: 100%%;
                max-width: 1024px;
                margin: 0 auto;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Isotoma</h1>
            <h2>%(brief)s</h2>
            <p>URLs should look like /:owner/:repos/:branch/path/to/file.html</p>
            <p><strong>%(detail)s</strong></p>
        </div>
    </body>
    </html>
    """)

class HtmlHub(Resource):

    isLeaf = False

    def __init__(self, github_client):
        Resource.__init__(self)
        self.github_client = github_client

    def render_GET(self, request):
        return NoResource().render(request)

    def getChild(self, owner, request):
        return Owner(self.github_client, owner)


class Owner(Resource):

    isLeaf = False

    def __init__(self, github_client, owner):
        Resource.__init__(self)
        self.github_client = github_client
        self.owner = owner

    def render_GET(self, request):
        return NoResource('').render(request)

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
        return NoResource('').render(request)

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
            returnValue(NoResource('Cannot find branch {}'.format(branch)))
        except github.GitError, e:
            logger.error(e)
            returnValue(NoResource(''))

    def getChild(self, branch, request):
        return DeferredResource(self._getChild(branch, request))


class Branch(Resource):

    isLeaf = True
    default_doc = 'index.html'

    def __init__(self, git_branch):
        Resource.__init__(self)
        self.git_branch = git_branch

    def render_GET(self, request):
        if request.postpath:
            self.segments = request.postpath[:]
            if self.segments[-1] == '':
                self.segments[-1] = self.default_doc
        else:
            self.segments = [self.default_doc]

        if self.segments[-1] == 'passwd':
            return None

        self.content_type = ctype(self.segments[-1])

        def _callback(data):
            if data:
                request.setHeader('Content-Type', self.content_type)
                request.setHeader('X-Frame-Options', 'SAMEORIGIN')
                request.write(data)
            else:
                request.setHeader('Content-Type', 'text/html')
                request.setHeader('X-Frame-Options', 'SAMEORIGIN')
                request.setResponseCode(http.NOT_FOUND)
                request.write(NoResource('Cannot find file').render(request))
            request.finish()

        def _errback(failure):
            if failure.type == github.ExpectedFileButGotDirectory:
                self.segments = request.postpath[:] + [self.default_doc]
                self.content_type = ctype(self.default_doc)
                _get_file()
                return
            request.finish()

        def _get_file():
            self.git_branch.get_html_file(self.segments).addCallback(_callback).addErrback(_errback)

        _get_file()

        return server.NOT_DONE_YET


def main():
    observer = log.PythonLoggingObserver()
    observer.start()
    logging.basicConfig(stream=sys.stdout, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    conffile = os.path.join(sys.prefix, "etc", "htmlhub.conf")
    if os.path.exists(conffile):
        parser = ConfigParser()
        parser.read(conffile)
        username = parser.get("github", "username")
        password = parser.get("github", "password")
        expiry = int(parser.get("cache", "expiry"))
    else:
        username = os.environ['GITHUB_USERNAME']
        password = os.environ['GITHUB_PASSWORD']
        expiry = int(os.environ['CACHE_EXPIRY'])
    port = int(os.environ.get('PORT', '8000'))
    ghc = github.GitHubClient(username, password, expiry=expiry)
    site = server.Site(HtmlHub(ghc), logPath="/dev/null")
    reactor.listenTCP(port, site)
    reactor.run()
