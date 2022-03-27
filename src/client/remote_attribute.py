from .remote_object import RemoteObject


class RemoteAttribute(RemoteObject):
    def __init__(self,
                 server_uri: str,
                 root_object_id: str,
                 attribute_path: str,
                 allowed_upload_extension_regex=r'.*'
                 ):
        super().__init__(
            server_uri,
            allowed_upload_extension_regex
        )
        self._remote_root_object_id = root_object_id
        self._attribute_path = attribute_path

        response = self._get(
            'remoteobjects/registry/signature',
            params={
                'object_id': self._remote_root_object_id,
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
                        self._remote_root_object_id,
                        attribute_absolute_path=self._attribute_path
                    )
                )
        for (name, _) in response.json()['attributes'].items():
            self._add_property(
                self._remote_root_object_id,
                f'{self._attribute_path}.{name}'
            )
        for (name, _) in response.json()['attributes_nonbuiltins'].items():
            setattr(self, name, RemoteAttribute(
                self._server_uri,
                self._remote_root_object_id,
                f'{self._attribute_path}.{name}',
                allowed_upload_extension_regex
            ))
