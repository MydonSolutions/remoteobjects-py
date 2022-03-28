#!/usr/bin/env python

# Server imports
from flask import Flask
from remoteobjects.server import addRemoteObjectResources

# Client imports
from remoteobjects.client import defineRemoteClass, RestClient

# Unit Testing imports
import time
import threading
import unittest
import os


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
            remoteDummy = DummyRemote(dumbness=dumbness)
            self.assertEqual(dumbness, remoteDummy.is_dumb())

    def test_method_kwargs(self):
        remoteDummy = DummyRemote(dumbness='A plausibility')
        remoteDummy.is_dumb(dumbness='Misconstrued')
        self.assertEqual('Misconstrued', remoteDummy.is_dumb())

    def test_method_positional(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertEqual(42, remoteDummy.add(31, 11))

    def test_method_positional_missing(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        with self.assertRaises(TypeError) as err:
            remoteDummy.add(31)

    def test_method_positional_wrong_type(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        with self.assertRaises(RuntimeError) as err:
            remoteDummy.add(31, '11')

    def test_method_filepath_upload(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        script_dir, _ = os.path.split(os.path.realpath(__file__))
        self.assertTrue(remoteDummy.file_contains_affirmative(
            script_dir + '/affirmative.txt'))

    def test_id_control(self):
        remoteDummy = DummyRemote(
            dumbness='Resilient',
            remote_object_id='PersistentDummy',
            delete_remote_on_del=False
        )
        remoteDummy.__del__()

        client = RestClient('http://localhost:6000')
        response = client._get(
            'remoteobjects/registry',
            params={
                'class_key': 'Dummy',
                'object_id': 'PersistentDummy'
            }
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['new_object'])

        response = client._delete(
            'remoteobjects/registry',
            params={
                'object_id': 'PersistentDummy'
            }
        )
        self.assertEqual(response.status_code, 200)

    def test_property_access(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertTrue(isinstance(remoteDummy.dumbness, str))
        self.assertTrue(isinstance(remoteDummy.int_attribute, int))
        self.assertEqual(remoteDummy.dumbness, 'A tired subject')
        remoteDummy.dumbness = 'A tried subject'
        self.assertEqual(remoteDummy.dumbness, 'A tried subject')

    def test_property_method(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertTrue(remoteDummy.dumbness.endswith('subject'))

    def test_internal_access(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertEqual(remoteDummy.internal_object.str_attr, 'Internal')
        remoteDummy.internal_object.str_attr = 'Accessed!'
        self.assertEqual(remoteDummy.internal_object.str_attr, 'Accessed!')

    def test_internal_method(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertEqual(remoteDummy.internal_object.int_attr, 420)
        remoteDummy.internal_object.decrement(378)
        self.assertEqual(remoteDummy.internal_object.int_attr, 42)
    
    def test_nested_access(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertEqual(remoteDummy.internal_object.nested_object.str_attribute, 'Nested')
        remoteDummy.internal_object.nested_object.str_attribute = 'Accessed!'
        self.assertEqual(remoteDummy.internal_object.nested_object.str_attribute, 'Accessed!')

    def test_nested_method(self):
        remoteDummy = DummyRemote(dumbness='A tired subject')
        self.assertEqual(remoteDummy.internal_object.nested_object.int_attribute, 420)
        remoteDummy.internal_object.nested_object.increment(-378)
        self.assertEqual(remoteDummy.internal_object.nested_object.int_attribute, 42)

###############################################################################


if __name__ == '__main__':
    class Nested(object):
        def __init__(self, **kwargs):
            self.int_attribute = 420
            self.str_attribute = 'Hello World!'
            if 'string' in kwargs:
                self.str_attribute = kwargs['string']

        def increment(self, inc=1):
            self.int_attribute += inc
            return self.int_attribute

    class Internal(object):
        def __init__(self, string='Hello World!'):
            self.int_attr = 420
            self.str_attr = string
            self.nested_object: Nested = Nested(string='Nested')

        def decrement(self, dec=1):
            self.int_attr -= dec
            return self.int_attr

        def print(self):
            print(f'Internal(int:{self.int_attr}, str:{self.str_attr}')

    # define a simple class to be offered in the remote-object server
    class Dummy(object):
        def __init__(self, **kwargs):
            self.int_attribute: int = 1
            self.internal_object: Internal = Internal(string='Internal')
            self.dumbness = 'Not at all'
            if 'dumbness' in kwargs:
                self.dumbness = kwargs['dumbness']

        def is_dumb(self, **kwargs):
            if 'dumbness' in kwargs:
                self.dumbness = kwargs['dumbness']
            return self.dumbness

        def add(self, a: int, b: int):
            return a + b

        def file_contains_affirmative(self, filepath):
            with open(filepath, 'r') as fio:
                content = fio.read()
                return content.startswith('SUCCESS')

    # start a Flask server, adding remote-object resources to the RESTful API
    app = Flask(__name__)
    addRemoteObjectResources(
        app,
        [Dummy]
    )
    server_thread = threading.Thread(
        target=app.run,
        kwargs={
            'host': '0.0.0.0',
            'port': 6000,
            'debug': False},
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)

    # run remote-object access tests
    unittest.main()

    server_thread.terminate()
    server_thread.join()
