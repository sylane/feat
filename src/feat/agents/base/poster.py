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

from feat.agents.base import message, replay, protocols
from feat.common import defer, reflect, serialization, fiber

from feat.interface.poster import *
from feat.interface.protocols import *


class MetaPoster(type(replay.Replayable)):

    implements(IPosterFactory)

    def __init__(cls, name, bases, dct):
        cls.type_name = reflect.canonical_name(cls)
        serialization.register(cls)
        super(MetaPoster, cls).__init__(name, bases, dct)


class BasePoster(protocols.BaseInitiator):

    __metaclass__ = MetaPoster

    implements(IAgentPoster)

    protocol_type = "Notification"
    protocol_id = None

    notification_timeout = 10

    ### Method to be Overridden ###

    def pack_payload(self, *args, **kwargs):
        return dict(args=args, kwargs=kwargs)

    ### IAgentPoster Methods ###

    def notify(self, *args, **kwargs):
        d = defer.maybeDeferred(self.pack_payload, *args, **kwargs)
        d.addCallback(self._build_message)
        return d

    ### Private Methods ###

    @replay.immutable
    def _build_message(self, state, payload):
        msg = message.Notification()
        msg.payload = payload
        return state.medium.post(msg)
