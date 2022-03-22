from flask import request
from flask_restful import Resource, Api, reqparse

from .object_registry import ObjectRegistry

__REMOTE_OBJECT_REGISTRY__ = None

class RemoteObjectEndpoint_Signature(Resource):
    def get(self):
        class_key = request.args.get('class_key', default = None, type = str)
        object_id = request.args.get('object_id', default = None, type = str)
        
        if class_key is not None:
            # return the {method_name: method_signature...} of the class
            try:
                return {
                    'methods': __REMOTE_OBJECT_REGISTRY__.class_interface_signature(class_key)
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        elif object_id is not None:
            # return the {method_name: method_signature...} of the registered
            # object
            try:
                return {
                    'methods': __REMOTE_OBJECT_REGISTRY__.obj_interface_signature(object_id)
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500

class RemoteObjectEndpoint_Registry(Resource):
    @staticmethod
    def _arg_dict(request):
        arg_dict = request.json if request.json is not None else {}
        for file_key, file_obj in request.files.items():
            arg_dict[file_key] = file_obj.stream.read()
        return arg_dict

    def get(self):
        class_key = request.args.get('class_key', default = None, type = str)
        object_id = request.args.get('object_id', default = None, type = str)
        if class_key is None and object_id is None:
            # return the abstract-object keys available for registration
            return {
                'class_keys': list(__REMOTE_OBJECT_REGISTRY__._abstract_class_key_dict.keys())
            }, 200
        elif object_id is not None and class_key is not None:
            # confirm the object at ID matches the type of Key,
            # or if the object_id is empty register an a new object by key,
            # setting its ID
            if not object_id in object_registry._registered_obj_dict:
                try:
                    temp_id = __REMOTE_OBJECT_REGISTRY__.register_new_object(class_key, self._arg_dict(request))
                    __REMOTE_OBJECT_REGISTRY__.obj_set_id(temp_id, object_id)
                except BaseException as err:
                    return {
                        'error': f'{type(err)}: {str(err)}'
                    }, 500
            
            try:
                obj = __REMOTE_OBJECT_REGISTRY__.get_registered_object(object_id)
                return {
                    'return': obj.__name__ == class_key,
                    'object_id': object_id,
                    'class_key': class_key,
                    'object__name__': obj.__name__,
                    'object': str(obj),
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500
        elif class_key is not None:
            # register a new object by key, returning its ID
            try:
                return {
                    'id': __REMOTE_OBJECT_REGISTRY__.register_new_object(class_key, self._arg_dict(request))
                }, 200
            except BaseException as err:
                return {
                    'error': f'{type(err)}: {str(err)}'
                }, 500

    def post(self):
        object_id = request.args.get('object_id', type = str)
        func_name = request.args.get('func_name', type = str)
        try:
            return {
                'return': __REMOTE_OBJECT_REGISTRY__.obj_call_function(object_id, func_name, self._arg_dict(request))
            }, 200
        except BaseException as err:
            return {
                'error': f'{type(err)}: {err}'
            }, 500

    def patch(self):
        object_id = request.args.get('old_id', type = str)
        new_id = request.args.get('new_id', type = str)
        try:
            return {
                'id': __REMOTE_OBJECT_REGISTRY__.obj_set_id(object_id, new_id)
            }, 200
        except BaseException as err:
            return {
                'error': f'{type(err)}: {err}'
            }, 500

    def delete(self):
        object_id = request.args.get('object_id', type = str)
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
            'response': '1.0.0'
        }, 200

def addRemoteObjectResources(flask_api, object_registry):
    global __REMOTE_OBJECT_REGISTRY__
    
    __REMOTE_OBJECT_REGISTRY__ = object_registry
    flask_api.add_resource(RemoteObjectEndpoint_Signature, '/registry/signature')
    flask_api.add_resource(RemoteObjectEndpoint_Registry, '/registry')
    flask_api.add_resource(RemoteObjectEndpoint_Version, '/version')