from .remote_attribute import RemoteAttribute
from .remote_instance import RemoteInstance, RequiredParameter
from .remote_object import RemoteObject
from .rest_client import RestClient
from ..server import __VERSION__
from .define_remote_object_loc import _define_remote_constructor

import json


def defineRemoteClass(
    class_key,
    server_uri,
    globals_dict,
    delete_remote_on_del=True,
    allowed_upload_extension_regex=r".*",
    attribute_depth_allowance=0,
):
    RemoteObject._confirm_server_version(server_uri)
    r = RestClient(server_uri)
    init_signature_response = r._get(
        "remoteobjects/registry/signature", params={"class_key": class_key}
    )
    if init_signature_response.status_code != 200:
        raise RuntimeError(init_signature_response.json())
    init_signature = init_signature_response.json()["methods"]["__init__"]

    definition_loc = ["", f"class {class_key}Remote(RemoteInstance):"]
    definition_loc += _define_remote_constructor(
        init_signature,
        server_uri,
        class_key,
        delete_remote_on_del,
        allowed_upload_extension_regex,
        attribute_depth_allowance,
    )

    definition_code = "\n".join(definition_loc)
    local_env_dict = {}
    try:
        exec(definition_code, None, local_env_dict)
    except BaseException as err:
        print(f"`{definition_code}`")
        raise err
    globals_dict[f"{class_key}Remote"] = local_env_dict[f"{class_key}Remote"]


def defineRemoteClasses(
    server_uri,
    globals_dict,
    delete_remote_on_del=True,
    allowed_upload_extension_regex=r".*",
    attribute_depth_allowance=0,
):
    RemoteObject._confirm_server_version(server_uri)
    r = RestClient(server_uri)
    class_keys_response = r._get("remoteobjects/registry")
    if class_keys_response.status_code != 200:
        raise RuntimeError(class_keys_response.json())
    for class_key in class_keys_response.json()["class_keys"]:
        print(f"Defining {class_key}Remote...")
        defineRemoteClass(
            class_key,
            server_uri,
            globals_dict,
            delete_remote_on_del,
            allowed_upload_extension_regex,
            attribute_depth_allowance,
        )
