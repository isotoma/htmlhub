from twisted.internet.defer import Deferred
from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Protocol
from functools import partial
from base64 import b64encode, b64decode
import json

username = 'winjer'
endpoint = "https://api.github.com"
password = open("token").read().strip()
authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

contextFactory = WebClientContextFactory()

agent = Agent(reactor, contextFactory)

class Consumer(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, bytes):
        self.data.append(bytes)

    def connectionLost(self, reason):
        self.finished.callback(json.loads("".join(self.data)))


def cb_error(error):
    print error

def git_request(request):
    print request
    finished = Deferred()

    def cb_response(response):
        response.deliverBody(Consumer(finished))

    agent.request(
        'GET',
        endpoint + request,
        Headers({
            'Accept': ['application/vnd.github.v3+json'],
            'Authorization': [authorization],
            'User-Agent': ['htmlhub'],
        }),
        None
    ).addCallback(cb_response).addErrback(cb_error)

    return finished


def cbShutdown(ignored):
    reactor.stop()

def print_results(results):
    print results

def get_branch_sha(branch, results):
    for d in results:
        if d['name'] == branch:
            return d['commit']['sha']

def git_tree_request(owner, repository, sha):
    return git_request(str('/repos/%s/%s/git/trees/%s' % (owner, repository, sha)))

def git_get_file_sha(owner, repository, segments, root_sha):
    def _(results):
        leaf = segments.pop(0)
        sha = None
        for d in results['tree']:
            if d['path'] == leaf:
                sha = d['sha']
        if sha is None:
            return None
        if segments:
            return git_get_file_sha(owner, repository, segments, sha)
        else:
            return sha
    return git_tree_request(owner, repository, root_sha).addCallback(_)

def git_get_blob(owner, repository, sha):
    return git_request(str('/repos/%s/%s/git/blobs/%s' % (owner,repository, sha)))

def extract_content(results):
    content = results['content']
    return b64decode(content)

def get_git_path(owner, repository, branch, filepath):
    return git_request('/repos/%s/%s/branches' % (owner, repository),).\
        addCallback(partial(get_branch_sha, branch)).\
        addCallback(partial(git_get_file_sha, owner, repository, filepath)).\
        addCallback(partial(git_get_blob, owner, repository)).\
        addCallback(extract_content).\
        addErrback(cb_error)


