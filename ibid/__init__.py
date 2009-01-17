import logging
from logging.handlers import SMTPHandler

import sys
sys.path.append("./lib/wokkel.egg")
sys.path.insert(0, './lib')

import ibid.core
from ibid.config import FileConfig

sources = {}
config = {}
dispatcher = None
processors = []
reloader = None
databases = None
auth = None
service = None
log = logging.getLogger('core')

def setup(service=None):
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s: %(message)s', datefmt='%Y/%m/%d %H:%M:%S', filename='logs/ibid.log')

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(name)s %(levelname)s: %(message)s')
    console.setFormatter(formatter)
    logging.getLogger('').addHandler(console)

    service = service
    ibid.config = FileConfig("ibid.ini")
    ibid.config.merge(FileConfig("local.ini"))

    if 'email_errors' in ibid.config:
        email = SMTPHandler('localhost', 'ibid@localhost', ibid.config['email_errors'], 'Error Report')
        email.setLevel(logging.ERROR)
        logging.getLogger('').addHandler(email)
     
    ibid.reload_reloader()
    ibid.reloader.reload_dispatcher()
    ibid.reloader.reload_databases()
    ibid.reloader.load_processors()
    ibid.reloader.load_sources(service)
    ibid.reloader.reload_auth()

def reload_reloader():
    try:
        reload(ibid.core)
        new_reloader = ibid.core.Reloader()
        ibid.reloader = new_reloader
        return True
    except:
        log.exception(u"Exception occured while reloading Reloader")
        return False

# vi: set et sta sw=4 ts=4:
