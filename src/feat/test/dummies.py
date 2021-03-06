# F3AT - Flumotion Asynchronous Autonomous Agent Toolkit
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# See "LICENSE.GPL" in the source distribution for more information.

# Headers in this file shall remain intact.
from zope.interface import implements
from twisted.python import components

from feat.common import defer, time, log, journal, fiber
from feat.agents.base import descriptor, requester, replier, replay, message,\
                             cache
from feat.agencies import protocols
from feat.agencies.emu import database

from feat.agencies.interface import *
from feat.agents.monitor.interface import *
from feat.interface.protocols import *
from feat.interface.log import *
from feat.interface.agent import *
from feat.interface.agency import ExecMode


class DummyBase(journal.DummyRecorderNode, log.LogProxy, log.Logger):

    def __init__(self, logger, now=None):
        journal.DummyRecorderNode.__init__(self)
        log.LogProxy.__init__(self, logger)
        log.Logger.__init__(self, logger)

        self.calls = {}
        self.now = now or time.time()
        self.call = None

    def do_calls(self):
        calls = self.calls.values()
        self.calls.clear()
        for _time, fun, args, kwargs in calls:
            fun(*args, **kwargs)

    def reset(self):
        self.calls.clear()

    def get_time(self):
        return self.now

    def call_next(self, call, *args, **kwargs):
        call(*args, **kwargs)

    def call_later(self, time, fun, *args, **kwargs):
        payload = (time, fun, args, kwargs)
        callid = id(payload)
        self.calls[callid] = payload
        return callid

    def call_later_ex(self, time, fun, args=(), kwargs={}, busy=True):
        payload = (time, fun, args, kwargs)
        callid = id(payload)
        self.calls[callid] = payload
        return callid

    def cancel_delayed_call(self, callid):
        if callid in self.calls:
            del self.calls[callid]


class DummyAgent(DummyBase):

    descriptor_class = descriptor.Descriptor

    def __init__(self, logger, db=None):
        DummyBase.__init__(self, logger)
        self.descriptor = self.descriptor_class()
        self.protocols = list()

        # db connection
        self._db = db and db or database.Database().get_connection()

        self.notifications = list()

        # call_id -> DelayedCall
        self._delayed_calls = dict()

    def reset(self):
        self.protocols = list()
        DummyBase.reset(self)

    def initiate_protocol(self, factory, *args, **kwargs):
        instance = DummyProtocol(factory, args, kwargs)
        self.protocols.append(instance)
        return instance

    def get_descriptor(self):
        return self.descriptor

    def update_descriptor(self, _method, *args, **kwargs):
        f = fiber.succeed()
        f.add_callback(fiber.drop_param,
                      _method, self.descriptor, *args, **kwargs)
        return f

    def register_change_listener(self, doc_id, cb, **kwargs):
        if isinstance(doc_id, (str, unicode)):
            doc_id = (doc_id, )
        self._db.changes_listener(doc_id, cb, **kwargs)

    def cancel_change_listener(self, doc_id):
        self._db.cancel_listener(doc_id)

    def get_document(self, doc_id):
        return fiber.wrap_defer(self._db.get_document, doc_id)

    def save_document(self, document):
        return fiber.wrap_defer(self._db.save_document, document)

    def delete_document(self, document):
        return fiber.wrap_defer(self._db.delete_document, document)

    def query_view(self, factory, **kwargs):
        return fiber.wrap_defer(self._db.query_view, factory, **kwargs)

    ### IDocumentChangeListner ###

    def on_document_change(self, doc):
        self.notifications.append(('change', doc.doc_id, doc))

    def on_document_deleted(self, doc_id):
        self.notifications.append(('delete', doc_id, None))


class DummyMediumBase(DummyAgent):

    implements(IAgencyAgent)

    def register_interest(self, interest):
        return DummyInterest()

    def get_ip(self):
        return '127.0.0.1'

    def bid(self, message):
        pass

    def finalize(self):
        pass

    def get_mode(self, compoment):
        return ExecMode.test

    def get_configuration(self):
        raise NotImplemented()


class DummyMedium(DummyMediumBase):
    pass


class DummyProtocol(object):

    def __init__(self, factory, args, kwargs):
        self.factory = factory
        self.args = args
        self.kwargs = kwargs
        self.deferred = defer.Deferred()

    def notify_finish(self):
        return fiber.wrap_defer(self.get_def)

    def get_def(self):
        return self.deferred


class DummyAgencyInterest(protocols.DialogInterest):
    pass


components.registerAdapter(DummyAgencyInterest, IInterest,
                           IAgencyInterestInternalFactory)


class DummyInterest(object):

    implements(IInterest)

    def __init__(self):
        self.protocol_type = "Contract"
        self.protocol_id = "some-contract"
        self.interest_type = InterestType.public
        self.initiator = message.Announcement

    def bind_to_lobby(self):
        pass


class DummyRequester(requester.BaseRequester):

    protocol_id = 'dummy-request'
    timeout = 2

    @replay.entry_point
    def initiate(self, state, argument):
        state._got_response = False
        msg = message.RequestMessage()
        msg.payload = argument
        state.medium.request(msg)

    @replay.entry_point
    def got_reply(self, state, message):
        state._got_response = True

    @replay.immutable
    def _get_medium(self, state):
        self.log(state)
        return state.medium

    @replay.immutable
    def got_response(self, state):
        return state._got_response


class DummyReplier(replier.BaseReplier):

    protocol_id = 'dummy-request'

    @replay.entry_point
    def requested(self, state, request):
        state.agent.got_payload = request.payload
        state.medium.reply(message.ResponseMessage())


class DummyCache():

    def __init__(self, agent):
        self.documents = {}
        self.agent = agent

    def update(self, doc_id, operation, *args, **kwargs):
        method = getattr(self.agent, operation)
        document = self.documents.get(doc_id)
        try:
            self.documents[doc_id] = method(document, *args, **kwargs)
        except cache.DeleteDocument:
            del self.documents[doc_id]
        except cache.ResignFromModifying:
            pass

    def get_document(self, doc_id):
        if not doc_id in self.documents:
            raise NotFoundError()
        return self.documents[doc_id]
