def _define_remote_constructor(
        init_signature: dict,
        server_uri: str,
        class_key: str,
        delete_remote_on_del: bool,
        allowed_upload_extension_regex: str
):
    last_param_key = list(init_signature)[-1]
    kwargs_param_present = init_signature[last_param_key][
        'code_string'].startswith('**')
    if kwargs_param_present:
        init_signature.pop(last_param_key)

    definition_loc = [
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
    return definition_loc
