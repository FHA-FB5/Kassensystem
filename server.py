from flask import Flask, render_template, render_template_string, g, session, Response, redirect, request, url_for, flash
from functools import wraps
import sqlite3
import hashlib
import locale
import random
import string
import os
import datetime
from PIL import Image
import io

locale.setlocale(locale.LC_ALL, 'de_DE.utf8')

app = Flask(__name__)

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

config = app.config
config.from_pyfile('config.py.example', silent=True)
config.from_pyfile('config.py', silent=True)
if not config.get('SECRET_KEY', None):
        config['SECRET_KEY'] = os.urandom(32)
if config['DEBUG']:
        app.jinja_env.auto_reload = True

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

def modify(operation, *params):
	cur = get_dbcursor()
	cur.execute(operation, params)
	return cur.lastrowid

@app.template_global()
def isadmin(*args):
        return session.get('loggedin', False)

admin_endpoints = []
def admin_required(func):
	admin_endpoints.append(func.__name__)
	@wraps(func)
	def decorator(*args, **kwargs):
		if not isadmin():
			flash('You need to be logged in to do that!')
			return redirect(url_for('login', ref=request.url))

		else:
			return func(*args, **kwargs)
	return decorator

@app.template_filter()
def md5(val):
	return hashlib.md5(val.encode('ascii', 'ignore')).hexdigest()

@app.template_filter()
def itemidtoobj(val):
	return query("SELECT * FROM item where id = ?", val)[0]

@app.template_filter()
def useridtoobj(val):
	return query("SELECT * FROM user where id = ?", val)[0]

@app.template_filter()
def euro(val, symbol=True):
	if symbol:
		return '{:.2f}€'.format(val/100)
	else:
		return '{:.2f}'.format(val/100)

@app.template_filter()
def itemprice(item):
	if not item:
		return -1
	if item['price']:
		return item['price']
	else:
		step = 20
		margin = 0.2
		base = item['purchasingprice']*(1+margin)
		if base % step != 0:
			if base > 0:
				return int(base/step)*step + step
			else:
				return int(base/step)*step - step
		else:
			return base

@app.template_filter()
def itemstock(item):
	return 0

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
def register_navbar(name, iconlib='bootstrap', icon=None, visible=False):
	def wrapper(func):
		endpoint = func.__name__
		app.jinja_env.globals['navbar'].append((endpoint, name, iconlib, icon, visible))
		return func
	return wrapper

def log_action(userid,old,new,method,parameter):
	if useridtoobj(userid)['allow_logging']:
		query('INSERT INTO "log" (user_id, method, oldbalance, newbalance, parameter) values (?, ?, ?, ?, ?)', userid, method, old, new, parameter)

@register_navbar('User', icon='user', iconlib='fa', visible=True)
@app.route("/")
def index():
	return render_template('index.html', allusers=query('SELECT * FROM user WHERE deleted=0'))

@register_navbar('Items', icon='list', iconlib='fa')
@app.route("/items")
@admin_required
def itemlist():
	return render_template('itemlist.html',
			groups=query('SELECT * FROM "group" ORDER BY sortorder '),
			items=query('SELECT * FROM "item" WHERE deleted=0 or deleted=? ORDER BY name',
				request.values.get('showdeleted', 0)))

@register_navbar('Groups', icon='object-group', iconlib='fa')
@app.route("/groups")
@admin_required
def grouplist():
	return render_template('grouplist.html', groups=query('SELECT * FROM "group" ORDER BY sortorder '))

@app.route("/items/<itemid>", methods=['GET', 'POST'])
@csrf_protect
@admin_required
def edititem(itemid):
	itemid = int(itemid)
	newid = int(itemid)

	if ('name' in request.values):
		args = []
		args.append(request.values.get('name', 'FIXME'))
		args.append(request.values.get('group_id', -1))
		args.append(int(float(request.values.get('purchasingprice', 0))*100))
		if not request.values.get('usecalculated', False):
			args.append(int(float(request.values.get('price', 0))*100))
		else:
			args.append(None)
		args.append(request.values.get('info_public', ''))
		args.append(request.values.get('picture_id', -1))

		if len(query("SELECT * from item WHERE id = ?", itemid)) > 0:
			query("UPDATE item SET name = ?, group_id = ?, purchasingprice = ?, price = ?, info_public = ?, picture_id = ? WHERE id = ?", *args, itemid)
		else:
			newid = modify("INSERT INTO item (name, group_id, purchasingprice, price, info_public, picture_id) VALUES (?, ?, ?, ?, ?, ?)", *args)
	
	if 'action' in request.values:
		if (request.values.get('action', 'save') == 'save'):
			if itemid != newid :
				return redirect(url_for("edititem", itemid=newid))
		else:
			return redirect(url_for("itemlist"))

	if itemid != -1:
		item = query("SELECT * from item WHERE id = ?", itemid)[0]
	else:
		item = None
	pictures = query("SELECT id from pictures")
	return render_template('item.html', item=item, pictures=pictures, groups=query('SELECT * FROM "group" ORDER BY sortorder'))

@app.route("/groups/<groupid>", methods=['GET', 'POST'])
@csrf_protect
@admin_required
def editgroup(groupid):
	groupid = int(groupid)
	newid = int(groupid)

	if ('name' in request.values):
		args = []
		args.append(request.values.get('name', 'FIXME'))
		args.append(request.values.get('sortorder', 0))

		if len(query('SELECT * from "group" WHERE id = ?', groupid)) > 0:
			query('UPDATE "group" SET name = ?, sortorder = ? WHERE id = ?', *args, groupid)
		else:
			newid = modify('INSERT INTO "group" (name, sortorder) VALUES (?, ?)', *args)
	
	if 'action' in request.values:
		if (request.values.get('action', 'save') == 'save'):
			if groupid != newid :
				return redirect(url_for("editgroup", groupid=groupid))
		else:
			return redirect(url_for("grouplist"))
	if groupid != -1:
		group = query('SELECT * from "group" WHERE id = ?', groupid)[0]
	else:
		group = None
	return render_template('group.html', group=group)

@app.route("/u/<name>")
@app.route("/u/<int:id>")
def userpage(name=None, id=None):
	user=query('SELECT * FROM user WHERE (name = ?) or (id = ?)', name, id)
	if len(user) != 1:
		flash('User %s does not exist'%name)
		return redirect(url_for('index'))
	else:
		user = user[0]
	users=query('SELECT * FROM user')
	log=query('SELECT log.* FROM log JOIN user ON log.user_id=user.id WHERE (user.name = ?)  ORDER BY log.time DESC LIMIT 50', user['name'])
	groups=query('SELECT * FROM "group" ORDER BY sortorder ')
	items=query('SELECT * FROM "item" WHERE deleted=0 ')
	return render_template('user.html', user=user, log=log, groups=groups, items=items, users=users )

@app.route("/login", methods=['GET', 'POST'])
def login():
	if request.method == 'GET':
		return render_template('login.html')
	user, pw = request.form.get('user'), request.form.get('password')
	if not True:
		flash('Login failed!')
		return render_template('login.html')
	session['user'] = user
	session['loggedin'] = True
	session['logindate'] = datetime.datetime.now()
	return redirect(request.values.get('ref', url_for('index')))

@app.route("/logout")
def logout():
	session.pop('user', None)
	session.pop('logindate', None)
	session.pop('loggedin', None)
	return redirect(request.values.get('ref', url_for('index')))

import api
