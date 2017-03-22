from base.listener import BaseListener
from base.server import BaseServer
from tornado import gen

from base.message import SourceMessage, ServerMessage
from base.exceptions import ListenerClosedException, InvalidMessageException, SourceException
from base.source import Source


class ApplicationServer(BaseServer):
    """
    This server add listeners to BaseServer.
    Specify SOURCE_PORT and LISTENER_PORT for working with sources and listeners accordingly.
    ALLOWED MESSAGES contains tuple of messages classes sending from sources.
    """

    # dict of sources: key - source id, value - Source instance
    sources = {}

    # dict of listeners: key - connection stream address, value - Listener instance
    listeners = {}

    SOURCE_PORT = 8888

    LISTENER_PORT = 8889

    ALLOWED_MESSAGES = (SourceMessage, )

    @gen.coroutine
    def handle(self, stream, address):
        """
        This method overrides `handle` class and added routing of streams by port.
        If used source port then default handler logic (see BaseServer).
        If used listener port - invoking `handle_listener`
        :param stream: stream :tornado.iostream.IOStream
        :param address: address :
        :return: future :tornado.concurrent.Future
        """
        port = stream.socket.getsockname()[1]
        # if source
        if port == self.SOURCE_PORT:
            yield super().handle(stream, address)
        elif port == self.LISTENER_PORT:
            yield self.handle_listener(stream, address)

    @gen.coroutine
    def handle_listener(self, stream, address):
        """
        Handles listeners connections to server and save it for later broadcasting.
        :param stream :stream :tornado.iostream.IOStream
        :param address :address
        :return: future :tornado.concurrent.Future
        """
        listener = BaseListener(stream)
        self.listeners[address] = listener
        # send sources info
        last_messages = '\n'.join([str(source) for source in self.sources.values()])
        if not last_messages:
            last_messages = 'No sources yet'
        last_messages += '\n'
        try:
            yield listener.send(last_messages.encode())
        except ListenerClosedException:
            self.listeners.pop(address)

    @gen.coroutine
    def handler_SourceMessage(self, stream, address, header):
        """
        Handler of SourceMessage instances
        :param stream: stream: tornado.iostream.IOStream
        :param address: address
        :param header: header of message: int
        :return: future: tornado.concurrent.Future
        """
        try:
            message = yield SourceMessage.decode_stream(stream, header)

            source_id = message.source_id
            status = message.status

            # TODO: add handshake (now source with same name could send wrong messages)

            # create source instance and add it to _sources if not exists
            source = self.sources.get(source_id)
            if not source:
                source = Source(source_id, status)
                self.sources[source_id] = source

            # push message to source
            source.get_message(message)

            # send response to source
            ok_message = ServerMessage(message.num, ServerMessage.HEADER_SUCCESS)
            yield stream.write(ok_message.encode())

            # notify listeners
            yield self.broadcast_message(message)

        # invalid message or processing error
        except (InvalidMessageException, SourceException):
            print('exception')
            error_message = ServerMessage(0, ServerMessage.HEADER_ERROR)
            yield stream.write(error_message.encode())

    @gen.coroutine
    def stream_closed_handler(self, stream, address):
        """
        Stream closed handler
        :param stream: stream: tornado.iostream.IOStream
        :param address: connection address
        :return: None
        """
        # TODO: removing of disconnected sources
        pass

    @gen.coroutine
    def broadcast_message(self, message):
        """
        Broadcast message to all connected listeners
        :param message: message: AbstractMessage
        :return: future: tornado.concurrent.Future
        """
        if self.listeners:
            for listener_id, listener in self.listeners.items():
                try:
                    yield listener.send(str(message).encode())
                except ListenerClosedException:
                    # Remove listener if it no more exist
                    self.listeners.pop(listener_id)
