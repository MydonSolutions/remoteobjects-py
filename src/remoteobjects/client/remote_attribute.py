from .remote_object import RemoteObject


class RemoteAttribute(RemoteObject):
    def __init__(
        self,
        server_uri: str,
        root_object_id: str,
        attribute_path: str,
        remote_object_str: str,
        ancestor_obj: dict,
        allowed_upload_extension_regex=r'.*',
        attribute_depth_allowance: int = 0
    ):
        super().__init__(
            server_uri,
            root_object_id,
            allowed_upload_extension_regex
        )
        ancestor_obj[remote_object_str] = self
        self._attribute_path = attribute_path
        self._remote_object_str = remote_object_str

        response = self._get(
            'remoteobjects/registry/signature',
            params={
                'object_id': self._remote_object_id,
                'attribute_path': self._attribute_path
            }
        )
        for (name, parameters) in response.json()['methods'].items():
            if name != '__init__':
                self._add_method_loc(
                    name,
                    self._define_remote_function_loc(
                        name,
                        parameters,  # name:code-string dict
                        self._remote_object_id,
                        attribute_absolute_path=self._attribute_path
                    )
                )
        if attribute_depth_allowance != 0:
            for (name, obj_str) in response.json()['attributes'].items():
                if hasattr(self, name): # how come???
                    input()
                    print(f'{self._remote_object_id}.{self._attribute_path} has already defined attribute `{name}`...')
                    print('\tself:', self)
                    print('\tremote_object_str:', remote_object_str)
                    print('\tproperty:', obj_str)
                    print('\tattribute:', getattr(self, name).__class__)
                    # print('nonprimitive:', response.json()["attributes_nonprimitive"][name])
                    input()
                else:
                    self._add_property(
                        f'{self._attribute_path}.{name}'
                    )
            for (name, obj_str) in response.json()['attributes_nonprimitive'].items():
                if obj_str in ancestor_obj:
                    setattr(self, name, ancestor_obj[obj_str])
                else:
                    setattr(self, name, RemoteAttribute(
                        self._server_uri,
                        self._remote_object_id,
                        f'{self._attribute_path}.{name}',
                        obj_str,
                        ancestor_obj,
                        allowed_upload_extension_regex,
                        attribute_depth_allowance-1
                    ))
