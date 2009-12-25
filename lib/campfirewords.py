#!/usr/bin/env python
# Copyright 2009 Stefano Rivera <scripts@rivera.za.net>
# Released under the MIT license

# Speaks Campfire API protocol.

from base64 import b64encode
import logging

from twisted.internet import protocol, reactor, ssl
from twisted.web.client import HTTPPageGetter, HTTPClientFactory, getPage

from ibid.compat import json

log = logging.getLogger('campfire')

class HTTPStreamGetter(HTTPPageGetter):

    def connectionMade(self):
        log.debug(u'Stream Connected')
        self.__buffer = ''
        self.factory.stream_connected()
        HTTPPageGetter.connectionMade(self)

    def handleResponsePart(self, data):
        self.factory.keepalive_received()
        if self.__buffer == '' and data == ' ':
            return
        if '\r' in data:
            data = self.__buffer + data
            self.__buffer = ''
            for part in data.split('\r'):
                part = part.strip()
                if part != '':
                    self.factory.event(part)
        else:
            self.__buffer += data

class JSONStream(HTTPClientFactory, protocol.ReconnectingClientFactory):

    protocol = HTTPStreamGetter

    _reconnect_deferred = None

    def __init__(self, url, keepalive_timeout=0, *args, **kwargs):
        self.keepalive_timeout = keepalive_timeout
        HTTPClientFactory.__init__(self, url, *args, **kwargs)

    def connectionMade(self):
        HTTPClientFactory.connectionMade(self)
        self.keepalive_received()

    def keepalive_received(self):
        if self._reconnect_deferred:
            self._reconnect_deferred.cancel()
        if self.keepalive_timeout:
            self._reconnect_deferred = reactor.callLater(self.keepalive_timeout,
                     self.keepalive_reconnect)

    def keepalive_reconnect(self):
        log.info(u'No keep-alive received in a while, reconnecting.')
        self._reconnect_deferred = None
        self.proto.transport.loseConnection()


class RoomNameException(Exception):
    pass


