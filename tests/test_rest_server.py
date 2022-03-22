#!/usr/bin/env python

###############################################################################
class Dummy(object):
    def __init__(self, **kwargs):
        self.dumbness = 'Not at all'
        if 'dumbness' in kwargs:
            self.dumbness = kwargs['dumbness']
    
    def is_dumb(self, **kwargs):
        if 'dumbness' in kwargs:
            self.dumbness = kwargs['dumbness']
        return self.dumbness

    def add(self, a, b):
        return a + b
###############################################################################

from flask import Flask
from flask_restful import Api
import remoteobjects.server as remoteobjectserver
from multiprocessing import Process

app = Flask(__name__)
remoteobjectserver.addRemoteObjectResources(
    Api(app),
    remoteobjectserver.ObjectRegistry([
        Dummy
    ])
)


server_thread = Process(target=app.run, kwargs={'host':'0.0.0.0', 'port':6000, 'debug':False})
server_thread.start()

###############################################################################

from remoteobjects.client import defineRemoteClass

defineRemoteClass(
    'Dummy',
    'http://localhost:6000',
    globals(),
    server_version = '1.0.0'
)

remoteDummy = DummyRemote(dumbness = 'Seemingly so..')

print(remoteDummy.is_dumb())
print(remoteDummy.add(31, 13))
print(remoteDummy.is_dumb(dumbness = 'No way baby!'))
print(remoteDummy.is_dumb())
try:
    remoteDummy.add(31, '31')
    assert False, 'Unexpected success.'
except RuntimeError as err:
    print(f'Expected error caught: `{err}`.')

###############################################################################

server_thread.terminate()
server_thread.join()