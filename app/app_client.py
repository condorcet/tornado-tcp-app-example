from tornado import gen
from tornado.tcpclient import TCPClient

from base.message import ServerMessage
from base.exceptions import InvalidMessageException, EncodeMessageError


class ClientException(Exception):
    """Base client exception"""
    pass


class ApplicationClient:
    """
    Simple application client based on tornado.tcpclient.TCPClient
    To connect to server use `connect` method
    `stream` is opened by TCPClient IOStream object (available after `connect`)
    """
    def __init__(self):
        self.stream = None
        self.client = None

    @gen.coroutine
    def connect(self, host, port, io_loop=None):
        """
        Connect to server. Based on tornado.tcpclient.TCPClient `connect` method
        :param host: server host :str
        :param port: server port :int
        :param io_loop: io_loop :tornado.ioloop.IOLoop
        :return: opened stream :tornado.iostream.IOStream
        """
        if not self.client:
            self.client = TCPClient(io_loop=io_loop)
        if not self.stream:
            self.stream = yield self.client.connect(host, port)
        return self.stream

    @gen.coroutine
    def stop(self):
        """
        Stop client
        :return: None
        """
        if self.client:
            self.client.close()
        if self.stream:
            self.stream.close()

class ApplicationSourceClient(ApplicationClient):
    """
    Application client for sources.
    Use `send_message` to send message from source with additional data
    `listen` method get data from server and decode it to ServerMessage
    """
    def __init__(self, source):
        super().__init__()
        self.source = source

    @gen.coroutine
    def send_message(self, data):
        """
        Send message to server with additional data
        :param data: message data :dict
        :return: future :tornado.concurrent.Future
        """
        try:
            message = self.source.new_message(data).encode()
            yield self.stream.write(message)
        except EncodeMessageError as e:
            raise ClientException(e.args[0]) from e


    @gen.coroutine
    def listen(self):
        """
        Listen server for response
        :return: future with message :tornado.concurrent.Future
        """
        header = yield self.stream.read_bytes(1)
        header = int.from_bytes(header, ServerMessage.BYTE_ORDER)
        if header in ServerMessage.HEADERS:
            try:
                message = yield ServerMessage.decode_stream(self.stream, header)
                return message
            except InvalidMessageException:
                print('invalid message')


class ApplicationListenerClient(ApplicationClient):
    """
    Application client for listeners
    """
    @gen.coroutine
    def listen(self):
        """
        Listen text messages from server
        :return: future with text message :tornado.concurrent.Future
        """
        data = yield self.stream.read_until(b'\n')
        return data