import types
from os import path
import re
import requests

from .rest_client import RestClient
from ..server import __VERSION__


class RemoteObject(RestClient):
    def __init__(self,
                 server_uri,
                 allowed_upload_extension_regex=r'.*',
                 ):
        self._confirm_server_version(server_uri)
        super().__init__(server_uri)
        self._allowed_extension_regex = allowed_upload_extension_regex

        self.files_uploaded = {}

    @staticmethod
    def _confirm_server_version(server_uri):
        version_response = requests.get(
            server_uri + '/remoteobjects/version',
        ).json()['response']
        if version_response != __VERSION__:
            raise RuntimeError(
                f'Server\'s version `{version_response}` != `{__VERSION__}`')

    def _manage_CRUD_request(
        self,
        request_func,
        endpoint,
        data=None,
        params={},
        files=None
    ):
        files_uploaded = {}
        # manage uploading data filepath values
        if data is not None and isinstance(data, dict):
            for data_arg, data_arg_val in data.items():
                if (isinstance(data_arg_val, str) and
                    path.exists(data_arg_val) and
                    re.match(
                        self._allowed_extension_regex,
                        path.splitext(data_arg_val)[1].lower()
                ) is not None
                ):
                    files_uploaded[data_arg] = open(data_arg_val, 'rb')

        if len(files_uploaded) > 0:
            upload_response = super()._manage_CRUD_request(
                requests.put, 'remoteobjects/upload', files=files_uploaded)
            if upload_response.status_code != 200:
                raise RuntimeError(
                    f'Failed to upload file arguments: {files_uploaded}')
            for data_arg, data_arg_filepath in upload_response.json()[
                'files_uploaded'
            ].items():
                files_uploaded[data_arg].close()
                # update filepath arg_val to the server-local filepath returned
                data[data_arg] = data_arg_filepath

            self._delete_files_uploaded(
                [file_key_dupe for file_key_dupe in files_uploaded.keys()
                    if file_key_dupe in self.files_uploaded
                 ]
            )
            self.files_uploaded.update(files_uploaded)

        fileless_response = super()._manage_CRUD_request(
            request_func, endpoint, data, params)

        if fileless_response.status_code != 200:
            raise RuntimeError(fileless_response.json())
        return fileless_response

    def __del__(self):
        self._delete_files_uploaded()

    def _delete_files_uploaded(self, file_keys=None):
        if file_keys is None:
            file_keys = list(self.files_uploaded.keys())

        if len(file_keys) > 0:
            upload_response = super()._delete(
                'remoteobjects/upload', data={'file_keys': file_keys})
            if upload_response.status_code != 200:
                raise RuntimeError(
                    (f'Failed to delete uploaded {file_keys}, '
                     '{upload_response.json()}'))
            for file_key in file_keys:
                self.files_uploaded.pop(file_key)

    def _define_remote_function_loc(self,
                                    func_name: str,
                                    parameters: dict,
                                    remote_root_object_id: str,
                                    attribute_absolute_path: str = None,
                                    crud_operation: str = 'post',
                                    crud_endpoint: str = ('remoteobjects/'
                                                          'registry'),
                                    ):
        last_param_key = list(parameters)[-1]
        kwargs_param_present = parameters[
            last_param_key]['code_string'].startswith('**')
        loc = [
            "def {}({}):".format(
                func_name,
                ','.join(['self'] + [
                    param_dict['code_string']
                    for param_dict in parameters.values()
                ])
            ),
            "\targs = {",
            *[
                f"\t\t\t'{arg_name}': {arg_name},"
                for arg_name in parameters.keys()
                if arg_name != 'self' and not (
                    kwargs_param_present and
                    arg_name == last_param_key
                )
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
            "\treturn resp.json()['return']",
            "",
        ]
        return loc

    def _add_method_loc(self, func_name, func_loc):
        func_code = '\n'.join(func_loc)
        local_env_dict = {}
        try:
            exec(func_code, None, local_env_dict)
        except BaseException as err:
            print(f"`{func_code}`")
            raise err
        setattr(self, func_name, types.MethodType(
            local_env_dict[func_name], self))

    def _get_attribute(self, remote_root_object_id, attribute_absolute_path):
        params = {
            'object_id': remote_root_object_id,
        }
        if attribute_absolute_path is not None:
            params['attribute_path'] = attribute_absolute_path
        response = self._get(
            'remoteobjects/registry',
            params=params
        )
        return response.json()['value']

    def _set_attribute(
        self,
        remote_root_object_id,
        attribute_absolute_path,
        value
    ):
        if value.__class__.__module__ != 'builtins':
            raise RuntimeError(
                f'Cannot set remote attribute `{attribute_absolute_path}` to' +
                f' non-primitive value {value} <{value.__class__}>.'
            )
        params = {
            'object_id': remote_root_object_id,
        }
        if attribute_absolute_path is not None:
            params['attribute_path'] = attribute_absolute_path
        self._put(
            'remoteobjects/registry',
            params=params,
            data={'value': value}
        )

    def _add_property(self, remote_root_object_id, attribute_absolute_path):
        setattr(
            self.__class__,
            attribute_absolute_path.split('.')[-1],
            property(
                fget=lambda self: self._get_attribute(
                    remote_root_object_id,
                    attribute_absolute_path
                ),
                fset=lambda self, value: self._set_attribute(
                    remote_root_object_id,
                    attribute_absolute_path,
                    value
                ),
                fdel=None,
                doc=None,
            )
        )
