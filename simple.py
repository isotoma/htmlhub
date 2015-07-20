from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Protocol
from base64 import b64encode
import json

password = open("token").read().strip()
username = 'winjer'
owner = 'isotoma'
repository = 'arcadia-website'

authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

contextFactory = WebClientContextFactory()

agent = Agent(reactor, contextFactory)

endpoint = "https://api.github.com"
#endpoint + '/users/winjer/orgs',

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

def get_branch_shas(results):
    r = {}
    for d in results:
        r[d['name']] = d['commit']['sha']
    return r

def git_tree_request(sha):
    return git_request(str('/repos/%s/%s/git/trees/%s' % (owner, repository, sha)))

def git_get_file_sha(root_sha, segments):
    def _(results):
        leaf = segments.pop(0)
        for d in results['tree']:
            if d['path'] == leaf:
                sha = d['sha']
        if segments:
            return git_get_file_sha(sha, segments)
        else:
            return sha
    return git_tree_request(root_sha).addCallback(_)

def get_home(branch_shas):
    root_sha = branch_shas['master']
    return git_get_file_sha(root_sha, ['html-templates', 'home.html'])

git_request('/repos/%s/%s/branches' % (owner, repository),).\
    addCallback(get_branch_shas).\
    addCallback(get_home).\
    addCallback(print_results).\
    addErrback(cb_error).\
    addBoth(cbShutdown)

reactor.run()


