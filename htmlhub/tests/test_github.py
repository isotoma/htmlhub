from base64 import b64encode
import os.path
import sha

from twisted.internet.defer import inlineCallbacks
from twisted.internet.defer import maybeDeferred
from twisted.trial.unittest import TestCase

from htmlhub import github


marker = object()


def maybe_pop(sequence, index=None, default=marker):
    try:
        return sequence.pop(index)
    except IndexError:
        if default is marker:
            raise
        else:
            return default


class MockClient(object):

    def __init__(self, owner, repo, **branches):
        self.owner = owner
        self.repo = repo
        self.populate(branches)

    def make_commit_url(self, commit):
        return 'https://api.github.com/repos/{}/{}/commits/{}'.format(
            self.owner, self.repo, commit
            )

    def populate(self, branches):
        self.commits = {}
        self.branches = {}
        self.tree = {}
        self.blobs = {}
        self.populate_branches(branches)

    def populate_branches(self, branches):
        for b, root_items in branches.items():
            commit = sha.new(b).hexdigest()
            url = self.make_commit_url(commit)
            self.commits[commit] = {
                'sha': commit,
                'url': url,
                }
            self.branches[b] = {
                'name': b,
                'commit': self.commits[commit],
                }
            self.populate_tree(commit, root_items, '/')

    def populate_tree(self, commit, items, root):
        url = self.make_commit_url(commit)
        tree_items = []
        for item in items:
            name = item['name']
            path = os.path.join(root, name)
            sub_items = item.get('items', [])
            type_ = item.get('type', 'tree' if sub_items else 'blob')
            item_commit = sha.new(path).hexdigest()
            item_commit_url = self.make_commit_url(item_commit)
            item_url = 'https://api.github.com/repos/{}/{}/{}s/{}'.format(
                self.owner, self.repo, type_, commit
                )
            self.commits[item_commit] = {
                'sha': item_commit,
                'url': item_commit_url,
                }
            mode = item.get('mode', '100644' if type_ == 'blob' else '040000')
            tree_items.append({
                'path': name,
                'mode': mode,
                'type': type_,
                'sha': item_commit,
                'url': item_url,
                })
            if type_ == 'blob':
                content = item.get('content', '')
                size = item.get('size', len(content))
                tree_items[-1]['size'] = size
                self.blobs[item_commit] = {
                    'sha': item_commit,
                    'size': size,
                    'url': item_url,
                    'content': b64encode(content),
                    'encoding': 'base64'
                    }
            self.populate_tree(item_commit, sub_items, path)

        self.tree[commit] = {
            'sha': commit,
            'url': url,
            'tree': tree_items,
            }

    def repo_response(self, parts):
        owner = maybe_pop(parts, 0, '')
        repo = maybe_pop(parts, 0, '')
        if owner != self.owner or repo != self.repo:
            return {
                'message': 'Not found',
                'documentation_url': 'https://developer.github.com/v3',
                }
        req_type = maybe_pop(parts, 0, '')
        if req_type == 'branches':
            return list(self.branches.values())
        elif req_type == 'git':
            sub_type = maybe_pop(parts, 0, '')
            commit = maybe_pop(parts, 0, '')
            if sub_type == 'trees':
                return self.tree[commit]
            elif sub_type == 'blobs':
                return self.blobs[commit]
            else:
                raise ValueError(sub_type)
        else:
            raise ValueError(req_type)

    def git_request(self, path):
        parts = [p for p in path.split('/') if p not in ('', '.')]
        endpoint = maybe_pop(parts, 0, '')
        if endpoint == 'repos':
            return self.repo_response(parts)
        raise ValueError(path)


class TestGitBranch(TestCase):

    def setUp(self):
        client = MockClient('isotoma', 'htmlhub', master=[
            {
                'name': 'html-templates',
                'items': [{
                    'name': 'passwd',
                    },
                    {
                    'name': 'favicon.ico',
                    'content': 'my Icon',
                    },
                    {
                    'name': 'js',
                    'items': [
                        {'name': 'index.js', 'content': 'my JS'},
                        ]
                    },
                    {
                    'name': 'css',
                    'mode': '120000',
                    'type': 'blob',
                    'content': '../src/dev_css'
                    }],
            },
            {
                'name': 'src',
                'items': [{
                    'name': 'dev_css',
                    'items': [
                        {'name': 'index.css',
                         'content': 'my CSS'},
                        ]
                    }]
            }
            ])
        self.ghb = github.GitBranch(client, 'isotoma', 'htmlhub', 'master')
        self.ghb.initialise()

    @inlineCallbacks
    def test_regular(self):
        result = yield maybeDeferred(self.ghb.get_html_file, ['favicon.ico'])
        self.assertEqual(result, 'my Icon')

    @inlineCallbacks
    def test_regular_subdir(self):
        result = yield maybeDeferred(self.ghb.get_html_file, ['js', 'index.js'])
        self.assertEqual(result, 'my JS')

    @inlineCallbacks
    def test_symlink(self):
        result = yield maybeDeferred(self.ghb.get_html_file, ['css', 'index.css'])
        self.assertEqual(result, 'my CSS')

    @inlineCallbacks
    def test_file_expected(self):
        deferred = maybeDeferred(self.ghb.get_html_file, ['js'])
        yield self.assertFailure(
            deferred,
            github.ExpectedFileButGotDirectory,
            )

    @inlineCallbacks
    def test_file_expected_symlink(self):
        deferred = maybeDeferred(self.ghb.get_html_file, ['css'])
        yield self.assertFailure(
            deferred,
            github.ExpectedFileButGotDirectory,
            )
