PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS 'user' (
	id		integer primary key autoincrement,
	name		varchar(255) default 'user',
	mail		varchar(255) default '',
	balance		integer default 0,
	deleted		boolean not null default 0 check (deleted IN (0,1)),
	transaction_mail BOOLEAN not NULL default 0 CHECK (transaction_mail IN (0,1)),
	allow_logging	BOOLEAN not NULL default 0 CHECK (allow_logging IN (0,1)),
	enable_stats	BOOLEAN not NULL default 1 CHECK (enable_stats IN (0,1))
);
CREATE TABLE IF NOT EXISTS 'item' (
	id		integer primary key autoincrement,
	name		varchar(255) default 'item',
	group_id	integer default -1,
	picture_id	integer default -1,
	price		integer default 0,
	purchasingprice	integer default 0,
	price		integer default 0,
	info_public	text default '',
	deleted		BOOLEAN NOT NULL default 0 CHECK (deleted IN (0,1))
);
CREATE TABLE IF NOT EXISTS 'pictures' (
	id		integer primary key autoincrement,
	data		blob
);
CREATE TABLE IF NOT EXISTS 'group' (
	id		integer primary key autoincrement,
	name		varchar(255) default 'group',
	sortorder	integer default 0
);
CREATE TABLE IF NOT EXISTS 'log' (
	id		integer primary key autoincrement,
	user_id 	integer,
	time		timestamp default current_timestamp,
	methode		varchar(255),
	oldbalance 	integer ,
	newbalance 	integer,
	parameter	integer
);
CREATE TABLE IF NOT EXISTS 'stats' (
	id		integer primary key autoincrement,
	item_id 	integer,
	time		timestamp default current_timestamp
);
CREATE TABLE IF NOT EXISTS 'barcode' (
	id		varchar(255) primary key,
	type		varchar(255) default 'item',
	parameter	integer default -1
);
CREATE TABLE IF NOT EXISTS 'mail' (
	id		integer primary key autoincrement,
	'to'		varchar(255),
	content		text
);

COMMIT
