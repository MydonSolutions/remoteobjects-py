from flask import request
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename
import re
import os.path
from datetime import datetime

from .object_registry import ObjectRegistry
from .server_version import __VERSION__

__REMOTE_OBJECT_REGISTRY__ = None

__UPLOAD_DIRECTORY__ = '/tmp'
__ALLOWED_EXTENSION_REGEX__ = r'.*'

__UPLOADED_FILE_DICT__ = {}


class RemoteObjectEndpoint_Upload(Resource):
    @staticmethod
    def _allowed_file(filename):
        return re.match(
            __ALLOWED_EXTENSION_REGEX__,
            os.path.splitext(filename)[1].lower()
        ) is not None

    def put(self):
        file_key_to_path_dict = {}
        for file_key, file_obj in request.files.items():
            if (self._allowed_file(file_obj.filename)):
                # argument was initially a filepath, but was uploaded
                filename = secure_filename(file_obj.filename)
                filepath = os.path.join(
                    __UPLOAD_DIRECTORY__,
                    '{}{}'.format(
                        datetime.now().strftime("%Y-%m-%d_%Hh%Mm%S_"),
                        filename
                    )
                )
                file_obj.save(filepath)
                file_key_to_path_dict[file_key] = filepath
            else:
                __UPLOADED_FILE_DICT__.update(file_key_to_path_dict)
                return {
                    'error': ('Allowed extension regex '
                              f'`{__ALLOWED_EXTENSION_REGEX__}` not met.'),
                    'files_uploaded': file_key_to_path_dict
                }, 500

        __UPLOADED_FILE_DICT__.update(file_key_to_path_dict)
        return {
            'files_uploaded': file_key_to_path_dict
        }, 200

    def delete(self):
        deleted_files_dict = {}
        try:
            for file_key in request.json['file_keys']:
                if file_key in __UPLOADED_FILE_DICT__:
                    filepath = __UPLOADED_FILE_DICT__[file_key]
                    os.remove(filepath)
                    deleted_files_dict[file_key] = filepath
        except BaseException as err:
            return {
                'files_removed': deleted_files_dict,
                'error': str(err)
            }, 500
        return {
            'files_removed': deleted_files_dict
        }, 200


class RemoteObjectEndpoint_Signature(Resource):
    def get(self):
        class_key = request.args.get('class_key', default=None, type=str)
        object_id = request.args.get('object_id', default=None, type=str)
        attribute_path = request.args.get(
            'attribute_path', default=None, type=str)

        if class_key is not None:
            # return the {method_name: method_signature...} of the class
            try:
                return {
                    'methods': __REMOTE_OBJECT_REGISTRY__.class_init_signature(
                        class_key
                    )
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        elif object_id is not None:
            # return the {method_name: method_signature...} of the registered
            # object
            try:
                return __REMOTE_OBJECT_REGISTRY__.obj_signature(
                    object_id,
                    attribute_path
                ), 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500


class RemoteObjectEndpoint_Registry(Resource):
    @staticmethod
    def _arg_dict(request):
        return request.json if request.json is not None else {}

    def get(self):
        class_key = request.args.get('class_key', default=None, type=str)
        object_id = request.args.get('object_id', default=None, type=str)
        attribute_path = request.args.get(
            'attribute_path', default="", type=str)
        if class_key is None and object_id is None:
            # return the abstract-object keys available for registration
            return {
                'class_keys': list(
                    __REMOTE_OBJECT_REGISTRY__._abstract_class_key_dict.keys()
                )
            }, 200
        elif class_key is not None:
            # register a new object by key, returning its ID
            try:
                return {
                    'id': __REMOTE_OBJECT_REGISTRY__.register_new_object(
                        class_key,
                        self._arg_dict(request)
                    )
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        elif object_id is not None:
            # return the value of the object's attribute
            try:
                value = __REMOTE_OBJECT_REGISTRY__.obj_attribute(
                    object_id,
                    attribute_path
                )
                if ObjectRegistry.class_is_primitive(value.__class__):
                    return {
                        'value': value
                    }, 200
                else:
                    return ObjectRegistry._obj_signature(value), 200

            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        return {
            'errror': 'Unsupported parameter combination.',
            'class_key': class_key,
            'object_id': object_id,
            'attribute_path': attribute_path,
        }, 500

    def put(self):
        object_id = request.args.get('object_id', default=None, type=str)
        attribute_path = request.args.get(
            'attribute_path',
            default=None,
            type=str
        )
        if object_id is not None and attribute_path is not None:
            # return the value of the object's attribute
            try:
                __REMOTE_OBJECT_REGISTRY__.obj_attribute_set(
                    object_id,
                    attribute_path,
                    request.json['value']
                )
                return {}, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        return {
            'errror': ('Unsupported parameter combination. Both `object_id` '
                       'and `attribute_path` must be supplied.'),
            'object_id': object_id,
            'attribute_path': attribute_path,
        }, 500

    def post(self):
        object_id = request.args.get('object_id', type=str)
        func_name = request.args.get('func_name', type=str)
        attribute_path = request.args.get(
            'attribute_path',
            default=None,
            type=str
        )
        try:
            return {
                'return': __REMOTE_OBJECT_REGISTRY__.obj_call_method(
                    object_id,
                    func_name,
                    self._arg_dict(request),
                    attribute_path=attribute_path
                )
            }, 200
        except BaseException as err:
            return {
                'error': f'{type(err)}: {err}'
            }, 500

    def patch(self):
        object_id = request.args.get('old_id', type=str)
        new_id = request.args.get('new_id', type=str)
        try:
            return {
                'id': __REMOTE_OBJECT_REGISTRY__.obj_set_id(object_id, new_id)
            }, 200
        except BaseException as err:
            return {
                'error': f'{type(err)}: {err}'
            }, 500

    def delete(self):
        object_id = request.args.get('object_id', type=str)
        try:
            __REMOTE_OBJECT_REGISTRY__.deregister_object(object_id)
            return {}, 200
        except BaseException as err:
            return {
                'error': f'{type(err)}: {err}'
            }, 500


class RemoteObjectEndpoint_Version(Resource):
    def get(self):
        return {
            'response': __VERSION__
        }, 200


def addRemoteObjectResources(flask_app, class_list):
    global __REMOTE_OBJECT_REGISTRY__
    global __UPLOAD_DIRECTORY__
    global __ALLOWED_EXTENSION_REGEX__

    if 'UPLOAD_DIRECTORY' in flask_app.config:
        __UPLOAD_DIRECTORY__ = flask_app.config['UPLOAD_DIRECTORY']
    if 'ALLOWED_EXTENSION_REGEX' in flask_app.config:
        __ALLOWED_EXTENSION_REGEX__ = flask_app.config[
            'ALLOWED_EXTENSION_REGEX'
        ]

    __REMOTE_OBJECT_REGISTRY__ = ObjectRegistry(class_list)

    flask_api = Api(flask_app)
    flask_api.add_resource(RemoteObjectEndpoint_Signature,
                           '/remoteobjects/registry/signature')
    flask_api.add_resource(RemoteObjectEndpoint_Registry,
                           '/remoteobjects/registry')
    flask_api.add_resource(RemoteObjectEndpoint_Upload,
                           '/remoteobjects/upload')
    flask_api.add_resource(RemoteObjectEndpoint_Version,
                           '/remoteobjects/version')
    return flask_api
