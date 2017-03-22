from datetime import datetime

from base.message import SourceMessage
from base.exceptions import *


class AbstractSource:
    """
    Abstract source class.
    Child classes must implement `new_message` and `get_message` methods.
    `new_message` must generate message of source.
    `get_message` must received.
    This class represents state of source. On client you will use `new_message` to send message,
    on server - `get_message` for actualize state of client source and not
    intended for directly receive incoming messages from server.
    """

    def new_message(self):
        """
        Generate new message
        :return: message: AbstractMessage
        """
        raise SourceException('Method `new message` not implemented')

    def get_message(self, message):
        """
        Save incoming message for actualize state of source
        :param message: incoming message: AbstractMessage
        :return: None
        """
        raise SourceException('Method `get_message` not implemented')


class BaseSource(AbstractSource):
    """
    BaseSource implementing base source logic for application.
    It includes list of sent/received messages (depending of using context), current status of source,
    """

    # source message class (must be child of SourceMessage)
    MESSAGE_CLASS = None

    # default status for new source
    DEFAULT_STATUS = 0x00

    # dict of allowed statuses for source, key - integer value of status, value - string representation
    STATUS = {}

    # init value of status
    _status = None

    def __init__(self, source_id, status=None):
        self.source_id = source_id
        self.messages = []  # list of messages
        if not status:
            status = self.DEFAULT_STATUS
        self.status = status

    def new_message(self, data=None):
        """
        Generates new message from source state and message `data`.
        :param data: message data: dict
        :return: message: SourceMessage
        """
        message = self.MESSAGE_CLASS(len(self.messages), self.source_id, self.status, data=data)
        self.messages.append(message)
        return message

    def get_message(self, message):
        """
        Push message to list of incoming messages and updates source status.
        :param message:
        :return: None
        """
        self.status = message.status
        self.messages.append(message)

    @property
    def status(self):
        """
        Status getter
        :return: status: int
        """
        return self._status

    @status.setter
    def status(self, value):
        """
        Status setter. It must be in accepted `STATUS` dictionary else raise `SourceException`
        :param value:
        :return: None
        """
        if self.STATUS:
            if value not in self.STATUS:
                raise SourceException('status "{}" not allowed on "{}" source'.format(value, self.source_id))
        self._status = value

    @property
    def status_str(self):
        """
        String representation of status accordingly of `STATUS` dict.
        :return: status: str
        """
        if self.STATUS:
            status_str = self.STATUS[self._status]
        else:
            status_str = self._status
        return status_str

    @property
    def last_message(self):
        """
        Returns last source message
        :return: message
        """
        try:
            return self.messages[-1]
        except IndexError:
            return None



class Source(BaseSource):

    """
    Implementation of source for application.
    """

    MESSAGE_CLASS = SourceMessage

    # source statuses
    STATUS_IDLE = 0x01
    STATUS_ACTIVE = 0x02
    STATUS_RECHARGE = 0x03

    DEFAULT_STATUS = STATUS_IDLE

    SOURCE_NAME_LENGTH = 8

    STATUS = {
        STATUS_IDLE: 'IDLE',
        STATUS_ACTIVE: 'ACTIVE',
        STATUS_RECHARGE: 'RECHARGE'
    }

    def __init__(self, source_id, status=None):
        if len(source_id) > self.SOURCE_NAME_LENGTH:
            raise SourceException('length of source_id more than {}'.format(self.SOURCE_NAME_LENGTH))
        super().__init__(source_id, status)

    def __str__(self):
        """
        String representation of source.
        Returns string in format [<source_id>] | {num} | {status} | {time}
        where `num` - is number of last message, `status` - string status of source,
        `time` - count of milliseconds from last message
        :return:
        """
        last_message = self.last_message
        if last_message:
            milliseconds = str(int((datetime.now() - last_message.date_received).total_seconds()*1000))
        else:
            milliseconds = '-'
        return '[{}] {} | {} | {}'.format(self.source_id, last_message.num, self.status_str, milliseconds)
