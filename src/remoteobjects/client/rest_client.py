import requests
import json


class RestClient(object):
    def __init__(self, server_uri):
        self._server_uri = server_uri

    @staticmethod
    def _content_type(data):  # returns converted data, {"Content-Type": }
        if isinstance(data, dict):
            return json.dumps(data), {"Content-Type": "application/json"}
        bytes_data = bytes(data) if not isinstance(data, bytes) else data
        bytes_data_len = len(bytes_data)
        return bytes_data, {
            "Content-Type": "application/octet-stream",
            "Content-Length": str(bytes_data_len),
        }

    def _manage_CRUD_request(
        self, request_func, endpoint, data=None, params={}, files=None
    ):
        uri = self._server_uri + "/" + endpoint

        if data is None and files is None:
            response = request_func(url=uri, params=params)
        elif data is not None and (files is None or len(files) == 0):
            reqdata, header = self._content_type(data)
            response = request_func(
                url=uri, params=params, data=reqdata, headers=header
            )
        else:  # data and files
            response = request_func(url=uri, params=params, data=data, files=files)
        return response

    def _delete(self, endpoint, data=None, params={}):
        return self._manage_CRUD_request(requests.delete, endpoint, data, params)

    def _get(self, endpoint, data=None, params={}):
        return self._manage_CRUD_request(requests.get, endpoint, data, params)

    def _patch(self, endpoint, data=None, params={}, files=None):
        return self._manage_CRUD_request(requests.patch, endpoint, data, params, files)

    def _post(self, endpoint, data=None, params={}, files=None):
        return self._manage_CRUD_request(requests.post, endpoint, data, params, files)

    def _put(self, endpoint, data=None, params={}, files=None):
        return self._manage_CRUD_request(requests.put, endpoint, data, params, files)
