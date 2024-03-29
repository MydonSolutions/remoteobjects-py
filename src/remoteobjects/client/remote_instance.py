from .remote_object import RemoteObject
from .rest_client import RestClient
import json


class RequiredParameter(object):
    pass


class RemoteInstance(RemoteObject):
    def __init__(
        self,
        class_key,
        server_uri=None,
        init_args_dict={},
        delete_remote_on_del=True,
        remote_object_id=None,
        allowed_upload_extension_regex=r".*",
        jsonEncoder=json.JSONEncoder,
        jsonDecoder=json.JSONDecoder,
    ):
        if remote_object_id is None:
            # Register a new instance
            for (key, value) in init_args_dict.items():
                if isinstance(value, RequiredParameter):
                    raise TypeError(
                        f"{class_key}.__init__() missing a required positional argument: '{key}'"
                    )

            client = RestClient(server_uri)
            registration_response = client._get(
                "remoteobjects/registry",
                params={
                    "class_key": class_key,
                },
                data=init_args_dict,
            )
            registration_response_json = json.loads(
                registration_response.content, cls=jsonDecoder
            )
            if registration_response.status_code != 200:
                raise RuntimeError(registration_response_json)
            remote_object_id = registration_response_json["id"]

        super().__init__(
            server_uri,
            remote_object_id,
            allowed_upload_extension_regex,
            jsonEncoder=jsonEncoder,
            jsonDecoder=jsonDecoder,
            confirm_server_version=True,
        )
        self._del_remote = delete_remote_on_del

    def _manage_CRUD_request(
        self, request_func, endpoint, data=None, params={}, files=None
    ):
        if "object_id" not in params and hasattr(self, "_remote_object_id"):
            params["object_id"] = self._remote_object_id
        return super()._manage_CRUD_request(
            request_func, endpoint, data=data, params=params, files=files
        )

    def __del__(self):
        self._delete_files_uploaded()
        if hasattr(self, "_del_remote") and self._del_remote:
            self._delete(
                "remoteobjects/registry", params={"object_id": self._remote_object_id}
            )

    def _set_id(self, new_id):
        response = self._patch(
            "remoteobjects/registry",
            params={
                "object_id": self._remote_object_id,
                "new_id": new_id,
            },
        )
        response_json = json.loads(response.content, cls=self.jsonDecoder)
        if response.status_code != 200:
            raise RuntimeError(response_json)
        self._remote_object_id = response_json["id"]
