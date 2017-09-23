#!/usr/bin/env python3
from server import *

if __name__ == '__main__':
	load_config_file()
	init_db()
	app.run(threaded=True, host="127.0.0.1")

