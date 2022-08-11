def _ensure_default(code_string):
    if "=" not in code_string and not code_string.startswith("self"):
        return f"{code_string} = RequiredParameter()"
    return code_string


def _define_remote_constructor(
    init_signature: dict,
    server_uri: str,
    class_key: str,
    delete_remote_on_del: bool,
    allowed_upload_extension_regex: str,
    attribute_depth_allowance: int = 0,
):
    kwargs_param_present = False
    if len(init_signature) > 0:
        last_param_key = list(init_signature)[-1]
        kwargs_param_present = init_signature[last_param_key]["code_string"].startswith(
            "**"
        )

    if kwargs_param_present:
        init_signature.pop(last_param_key)

    definition_loc = [
        "\tdef __init__({},".format(
            ",".join(
                [
                    _ensure_default(param_dict["code_string"])
                    for param_dict in init_signature.values()
                ]
            )
        ),
        f"\t\tserver_uri = '{server_uri}',",
        "\t\tremote_object_id = None,",
        f"\t\tdelete_remote_on_del = {delete_remote_on_del},",
        (
            "\t\tallowed_upload_extension_regex = "
            f"r'{allowed_upload_extension_regex}',"
        ),
        "\t\tjsonEncoder = json.JSONEncoder,",
        "\t\tjsonDecoder = json.JSONDecoder,",
    ]

    if kwargs_param_present:
        definition_loc.append("\t\t**kwargs")

    definition_loc += [
        "\t):",
        "\t\tinit_args_dict = {",
        *[
            f"\t\t\t'{arg_name}': {arg_name},"
            for arg_name in init_signature.keys()
            if arg_name != "self"
        ],
        "\t\t}",
    ]

    if kwargs_param_present:
        definition_loc.append("\t\tinit_args_dict.update(kwargs)")

    definition_loc += [
        "\t\tsuper().__init__(",
        f"\t\t\t'{class_key}',",
        "\t\t\tserver_uri = server_uri,",
        "\t\t\tinit_args_dict = init_args_dict,",
        "\t\t\tremote_object_id = remote_object_id,",
        "\t\t\tdelete_remote_on_del = delete_remote_on_del,",
        "\t\t\tallowed_upload_extension_regex = allowed_upload_extension_regex,",
        "\t\t\tjsonEncoder = jsonEncoder,",
        "\t\t\tjsonDecoder = jsonDecoder",
        "\t\t)",
        "\t\tresponse = self._get(",
        "\t\t\t'remoteobjects/registry/signature',",
        "\t\t\tparams = {'object_id': self._remote_object_id},",
        "\t\t)",
        "",
        "\t\tresponse_json = json.loads(response.content, cls=jsonDecoder)",
        "\t\tfor (name, parameters) in response_json['methods'].items():",
        "\t\t\tif name != '__init__':",
        "\t\t\t\tself._add_method_loc(",
        "\t\t\t\t\tname,",
        "\t\t\t\t\tself._define_remote_function_loc(",
        "\t\t\t\t\t\tname,",
        "\t\t\t\t\t\tparameters, # name:code-string dict",
        "\t\t\t\t\t\tself._remote_object_id",
        "\t\t\t\t\t)",
        "\t\t\t\t)",
    ]
    if attribute_depth_allowance != 0:
        definition_loc += [
            "\t\tfor (name, _) in response_json['attributes'].items():",
            "\t\t\tself._add_property(name)",
            "\t\tancestor_obj = {response_json['object_str']: self}",
            (
                "\t\tfor (name, obj_str) in response_json["
                "'attributes_nonprimitive'].items():"
            ),
            "\t\t\tremote_attribute = RemoteAttribute(",
            "\t\t\t\tself._server_uri,",
            "\t\t\t\tself._remote_object_id,",
            "\t\t\t\tname,",
            "\t\t\t\tobj_str,",
            "\t\t\t\tancestor_obj,",
            "\t\t\t\tallowed_upload_extension_regex,",
            f"\t\t\t\t{attribute_depth_allowance-1},",
            "\t\t\tjsonEncoder = self.jsonEncoder,",
            "\t\t\tjsonDecoder = self.jsonDecoder,",
            "\t\t\t)",
            "\t\t\tself._add_remote_property(name, remote_attribute)",
            "",
        ]
    return definition_loc
