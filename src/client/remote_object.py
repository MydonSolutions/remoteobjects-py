import types

from .rest_client import RestClient
from ..server import __VERSION__

class RemoteObject(RestClient):
    def __init__(self,
        server_uri,
        class_key,
        init_args_dict={},
        delete_remote_on_del = True,
        remote_object_id = None,
    ):
        super().__init__(server_uri, __VERSION__)

        params = {
            'class_key': class_key,
        }
        if remote_object_id is not None:
            params['object_id'] = remote_object_id

        registration_response = self._get(
            'registry',
            params = params,
            data = init_args_dict
        )
        if registration_response.status_code != 200:
            raise RuntimeError(registration_response.json())
        self._remote_object_id = registration_response.json()['id']
        self._del_remote = delete_remote_on_del

    def _manage_CRUD_request(self, request_func, endpoint, data = None, params = {}, files = None):
        if 'object_id' not in params and hasattr(self, '_remote_object_id'):
            params['object_id'] = self._remote_object_id
        return super()._manage_CRUD_request(request_func, endpoint, data, params, files)

    def __del__(self):
        if self._del_remote:
            self._delete(
                'registry',
                params = {
                    'object_id': self._remote_object_id
                }
            )

    def _set_id(self, new_id):
        response = self._patch(
            'registry',
            params = {
                'old_id': self._remote_object_id,
                'new_id': new_id,
            }
        )
        if response.status_code != 200:
            raise RuntimeError(registration_response.json())
        self._remote_object_id = registration_response.json()['id']

    def _define_remote_function_loc(self,
        func_name,
        req_args,
        opt_args,
        crud_operation='post',
        crud_endpoint='registry',
    ):
        return [
            "def {}({}{}{}, **kwargs):".format(
                func_name,
                ', '.join(req_args),
                ', ' if len(opt_args) > 0 else '',
                ', '.join(f"{argname}={default}" for (argname, default) in opt_args.items()),
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
        setattr(self, func_name, types.MethodType(local_env_dict[func_name], self))

def defineRemoteClass(
    class_key,
    server_uri,
    globals_dict,
    delete_remote_on_del = True
):
    r = RestClient(server_uri, __VERSION__)
    init_signature_response = r._get(
        'registry/signature',
        params= {'class_key': class_key}
    )
    if init_signature_response.status_code != 200:
        raise RuntimeError(init_signature_response.json())
    init_signature = init_signature_response.json()['methods']['__init__']
    init_req_args, init_opt_args = init_signature[0], init_signature[1]

    definition_loc =  [f"class {class_key}Remote(RemoteObject):"]
    definition_loc += [
        "\tdef __init__("
        "\t\t{}{}{},".format(
            ', '.join(init_req_args),
            ', ' if len(init_opt_args) > 0 else '',
            ', '.join(f'{name}:{default}' for name, default in init_opt_args.items()),
        ),
        f"\t\tremote_object_id = None,",
        f"\t\tdelete_remote_on_del = {delete_remote_on_del},",
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
        f"\t\t)",
        # f"\t\tprint(f'`{class_key}Remote`.__init__({{kwargs}})')",
        f"\t\tresponse = self._get(",
        f"\t\t\t'registry/signature',",
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
