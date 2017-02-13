#!/usr/bin/python3
from werkzeug.contrib.profiler import ProfilerMiddleware
from server import app
app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30])
app.run(debug = True)

