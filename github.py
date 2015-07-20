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

def git_request(request):
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

class GitHubClient(object):

    endpoint = "https://api.github.com"

    def __init__(self, username, password):
        self.authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))
        self.contextFactory = WebClientContextFactory()
        self.agent = Agent(reactor, self.contextFactory)

    def get_branch(self, owner, repository, branch):
        # todo, a spot of caching
        branch = GitBranch(self, owner, repository, branch)
        branch.initialise()

class GitBranch(object):

    def __init__(self, client, owner, repository, branch_name):
        self.client = client
        self.owner = owner
        self.repository = repository
        self.branch_name = branch_name
        self.branch_sha = None

    def initialise(self):
        def get_branch_sha(results):
            for d in results:
                if d['name'] == self.branch_name:
                    self.branch_sha = d['sha']
                    return
            raise KeyError()
        return git_request(
            '/repos/%s/%s/branches' % (owner, repository)
        ).addCallback(
            get_branch_sha
        ).addCallback(get_passwd)

            #addCallback(partial(git_get_file_sha, owner, repository, filepath)).\
            #addCallback(partial(git_get_blob, owner, repository)).\
            #addCallback(extract_content).\
            #addErrback(cb_error)





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

