from .remote_object import RemoteObject
from .rest_client import RestClient
from ..server import __VERSION__


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
    last_param_key = list(init_signature)[-1]
    kwargs_param_present = init_signature[last_param_key]['code_string'].startswith('**')
    if kwargs_param_present:
        init_signature.pop(last_param_key)

    definition_loc = [f"class {class_key}Remote(RemoteObject):"]
    definition_loc += [
        "\tdef __init__({},".format(
            ','.join([
                param_dict['code_string']
                    for param_dict in init_signature.values()
            ])
        ),
        f"\t\tremote_object_id = None,",
        f"\t\tdelete_remote_on_del = {delete_remote_on_del},",
        f"\t\tallowed_upload_extension_regex = r'{allowed_upload_extension_regex}',",
    ]
    if kwargs_param_present:
        definition_loc.append(f"\t\t**kwargs")
    definition_loc += [
        f"\t):",
        f"\t\tkwargs.update({{",
        *[
            f"\t\t\t\t'{arg_name}': {arg_name},"
            for arg_name in init_signature.keys()
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
        f"\t\tfor (name, parameters) in response.json()['methods'].items():",
        f"\t\t\tif name != '__init__':",
        f"\t\t\t\tself._add_method_loc(",
        f"\t\t\t\t\tname,",
        f"\t\t\t\t\tself._define_remote_function_loc(",
        f"\t\t\t\t\t\tname,",
        f"\t\t\t\t\t\tparameters, # name:code-string dict",
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
