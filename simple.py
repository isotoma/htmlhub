from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from base64 import b64encode

password = open("token").read().strip()
username = 'winjer'

authorization = b64encode("%s:%s" % (username, password)).decode("ascii")
print authorization

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
        'Authorization': ["Basic d2luamVyOjViMjM5MGZmMDExZmQzMjg1OWYxOGVjNDcyYTJiMWI1YzJjMjEzNmI="],
        'User-Agent': ['htmlhub'],
    }),
    None
)

def cbResponse(response):
    print response.__dict__
d.addCallback(cbResponse)

def cbError(response):
    print response
    print response.__dict__
d.addErrback(cbError)

def cbShutdown(ignored):
    reactor.stop()
d.addBoth(cbShutdown)

reactor.run()


