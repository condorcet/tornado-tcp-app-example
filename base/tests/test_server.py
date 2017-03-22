import unittest

from time import time
import contextlib

from tornado import gen
from tornado import testing
from tornado.ioloop import IOLoop
from tornado.tcpclient import TCPClient
from tornado import stack_context

from base.server import BaseServer
from base.message import AbstractMessage
from base.exceptions import ServerException

class BaseServerTestCase(testing.AsyncTestCase):

    # simple server with only default handler
    @testing.gen_test
    def test_default_handler(self):

        # flag of passed test
        passed = False

        def pass_test():
            nonlocal passed
            passed = True

        class TestServer(BaseServer):
            @gen.coroutine
            def handler_default(self, stream, address, header):
                pass_test()

        server = TestServer(io_loop=self.io_loop)
        server.listen(8888)
        client = TCPClient(io_loop=self.io_loop)
        stream = yield client.connect('127.0.0.1', 8888)
        # send data
        yield stream.write(bytes([0x01, ]))
        # wait for handling message
        yield gen.sleep(0.1)
        server.stop()
        client.close()
        # check if test passed
        self.assertTrue(passed)

    @testing.gen_test
    def test_lost_connection(self):

        # flag of passed test
        passed = False

        def pass_test():
            nonlocal passed
            passed = True

        class TestServer(BaseServer):

            @gen.coroutine
            def stream_closed_handler(self, stream, address):
                pass_test()

        server = TestServer(io_loop=self.io_loop)
        server.listen(8888)
        client = TCPClient(io_loop=self.io_loop)
        stream = yield client.connect('127.0.0.1', 8888)
        # send data
        stream.close()
        # wait for handling message
        yield gen.sleep(0.1)
        server.stop()
        # check if test passed
        self.assertTrue(passed)

class BaseServerHandlingTestCase(testing.AsyncTestCase):

    #  test handling for only one type message
    @testing.gen_test
    def test_source_one_message_handling(self):

        passed = False

        message_body = bytes([0x01, 0x02])

        class MockMessage(AbstractMessage):
            HEADERS = (0xee, 0xff)
            DEFAULT_HEADER = 0xee

        class TestServer(BaseServer):
            ALLOWED_MESSAGES = (MockMessage,)
            @gen.coroutine
            def handler_MockMessage(self, stream, address, header):
                nonlocal passed, message_body
                body = yield stream.read_bytes(2)
                if body == message_body:
                    passed = True

        server = TestServer(io_loop=self.io_loop)
        server.listen(8888)
        client = TCPClient(io_loop=self.io_loop)
        stream = yield client.connect('127.0.0.1', 8888)
        stream.write(bytes([0xff, ]) + message_body)
        yield gen.sleep(0.5)
        server.stop()
        self.assertTrue(passed)


    #  handling two message same type
    @testing.gen_test
    def test_source_two_message_handling(self):

        passed1 = False
        passed2 = False

        message_body1 = bytes([0x01, 0x02])
        message_body2 = bytes([0xff, 0xab])

        class MockMessage(AbstractMessage):
            HEADERS = (0xee, 0xff)
            DEFAULT_HEADER = 0xee

        class TestServer(BaseServer):
            ALLOWED_MESSAGES = (MockMessage,)

            @gen.coroutine
            def handler_MockMessage(self, stream, address, header):
                nonlocal passed1, passed2, message_body1, message_body2
                body = yield stream.read_bytes(2)
                if body == message_body1:
                    passed1 = True
                if body == message_body2:
                    passed2 = True

        server = TestServer(io_loop=self.io_loop)
        server.listen(8888)
        client = TCPClient(io_loop=self.io_loop)
        stream = yield client.connect('127.0.0.1', 8888)
        stream.write(bytes([0xff, ]) + message_body1)
        stream.write(bytes([0xee, ]) + message_body2)
        yield gen.sleep(0.5)
        server.stop()
        self.assertTrue(passed1, 'uncaught first message')
        self.assertTrue(passed2, 'uncaught second message')

    #  handling two message different types
    @testing.gen_test
    def test_source_two_type_messages_handling(self):

        passed1 = False
        passed2 = False

        message_body1 = bytes([0x01, 0x02])
        message_body2 = bytes([0xff, 0xab])

        class MockMessage1(AbstractMessage):
            HEADERS = (0xee, 0xff)
            DEFAULT_HEADER = 0xee

        class MockMessage2(AbstractMessage):
            HEADERS = (0x01, 0x03)
            DEFAULT_HEADER = 0x01

        class TestServer(BaseServer):

            ALLOWED_MESSAGES = (MockMessage1, MockMessage2)

            @gen.coroutine
            def handler_MockMessage1(self, stream, address, header):
                nonlocal passed1, message_body1
                body = yield stream.read_bytes(2)
                if body == message_body1:
                    passed1 = True

            @gen.coroutine
            def handler_MockMessage2(self, stream, address, header):
                nonlocal passed2, message_body2
                body = yield stream.read_bytes(2)
                if body == message_body2:
                    passed2 = True

        server = TestServer(io_loop=self.io_loop)
        server.listen(8888)
        client = TCPClient(io_loop=self.io_loop)
        stream = yield client.connect('127.0.0.1', 8888)
        stream.write(bytes([0xff, ]) + message_body1)
        stream.write(bytes([0x03, ]) + message_body2)
        yield gen.sleep(0.5)
        server.stop()
        self.assertTrue(passed1, 'uncaught MockMessage1')
        self.assertTrue(passed2, 'uncaught MockMessage2')

    #  no handler for message (wait for exception)
    @testing.gen_test
    def test_no_message_handler(self):

        passed1 = False
        passed2 = False
        exception = False

        message_body1 = bytes([0x01, 0x02])
        message_body2 = bytes([0xff, 0xab])

        @contextlib.contextmanager
        def callback(type, value, traceback):
            nonlocal exception
            exception = True

        class MockMessage1(AbstractMessage):
            HEADERS = (0xee, 0xff)
            DEFAULT_HEADER = 0xee

        class MockMessage2(AbstractMessage):
            HEADERS = (0x01, 0x03)
            DEFAULT_HEADER = 0x01

        class TestServer(BaseServer):
            ALLOWED_MESSAGES = (MockMessage1, MockMessage2)

            @gen.coroutine
            def handler_MockMessage1(self, stream, address, header):
                nonlocal passed1, message_body1
                body = yield stream.read_bytes(2)
                if body == message_body1:
                    passed1 = True

                    # no handler for MockMessage2

        with stack_context.ExceptionStackContext(callback):
            server = TestServer(io_loop=self.io_loop)
            server.listen(8888)
            client = TCPClient(io_loop=self.io_loop)
            stream = yield client.connect('127.0.0.1', 8888)

            stream.write(bytes([0xff, ]) + message_body1)
            stream.write(bytes([0x03, ]) + message_body2)
            yield gen.sleep(0.5)
            server.stop()

        self.assertTrue(exception, 'exception not raised')

if __name__ == '__main__':
    unittest.main()
