from flask import Flask, render_template, g, session, Response, redirect, request, url_for
from functools import wraps
import sqlite3
import hashlib
import locale
import random
import string
import os

locale.setlocale(locale.LC_ALL, 'de_DE.utf8')

app = Flask(__name__)

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

config = app.config
config.from_pyfile('config.py.example', silent=True)
if not config.get('SECRET_KEY', None):
        config['SECRET_KEY'] = os.urandom(32)


def get_db():
	db = getattr(g, '_database', None)
	if db is None:
		db = g._database = sqlite3.connect('db.sqlite')
		db.row_factory = sqlite3.Row
		db.cursor().executescript(app.open_resource('schema.sql', mode='r').read())
		db.commit()
	return db

@app.teardown_appcontext
def close_connection(exception):
	db = getattr(g, '_database', None)
	if db is not None:
		db.commit()
		db.close()

def query(query, args=(), one=False):
	cur = get_db().execute(query, args)
	rv = cur.fetchall()
	cur.close()
	res = [];
	for l in rv:
		res.append(dict(l))
	return (res[0] if res else None) if one else res

@app.template_global()
def isadmin(*args):
        return False

@app.template_filter()
def md5(val):
	return hashlib.md5(val.encode('ascii', 'ignore')).hexdigest()

@app.template_filter()
def itemid(val):
	return query("SELECT * FROM item where id = ?", [val], True)

@app.template_filter()
def euro(val):
	return '{:.2f}€'.format(val/100)

csrf_endpoints = []

def csrf_protect(func):
	csrf_endpoints.append(func.__name__)
	@wraps(func)
	def decorator(*args, **kwargs):
		if '_csrf_token' in request.values:
			token = request.values['_csrf_token']
		elif request.get_json() and ('_csrf_token' in request.get_json()):
			token = request.get_json()['_csrf_token']
		else:
			token = None
		if not ('_csrf_token' in session) or (session['_csrf_token'] != token ) or not token:
			return 'csrf test failed', 403
		else:
			return func(*args, **kwargs)
	return decorator

@app.url_defaults
def csrf_inject(endpoint, values):
	if not '_csrf_token' in session:
		session['_csrf_token'] = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(64))
	if endpoint not in csrf_endpoints or not session.get('_csrf_token'):
		return
	values['_csrf_token'] = session['_csrf_token']

def log_action(userid,old,new,methode,parameter):
	user = query('SELECT * FROM user WHERE id = ?', [userid], True)
	query('INSERT INTO "log" (user_id, methode, oldbalance, newbalance, parameter) values (?, ?, ?, ?, ?)', [userid, methode, old, new, parameter])

@app.route("/")
def index():
	return render_template('index.html', allusers=query('SELECT * FROM user WHERE deleted=0'))

@app.route("/u/<name>")
def userpage(name):
	user=query('SELECT * FROM user WHERE name = ?', [name], True)
	log=query('SELECT log.* FROM log JOIN user ON log.user_id=user.id WHERE user.name = ? order by log.time DESC limit 5', [name])
	groups=query('SELECT * FROM "group" ORDER BY sortorder ')
	items=query('SELECT * FROM "item" WHERE deleted=0 ')
	return render_template('user.html', user=user, log=log, groups=groups, items=items )

@app.route("/u/<name>/<itemid>")
@csrf_protect
def buy(name, itemid):
	user = query('SELECT * FROM user WHERE name = ?', [name], True)
	if user:
		query('UPDATE "user" SET balance = balance - (SELECT price FROM item WHERE id = ?) WHERE name = ?', [itemid, name])
		usernew = query('SELECT * FROM user WHERE name = ?', [name], True)
		if query('SELECT price FROM item WHERE id = ?', [itemid], True)['price'] > 0:
			log_action(user['id'], user['balance'], usernew['balance'], 'buy', itemid)
		else:
			log_action(user['id'], user['balance'], usernew['balance'], 'recharge', itemid)
	return redirect(request.values.get('ref', url_for('userpage', name=name)))

@app.route("/login")
def login():
	return "Test"

@app.route("/logout")
def logout():
	return "Test"

