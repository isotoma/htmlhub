import unittest

from htmlhub import auth


class TestPasswordDB(unittest.TestCase):

    def setUp(self):
        self.password_db = auth.PasswordDB({
            'hugh': '$apr1$vjU43qRU$L156CJdAGC3ceGhF9TAsW1',
            'eric': '{SHA}1Q89PVJTA5l9cF+GzYAYI2X5ZO0=',
            'graham': 'MzeF8DuXnmjHA',
            'john': '[]INVALID',
            })

    def test_hash_md5(self):
        u, p = self.password_db.getUser('hugh')
        self.assertEqual(self.password_db.hash(u, 'drowssap', p), p)

    def test_hash_sha1(self):
        u, p = self.password_db.getUser('eric')
        self.assertEqual(self.password_db.hash(u, 'drowssap', p), p)

    def test_hash_crypt(self):
        u, p = self.password_db.getUser('graham')
        self.assertEqual(self.password_db.hash(u, 'drowssap', p), p)

    def test_hash_invalid(self):
        u, p = self.password_db.getUser('john')
        self.assertEqual(self.password_db.hash(u, 'drowssap', p), None)
