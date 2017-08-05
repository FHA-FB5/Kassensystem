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

db = sqlite3.connect(config['SQLITE_DB'])
cur = db.cursor()
cur.executescript(app.open_resource('schema.sql', mode='r').read())
db.commit()
db.close()

def get_dbcursor():
	if 'db' not in g:
		g.db = sqlite3.connect(config['SQLITE_DB'], detect_types=sqlite3.PARSE_DECLTYPES)
		g.db.isolation_level = None
	if not hasattr(request, 'db'):
		request.db = g.db.cursor()
	return request.db

@app.teardown_request
def commit_db(*args):
	if hasattr(request, 'db'):
		request.db.close()
		g.db.commit()

@app.teardown_appcontext
def close_db(*args):
	if 'db' in g:
		g.db.close()
		del g.db

def query(operation, *params, delim="sep"):
	cur = get_dbcursor()
	cur.execute(operation, params)
	rows = []
	rows = cur.fetchall()
	res = []
	for row in rows:
		res.append({})
		ptr = res[-1]
		for col, desc in zip(row, cur.description):
			name = desc[0].split('.')[-1].split(':')[0]
			if name == delim:
				ptr = res[-1][col] = {}
				continue
			if type(col) == str:
				col = col.replace('\\n', '\n').replace('\\r', '\r')
			ptr[name] = col
	return res

@app.template_global()
def isadmin(*args):
        return False

@app.template_filter()
def md5(val):
	return hashlib.md5(val.encode('ascii', 'ignore')).hexdigest()

@app.template_filter()
def itemidtoobj(val):
	return query("SELECT * FROM item where id = ?", val)[0]

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

app.jinja_env.globals['navbar'] = []
# iconlib can be 'bootstrap'
# ( see: http://getbootstrap.com/components/#glyphicons )
# or 'fa'
# ( see: http://fontawesome.io/icons/ )
def register_navbar(name, iconlib='bootstrap', icon=None):
	def wrapper(func):
		endpoint = func.__name__
		app.jinja_env.globals['navbar'].append((endpoint, name, iconlib, icon, True))
		return func
	return wrapper

def log_action(userid,old,new,methode,parameter):
	user = query('SELECT * FROM user WHERE id = ?', userid)[0]
	print([userid, methode, old, new, parameter])
	query('INSERT INTO "log" (user_id, methode, oldbalance, newbalance, parameter) values (?, ?, ?, ?, ?)', userid, methode, old, new, parameter)

@register_navbar('User', icon='user', iconlib='fa')
@app.route("/")
def index():
	return render_template('index.html', allusers=query('SELECT * FROM user WHERE deleted=0'))

@app.route("/u/<name>")
def userpage(name):
	user=query('SELECT * FROM user WHERE name = ?', name)[0]
	log=query('SELECT log.* FROM log JOIN user ON log.user_id=user.id WHERE user.name = ? order by log.time DESC limit 5', name)
	groups=query('SELECT * FROM "group" ORDER BY sortorder ')
	items=query('SELECT * FROM "item" WHERE deleted=0 ')
	return render_template('user.html', user=user, log=log, groups=groups, items=items )


@app.route("/api/get_img/<imgid>")
def get_img(imgid):
	data = query('SELECT data FROM pictures WHERE id = ?', imgid)
	if len(data) == 1:
		return Response(data[0]['data'], mimetype='image/png')
	else:
		return 'Not found', 404

@app.route("/api/buy/<name>/<int:itemid>")
@csrf_protect
def buy(name, itemid):
	user = query('SELECT * FROM user WHERE name = ?', name)[0]
	if user:
		query('UPDATE user SET balance = balance - (SELECT price FROM item WHERE id = ?) WHERE name = ?', itemid, name)
		usernew = query('SELECT * FROM user WHERE name = ?', name)[0]
		if query('SELECT price FROM item WHERE id = ?', itemid)[0]['price'] > 0:
			log_action(user['id'], user['balance'], usernew['balance'], 'buy', itemid)
		else:
			log_action(user['id'], user['balance'], usernew['balance'], 'recharge', itemid)
	if request.values.get('noref', False):
		return 'OK', 200
	else:
		return redirect(request.values.get('ref', url_for('userpage', name=name)))

@app.route("/api/setbalance/<name>/<int:newbalance>", methods=['GET', 'POST'])
@app.route("/api/setbalance/<name>", methods=['GET', 'POST'])
@csrf_protect
def set_balance(name, newbalance=None):
	user = query('SELECT * FROM user WHERE name = ?', name)[0]
	if user:
		if not newbalance:
			newbalance = request.values.get('newbalance', 0)
		newbalance = int(newbalance)
		query('UPDATE user SET balance = ? WHERE name = ?', newbalance, name)
		log_action(user['id'], user['balance'], newbalance, 'set_balance', 0)
	return redirect(request.values.get('ref', url_for('userpage', name=name)))

@app.route("/api/userbalance/<name>")
@csrf_protect
def get_balance(name):
	return str(query('SELECT balance FROM user WHERE name = ?', name)[0]['balance']),200

@app.route("/login", methods=['GET', 'POST'])
def login():
	return "Test"

@app.route("/logout")
def logout():
	return "Test"

