import types
import inspect
import re
import threading

__PRIMITIVE_CLASSES__ = [
    str,
    int,
    float,
    bool,
    # dict,
    # list,
]


class ObjectRegistry(object):
    def __init__(self, registration_class_objects, registration_semaphore_dict=None):
        """
        :registration_class_objects list: {object_type} i.e.
            [cosmic_fengine.CosmicFengine,...]

        :registration_semaphore_dict dict|None:
            Registrations, and ID changes, of objects are
            reflected in the provided dictionary. However, the ObjectRegistry will
            not acquire/release the semapohores. The internal dict should be used
            by upstream code as it sees fit.
        """
        self._abstract_class_key_dict = {
            abs_obj.__name__: abs_obj for abs_obj in registration_class_objects
        }
        self._class_dict = {key: 0 for key in self._abstract_class_key_dict.keys()}
        self._registered_obj_dict = {}
        self._registered_sem_dict = registration_semaphore_dict

    @staticmethod
    def class_is_primitive(class_obj):
        return class_obj in __PRIMITIVE_CLASSES__

    @staticmethod
    def _object_str(obj):
        return f"<{obj.__class__.__name__}>{hex(id(obj))}"

    @staticmethod
    def _get_attributes(obj, primitives_not_custom=True):
        return {
            name: ObjectRegistry._object_str(value)
            for (name, value) in inspect.getmembers(
                obj, lambda a: not inspect.isroutine(a)
            )
            if (
                re.match(r"__.*__", name) is None
                and not (
                    primitives_not_custom
                    ^ ObjectRegistry.class_is_primitive(value.__class__)
                )
            )
        }

    @staticmethod
    def _get_method_names(obj):
        return [
            name for (name, _) in inspect.getmembers(obj, lambda a: inspect.ismethod(a))
        ]

    @staticmethod
    def _get_parameter_dict(param: inspect.Parameter):
        ret = {"code_string": str(param)}
        if param.default != inspect.Parameter.empty:
            ret["default"] = param.default
        return ret

    @staticmethod
    def _get_function_args(func):
        """
        Return
        ------
        (dict): {name: {
                'code_string': code-string, ?'default': default}
            }
        """
        if not (
            isinstance(func, types.FunctionType) or isinstance(func, types.MethodType)
        ):
            raise RuntimeError(f"`{func}` is not a function nor method")
        return {
            key: ObjectRegistry._get_parameter_dict(parameter)
            for (key, parameter) in inspect.signature(func).parameters.items()
        }

    @staticmethod
    def _obj_method_signature(obj, method_name):
        """
        Return
        ------
        (dict): {name: {
                'code_string': code-string, ?'default': default}
            }
        """
        if hasattr(obj, method_name):
            func = getattr(obj, method_name)
        else:
            raise NotImplementedError(
                "Class `{}` does not implement `{}`".format(obj, method_name)
            )
        return ObjectRegistry._get_function_args(func)

    @staticmethod
    def _obj_call_method(obj, method_name, method_args_dict=None):
        if method_args_dict is None:
            method_args_dict = {}
        assert isinstance(method_args_dict, dict)
        if hasattr(obj, method_name):
            func = getattr(obj, method_name)
        else:
            raise NotImplementedError(
                "Class `{}` does not implement `{}`".format(obj, method_name)
            )

        if method_name == "__init__":
            return obj(**method_args_dict)
        else:
            return func(**method_args_dict)

    def get_registered_object(self, objid):
        if objid not in self._registered_obj_dict:
            raise NotImplementedError("No registered object for `{}`.".format(objid))
        return self._registered_obj_dict[objid]

    @staticmethod
    def _obj_signature(obj):
        return {
            "class": obj.__class__.__name__,
            "object_str": ObjectRegistry._object_str(obj),
            "methods": {
                method_name: ObjectRegistry._obj_method_signature(obj, method_name)
                for method_name in ObjectRegistry._get_method_names(obj)
            },
            "attributes": ObjectRegistry._get_attributes(
                obj, primitives_not_custom=True
            ),
            "attributes_nonprimitive": ObjectRegistry._get_attributes(
                obj, primitives_not_custom=False
            ),
        }

    @staticmethod
    def _traverse_attribute_path(obj, attribute_path):
        attributes = attribute_path.split(".")
        attribute_final = attributes.pop()
        for attr in attributes:
            obj = getattr(obj, attr)
        return obj, attribute_final

    def _obj_attribute(self, obj, attribute_path):
        obj_leaf, attribute = self._traverse_attribute_path(obj, attribute_path)
        return getattr(obj_leaf, attribute)

    def obj_attribute(self, objid, attribute_path):
        obj = self.get_registered_object(objid)
        if attribute_path is None:
            return obj
        return self._obj_attribute(obj, attribute_path)

    def _obj_attribute_set(self, obj, attribute_path, value):
        obj_leaf, attribute = self._traverse_attribute_path(obj, attribute_path)
        setattr(obj_leaf, attribute, value)

    def obj_attribute_set(self, objid, attribute_path, value):
        obj = self.get_registered_object(objid)
        return self._obj_attribute_set(obj, attribute_path, value)

    def obj_signature(self, objid, attribute_path=None):
        obj = self.get_registered_object(objid)
        if attribute_path is not None:
            obj = self._obj_attribute(obj, attribute_path)
        return self._obj_signature(obj)

    def class_init_signature(self, class_key):
        if class_key not in self._abstract_class_key_dict:
            raise RuntimeError("No such class: `{}`".format(class_key))
        class_obj = self._abstract_class_key_dict[class_key]
        return {
            method_name: self._obj_method_signature(class_obj, method_name)
            for method_name in ["__init__"]
        }

    def obj_call_method(
        self, objid, method_name, method_args_dict=None, attribute_path=None
    ):
        if method_args_dict is None:
            method_args_dict = {}
        obj = self.get_registered_object(objid)
        if attribute_path is not None:
            obj = self._obj_attribute(obj, attribute_path)
        return self._obj_call_method(obj, method_name, method_args_dict)

    def register_new_object(self, class_key, args_dict=None):
        if args_dict is None:
            args_dict = {}
        if class_key not in self._abstract_class_key_dict:
            raise RuntimeError("No such class: `{}`".format(class_key))
        class_obj = self._abstract_class_key_dict[class_key]
        objid = "{}#{}".format(class_key, self._class_dict[class_key])
        try:
            self._registered_obj_dict[objid] = self._obj_call_method(
                class_obj, "__init__", args_dict
            )
            self._class_dict[class_key] += 1
            if self._registered_sem_dict is not None:
                self._registered_sem_dict[objid] = threading.Semaphore()
        except NotImplementedError as err:
            raise err
        except RuntimeError as err:
            raise err

        return objid

    def obj_set_id(self, objid, newid):
        if objid not in self._registered_obj_dict:
            raise NotImplementedError("No registered object for `{}`.".format(objid))
        if newid in self._registered_obj_dict:
            raise RuntimeError(
                ("Proposed ID `{}` for object already used for `{}`.").format(
                    newid, self._registered_obj_dict[newid]
                )
            )
        self._registered_obj_dict[newid] = self._registered_obj_dict.pop(objid)
        if self._registered_sem_dict is not None:
            self._registered_sem_dict[newid] = self._registered_sem_dict.pop(objid)
        return newid

    def deregister_object(self, objid):
        if objid not in self._registered_obj_dict:
            raise NotImplementedError("No registered object for `{}`.".format(objid))
        self._registered_obj_dict.pop(objid)
        if self._registered_sem_dict is not None:
            self._registered_sem_dict.pop(objid)
