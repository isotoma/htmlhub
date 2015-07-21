from __future__ import absolute_import, print_function

from twisted.internet.defer import Deferred, inlineCallbacks, maybeDeferred, returnValue
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Protocol
from functools import partial
from base64 import b64encode, b64decode
import json
import time

def print_error(error):
    print(error)

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


    def __init__(self, username, password, expiry=120):
        self.authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))
        self.cache = {}
        self.expiry = expiry
        reactor.callLater(self.expiry, self.housekeeping)

    def housekeeping(self):
        delete = []
        now = time.time()
        for key, value in self.cache.items():
            if now - value[0] > self.expiry:
                delete.append(key)
        for d in delete:
            del self.cache[d]
        reactor.callLater(self.expiry, self.housekeeping)

    def get_branch(self, owner, repository, branch_name):
        now = time.time()
        when, branch = self.cache.get((owner, repository, branch_name), (None, None))
        if when is not None:
            if now - when < self.expiry:
                return branch
        branch = GitBranch(self, owner, repository, branch_name)
        def _(ignored):
            self.cache[(owner, repository, branch_name)] = (now, branch)
            return branch
        return branch.initialise().addCallback(_)

    def git_request(self, request):
        print(request)
        finished = Deferred()

        def cb_response(response):
            response.deliverBody(JSONProtocol(finished))

        agent.request(
            'GET',
            str(endpoint + request),
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
        self.tree_cache = {}
        self.blob_cache = {}

    def git_request(self, request):
        return self.client.git_request(request)

    def get_branch_sha(self, results):
        for d in results:
            if d['name'] == self.branch_name:
                return d['commit']['sha']
        raise KeyError()

    def get_html_templates_sha(self):
        def _(results):
            for d in results['tree']:
                if d['path'] == 'html-templates':
                    return d['sha']
        return self.git_tree_request(self.branch_sha).addCallback(_)

    @inlineCallbacks
    def initialise(self):
        r = yield self.git_request('/repos/%s/%s/branches' % (self.owner, self.repository))
        self.branch_sha = yield self.get_branch_sha(r)
        self.html_templates_sha = yield self.get_html_templates_sha()
        self.passwd = yield self.get_html_file(["passwd"])

    @inlineCallbacks
    def git_tree_request(self, sha):
        if sha in self.tree_cache:
            returnValue(self.tree_cache[sha])
        else:
            result = yield self.git_request(str('/repos/%s/%s/git/trees/%s' % (self.owner, self.repository, sha)))
            self.tree_cache[sha] = result
            returnValue(result)

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
                return self.get_html_file(segments, sha)
            else:
                return self.git_get_blob(sha)
        return self.git_tree_request(parent_sha).addCallback(_)

    @inlineCallbacks
    def git_get_blob(self, sha):
        if sha in self.blob_cache:
            returnValue(self.blob_cache[sha])
        else:
            value = yield self.git_request('/repos/%s/%s/git/blobs/%s' % (self.owner, self.repository, sha))
            returnValue(b64decode(value['content']))
