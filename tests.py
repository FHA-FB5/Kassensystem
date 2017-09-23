#!/usr/bin/env python3

import os
import tempfile
import unittest

import api
import server

class MukasTestCase(unittest.TestCase):

	def setUp(self):
		self.db_fd, server.app.config['SQLITE_DB'] = tempfile.mkstemp()
		server.app.testing = True
		self.app = server.app.test_client()
		with server.app.app_context():
			server.init_db()

	def tearDown(self):
		os.close(self.db_fd)
		os.unlink(server.app.config['SQLITE_DB'])

	def test_index(self):
		r = self.app.get('/')
		assert r.status_code == 200

	def test_api_user_add_empty(self):
		r = self.app.post('/api/user/add', data=dict(
			))
		assert r.status_code == 422
		assert r.data == b'name is empty'

	def test_api_user_add_twice(self):
		r = self.app.post('/api/user/add', data={
			'name': 'user_add_twice',
			})
		assert r.status_code == 200
		assert r.data == b'OK'

		r = self.app.post('/api/user/add', data={
			'name': 'user_add_twice',
			})
		assert r.status_code != 200
		assert r.data != b'OK'

	def test_api_user_add_full(self):
		r = self.app.post('/api/user/add', data={
			'name': 'user_add_full',
			'mail': 'foo@example.org',
			'allow_logging': True,
			'transaction_mail': True,
			})
		assert r.status_code == 200
		assert r.data == b'OK'

		r = self.app.get('/')
		assert b'user_add_full' in r.data

	def test_api_user_edit(self):
		r = self.app.post('/api/user/add', data={
			'name': 'user_edit_foo',
			})
		assert r.status_code == 200
		assert r.data == b'OK'

		r = self.app.get('/')
		assert b'user_edit_foo' in r.data
		assert b'user_edit_bar' not in r.data

		r = self.app.post('/api/user/user_edit_foo/edit', data={
			'name': 'user_edit_bar',
			'mail': 'foo@example.org',
			})
		assert r.status_code == 200
		assert r.data == b'OK'

		r = self.app.get('/')
		assert b'user_edit_foo' not in r.data
		assert b'user_edit_bar' in r.data

	def test_api_user_edit_nonexisting_user(self):
		r = self.app.post('/api/user/user_edit_nonexisting_user/edit', data={
			'name': 'user_edit_nonexisting_user',
			})
		assert r.status_code != 200
		assert r.data != b'OK'

if __name__ == '__main__':
	unittest.main()



