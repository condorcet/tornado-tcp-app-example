import unittest

from tornado import gen
from tornado import testing
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient
from tornado.tcpserver import TCPServer

from base.message import SourceMessage, ServerMessage, InvalidMessageException, EncodeMessageError


class TestMessage(unittest.TestCase):

    bytes_data0 = [
        0x01,  # header
        0x00, 0x01,  # num
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63,  # ascii id
        0x01,  # status
        0x00,  # numfields (no data)
        0x61,  # checksum
    ]

    bytes_data1 = [
        0x01,  # header
        0x00, 0x01,  # num
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63,  # ascii id
        0x01,  # status
        0x01,  # numfields
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63, 0x00, 0x01, 0x02, 0x03,  # chunk of data
        0x0,  # checksum
    ]

    bytes_data2 = [
        0x01,  # header
        0x00, 0x01,  # num
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63,  # ascii id
        0x01,  # status
        0x02,  # numfields
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63, 0x00, 0x01, 0x02, 0x03,  # first chunk of data
        0x00, 0x00, 0x00, 0x00, 0x00, 0x64, 0x65, 0x66, 0x00, 0x03, 0x02, 0x01,  # second chunk of data
        0x64,  # checksum
    ]

    server_message1 = [
        0x11,  # header
        0x00, 0x01,  # num
        0x10,  # check_sum
    ]

    server_message2 = [
        0x12,  # header
        0x00, 0x00,  # num
        0x12,  # check_sum
    ]
    # fail
    server_message3 = [
        0x12,  # header
        0x00, 0x01,  # num
        0x12,  # check_sum
    ]


    def test_source_message_not_accept_wrong_status(self):
        with self.assertRaises(InvalidMessageException):
            message = SourceMessage(1, '1', 0, 0x01)  # status_id = 0 not allowed

    def test_source_message_encoded_with_zero_data(self):
        original_bytes = self.bytes_data0
        # encode
        message = SourceMessage(1, 'abc', 1, 0x01, None)
        message_bytes = message.encode()
        self.assertEqual(bytes(original_bytes), message_bytes)

        # decode from raw data
        message1 = SourceMessage.decode(bytes(original_bytes))
        self.assertEqual(message1.num, 1)
        self.assertEqual(message1.source_id, 'abc')
        self.assertEqual(message1.status, 1)
        self.assertIsNone(message1.data)
        self.assertEqual(message1.check_sum(), 0x61)

    def test_source_message_encoded_with_one_field_data(self):
        original_bytes = self.bytes_data1

        # encode
        message = SourceMessage(1, 'abc', 1, 0x01, {'abc': 0x010203})
        message_bytes = message.encode()
        self.assertEqual(bytes(original_bytes), message_bytes)

        # decode from raw data
        message1 = SourceMessage.decode(bytes(original_bytes))
        self.assertEqual(message1.num, 1)
        self.assertEqual(message1.source_id, 'abc')
        self.assertEqual(message1.status, 1)
        self.assertEqual(len(message1.data), 1)
        self.assertEqual(message1.data['abc'], 0x010203)
        self.assertEqual(message1.check_sum(), 0x0)

    def test_source_message_encoded_with_two_fields_data(self):

        original_bytes = self.bytes_data2

        # encode message
        message = SourceMessage(1, 'abc', 1, 0x01, {'abc': 0x010203, 'def': 0x030201})
        message_bytes = message.encode()
        self.assertEqual(bytes(original_bytes), message_bytes)

        # decode from raw data
        message1 = SourceMessage.decode(bytes(original_bytes))
        self.assertEqual(message1.num, 1)
        self.assertEqual(message1.source_id, 'abc')
        self.assertEqual(message1.status, 1)
        self.assertEqual(len(message1.data), 2)
        self.assertEqual(message1.data['abc'], 0x010203)
        self.assertEqual(message1.data['def'], 0x030201)
        self.assertEqual(message1.check_sum(), 0x64)

    def test_source_message_too_long_data_values(self):

        message_data = {
            'a': 11111111111111111111111111111111111
        }
        message = SourceMessage(1, 'abc', SourceMessage.STATUS_IDLE, data=message_data)
        with self.assertRaises(EncodeMessageError):
            message.encode()

    def test_server_message_success(self):
        original_bytes = self.server_message1

        # encode message
        message = ServerMessage(0x0001, 0x11)
        message_bytes = message.encode()
        self.assertEqual(bytes(original_bytes), message_bytes)

    def test_server_message_success2(self):
        message = ServerMessage(0x0000, 0x12)
        message_bytes = message.encode()
        self.assertEqual(bytes(self.server_message2), message_bytes)

    def test_server_message_fail1(self):
        with self.assertRaises(InvalidMessageException):
            ServerMessage.decode(self.server_message3)



