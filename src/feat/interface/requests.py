from zope.interface import Interface, Attribute

from feat.common import enum

__all__ = ["RequestState", "IRequestPeer"]


class RequestState(enum.Enum):
    '''Request protocol state:

      - none: Not initiated.
      - requested: The requested has send a request message to to repliers.
      - closed: The request expire or a response has been received
        from all repliers.
      - wtf: What a Terrible Failure
    '''
    none, requested, closed, wtf = range(4)


class IRequestPeer(Interface):
    '''Define common interface between both peers of the request protocol.'''

    state = Attribute("L{RequestState}")
    request = Attribute("Request's request message")
