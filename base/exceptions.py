class ListenerException(Exception):
    """
    Base listener exception
    """
    pass


class ListenerClosedException(ListenerException):
    """
    Connection with listener lost
    """
    pass


class MessageException(Exception):
    """
    Base message exception
    """
    pass


class DecodeMessageError(MessageException):
    """
    Decoding error
    """
    pass


class EncodeMessageError(MessageException):
    """
    Encoding error
    """
    pass


class InvalidMessageException(MessageException):
    """
    Message is not valid
    """
    pass


class ServerException(Exception):
    """
    Base server exception
    """
    pass


class SourceException(Exception):
    """
    Base source exception
    """
    pass