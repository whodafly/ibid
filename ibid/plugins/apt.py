from subprocess import Popen, PIPE

from ibid.plugins import Processor, match
from ibid.config import Option
from ibid.utils import file_in_path

help = {}

help['aptitude'] = u'Searches for packages'
class Aptitude(Processor):
    """(apt|aptitude|apt-get) [search] <term>"""
    feature = 'aptitude'

    aptitude = Option('aptitude', 'Path to aptitude executable', 'aptitude')

    def setup(self):
        if not file_in_path(self.aptitude):
            raise Exception("Cannot locate aptitude executeable")

    @match(r'^(?:apt|aptitude|apt-get)\s+(?:search\s+)(.+)$')
    def search(self, event, term):
        apt = Popen([self.aptitude, 'search', '-F', '%p', term], stdout=PIPE, stderr=PIPE)
        output, error = apt.communicate()
        code = apt.wait()

        if code == 0 and output:
            if output:
                event.addresponse(u', '.join(line.strip() for line in output.splitlines()))
            else:
                event.addresponse(u'No packages found')

    @match(r'(?:apt|aptitude|apt-get)\s+(?:show\s+)(.+)$')
    def show(self, event, package):
        apt = Popen([self.aptitude, 'show', package], stdout=PIPE, stderr=PIPE)
        output, error = apt.communicate()
        code = apt.wait()

        if code == 0 and output:
            print output
            description = None
            for line in output.splitlines():
                if not description:
                    if line.startswith('Description:'):
                        description = u'%s:' % line.replace('Description:', '', 1).strip()
                    elif line.startswith('Provided by:'):
                        description = u'Virtual package provided by %s' % line.replace('Provided by:', '', 1).strip()
                else:
                    description += ' ' + line.strip()
            if description:
                event.addresponse(description)
            else:
                event.addresponse(u'No such package')
    
help['apt-file'] = u'Searches for packages containing the specified file'
class AptFile(Processor):
    """apt-file [search] <term>"""
    feature = 'apt-file'

    aptfile = Option('apt-file', 'Path to apt-file executable', 'apt-file')

    def setup(self):
        if not file_in_path(self.aptfile):
            raise Exception("Cannot locate apt-file executeable")

    @match(r'^apt-?file\s+(?:search\s+)?(.+)$')
    def search(self, event, term):
        apt = Popen([self.aptfile, 'search', term], stdout=PIPE, stderr=PIPE)
        output, error = apt.communicate()
        code = apt.wait()

        if code == 0 and output:
            if output:
                event.addresponse(u', '.join(line.split(':')[0] for line in output.splitlines()))
            else:
                event.addresponse(u'No packages found')

# vi: set et sta sw=4 ts=4:
