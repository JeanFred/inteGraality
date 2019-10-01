#!/usr/bin/python
# -*- coding: utf-8  -*-

import os

from flask import Flask, render_template, request

from pages_processor import PagesProcessor, ProcessingException

app = Flask(__name__)
app.debug = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/update')
def update():
    page = request.args.get('page')
    processor = PagesProcessor()
    try:
        processor.process_one_page(page)
        return render_template('update.html', page=page)
    except ProcessingException as e:
        return render_template('update_error.html', page=page, error_message=e)
    except Exception as e:
        return render_template('update_unknown_error.html', page=page, error_type=type(e), error_message=e)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html', title=u'Page not found'), 404


if __name__ == '__main__':
    if os.uname()[1].startswith('tools-webgrid'):
        from flup.server.fcgi_fork import WSGIServer
        WSGIServer(app).run()
    else:
        if os.environ.get('LOCAL_ENVIRONMENT', False):
            app.run(host='0.0.0.0')
        else:
            app.run()
