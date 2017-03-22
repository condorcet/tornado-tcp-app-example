from tornado.tcpserver import TCPServer
from tornado import gen
from tornado.iostream import StreamClosedError

from .exceptions import ServerException

class BaseServer(TCPServer):
    """
    Base server implements message handler logic from clients sources.
    Allowed messages must be children of `AbstractMessage` class and listed in `ALLOWED_MESSAGES` field.
    Base server handle messages using it `HEADERS` values.

    For allowed message will be invoked 'handler_<MessageClassName>(stream, address, header)`
    of server class, so you must define all handlers for all allowed messages.
    Signature of handler includes `stream` and `address` from `handle_stream` method of tornado TCPServer,
    and also `header` of incoming message.
    NOTE that header of message has already read, and stream contains message without it.

    To change handler prefix use `HANDLER_PREFIX` field of class.

    You could catch unhandled data by `default_handler`
    """

    # tuple of messages classes
    ALLOWED_MESSAGES = None

    # big-endian or little-endian byte order: `big` and `little` accordingly
    BYTE_ORDER = 'big'

    # prefix for handler methods
    HANDLER_PREFIX = 'handler_'

    @gen.coroutine
    def catch_message(self, header, stream, address):
        """
        This method "catches" incoming allowed message and invokes according handler of it.
        Uncaught messages could handled by `default_handler`.
        :param header: message header: int
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :return: future: tornado.concurrent.Future
        """
        if self.ALLOWED_MESSAGES:
            for message_class in self.ALLOWED_MESSAGES:
                if header in message_class.HEADERS:
                    handler_func_name = self._get_message_handler(message_class)
                    try:
                        yield getattr(self, handler_func_name)(stream, address, header)
                    except AttributeError:
                        raise ServerException('No handler for message "{}"'.format(message_class.__name__))
                    return
        yield self.handler_default(stream, address, header)

    @gen.coroutine
    def handle_stream(self, stream, address):
        """
        Tornado TCPServer handler. It used for implement handling logic.
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :return: future: tornado.concurrent.Future
        """
        try:
            yield self.handle(stream, address)
        except StreamClosedError:
            yield self.stream_closed_handler(stream, address)

    @gen.coroutine
    def handle(self, stream, address):
        """
        Get header of incoming message and invoke `catch_message`.
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :return: future: tornado.concurrent.Future
        """
        while True:
            byte_header = yield stream.read_bytes(1)
            header = int.from_bytes(byte_header, self.BYTE_ORDER)
            yield self.catch_message(header, stream, address)

    @gen.coroutine
    def stream_closed_handler(self, stream, address):
        """
        Handles lost connection.
        Override this method in child class.
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :return: None
        """
        pass

    @gen.coroutine
    def handler_default(self, stream, address, header):
        """
        Default handler invokes if no handler were found or `ALLOWED_MESSAGES` is not specified.
        Override this method in child class.
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :param header: message header: int
        :return: None
        """
        pass

    def _get_message_handler(self, message_class):
        return self.HANDLER_PREFIX + str(message_class.__name__)