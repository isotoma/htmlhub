
from zope.interface import implements

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.cred.checkers import FilePasswordDB
from twisted.web.guard import HTTPAuthSessionWrapper, DigestCredentialFactory
from twisted.cred.portal import IRealm, Portal

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

class Root(resource.Resource):
    isLeaf = True

    def render_GET(self, request):
        if len(request.postpath) < 4:
            return "<html>URLs should look like /:owner/:repos/:branch/path/to/file.html</html>"
        owner = request.postpath[0]
        repository = request.postpath[1]
        branch = request.postpath[2]
        filepath = ['html-templates'] + request.postpath[3:]
        print owner, repository, filepath
        def _(data):
            extension = request.postpath[-1].split(".")[-1]
            request.setHeader('Content-Type', ctype(extension))
            request.write(data)
            request.finish()
        #get_git_path(owner, repository, branch, filepath).addCallback(_)
        return server.NOT_DONE_YET

class MyRealm(object):

    implements(IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if resource.IResource in interfaces:
            return (resource.IResource, Root(), lambda: None)
        raise NotImplementedError()

portal = Portal(MyRealm(), [FilePasswordDB('httpd.password')])
credentialFactory = DigestCredentialFactory("md5", "localhost):8080")
resource = HTTPAuthSessionWrapper(portal, [credentialFactory])
site = server.Site(resource)
reactor.listenTCP(8000, site)
reactor.run()

