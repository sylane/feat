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
# -*- coding: utf-8 -*-
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
import uuid
import time

from twisted.internet import defer, reactor

from feat.common import log, time
from feat.agencies import protocols, retrying, periodic
from feat.agents.base import task, replay

from feat.agencies.interface import *
from feat.interface.requests import *
from feat.interface.protocols import *

from . import common


class DummyAgent(object):

    def __init__(self):
        self.descriptor_type = "dummy-agent"


class CallLaterMixin(object):

    def call_later_ex(self, _time, _method, args=None, kwargs=None, busy=True):
        args = args or ()
        kwargs = kwargs or {}
        return time.callLater(_time, _method, *args, **kwargs)

    def call_later(self, _time, _method, *args, **kwargs):
        return self.call_later_ex(_time, _method, args, kwargs)

    def call_next(self, _method, *args, **kwargs):
        self.call_later_ex(0, _method, args, kwargs)

    def cancel_delayed_call(self, call_id):
        if call_id.active():
            call_id.cancel()


class DummyRepeatMedium(common.Mock, CallLaterMixin,
                        log.Logger, log.LogProxy):

    def __init__(self, testcase, success_at_try=None):
        log.Logger.__init__(self, testcase)
        log.LogProxy.__init__(self, testcase)

        self.number_called = 0
        self.success_at_try = success_at_try

        self.agent = DummyAgent()

    def get_full_id(self):
        return "dummy-medium"

    def initiate_protocol(self, factory, *args, **kwargs):
        self.number_called += 1
        self.info('called %d time', self.number_called)
        if self.success_at_try is not None and\
            self.success_at_try < self.number_called:
            return factory(True)
        else:
            return factory(False)


class DummyInitiator(common.Mock):

    protocol_type = "Dummy"
    protocol_id = "dummy"

    def __init__(self, should_work):
        self.should_work = should_work

    def notify_finish(self):
        if self.should_work:
            return defer.succeed(None)
        else:
            return defer.fail(RuntimeError())


class DummySyncTask(object):

    protocol_type = "Task"
    protocol_id = "dummy-sync-task"

    def __init__(self, agent, medium):
        self.agent = agent
        self.medium = medium

    def initiate(self):
        self.medium.external_counter += 1

    def notify_finish(self):
        return defer.succeed(self)


class DummyAsyncTask(object):

    protocol_type = "Task"
    protocol_id = "dummy-async-task"

    def __init__(self, agent, medium):
        self.agent = agent
        self.medium = medium
        self.finish = defer.Deferred()

    def initiate(self):
        self.medium.external_counter += 1
        time.callLater(2, self.finish.callback, self)
        return task.NOT_DONE_YET

    def notify_finish(self):
        return self.finish


class DummyPeriodicalMedium(common.Mock, CallLaterMixin,
                            log.Logger, log.LogProxy):

    def __init__(self, testcase, success_at_try=None):
        log.Logger.__init__(self, testcase)
        log.LogProxy.__init__(self, testcase)

        self.agent = DummyAgent()

        self.external_counter = 0
        self.internal_counter = 0

        self.current = None

    def get_full_id(self):
        return "dummy-medium"

    def initiate_protocol(self, factory, *args, **kwargs):
        assert self.current is None
        self.internal_counter += 1
        f = factory(self.agent, self)
        self.current = f
        f.initiate(*args, **kwargs)
        d = f.notify_finish()
        d.addCallback(self._finished)
        return f

    def _finished(self, _):
        self.current = None


@common.attr(timescale=0.05)
class TestRetryingProtocol(common.TestCase):

    timeout = 20

    def setUp(self):
        self.medium = DummyRepeatMedium(self)
        common.TestCase.setUp(self)

    @defer.inlineCallbacks
    def testRetriesForever(self):
        d = self.cb_after(None, self.medium, 'initiate_protocol')
        instance = self._start_instance(None, 1, None)
        yield d
        yield self.cb_after(None, self.medium, 'initiate_protocol')
        yield self.cb_after(None, self.medium, 'initiate_protocol')
        yield self.cb_after(None, self.medium, 'initiate_protocol')
        yield self.cb_after(None, self.medium, 'initiate_protocol')
        instance.cancel()
        self.assertEqual(5, self.medium.number_called)

    @defer.inlineCallbacks
    def testMaximumNumberOfRetries(self):
        instance = self._start_instance(3, 1, None)
        d = instance.notify_finish()
        self.assertFailure(d, RuntimeError)
        yield d
        self.assertEqual(4, self.medium.number_called)
        self.assertEqual(8, instance.delay)

    @defer.inlineCallbacks
    def testMaximumDelay(self):
        instance = self._start_instance(3, 1, 2)
        d = instance.notify_finish()
        self.assertFailure(d, RuntimeError)
        yield d
        self.assertEqual(4, self.medium.number_called)
        self.assertEqual(2, instance.delay)

    def _start_instance(self, max_retries, initial_delay, max_delay):
        instance = retrying.RetryingProtocol(
            self.medium, DummyInitiator, max_retries=max_retries,
            initial_delay=initial_delay, max_delay=max_delay)
        return instance.initiate()


@common.attr(timescale=0.1)
class TestPeriodicalProtocol(common.TestCase):

    timeout = 30

    def setUp(self):
        self.medium = DummyPeriodicalMedium(self)
        common.TestCase.setUp(self)

    @defer.inlineCallbacks
    def testSyncTask(self):
        self.assertEqual(self.medium.internal_counter, 0)
        self.assertEqual(self.medium.external_counter, 0)
        p = self.start_protocol(DummySyncTask, 10)
        yield self.wait_counter(p, 3, 30)
        self.assertEqual(self.medium.internal_counter, 3)
        self.assertEqual(self.medium.external_counter, 3)
        p.cancel()

    @defer.inlineCallbacks
    def testAsyncTask(self):
        self.assertEqual(self.medium.internal_counter, 0)
        self.assertEqual(self.medium.external_counter, 0)
        p = self.start_protocol(DummyAsyncTask, 10)
        yield self.wait_counter(p, 3, 30)
        self.assertEqual(self.medium.internal_counter, 3)
        self.assertEqual(self.medium.external_counter, 3)
        p.cancel()

    def start_protocol(self, factory, period):
        instance = periodic.PeriodicProtocol(self.medium, factory,
                                             period=period)
        return instance.initiate()

    @defer.inlineCallbacks
    def wait_counter(self, proto, value, timeout):

        def check():
            return self.medium.current is None \
                   and self.medium.internal_counter == value

        yield self.wait_for(check, timeout)
