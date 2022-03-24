#!/usr/bin/env python

# Server imports
from flask import Flask
from flask_restful import Api
from remoteobjects.server import addRemoteObjectResources

# Client imports
from remoteobjects.client import defineRemoteClass, RestClient

# Unit Testing imports
import time
import threading
import unittest

class TestRemoteObject(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # define a *Remote class, independent of the underlying local-class
        defineRemoteClass(
            'Dummy',
            'http://localhost:6000',
            globals()
        )

    def test_initialisation_kwargs(self):
        for dumbness in ['A possibility', 'A misnomer']:
            remoteDummy = DummyRemote(dumbness = dumbness)
            self.assertEqual(dumbness, remoteDummy.is_dumb())
    
    def test_method_kwargs(self):
        remoteDummy = DummyRemote(dumbness = 'A plausibility')
        remoteDummy.is_dumb(dumbness = 'Misconstrued')
        self.assertEqual('Misconstrued', remoteDummy.is_dumb())
    
    def test_method_positional(self):
        remoteDummy = DummyRemote(dumbness = 'A tired subject')
        self.assertEqual(42, remoteDummy.add(31, 11))
    
    def test_method_positional_missing(self):
        remoteDummy = DummyRemote(dumbness = 'A tired subject')
        with self.assertRaises(TypeError) as err:
            remoteDummy.add(31)
    
    def test_method_positional_wrong_type(self):
        remoteDummy = DummyRemote(dumbness = 'A tired subject')
        with self.assertRaises(RuntimeError) as err:
            remoteDummy.add(31, '11')
    
    def test_id_control(self):
        remoteDummy = DummyRemote(
            dumbness = 'Resilient',
            remote_object_id='PersistentDummy',
            delete_remote_on_del=False
        )
        remoteDummy.__del__()

        client = RestClient('http://localhost:6000')
        response = client._get(
            'registry',
            params = {
                'class_key': 'Dummy',
                'object_id': 'PersistentDummy'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['new_object'])

        response = client._delete(
            'registry',
            params = {
                'object_id': 'PersistentDummy'
            }
        )
        self.assertEqual(response.status_code, 200)

###############################################################################

if __name__ == '__main__':
    # define a simple class to be offered in the remote-object server
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

    # start a Flask server, adding remote-object resources to the RESTful API
    app = Flask(__name__)
    addRemoteObjectResources(
        Api(app),
        [Dummy]
    )
    server_thread = threading.Thread(target=app.run, kwargs={'host':'0.0.0.0', 'port':6000, 'debug':False}, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    # run remote-object access tests
    unittest.main()
    
    server_thread.terminate()
    server_thread.join()