class CampfireClient(object):

    # Configuration
    subdomain = 'ibid'
    token = '7c6f164ef01eb3b75a52810ee145f28e8cd49f2a'
    rooms = ('Room 1',)
    keepalive_timeout = 10

    # Looked up
    my_id = 0
    my_name = ''

    _streams = {}
    _rooms = {}
    _users = {}

    # Callbacks:
    def joined_room(self, room_info):
        pass

    # Actions:
    def say(self, room_name, message):
        data = {'message': { 'body': message }}

        self._get_data('room/%(room_id)i/speak.json',
                      self._locate_room(room_name), 'speak', method='POST',
                      headers={'Content-Type': 'application/json'},
                      postdata=json.dumps(data))

    def topic(self, room_name, topic):
        data = {'request': {'room': {'topic': topic}}}

        self._get_data('room/%(room_id)i.json',
                      self._locate_room(room_name), 'set topic', method='PUT',
                      headers={'Content-Type': 'application/json'},
                      postdata=json.dumps(data))

    # Internal:
    def _locate_room(self, room_name):
        if isinstance(room_name, int):
            return room_name
        else:
            rooms = [k for k, r in self._rooms.iteritems()
                                if r['name'] == room_name]
            if len(rooms) != 1:
                raise RoomNameException(room_name)

            return rooms[0]

    def failure(self, failure, room_id, task):
        log.error(u'Request failed: %s for room %s: %s', task, repr(room_id),
                  unicode(failure))
        if room_id is not None:
            self.leave_room(room_id) \
                    .addCallback(lambda x: self.join_room(room_id))

    def disconnect(self):
        for id in self._streams.iterkeys():
            self.leave_room(id)

    def connect(self):
        self._get_id()

    def _get_id(self):
        log.debug(u'Finding my ID')
        self._get_data('users/me.json', None, 'my info') \
                .addCallback(self._do_get_id)

    def _do_get_id(self, data):
        log.debug(u'Parsing my info')
        meta = json.loads(data)['user']
        self.my_id = meta['id']
        self.my_name = meta['name']
        self.get_room_list()

    def get_room_list(self):
        log.debug(u'Getting room list')
        self._get_data('rooms.json', None, 'room list') \
                .addCallback(self._do_room_list)

    def _do_room_list(self, data):
        log.debug(u'Parsing room list')
        roommeta = json.loads(data)['rooms']

        for room in roommeta:
            # We want this present before we get to room metadata
            self._rooms[room['id']] = {'name': room['name']}

            if room['name'] in self.rooms:
                logging.debug(u'Connecting to: %s', room['name'])

                self.join_room(room['id'])

    def leave_room(self, room_id):
        log.debug('Leaving room: %i', room_id)
        if room_id in self._streams:
            self._streams[room_id].proto.transport.loseConnection()
        return self._get_data('room/%(room_id)i/leave.json', room_id,
                             method='POST')

    def join_room(self, room_id):
        log.debug('Joining room: %i', room_id)
        self._streams[room_id] = stream = JSONStream(
                'https://streaming.campfirenow.com/room/%i/live.json' % room_id,
                keepalive_timeout=self.keepalive_timeout,
                headers={'Authorization': self._auth_header()})
        stream.event = self._event
        stream.stream_connected = lambda : self._joined_room(room_id)
        stream.clientConnectionLost = lambda connector, unused_reason: \
                self.failure(unused_reason, room_id, 'stream')

        contextFactory = ssl.ClientContextFactory()
        stream.proto = reactor.connectSSL(
                'streaming.campfirenow.com', 443,
                stream, contextFactory)

    def _joined_room(self, room_id):
        self._get_data('room/%(room_id)i/join.json', room_id, 'join room',
                      method='POST')
        self._get_data('room/%(room_id)i.json', room_id, 'room info') \
                .addCallback(self._do_room_info)

    def _do_room_info(self, data):
        d = json.loads(data)['room']
        r = self._rooms[d['id']]
        for k, v in d.iteritems():
            if k != 'users':
                r[k] = v

        r['users'] = set()
        for user in d['users']:
            self._users[user['id']] = u = user
            r['users'].add(user['id'])
        self.joined_room(r)

    def _auth_header(self):
        return 'Basic ' + b64encode(self.token + ':')

    def _base_url(self):
        return str('http://%s.campfirenow.com/' % self.subdomain)

    def _get_data(self, path, room_id, errback_description=None, method='GET',
                 headers={}, postdata=None):
        "Make a campfire API request"

        headers['Authorization'] = self._auth_header()
        if postdata is None and method in ('POST', 'PUT'):
            postdata = ''

        d = getPage(self._base_url() + path % {'room_id': room_id},
                    method=method, headers=headers, postdata=postdata)
        if errback_description:
            d = d.addErrback(self.failure, room_id, errback_description)
        return d

    def _event(self, data):
        "Handle a JSON stream event, data is the JSON"
        d = json.loads(data)

        if d['user_id'] == self.my_id:
            return

        type = d['type']
        if type.endswith('Message'):
            type = type[:-7]
        if hasattr(self, 'handle_' + type):
            params = {}
            params['room_id'] = d['room_id']
            params['room_name'] = self._rooms[d['room_id']]['name']
            if d.get('user_id') is not None:
                params['user_id'] = d['user_id']
                params['user_name'] = self._users[d['user_id']]['name']
            if d.get('body', None) is not None:
                params['body'] = d['body']

            getattr(self, 'handle_' + type)(**params)

# Small testing framework:
def main():

    logging.basicConfig(level=logging.NOTSET)

    class TestClient(CampfireClient):
        pass

    t = TestClient()
    t.connect()

    reactor.run()

if __name__ == '__main__':
    main()

# vi: set et sta sw=4 ts=4:
