from flask import Flask, render_template, g, session, Response, redirect, request, url_for, flash
from functools import wraps
import sqlite3
import hashlib
import locale
import random
import string
import os
from PIL import Image
import io

locale.setlocale(locale.LC_ALL, 'de_DE.utf8')

app = Flask(__name__)

app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

config = app.config
config.from_pyfile('config.py.example', silent=True)
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
        return False

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
def register_navbar(name, iconlib='bootstrap', icon=None):
	def wrapper(func):
		endpoint = func.__name__
		app.jinja_env.globals['navbar'].append((endpoint, name, iconlib, icon, True))
		return func
	return wrapper

def log_action(userid,old,new,methode,parameter):
	print(userid,old,new,methode,parameter)
	query('INSERT INTO "log" (user_id, methode, oldbalance, newbalance, parameter) values (?, ?, ?, ?, ?)', userid, methode, old, new, parameter)

@register_navbar('User', icon='user', iconlib='fa')
@app.route("/")
def index():
	return render_template('index.html', allusers=query('SELECT * FROM user WHERE deleted=0'))

@app.route("/api/user/add", methods=['POST'])
@csrf_protect
def adduser():
	if request.values.get('name', '') == '':
		return redirect(url_for('index'))
	args = []
	args.append(request.values.get('name', ''))
	args.append(request.values.get('mail', ''))
	if request.values.get('transaction_mail', False):
		args.append(True)
	else:
		args.append(False)
	if request.values.get('allow_logging', False):
		args.append(True)
	else:
		args.append(False)

	query("INSERT INTO user (name, mail, transaction_mail, allow_logging) VALUES (?, ?, ?, ?)", *args)
	return redirect(url_for('index'))

@app.route("/api/user/transfere", methods=['POST'])
@csrf_protect
def transferemoney():
	args = []
	sender = int(request.values.get('sender', -1))
	sender = query('SELECT * FROM user WHERE id = ?', sender)
	if not len(sender) == 1:
		flash('Sender not found')
		print(sender)
		return redirect(request.values.get('ref', url_for('userpage', id=request.values.get('sender', -1))))
	sender = sender[0]

	recipient = request.values.get('recipient', None)
	recipient = query('SELECT * FROM user WHERE name = ?', recipient)
	if not len(recipient) == 1:
		print(recipient)
		flash('Recipient not found')
		return redirect(request.values.get('ref', url_for('userpage', id=request.values.get('sender', -1))))
	recipient = recipient[0]


	amount = int(float(request.values.get('amount', 0))*100)
	args.append(request.values.get('reason', ''))
		
	query('UPDATE user SET balance = balance - ? WHERE id = ?', amount , sender['id'])
	log_action(sender['id'], sender['balance'], sender['balance'] - amount, 'transfereTo', recipient['id'])

	query('UPDATE user SET balance = balance + ? WHERE id = ?', amount , recipient['id'])
	log_action(recipient['id'], recipient['balance'], recipient['balance'] + amount, 'transfereFrom', sender['id'])
	
	if request.values.get('noref', False):
		return 'OK', 200
	else:
		return redirect(request.values.get('ref', url_for('userpage', id=sender['id'])))

@register_navbar('Items', icon='list', iconlib='fa')
@app.route("/items")
def itemlist():
	return render_template('itemlist.html', groups=query('SELECT * FROM "group" ORDER BY sortorder '), items=query('SELECT * FROM "item" WHERE deleted=0 or deleted=? ORDER BY name', request.values.get('showdeleted', 0)))

@app.route("/items/<itemid>", methods=['GET', 'POST'])
@csrf_protect
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

@app.route("/items/<int:itemid>/del")
@csrf_protect
def delitem(itemid):
	query("UPDATE item SET deleted = ? WHERE id = ?", {0:1,1:0}[itemidtoobj(itemid).get('deleted', 0)], itemid)
	return redirect(request.values.get('ref', url_for('itemlist')))


@app.route("/u/<name>")
@app.route("/u/<int:id>")
def userpage(name=None, id=None):
	user=query('SELECT * FROM user WHERE (name = ?) or (id = ?)', name, id)[0]
	users=query('SELECT * FROM user')
	log=query('SELECT log.* FROM log JOIN user ON log.user_id=user.id WHERE (user.name = ?)  ORDER BY log.time DESC LIMIT 5', user['name'])
	groups=query('SELECT * FROM "group" ORDER BY sortorder ')
	items=query('SELECT * FROM "item" WHERE deleted=0 ')
	return render_template('user.html', user=user, log=log, groups=groups, items=items, users=users )


@app.route("/api/img/<imgid>")
@app.route("/api/img/")
def get_img(imgid=None):
	data = query('SELECT data FROM pictures WHERE id = ?', imgid)
	if len(data) == 1:
		return Response(data[0]['data'], mimetype='image/png')
	else:
		return 'Not found', 404

@app.route("/api/img/add", methods=['GET', 'POST'])
@app.route("/api/img/add/<imgid>", methods=['GET', 'POST'])
def add_img(imgid=None):
	if imgid:
		imgid = int(imgid)
	if (request.method == 'POST') and ('img' in request.files):
		img = Image.open(request.files['img'])
		tmp = io.BytesIO()
		with img:
			img.load()
			img.thumbnail((200,200) , Image.ANTIALIAS)
			img.save(tmp,format="PNG")
		query("INSERT INTO pictures (data) values (?)",sqlite3.Binary(tmp.getvalue()))
		return redirect(url_for("add_img",imgid=1))
	else:
		return render_template('imgupload.html', pictures=query("SELECT id from pictures"), selected=imgid)

@app.route("/api/buy/<name>/<int:itemid>")
@csrf_protect
def buy(name, itemid):
	user = query('SELECT * FROM user WHERE name = ?', name)[0]
	price = itemprice(itemidtoobj(itemid))
	if user:
		query('UPDATE user SET balance = balance - ? WHERE name = ?', price, name)
		usernew = query('SELECT * FROM user WHERE name = ?', name)[0]
		if price > 0:
			log_action(user['id'], user['balance'], usernew['balance'], 'buy', itemid)
		else:
			log_action(user['id'], user['balance'], usernew['balance'], 'recharge', itemid)
	if request.values.get('noref', False):
		return 'OK', 200
	else:
		return redirect(request.values.get('ref', url_for('userpage', name=name)))

@app.route("/api/setbalance/<name>/<newbalance>", methods=['GET', 'POST'])
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

