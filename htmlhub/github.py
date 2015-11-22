from __future__ import absolute_import, print_function

import abc
from base64 import b64encode, b64decode
import functools
import json
import logging
import os.path
import stat
import time

from twisted.internet.defer import Deferred, inlineCallbacks, returnValue
from twisted.internet import reactor
from twisted.web.client import Agent, _HTTP11ClientFactory
from twisted.web.http_headers import Headers
from twisted.internet.ssl import ClientContextFactory
from twisted.internet.protocol import Protocol

logger = logging.getLogger("github")

_HTTP11ClientFactory.noisy = False


def print_error(error):
    logging.error(error)


class WebClientContextFactory(ClientContextFactory):
    def getContext(self, hostname, port):
        return ClientContextFactory.getContext(self)


class GitError(RuntimeError):

    __metaclass__ = abc.ABCMeta


class NotFound(ValueError):

    def __init__(self, name, *args, **kwargs):
        self.name = name
        ValueError.__init__(self, *args, **kwargs)

    def __str__(self):
        return '{!r} not found'.format(self.name)


GitError.register(NotFound)


class BranchNotFound(NotFound):

    def __str__(self):
        return 'Branch {!r} not found'.format(self.name)


class ExpectedFileButGotDirectory(ValueError):

    pass


GitError.register(ExpectedFileButGotDirectory)


class UnsupportedBlobMode(TypeError):

    def __init__(self, path, mode, *args, **kwargs):
        self.path = path
        self.mode = mode
        TypeError.__init__(self, path, mode, *args, **kwargs)

    def __str__(self, *args, **kwargs):
        return 'Mode {} of {} is unsupported.'.format(
            oct(self.mode),
            self.path,
            )


GitError.register(UnsupportedBlobMode)


class JSONProtocol(Protocol):
    def __init__(self, finished):
        self.finished = finished
        self.data = []

    def dataReceived(self, bytes_):
        self.data.append(bytes_)

    def connectionLost(self, reason):
        self.finished.callback(json.loads("".join(self.data)))


agent = Agent(reactor, WebClientContextFactory())
DEFAULT_ENDPOINT = "https://api.github.com"


class GitHubClient(object):

    def __init__(self, username, password, expiry=120, endpoint=None,
                 index_files=None):
        self.authorization = "Basic {}".format(
            b64encode("%s:%s" % (username, password)).decode("ascii")
            )
        self.cache = {}
        self.expiry = expiry
        if endpoint is None:
            endpoint = DEFAULT_ENDPOINT
        self.endpoint = endpoint
        if index_files is None:
            index_files = []
        self.index_files = index_files
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
        branch = GitBranch(self, owner, repository, branch_name, index_files=self.index_files)

        def _(ignored):
            self.cache[(owner, repository, branch_name)] = (now, branch)
            return branch

        return branch.initialise().addCallback(_)

    def git_request(self, request):
        logger.debug("Requesting %s", request)
        finished = Deferred()

        def cb_response(response):
            response.deliverBody(JSONProtocol(finished))

        agent.request(
            'GET',
            str(self.endpoint + request),
            Headers({
                'Accept': ['application/vnd.github.v3+json'],
                'Authorization': [self.authorization],
                'User-Agent': ['htmlhub/GitHubClient'],
            }),
            None
        ).addCallback(cb_response)

        return finished


