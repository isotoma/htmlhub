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

authorization = "Basic " + str(b64encode("%s:%s" % (username, password)).decode("ascii"))

class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)

contextFactory = WebClientContextFactory()

agent = Agent(reactor, contextFactory)

d = agent.request(
    'GET',
    'https://api.github.com/users/winjer/orgs',
    Headers({
        'Accept': ['application/vnd.github.v3+json'],
        'Authorization': [authorization],
        'User-Agent': ['htmlhub'],
    }),
    None
)

class Consumer(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, bytes):
        self.data.append(bytes)

    def connectionLost(self, reason):
        self.finished.callback(None)
        print json.loads("".join(self.data))

def cbResponse(response):
    finished = Deferred()
    response.deliverBody(Consumer(finished))
    return finished

d.addCallback(cbResponse)

def cbError(response):
    print response.__dict__
d.addErrback(cbError)

def cbShutdown(ignored):
    reactor.stop()
d.addBoth(cbShutdown)

reactor.run()


