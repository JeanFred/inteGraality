#!/usr/bin/python
# -*- coding: utf-8  -*-

import logging
import os

from flask import Flask, render_template, request
from flask_opentracing import FlaskTracing
from jaeger_client import Config

from pages_processor import PagesProcessor, ProcessingException

def _initialize_tracer():
    config = Config(config={'sampler': {'type': 'const', 'param': 1},
                            'logging': True,
                            'local_agent': {
                                'reporting_host': os.environ.get('JAEGER_AGENT_HOST'),
                                'reporting_port': os.environ.get('JAEGER_AGENT_PORT'),
                                }
                            },
                    # Service name can be arbitrary string describing this particular web service.
                    service_name="integraality",
                    validate=True)
    print("Tracing enabled!")
    return config.initialize_tracer()


app = Flask(__name__)
app.debug = True
jaeger_tracer = _initialize_tracer()
tracing = FlaskTracing(jaeger_tracer, True, app)


@app.route('/')
def index():
    print("INDEX")
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


@app.route('/queries')
def queries():
    page = request.args.get('page')
    property = request.args.get('property')
    grouping = request.args.get('grouping')
    with jaeger_tracer.start_active_span('flask_queries_pages_processor') as scope:
        processor = PagesProcessor()
        scope.span.log_kv({'event': 'PagesProcessor created', 'result': processor})
    try:
        with jaeger_tracer.start_active_span('flask_queries_make_stats_object_for_page_title') as scope:
            stats = processor.make_stats_object_for_page_title(page)
            scope.span.log_kv({'event': 'stats object created', 'result': stats})

        with jaeger_tracer.start_active_span('flask_queries_positive_query') as scope:
            positive_query = stats.get_query_for_items_for_property_positive(property, grouping)
            scope.span.log_kv({'event': 'positive_query computed', 'result': positive_query})

        with jaeger_tracer.start_active_span('flask_queries_negative_query') as scope:
            negative_query = stats.get_query_for_items_for_property_negative(property, grouping)
            scope.span.log_kv({'event': 'negative_query computed', 'result': negative_query})

        return render_template('queries.html', page=page, property=property, grouping=grouping,
                               positive_query=positive_query, negative_query=negative_query)
    except ProcessingException as e:
        return render_template('queries_error.html', page=page, error_message=e)
    except Exception as e:
        return render_template('queries_unknown_error.html', page=page, error_type=type(e), error_message=e)


@app.errorhandler(404)
def page_not_found(error):
    return render_template('page_not_found.html', title=u'Page not found'), 404


if __name__ == '__main__':
    print("START")
    # if os.uname()[1].startswith('tools-webgrid'):
    #     from flup.server.fcgi_fork import WSGIServer
    #     WSGIServer(app).run()
    # else:
    #     if os.environ.get('LOCAL_ENVIRONMENT', False):
    #         jaeger_tracer = _initialize_tracer()
    #         tracing = FlaskTracing(jaeger_tracer, True, app)
    #         app.run(debug=True, host='0.0.0.0')
    #     else:
    #         print("NOT LOCAL")
    #         app.run()
    logging.info("INITIALISE")

    # app.run(debug=True, host='0.0.0.0')
