import logging

from configobj import ConfigObj
from validate import Validator
from pkg_resources import resource_stream

def monkeypatch(self, name):
    if self.has_key(name):
        return self[name]
    super(ConfigObj, self).__getattr__(name)

ConfigObj.__getattr__ = monkeypatch

def FileConfig(filename):
    spec = resource_stream(__name__, 'configspec.ini')
    configspec = ConfigObj(spec, list_values=False, encoding='utf-8')
    config = ConfigObj(filename, configspec=configspec, interpolation='Template', encoding='utf-8')
    config.validate(Validator())
    logging.getLogger('core.config').info(u"Loaded configuration from %s", filename)
    return config

# vi: set et sta sw=4 ts=4:
