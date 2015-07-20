from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Protocol
from functools import partial
from base64 import b64encode, b64decode
import json

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

class JSONProtocol(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, bytes):
        self.data.append(bytes)

    def connectionLost(self, reason):
        self.finished.callback(json.loads("".join(self.data)))

agent = Agent(reactor, WebClientContextFactory())
endpoint = "https://api.github.com"


class GitHubClient(object):


    def __init__(self, username, password):
        self.authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))

    def get_branch(self, owner, repository, branch):
        # todo, a spot of caching
        branch = GitBranch(self, owner, repository, branch)
        def _(ignored):
            return branch
        return branch.initialise().addCallback(_)

    def git_request(self, request):
        print request
        finished = Deferred()

        def cb_response(response):
            response.deliverBody(JSONProtocol(finished))

        agent.request(
            'GET',
            endpoint + request,
            Headers({
                'Accept': ['application/vnd.github.v3+json'],
                'Authorization': [self.authorization],
                'User-Agent': ['htmlhub/GitHubClient'],
            }),
            None
        ).addCallback(cb_response)

        return finished

class GitBranch(object):

    def __init__(self, client, owner, repository, branch_name):
        self.client = client
        self.owner = owner
        self.repository = repository
        self.branch_name = branch_name
        self.branch_sha = None
        self.html_templates_sha = None
        self.passwd = None

    def git_request(self, request):
        return self.client.git_request(request)

    def get_branch_sha(self, results):
        for d in results:
            if d['name'] == self.branch_name:
                self.branch_sha = d['commit']['sha']
                return
        raise KeyError()

    def get_html_templates_sha(self, ignored):
        def _(results):
            for d in results['tree']:
                if d['path'] == 'html-templates':
                    self.html_templates_sha = d['sha']
        return self.git_tree_request(self.branch_sha).addCallback(_)

    def get_passwd(self, ignored):
        def _(results):
            self.passwd = results
        self.get_html_file(["passwd"]).addCallback(_)

    def initialise(self):
        return self.git_request(
            '/repos/%s/%s/branches' % (self.owner, self.repository)
        ).addCallback(
            self.get_branch_sha
        ).addCallback(
            self.get_html_templates_sha
        ).addCallback(
            self.get_passwd
        )

    def git_tree_request(self, sha):
            return self.git_request(str('/repos/%s/%s/git/trees/%s' % (self.owner, self.repository, sha)))

    def get_html_file(self, segments, parent_sha=None):
        if parent_sha is None:
            parent_sha = self.html_templates_sha
        def _(results):
            leaf = segments.pop(0)
            sha = None
            for d in results['tree']:
                if d['path'] == leaf:
                    sha = d['sha']
            if sha is None:
                return None
            if segments:
                return self.git_get_html_file(segments, sha)
            else:
                return self.git_get_blob(sha)
        return self.git_tree_request(parent_sha).addCallback(_)

    def git_get_blob(self, sha):
        def _(results):
            return b64decode(results['content'])
        return self.git_request(
            str('/repos/%s/%s/git/blobs/%s' % (self.owner, self.repository, sha))
        ).addCallback(_)
