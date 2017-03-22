from tornado import gen
from tornado.iostream import StreamClosedError

from base.exceptions import ListenerClosedException


class BaseListener:
    """
    Listener class for usage on server-side.
    """

    def __init__(self, stream):
        """
        Init source
        :param stream: tornado.iostream.IOStream
        """
        self.stream = stream

    @gen.coroutine
    def send(self, bytes_data):
        """
        Send bytes to listener.
        Raises `ListenerClosedException` when connection with listener lost
        :param bytes_data:
        :return: future: tornado.concurrent.Future
        """
        try:
            self.stream.write(bytes_data)
        except StreamClosedError as e:
            raise ListenerClosedException('Stream closed') from e
