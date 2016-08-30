import threading
import Queue
import json
from oslo_log import log as logging
from oslo_log._i18n import _LE
from oslo_log._i18n import _LW
from oslo_log._i18n import _LI
from oslo_config import cfg
from requests import get, put, post, delete

LOG = logging.getLogger(__name__)

class MyData:
    pass

RegData = MyData()
RegData.reg_queue = Queue.Queue()
RegData.registered = False
RegData.thread_running = False
RegData.service_name = "proton"
RegData.service_type = "unknown"
RegData.port = 2705
RegData.host = '127.0.0.1'
RegData.gluon_port = 2704
RegData.gluon_host = '127.0.0.1'


class RegThread(threading.Thread):
    """
    A worker thread that will periodically try to register with
    the gluon service until it is successful.
    """

    def __init__(self, service_name, service_type, host, port, gluon_host, gluon_port):
        super(RegThread, self).__init__()
        self.input_q = RegData.reg_queue
        self.msg_q = []
        self.base_url = "http://%s:%d/v1" % (gluon_host, gluon_port)
        self.my_url = "http://%s:%d" % (host, port)
        self.service_name = service_name
        self.service_type = service_type
        LOG.info("RegThread starting")

    def _make_url(self, base_url, x):
        return '%s/%s' % (base_url, x)

    def proc_msg(self, msg):
        retVal = False
        if msg["operation"] == 'register':
            payload = {'id': msg["port_id"], 'owner': RegData.service_name}
            try:
                resp = post(self._make_url(self.base_url, 'ports'), json=payload)
                if resp.status_code == 201:
                    LOG.info(_LI("RegThread: port added gluon"))
                    retVal = True
                elif resp.status_code == 409:
                    LOG.info(_LI("RegThread: port already in gluon"))
                    retVal = True
                else:
                    LOG.info(_LI("RegThread: unexpected response code: %d" % resp.status_code))
            except:
                pass
        elif msg["operation"] == 'deregister':
            try:
                url = self._make_url(self.base_url, 'ports')
                url = self._make_url(url, msg["port_id"])
                resp = delete(url)
                if resp.status_code == 201 or resp.status_code == 200 or resp.status_code == 404:
                    LOG.info(_LI("RegThread: port removed from gluon"))
                    retVal = True
                else:
                    LOG.info(_LI("RegThread: unexpected response code: %d" % resp.status_code))
            except:
                pass
        else:
            LOG.error(_LE("Unknown reg message"))
            retVal = True
        return retVal

    def proc_msg_q(self):
        while len(self.msg_q):
            msg = self.msg_q.pop()
            if not self.proc_msg(msg):
                self.msg_q.append(msg)
                break

    def proc_reg_msg(self, msg):
        self.msg_q.insert(0, msg)
        if RegData.registered:
            self.proc_msg_q()

    def proc_timeout(self):
        if not RegData.registered:
            payload = {'name': self.service_name,
                       'service_type': self.service_type,
                       'url': self.my_url}
            try:
                resp = post(self._make_url(self.base_url, 'backends'), json=payload)
                if resp.status_code == 201:
                    LOG.info(_LI("RegThread: registered with gluon"))
                    RegData.registered = True
                elif resp.status_code == 409:
                    LOG.info(_LI("RegThread: already registered with gluon"))
                    RegData.registered = True
                else:
                    LOG.info(_LI("RegThread: unexpected response code: %d" % resp.status_code))
            except:
                pass
        if RegData.registered:
            self.proc_msg_q()

    def run(self):
        while 1:
            try:
                msg = self.input_q.get(True, 3.0)
                LOG.info(_LI("RegThread: received message %s ") % msg)
                self.proc_reg_msg(msg)
            except Queue.Empty:
                LOG.debug("RegThread: Queue timeout")
                self.proc_timeout()
            except ValueError:
                LOG.error(_LE("Error processing reg message"))
                break
        LOG.info(_LI("RegThread exiting"))
        RegData.thread_running = False


def register_with_gluon(**kwargs):
    """
    Kick of thread to register this proton with the gluon service.
    :param kwargs:
    :return:
    """
    if not RegData.registered:
        start_reg_thread(**kwargs)


def start_reg_thread(**kwargs):
    """
    Start the RegThread.  
    """
    for key, value in kwargs.iteritems():
        if key == "service_name":
            RegData.service_name = value
        elif key == "service_type":
            RegData.service_type = value
        elif key == "port":
            RegData.port = value
        elif key == "host":
            RegData.host = value
        elif key == "gluon_port":
            RegData.gluon_port = value
        elif key == "gluon_host":
            RegData.gluon_host = value
    if not RegData.thread_running:
        RegData.reg_thread = RegThread(RegData.service_name,
                                       RegData.service_type,
                                       RegData.host,
                                       RegData.port,
                                       RegData.gluon_host,
                                       RegData.gluon_port)
        RegData.reg_thread.start()
        RegData.thread_running = True
