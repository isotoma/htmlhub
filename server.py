from twisted.web import server, resource
from twisted.internet import reactor

from github import get_git_path

import wingdbstub

def ctype(extension):

    return {
        'css': 'text/css',
        'js': 'application/javascript',
        'html': 'text/html',
    }.get(extension, 'text/plain')

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
        get_git_path(owner, repository, branch, filepath).addCallback(_)
        return server.NOT_DONE_YET

site = server.Site(Root())
reactor.listenTCP(8000, site)
reactor.run()

