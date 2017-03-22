from datetime import datetime
from functools import reduce

from tornado import gen

from base.exceptions import MessageException, InvalidMessageException, DecodeMessageError, EncodeMessageError


class AbstractMessage:
    """
    AbstractMessage class.
    Child classes must implementing `get_raw` method to convert message to bytes.
    Also for decoding define class method `decode` and `decode_stream`.
    Allowed message headers must be defined in `HEADERS`, default `DEFAULT_HEADER`
    To control big-endian/little-endian style use `BYTE_ORDER` as `big` and `little` accordingly.
    Default check sum method based on bitwise XOR. You could override `check_sum_method` for change it

    To encode message to bytes use `encode` method

    """

    # 'big' or 'little'
    BYTE_ORDER = 'big'

    # default message header (int)
    DEFAULT_HEADER = None

    # tuple of allowed headers (int)
    HEADERS = None

    def __init__(self):
        self.date_received = datetime.now()

    def check_sum_method(self, bytes_data):
        """
        Default check sum implementation.
        Override this method for your own implementation.
        :param bytes_data: bytes: bytes
        :return: check sum result: bytes
        """
        return xor_checksum(bytes_data)

    def check_sum(self, bytes_data=None):
        """
        Calc check sum of message or bytes_data.
        If you want use your own check sum implementation, override `check_sum_method` method
        :param bytes_data: custom bytes data :bytes
        :return: check sum :int
        """
        if not bytes_data:
            bytes_data = self.get_raw()
        return self.check_sum_method(bytes_data)

    def get_raw(self):
        """
        Return message as bytes without check sum
        Override this message in child class.
        :return: raw message :bytes
        """
        raise MessageException('`get_raw` method not implemented')

    def encode(self):
        """
        Convert message to byte.
        This method use get raw message (`get_raw`) and add check_sum at the end
        :return: byte :byte
        """
        raw_body = self.get_raw()
        check_sum = self.check_sum(raw_body)
        return raw_body + bytes((check_sum,))


    @classmethod
    def decode(cls, bytes_data):
        """
        Converts byte to message instance.
        Override this message in child class.
        :return: message :AbstractMessage
        """
        raise MessageException('`decode` method not implemented')

    @classmethod
    def decode_stream(cls, bytes_data, header):
        """
        Decodes tornado.iostream.IOStream to message.
        Override this method in child class.
        :param bytes_data: bytes: bytes
        :param header: message header: int
        :return: instance of message: AbstractMessage
        """
        raise MessageException('`decode_stream` method implemented')

def xor_checksum(bytes_data):
    """
    Helper check sum function
    :param bytes_data: bytes: bytes
    :return: xor results in one byte: bytes
    """
    return reduce(lambda x, y: x ^ y, bytes_data)


class SourceMessage(AbstractMessage):
    """
    Source message class implements interface of AbstractMessage.
    Static method `decode` converts bytes to message and return instance of `SourceMessage`.
    Static method `decode_stream` converts tornado.iostream.IOStream to message of `SourceMessage`.
    If you want to convert message into bytes use `encode` method of SourceMessage `instance`
    """
    STATUS_IDLE = 0x01
    STATUS_ACTIVE = 0x02
    STATUS_RECHARGE = 0x03

    STATUS = {
        STATUS_IDLE: 'IDLE',
        STATUS_ACTIVE: 'ACTIVE',
        STATUS_RECHARGE: 'RECHARGE'
    }  # accepted statuses

    DEFAULT_HEADER = 0x01

    HEADERS = (DEFAULT_HEADER, )

    def __init__(self, num, source_id, status, header=None, data=None):
        """
        Construct message
        :param num: number of message
        :param source_id: id of message source
        :param status: source status
        :param data: data sent by source
        """
        super().__init__()
        if not header:
            header = self.DEFAULT_HEADER
        if header not in self.HEADERS:
            raise InvalidMessageException('invalid message {} header {} of source {}'.format(num, header, source_id))
        self.header = header
        self.num = num
        self.source_id = source_id
        if status not in self.STATUS:
            raise InvalidMessageException('Unknown source {} status "{}"'.format(source_id, status))
        self.status = status
        self.data = data

    def get_raw(self):
        message_data = []
        message_data.append(self.header)  # header
        try:
            message_data += self.num.to_bytes(2, self.BYTE_ORDER)  # num
        except OverflowError:
            raise EncodeMessageError('"num" value too long')
        message_data += trim_bytes(self.source_id.encode(), 8)  # source id limit to 8 bytes
        try:
            message_data += self.status.to_bytes(1, self.BYTE_ORDER)  # status
        except:
            raise EncodeMessageError('"status" value too long')
        if self.data:
            message_data.append(len(self.data))  # numfields
            message_data += self._encode_data()  # data
        else:
            message_data.append(0x00)  # numfields = 0
        return bytes(message_data)

    @property
    def status_text(self):
        """
        String representation of status
        :return: status :str
        """
        return self.STATUS[self.status]

    @classmethod
    def decode(cls, bytes_data):
        """
        Decode bytes and return `SourceMessage` instance
        :param bytes_data :bytes
        :return: message: Message
        """
        header = int.from_bytes((bytes_data[0],), cls.BYTE_ORDER)
        check_sum = int.from_bytes((bytes_data[-1],), cls.BYTE_ORDER)
        data_body = bytes_data[1:-1]
        num = int.from_bytes(data_body[0:2], cls.BYTE_ORDER)
        source_id = data_body[2:10].decode().replace('\0', '')
        status = int.from_bytes((data_body[10], ), cls.BYTE_ORDER)
        num_fields = int.from_bytes((data_body[11], ), cls.BYTE_ORDER)
        if num_fields > 0:
            data = data_body[12:]
            try:
                data = cls._decode_data(data, num_fields)
            except DecodeMessageError as e:
                raise InvalidMessageException('Invalid message {} body from source {}'.format(num, source_id)) from e
        else:
            data = None
        message = SourceMessage(num, source_id, status, header, data)
        if message.check_sum() != check_sum:
            raise InvalidMessageException('Invalid message {} from source {}'.format(num, source_id))
        return message

    @classmethod
    @gen.coroutine
    def decode_stream(cls, stream, header):
        """
        Convert to message from tornado.iostream.IOStream
        :param stream:
        :param header: message header :int
        :return:
        """
        chunk_size = 12
        byte_data = b''
        byte_data += header.to_bytes(1, cls.BYTE_ORDER)  # header
        byte_data += yield stream.read_bytes(2)  # num
        byte_data += yield stream.read_bytes(8)  # source_id
        byte_data += yield stream.read_bytes(1)  # status
        num_fields = yield stream.read_bytes(1)  # numfields
        byte_data += num_fields
        num = int.from_bytes(num_fields, cls.BYTE_ORDER)
        if num > 0:
            byte_data += yield stream.read_bytes(num * chunk_size)  # data
        byte_data += yield stream.read_bytes(1)  # check_sum
        message = cls.decode(byte_data)
        return message

    @classmethod
    def _decode_data(cls, bytes_data, num_fields):
        """
        Decodes message data and return dict
        :param bytes_data data: bytes
        :param num_fields num fields :int
        :return: dict :dict
        """

        chunk_size = 12
        if len(bytes_data) != num_fields * chunk_size:
            raise DecodeMessageError('invalid message data')
        result = {}
        chunks = [bytes_data[i*chunk_size:(i+1)*chunk_size] for i in range(num_fields)]
        for chunk in chunks:
            field = chunk[:8]
            value = chunk[8:]
            result[field.decode().replace('\0', '')] = int.from_bytes(value, cls.BYTE_ORDER)
        return result

    def _encode_data(self):
        """
        Encodes data of message.
        Data fields will be ordered by name.
        :return:
        """
        data = []
        keys = sorted(self.data.keys())  # define order of chunks of data by field name
        for key in keys:
            try:
                data += trim_bytes(key.encode(), 8)
                data += self.data[key].to_bytes(4, self.BYTE_ORDER)
            except OverflowError:
                raise EncodeMessageError('value of "{}" key is too long'.format(key))
        return data

    def __str__(self):
        result = '[{}] '.format(self.source_id)
        if self.data:
            result += '\r\n'.join(['{} | {}'.format(k, v) for k, v in self.data.items()])
        return result+'\n'


