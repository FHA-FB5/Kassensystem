from flask import Flask, render_template, g
import sqlite3
import hashlib
app = Flask(__name__)

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

@app.route("/")
def index():
	return render_template('index.html', allusers=query('SELECT * FROM user WHERE deleted=0'))

@app.route("/user/<id>")
def userpage(id):
	user=query('SELECT * FROM user WHERE id=?', [id], True)
	groups=query('SELECT * FROM "group" ORDER BY sortorder ')
	items=query('SELECT * FROM "item" WHERE deleted=0 ')
	return render_template('user.html', user=user, groups=groups, items=items )

@app.route("/login")
def login():
	return "Test"

@app.route("/logout")
def logout():
	return "Test"