class GitBranch(object):

    delim = ":"
    ufield = 0
    pfield = 1
    caseSensitive = False

    def __init__(self, client, owner, repository, branch_name, index_files):
        self.client = client
        self.owner = owner
        self.repository = repository
        self.branch_name = branch_name
        self.branch_sha = None
        self.html_templates_sha = None
        self.passwd = None
        self.tree_cache = {}
        self.blob_cache = {}
        self.index_files = []

    def git_request(self, request):
        return self.client.git_request(request)

    def get_branch_sha(self, results):
        # we get a dict back if its an error
        if type(results) is dict:
            raise GitError(results)
        for d in results:
            if d['name'] == self.branch_name:
                return d['commit']['sha']
        raise BranchNotFound(self.branch_name)

    def get_html_templates_sha(self):
        def _(results):
            for d in results['tree']:
                if d['path'] == 'html-templates':
                    return d['sha']
        return self.git_tree_request(self.branch_sha).addCallback(_)

    @inlineCallbacks
    def initialise(self):
        branch_list_addr = '/repos/{owner}/{repo}/branches'.format(
            owner=self.owner, repo=self.repository
            )
        r = yield self.git_request(branch_list_addr)
        self.branch_sha = yield self.get_branch_sha(r)
        self.html_templates_sha = yield self.get_html_templates_sha()
        passwd = yield self.get_html_file(["passwd"])
        self.passwd = dict(self._loadCredentials(passwd))

    def _loadCredentials(self, passwd):
        for line in passwd.splitlines():
            line = line.rstrip()
            parts = line.split(self.delim)

            if self.ufield >= len(parts) or self.pfield >= len(parts):
                continue
            if self.caseSensitive:
                yield parts[self.ufield], parts[self.pfield]
            else:
                yield parts[self.ufield].lower(), parts[self.pfield]

    @inlineCallbacks
    def git_tree_request(self, sha):
        if sha in self.tree_cache:
            returnValue(self.tree_cache[sha])
        else:
            tree_addr = '/repos/{owner}/{repo}/git/trees/{revision}'.format(
                owner=self.owner, repo=self.repository, revision=sha
                )
            result = yield self.git_request(tree_addr)
            self.tree_cache[sha] = result
            returnValue(result)

    @inlineCallbacks
    def git_resolve_link(self, sha, consumed, remaining):
        target = yield self.git_get_blob(sha)
        # We allow symbolic links to escape 'html-templates'
        real_path = os.path.abspath(os.path.join(
            os.path.sep,
            os.path.sep.join(consumed),
            target
            )).split('/')[1:] + remaining
        resolved = yield self.get_html_file(real_path, self.branch_sha)
        returnValue(resolved)

    def try_index_files(sha, consumed):
        for filename in self.index_files:
            try:
                return self.get_html_file([filename], sha, consumed)
            except NotFound:
                continue
        raise ExpectedFileButGotDirectory(os.path.sep.join(consumed))

    def _get_html_file_callback(self, segments, consumed, results):
        leaf = segments.pop(0)
        consumed.append(leaf)
        sha = None
        for d in results['tree']:
            if d['path'] == leaf:
                sha = d['sha']
                break
        if sha is None:
            raise NotFound('{}/{}'.format('/'.join(consumed), leaf))
        mode = int(d['mode'], 8)
        if stat.S_ISDIR(mode):
            if not segments:
                return self.try_index_files(sha, consumed)
            return self.get_html_file(segments, sha, consumed)
        elif stat.S_ISLNK(mode):  # is symlink
            # -1 because it's relative to the parent of the symlink
            return self.git_resolve_link(sha, consumed[:-1], segments)
        elif stat.S_ISREG(mode):
            return self.git_get_blob(sha)
        raise UnsupportedBlobMode(os.path.join(*consumed), mode)

    def get_html_file(self, segments, parent_sha=None, consumed=None):
        if parent_sha is None:
            parent_sha = self.html_templates_sha
        if consumed is None:
            consumed = ['html-templates']

        callback = functools.partial(self._get_html_file_callback, segments, consumed)
        return self.git_tree_request(parent_sha).addCallback(callback)

    @inlineCallbacks
    def git_get_blob(self, sha):
        if sha in self.blob_cache:
            returnValue(self.blob_cache[sha])
        else:
            blob_addr = '/repos/{owner}/{repo}/git/blobs/{revision}'.format(
                owner=self.owner, repo=self.repository, revision=sha
                )
            value = yield self.git_request(blob_addr)
            returnValue(b64decode(value['content']))
