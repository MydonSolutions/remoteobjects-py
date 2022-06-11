from .remote_object import RemoteObject


class RemoteAttribute(RemoteObject):
    def __init__(
        self,
        server_uri: str,
        root_object_id: str,
        attribute_path: str,
        remote_object_str: str,
        ancestor_obj: dict,
        allowed_upload_extension_regex=r".*",
        attribute_depth_allowance: int = 0,
    ):
        super().__init__(server_uri, root_object_id, allowed_upload_extension_regex)
        self._ancestor_obj = ancestor_obj
        self._attribute_path = attribute_path
        self._remote_object_str = remote_object_str
        self._attribute_depth_allowance = attribute_depth_allowance
        self._ancestor_obj[remote_object_str] = self
        self._initialised = False

    def _init_from_remote_signature(self):
        response = self._get(
            "remoteobjects/registry/signature",
            params={
                "object_id": self._remote_object_id,
                "attribute_path": self._attribute_path,
            },
        )
        for (name, parameters) in response.json()["methods"].items():
            if name != "__init__":
                self._add_method_loc(
                    name,
                    self._define_remote_function_loc(
                        name,
                        parameters,  # name:code-string dict
                        self._remote_object_id,
                        attribute_absolute_path=self._attribute_path,
                    ),
                )
        if self._attribute_depth_allowance != 0:
            for (name, obj_str) in response.json()["attributes"].items():
                # the class might already have the property defined
                if not hasattr(self, name):
                    self._add_property(f"{self._attribute_path}.{name}")

            for (name, obj_str) in response.json()["attributes_nonprimitive"].items():
                if obj_str in self._ancestor_obj:
                    self._add_remote_property(name, self._ancestor_obj[obj_str])
                else:
                    remote_attribute = RemoteAttribute(
                        self._server_uri,
                        self._remote_object_id,
                        f"{self._attribute_path}.{name}",
                        obj_str,
                        self._ancestor_obj,
                        self._allowed_extension_regex,
                        self._attribute_depth_allowance - 1,
                    )
                    self._add_remote_property(name, remote_attribute)
