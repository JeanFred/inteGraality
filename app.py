#!/usr/bin/python
# -*- coding: utf-8  -*-

import os

from flask import Flask, render_template

app = Flask(__name__)
app.debug = True


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    if os.uname()[1].startswith('tools-webgrid'):
        from flup.server.fcgi_fork import WSGIServer
        WSGIServer(app).run()
    else:
        if os.environ.get('LOCAL_ENVIRONMENT', False):
            app.run(host='0.0.0.0')
        else:
            app.run()