class ServerMessage(AbstractMessage):
    """
    Server message class implements interface of AbstractMessage.
    Static method `decode` converts bytes to message and return instance of `ServerMessage`.
    Static method `decode_stream` converts tornado.iostream.IOStream to message of `ServerMessage`.
    """

    # message headers
    HEADER_SUCCESS = 0x11
    HEADER_ERROR = 0x12

    DEFAULT_HEADER = HEADER_SUCCESS

    HEADERS = (HEADER_SUCCESS, HEADER_ERROR)

    def __init__(self, num, header=None):
        if not header:
            header = self.DEFAULT_HEADER
        if header not in self.HEADERS:
            raise InvalidMessageException('invalid message {} header'.format(num))
        self.header = header
        if header == self.HEADER_ERROR:
            if num != 0x0000:
                raise InvalidMessageException('number message is not zero "{}" with header "{}"'.format(num, header))
        self.num = num

    def get_raw(self):
        message_data = []
        message_data.append(self.header)  # header
        try:
            message_data += self.num.to_bytes(2, self.BYTE_ORDER)  # num
        except OverflowError:
            raise EncodeMessageError('"num" value too long')
        return bytes(message_data)

    @classmethod
    def decode(cls, bytes_data):
        """
        Decode bytes and return `ServerMessage` instance
        :param bytes_data :bytes
        :return: message: Message
        """
        header = int.from_bytes((bytes_data[0],), cls.BYTE_ORDER)
        check_sum = int.from_bytes((bytes_data[-1],), cls.BYTE_ORDER)
        data_body = bytes_data[1:-1]
        num = int.from_bytes(data_body[0:2], cls.BYTE_ORDER)

        message = ServerMessage(num, header)
        if message.check_sum() != check_sum:
            raise InvalidMessageException('Invalid message {} from source {}'.format(num))
        return message

    @classmethod
    @gen.coroutine
    def decode_stream(cls, stream, header):
        """
        Decode message from tornado.iostream.IOStream
        Header of message must be specified
        :param stream: data :tornado.iostream.IOStream
        :param header: message header :int
        :return:
        """
        bytes_data = b''
        bytes_data += header.to_bytes(1, cls.BYTE_ORDER)  # header
        bytes_data += yield stream.read_bytes(2)  # num
        bytes_data += yield stream.read_bytes(1)  # checksum
        message = cls.decode(bytes_data)
        return message

    def __str__(self):
        if self.header == self.HEADER_SUCCESS:
            return 'ok {}'.format(self.num)
        else:
            return 'err'

def trim_bytes(bytes_data, num):
    """
    Helper method thar trim `bytes_data` to `num` bytes
    :param bytes_data: bytes: bytes
    :param num: count of bytes: int
    :return: bytes: bytes
    """
    data = bytes_data[:num]
    if len(data) < num:
        data = bytes((num - len(data))) + data  # add empty bytes if need
    return data
