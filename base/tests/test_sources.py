import unittest

from base.message import SourceMessage
from base.exceptions import SourceException
from base.source import Source

class SourceTestCase(unittest.TestCase):

    def test_source_incorrect_status(self):
        source = Source('abc')
        with self.assertRaises(SourceException):
            source.status = 0x22

    def test_too_length_source_name(self):
        with self.assertRaises(SourceException):
            source = Source('abcdefghijklmnop')


class SourceGetMessageTestCase(unittest.TestCase):

    def test_source_last_message(self):
        source = Source('abc')
        message1 = SourceMessage(1, source.source_id, Source.STATUS_IDLE)
        message2 = SourceMessage(2, source.source_id, Source.STATUS_RECHARGE)
        source.get_message(message1)
        source.get_message(message2)
        self.assertEqual(source.last_message, message2)

    def test_source_status_updated(self):
        source = Source('abc')
        old_status = source.status
        message = SourceMessage(1, 'abc', Source.STATUS_ACTIVE)
        source.get_message(message)
        new_status = source.status
        self.assertNotEqual(old_status, new_status)
        self.assertEqual(new_status, Source.STATUS_ACTIVE)

    def test_source_incorrect_status_from_message(self):
        source = Source('abc')
        message = SourceMessage(1, 'abc', 0x01)
        message.status = 0x22
        with self.assertRaises(SourceException):
            source.get_message(message)


class SourceNewMessageTestCase(unittest.TestCase):

    def test_source_new_message_empty_data(self):
        source = Source('abc')
        source.status = source.STATUS_RECHARGE
        message = source.new_message()
        self.assertEqual(message.source_id, source.source_id)
        self.assertEqual(message.status, source.status)
        self.assertIsNone(message.data)

    def test_source_new_message_with_data(self):
        source = Source('abc')
        source.status = source.STATUS_RECHARGE
        message_data = {
            'hello': 1,
            'bye': 2
        }
        message = source.new_message(message_data)
        self.assertEqual(message.source_id, source.source_id)
        self.assertEqual(message.status, source.status)
        self.assertIsNotNone(message.data)
        self.assertEqual(message.data, message_data)

if __name__ == '__main__':
    unittest.main()
