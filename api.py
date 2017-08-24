from server import *

@app.route("/api/user/add", methods=['POST'])
@csrf_protect
def api_user_add():
	ref= request.values.get('ref', None)
	if request.values.get('name', '') == '':
		if ref:
			return redirect(ref)
		else:
			return 'name is empty', 422
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
	if ref:
		return redirect(ref)
	else:
		return 'OK'

@app.route("/api/user/<name>/edit", methods=['POST'])
@csrf_protect
def api_user_edit(name):
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
	args.append(int(request.values.get('picture_id', -1)))
	args.append(int(request.values.get('userid', -1)))

	query("UPDATE user SET name = ?, mail = ?, transaction_mail = ?, allow_logging = ?, picture_id = ? WHERE id = ?", *args)
	
	ref= request.values.get('ref', None)
	if ref:
		return redirect(ref)
	else:
		return 'OK'

@app.route("/api/user/<sender>/transfer", methods=['POST'])
@csrf_protect
def api_user_transfer(sender):
	ref= request.values.get('ref', None)
	args = []
	sender = query('SELECT * FROM user WHERE name = ?', sender)
	if not len(sender) == 1:
		if ref:
			flash('Sender not found')
			return redirect(ref)
		else:
			return 'Sender not found', 422
	sender = sender[0]

	recipient = request.values.get('recipient', None)
	recipient = query('SELECT * FROM user WHERE name = ?', recipient)
	if not len(recipient) == 1:
		if ref:
			flash('Recipient not found')
			return redirect(ref)
		else:
			return 'Recipient not found', 422
	recipient = recipient[0]


	amount = int(float(request.values.get('amount', 0))*100)
	args.append(request.values.get('reason', ''))
		
	query('UPDATE user SET balance = balance - ? WHERE id = ?', amount , sender['id'])
	log_action(sender['id'], sender['balance'], sender['balance'] - amount, 'transferTo', recipient['id'])

	query('UPDATE user SET balance = balance + ? WHERE id = ?', amount , recipient['id'])
	log_action(recipient['id'], recipient['balance'], recipient['balance'] + amount, 'transferFrom', sender['id'])
	
	if ref:
		return redirect(ref)
	else:
		return 'OK'


@app.route("/api/item/<int:itemid>/del")
@csrf_protect
@admin_required
def delitem(itemid):
	query("UPDATE item SET deleted = ? WHERE id = ?", {0:1,1:0}[itemidtoobj(itemid).get('deleted', 0)], itemid)
	return redirect(request.values.get('ref', url_for('itemlist')))

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
def api_img_add(imgid=None):
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

@app.route("/api/user/<name>/buy/<int:itemid>")
@csrf_protect
def api_user_buy(name, itemid):
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
		return 'OK'
	else:
		return redirect(request.values.get('ref', url_for('userpage', name=name)))

@app.route("/api/user/<name>/balance", methods=['GET', 'POST'])
@csrf_protect
def api_user_balance(name, newbalance=None):
	user = query('SELECT * FROM user WHERE name = ?', name)[0]
	if not newbalance:
		newbalance = request.values.get('newbalance', None)
	if newbalance:
		newbalance = int(newbalance)
		query('UPDATE user SET balance = ? WHERE name = ?', newbalance, name)
		log_action(user['id'], user['balance'], newbalance, 'set_balance', 0)
	else:
		return str(query('SELECT balance FROM user WHERE name = ?', name)[0]['balance']),200
	ref = request.values.get('ref', None)
	if ref:
		return redirect(ref)
	else:
		return 'OK'

@app.route("/api/user/<name>/log")
@csrf_protect
def api_user_log(name):
	return str(query('SELECT balance FROM user WHERE name = ?', name)[0]['balance']),200
