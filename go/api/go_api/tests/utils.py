from mock import Mock, patch

from vumi.tests.utils import MockHttpServer


class MockAuthServer(MockHttpServer):
    def __init__(self):
        self.responses = []
        self.requests = []
        super(MockAuthServer, self).__init__(self.handle_request)

    def handle_request(self, request):
        self.requests.append(request)
        response = self.responses.pop(0)
        for header, value in response['headers'].items():
            request.setHeader(header, value)
        request.setResponseCode(response['code'])
        return response['body']

    def add_response(self, code=200, body='', headers=None):
        self.responses.append({
            'code': code, 'body': body, 'headers': headers or {},
        })


class MockRpc(object):
    def __init__(self):
        self.response = self.set_response()
        self.request = None

        self.rpc_patcher = patch('go.api.go_api.client.rpc')
        self.mock_rpc = self.rpc_patcher.start()
        self.mock_rpc.side_effect = self.stubbed_rpc

    def tearDown(self):
        self.rpc_patcher.stop()

    def stubbed_rpc(self, session_id, method, params, id=None):
        self.request = {
            'session_id': session_id,
            'method': method,
            'params': params,
            'id': id,
        }

        return self.response

    @staticmethod
    def make_response_json_func(result={}, id=None, error=None):
        response_data = {
            'id': id,
            'jsonrpc': '2.0',
            'result': result,
        }
        if error is not None:
            response_data["error"] = error
        return (lambda: response_data)

    def set_response(self, result={}, id=None):
        response = Mock()
        response.status_code = 200
        response.json = self.make_response_json_func(result, id)
        self.response = response

    def set_rpc_error_response(self, error, id=None):
        response = Mock()
        response.status_code = 200
        response.json = self.make_response_json_func(
            result=None, id=id, error=error)
        self.response = response

    def set_error_response(self, code, text):
        response = Mock()
        response.status_code = code
        response.text = text
        self.response = response
