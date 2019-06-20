import json
import sys
import traceback

from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from SocketServer import ThreadingMixIn
import threading
from Queue import Queue

from oslo_config import cfg

from ceilometer import service
from ceilometer_fiprom.fiprom_storage import PrometheusStorage

from ceilometer.openstack.common import log
LOG = log.getLogger(__name__)

OPTS = [
    cfg.IntOpt('server_port',
               help='port where the fiprom server will be listning')
]

cfg.CONF.register_opts(OPTS, group="fiprom")


# thread safe queue to keep requests to process
q = Queue(maxsize=0)


def process_request():
    publisher = PrometheusStorage("")
    while True:
        data = q.get()
        try:
            LOG.debug('Processing request (%s left in the queue)', q.qsize())
            publisher.record_metering_data(data)
        except:
            traceback.print_exc(file=sys.stdout)

        q.task_done()


class Handler(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_POST(self):

        data = self.rfile.read(int(self.headers['Content-Length']))
        self._set_headers()

        jdata = json.loads(data)
        q.put(jdata)
        LOG.debug('Adding request (%s already in the queue) [n.threads=%s]', q.qsize(), threading.activeCount())



class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


if __name__ == '__main__':

    # load configuration
    service.prepare_service()

    # set-up a thread for reading from the queue
    worker = threading.Thread(target=process_request)
    worker.setDaemon(True)
    worker.start()

    # set-up the htt server
    port = cfg.CONF.fiprom.server_port
    server = ThreadedHTTPServer(('0.0.0.0', port), Handler)
    server.serve_forever()