class TestMessageAsync(testing.AsyncTestCase):

    # ok source message
    bytes_data2 = [
        0x01,  # header
        0x00, 0x01,  # num
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63,  # ascii id
        0x01,  # status
        0x02,  # numfields
        0x00, 0x00, 0x00, 0x00, 0x00, 0x61, 0x62, 0x63, 0x00, 0x01, 0x02, 0x03,  # first chunk of data
        0x00, 0x00, 0x00, 0x00, 0x00, 0x64, 0x65, 0x66, 0x00, 0x03, 0x02, 0x01,  # second chunk of data
        0x64,  # checksum
    ]

    # ok server message
    server_message1 = [
        0x11,  # header
        0x00, 0x01,  # num
        0x10,  # check_sum
    ]

    # ok server message
    server_message2 = [
        0x12,  # header
        0x00, 0x00,  # num
        0x12,  # check_sum
    ]

    # wrong server message
    server_message3 = [
        0x12,  # header
        0x00, 0x01,  # num
        0x12,  # check_sum
    ]

    @testing.gen_test
    def test_message_decode_from_stream(self):

        this = self

        class SimpleServer(TCPServer):

            @gen.coroutine
            def handle_stream(self, stream, address):
                try:
                    yield stream.write(bytes(this.bytes_data2))
                except StreamClosedError:
                    pass

        server = SimpleServer(io_loop=self.io_loop)
        server.listen(8888)

        stream = yield TCPClient(io_loop=self.io_loop).connect('localhost', 8888)
        header = yield stream.read_bytes(1)
        header = int.from_bytes(header, byteorder=SourceMessage.BYTE_ORDER)
        message = yield SourceMessage.decode_stream(stream, header=header)
        self.assertEqual(message.source_id, 'abc')
        self.assertEqual(message.data['def'], 0x00030201)
        self.assertEqual(message.data['abc'], 0x00010203)
        server.stop()

    @testing.gen_test
    def test_server_message_decode_from_stream(self):
        this = self

        class SimpleServer(TCPServer):

            @gen.coroutine
            def handle_stream(self, stream, address):
                try:
                    yield stream.write(bytes(this.server_message1))
                except StreamClosedError:
                    pass

        server = SimpleServer(io_loop=self.io_loop)
        server.listen(8888)

        stream = yield TCPClient(io_loop=self.io_loop).connect('localhost', 8888)
        header = yield stream.read_bytes(1)
        header = int.from_bytes(header, byteorder=ServerMessage.BYTE_ORDER)
        message = yield ServerMessage.decode_stream(stream, header=header)
        self.assertEqual(message.header, 0x11)
        self.assertEqual(message.num, 0x0001)
        server.stop()

    @testing.gen_test
    def test_server_message_decode_error_from_stream(self):
        this = self

        class SimpleServer(TCPServer):

            @gen.coroutine
            def handle_stream(self, stream, address):
                try:
                    yield stream.write(bytes(this.server_message3))
                except StreamClosedError:
                    pass

        server = SimpleServer(io_loop=self.io_loop)
        server.listen(8888)

        stream = yield TCPClient(io_loop=self.io_loop).connect('localhost', 8888)
        header = yield stream.read_bytes(1)
        header = int.from_bytes(header, byteorder=ServerMessage.BYTE_ORDER)
        with self.assertRaises(InvalidMessageException):
            message = yield ServerMessage.decode_stream(stream, header=header)
        server.stop()

if __name__ == '__main__':
    unittest.main()
