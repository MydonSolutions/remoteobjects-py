import types
from os import path
import re
import requests

from .rest_client import RestClient
from ..server import __VERSION__


class RemoteObject(RestClient):
    def __init__(self,
                 server_uri,
                 class_key,
                 init_args_dict={},
                 delete_remote_on_del=True,
                 remote_object_id=None,
                 allowed_upload_extension_regex=r'.*',
                 ):
        self._confirm_server_version(server_uri)
        super().__init__(server_uri)
        self._allowed_extension_regex = allowed_upload_extension_regex

        params = {
            'class_key': class_key,
        }
        if remote_object_id is not None:
            params['object_id'] = remote_object_id

        self.files_uploaded = {}

        registration_response = self._get(
            'remoteobjects/registry',
            params=params,
            data=init_args_dict
        )
        if registration_response.status_code != 200:
            raise RuntimeError(registration_response.json())
        self._remote_object_id = registration_response.json()['id']
        self._del_remote = delete_remote_on_del

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
        if 'object_id' not in params and hasattr(self, '_remote_object_id'):
            params['object_id'] = self._remote_object_id

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
        if self._del_remote:
            self._delete(
                'remoteobjects/registry',
                params={
                    'object_id': self._remote_object_id
                }
            )

    def _delete_files_uploaded(self, file_keys=None):
        if file_keys is None:
            file_keys = list(self.files_uploaded.keys())

        if len(file_keys) > 0:
            upload_response = super()._delete(
                'upload', data={'file_keys': file_keys})
            if upload_response.status_code != 200:
                raise RuntimeError(
                    (f'Failed to delete uploaded {file_keys}, '
                      '{upload_response.json()}'))

    def _set_id(self, new_id):
        response = self._patch(
            'remoteobjects/registry',
            params={
                'old_id': self._remote_object_id,
                'new_id': new_id,
            }
        )
        if response.status_code != 200:
            raise RuntimeError(response.json())
        self._remote_object_id = response.json()['id']

    def _define_remote_function_loc(self,
                                    func_name,
                                    req_args,
                                    opt_args,
                                    crud_operation='post',
                                    crud_endpoint='remoteobjects/registry',
                                    ):
        return [
            "def {}({}{}{}, **kwargs):".format(
                func_name,
                ', '.join(req_args),
                ', ' if len(opt_args) > 0 else '',
                ', '.join(f"{argname}={default}" for (
                    argname, default) in opt_args.items()),
            ),
            f"\tkwargs.update({{",
            *[
                f"\t\t\t'{arg_name}': {arg_name},"
                for arg_name in req_args + list(opt_args.keys())
                if arg_name != 'self'
            ],
            f"\t\t}}",
            f"\t)",
            f"\tresp = self._{crud_operation}(",
            f"\t\t'{crud_endpoint}',",
            f"\t\tparams = {{",
            f"\t\t\t'object_id': self._remote_object_id,",
            f"\t\t\t'func_name': '{func_name}',",
            f"\t\t}},",
            f"\t\tdata = kwargs,",
            f"\t)",
            f"\t",
            # f"\tif resp.status_code != 200:",
            # f"\t\traise RuntimeError(resp.json())",
            f"\treturn resp.json()['return']",
            f"",
        ]

    def _add_method_loc(self, func_name, func_loc):
        func_code = '\n'.join(func_loc)
        local_env_dict = {}
        exec(func_code, None, local_env_dict)
        setattr(self, func_name, types.MethodType(
            local_env_dict[func_name], self))


def defineRemoteClass(
    class_key,
    server_uri,
    globals_dict,
    delete_remote_on_del=True,
    allowed_upload_extension_regex=r'.*'
):
    RemoteObject._confirm_server_version(server_uri)
    r = RestClient(server_uri)
    init_signature_response = r._get(
        'remoteobjects/registry/signature',
        params={'class_key': class_key}
    )
    if init_signature_response.status_code != 200:
        raise RuntimeError(init_signature_response.json())
    init_signature = init_signature_response.json()['methods']['__init__']
    init_req_args, init_opt_args = init_signature[0], init_signature[1]

    definition_loc = [f"class {class_key}Remote(RemoteObject):"]
    definition_loc += [
        "\tdef __init__("
        "{}{}{},".format(
            ', '.join(init_req_args),
            ', ' if len(init_opt_args) > 0 else '',
            ', '.join(f'{name}={default}' for name,
                      default in init_opt_args.items()),
        ),
        f"\t\tremote_object_id = None,",
        f"\t\tdelete_remote_on_del = {delete_remote_on_del},",
        f"\t\tallowed_upload_extension_regex = r'{allowed_upload_extension_regex}',",
        f"\t\t**kwargs",
        f"\t):",
        f"\t\tkwargs.update({{",
        *[
            f"\t\t\t\t'{arg_name}': {arg_name},"
            for arg_name in init_req_args + list(init_opt_args.keys())
            if arg_name != 'self'
        ],
        f"\t\t\t}}",
        f"\t\t)",
        f"\t\tsuper().__init__(",
        f"\t\t\t'{server_uri}',",
        f"\t\t\t'{class_key}',",
        f"\t\t\tinit_args_dict = kwargs,",
        f"\t\t\tremote_object_id = remote_object_id,",
        f"\t\t\tdelete_remote_on_del = delete_remote_on_del,",
        f"\t\t\tallowed_upload_extension_regex = allowed_upload_extension_regex,",
        f"\t\t)",
        # f"\t\tprint(f'`{class_key}Remote`.__init__({{kwargs}})')",
        f"\t\tresponse = self._get(",
        f"\t\t\t'remoteobjects/registry/signature',",
        f"\t\t\tparams = {{'object_id': self._remote_object_id}},",
        f"\t\t)",
        # f"\t\tif response.status_code != 200:",
        # f"\t\t\traise RuntimeError(response.json())",
        f"",
        f"\t\tfor (name, signature) in response.json()['methods'].items():",
        f"\t\t\tif name != '__init__':",
        f"\t\t\t\tself._add_method_loc(",
        f"\t\t\t\t\tname,",
        f"\t\t\t\t\tself._define_remote_function_loc(",
        f"\t\t\t\t\t\tname,",
        f"\t\t\t\t\t\tsignature[0], #required argument names",
        f"\t\t\t\t\t\tsignature[1], #defaulted argument name:value dict",
        f"\t\t\t\t\t)",
        f"\t\t\t\t)",
        f"",
    ]
    definition_code = '\n'.join([''] + definition_loc)
    local_env_dict = {}
    try:
        exec(definition_code, None, local_env_dict)
    except BaseException as err:
        print(f'`{definition_code}`')
        raise err
    globals_dict[f"{class_key}Remote"] = local_env_dict[f"{class_key}Remote"]


def defineRemoteClasses(
    server_uri,
    globals_dict,
    delete_remote_on_del=True,
    allowed_upload_extension_regex=r'.*'
):
    r = RestClient(server_uri, __VERSION__)
    class_keys_response = r._get(
        'remoteobjects/registry'
    )
    if class_keys_response.status_code != 200:
        raise RuntimeError(class_keys_response.json())
    for class_key in class_keys_response.json()['class_keys']:
        print(f'Defining {class_key}Remote...')
        defineRemoteClass(
            class_key,
            server_uri,
            globals_dict,
            delete_remote_on_del,
            allowed_upload_extension_regex
        )
