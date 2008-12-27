import ibid

from ibid.plugins import Processor, match, authorise

class Config(Processor):
    """Usage: reload config"""

    @match('^\s*reread\s+config\s*$')
    @authorise('config')
    def reload(self, event):
        try:
            ibid.config.reload()
            event.addresponse(u"Configuration reread")
        except:
            event.addresponse(u"Error reloading configuration")

    @match('\s*set\s+config\s+(\S+?)(?:\s+to\s+|\s*=\s*)(\S.*?)\s*$')
    @authorise('config')
    def set(self, event, key, value):
        print "Setting '%s' to '%s'" % (key, value)
        config = ibid.config
        for part in key.split('.')[:-1]:
            if part not in config:
                config[part] = {}
            config = config[part]

        config[key.split('.')[-1]] = value
        ibid.config.write()

        event.addresponse(u'Done')

    @match('\s*get\s+config\s+(\S+?)\s*$')
    def get(self, event, key):
        config = ibid.config
        for part in key.split('.'):
            if part not in config:
                event.addresponse(u'No such option')
                return event
            config = config[part]
        event.addresponse(str(config))
        
# vi: set et sta sw=4 ts=4: