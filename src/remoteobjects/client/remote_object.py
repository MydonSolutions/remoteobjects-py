import types
from os import path
import re
import requests
import json

from .rest_client import RestClient
from ..server import __VERSION__


class RemoteObject(RestClient):
    def __init__(
        self,
        server_uri,
        remote_object_id,
        allowed_upload_extension_regex=r".*",
        jsonEncoder=json.JSONEncoder,
        jsonDecoder=json.JSONDecoder,
    ):
        self._confirm_server_version(server_uri)
        super().__init__(server_uri, jsonEncoder=jsonEncoder, jsonDecoder=jsonDecoder)
        self._allowed_extension_regex = allowed_upload_extension_regex
        self._remote_object_id = remote_object_id
        self.files_uploaded = {}

    @staticmethod
    def _confirm_server_version(server_uri, jsonDecoder=json.JSONDecoder):
        version_response = json.loads(requests.get(
            server_uri + "/remoteobjects/version",
        ).content, cls=jsonDecoder)["response"]
        if version_response != __VERSION__:
            raise RuntimeError(
                f"Server's version `{version_response}` != `{__VERSION__}`"
            )

    def _manage_CRUD_request(
        self, request_func, endpoint, data=None, params={}, files=None
    ):
        files_uploaded = {}
        # manage uploading data filepath values
        if data is not None and isinstance(data, dict):
            for data_arg, data_arg_val in data.items():
                if (
                    isinstance(data_arg_val, str)
                    and path.exists(data_arg_val)
                    and re.match(
                        self._allowed_extension_regex,
                        path.splitext(data_arg_val)[1].lower(),
                    )
                    is not None
                ):
                    files_uploaded[data_arg] = open(data_arg_val, "rb")

        if len(files_uploaded) > 0:
            upload_response = super()._manage_CRUD_request(
                requests.put, "remoteobjects/upload", files=files_uploaded
            )
            if upload_response.status_code != 200:
                raise RuntimeError(f"Failed to upload file arguments: {files_uploaded}")
            upload_response_json = json.loads(upload_response.content, cls=self.jsonDecoder)
            for data_arg, data_arg_filepath in upload_response_json["files_uploaded"].items():
                files_uploaded[data_arg].close()
                # update filepath arg_val to the server-local filepath returned
                data[data_arg] = data_arg_filepath

            self._delete_files_uploaded(
                [
                    file_key_dupe
                    for file_key_dupe in files_uploaded.keys()
                    if file_key_dupe in self.files_uploaded
                ]
            )
            self.files_uploaded.update(files_uploaded)

        fileless_response = super()._manage_CRUD_request(
            request_func, endpoint, data, params
        )

        if fileless_response.status_code != 200:
            resp_json = json(fileless_response, cls=self.jsonDecoder)
            if "logs" in resp_json:
                print(resp_json["logs"], end="")
            raise RuntimeError(resp_json["error"])
        return fileless_response

    def __del__(self):
        self._delete_files_uploaded()

    def _delete_files_uploaded(self, file_keys=None):
        if not hasattr(self, "files_uploaded"):
            return

        if file_keys is None:
            file_keys = list(self.files_uploaded.keys())

        if len(file_keys) > 0:
            upload_response = super()._delete(
                "remoteobjects/upload", data={"file_keys": file_keys}
            )
            if upload_response.status_code != 200:
                raise RuntimeError(
                    (
                        f"Failed to delete uploaded {file_keys}"
                    )
                )
            for file_key in file_keys:
                self.files_uploaded.pop(file_key)

    def _define_remote_function_loc(
        self,
        func_name: str,
        parameters: dict,
        remote_root_object_id: str,
        attribute_absolute_path: str = None,
        crud_operation: str = "post",
        crud_endpoint: str = ("remoteobjects/" "registry"),
    ):
        kwargs_param_present = False
        if len(parameters) > 0:
            last_param_key = list(parameters)[-1]
            kwargs_param_present = parameters[last_param_key]["code_string"].startswith(
                "**"
            )
        loc = [
            "def {}({}):".format(
                func_name,
                ",".join(
                    ["self"]
                    + [param_dict["code_string"] for param_dict in parameters.values()]
                ),
            ),
            "\targs = {",
            *[
                f"\t\t\t'{arg_name}': {arg_name},"
                for arg_name in parameters.keys()
                if arg_name != "self"
                and not (kwargs_param_present and arg_name == last_param_key)
            ],
            "\t}",
        ]
        if kwargs_param_present:
            loc.append(f"\targs.update({last_param_key})")

        loc += [
            f"\tresp = self._{crud_operation}(",
            f"\t\t'{crud_endpoint}',",
            "\t\tparams = {",
            f"\t\t\t'object_id': '{remote_root_object_id}',",
        ]
        if attribute_absolute_path is not None:
            loc.append(f"\t\t\t'attribute_path': '{attribute_absolute_path}',")
        loc += [
            f"\t\t\t'func_name': '{func_name}',",
            "\t\t},",
            "\t\tdata = args,",
            "\t)",
            "\tresp_json = json.loads(resp.content, cls=self.jsonDecoder)",
            "\tif 'logs' in resp_json and resp_json['logs'] is not None and len(resp_json['logs']) > 0:",
            "\t\tprint(resp_json['logs'], end='')",
            "\treturn resp_json['return']",
            "",
        ]
        return loc

    def _add_method_loc(self, func_name, func_loc):
        func_code = "\n".join(func_loc)
        local_env_dict = {}
        try:
            exec(func_code, None, local_env_dict)
        except BaseException as err:
            print(f"`{func_code}`")
            raise err
        setattr(self, func_name, types.MethodType(local_env_dict[func_name], self))

    def _get_attribute(self, attribute_absolute_path):
        params = {
            "object_id": self._remote_object_id,
        }
        if attribute_absolute_path is not None:
            params["attribute_path"] = attribute_absolute_path
        response = self._get("remoteobjects/registry", params=params)
        return json.loads(response.content, cls=self.jsonDecoder)["value"]

    def _set_attribute(self, attribute_absolute_path, value):
        if value.__class__.__module__ != "builtins":
            raise RuntimeError(
                f"Cannot set remote attribute `{attribute_absolute_path}` to"
                + f" non-primitive value {value} <{value.__class__}>."
            )
        params = {
            "object_id": self._remote_object_id,
        }
        if attribute_absolute_path is not None:
            params["attribute_path"] = attribute_absolute_path
        self._put("remoteobjects/registry", params=params, data={"value": value})

    def _add_property(self, attribute_absolute_path):
        setattr(
            self.__class__,
            attribute_absolute_path.split(".")[-1],
            property(
                fget=lambda self: self._get_attribute(attribute_absolute_path),
                fset=lambda self, value: self._set_attribute(
                    attribute_absolute_path, value
                ),
                fdel=None,
                doc=None,
            ),
        )

    def _get_remote_attribute(self, attribute_name):
        remote_attribute = getattr(self, "_" + attribute_name)
        if (
            hasattr(remote_attribute, "_initialised")
            and not remote_attribute._initialised
        ):
            remote_attribute._init_from_remote_signature()
        return remote_attribute

    def _add_remote_property(self, remote_attribute_name, remote_attribute):
        setattr(self, "_" + remote_attribute_name, remote_attribute)
        # the class might already have the property defined
        if not hasattr(self.__class__, remote_attribute_name):
            setattr(
                self.__class__,
                remote_attribute_name,
                property(
                    fget=lambda self: self._get_remote_attribute(
                        remote_attribute_name,
                    ),
                    fset=None,
                    fdel=None,
                    doc=None,
                ),
            )
