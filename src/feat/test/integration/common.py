# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
from twisted.trial.unittest import FailTest

from feat.test import common
from feat.common import text_helper, defer
from feat.common.serialization import pytree
from feat.simulation import driver
from feat.agencies import replay
from feat.agents.base import dbtools
from feat.agents.base.agent import registry_lookup


attr = common.attr
delay = common.delay
delay_errback = common.delay_errback
delay_callback = common.delay_callback
break_chain = common.break_chain
break_callback_chain = common.break_callback_chain
break_errback_chain = common.break_errback_chain


class IntegrationTest(common.TestCase):
    pass


def jid2str(jid):
    if isinstance(jid, basestring):
        return str(jid)
    return "-".join([str(i) for i in jid])


def format_journal(journal, prefix=""):

    def format_call(funid, args, kwargs):
        params = []
        if args:
            params += [repr(a) for a in args]
        if kwargs:
            params += ["%r=%r" % i for i in kwargs.items()]
        return [funid, "(", ", ".join(params), ")"]

    parts = []
    for _, jid, funid, fid, fdepth, args, kwargs, se, result in journal:
        parts += [prefix, jid2str(jid), ": \n"]
        parts += [prefix, " "*4]
        parts += format_call(funid, args, kwargs)
        parts += [":\n"]
        parts += [prefix, " "*8, "FIBER ", str(fid),
                  " DEPTH ", str(fdepth), "\n"]
        if se:
            parts += [prefix, " "*8, "SIDE EFFECTS:\n"]
            for se_funid, se_args, se_kwargs, se_effects, se_result in se:
                parts += [prefix, " "*12]
                parts += format_call(se_funid, se_args, se_kwargs)
                parts += [":\n"]
                if se_effects:
                    parts += [prefix, " "*16, "EFFECTS:\n"]
                    for eid, args, kwargs in se_effects:
                        parts += [prefix, " "*20]
                        parts += format_call(eid, args, kwargs) + ["\n"]
                parts += [prefix, " "*16, "RETURN: ", repr(se_result), "\n"]
        parts += [prefix, " "*8, "RETURN: ", repr(result), "\n\n"]
    return "".join(parts)


class SimulationTest(common.TestCase):

    configurable_attributes = ['skip_replayability', 'jourfile']
    skip_replayability = False
    jourfile = None

    overriden_configs = None

    def __init__(self, *args, **kwargs):
        common.TestCase.__init__(self, *args, **kwargs)
        initial_documents = dbtools.get_current_initials()
        self.addCleanup(dbtools.reset_documents, initial_documents)

    @defer.inlineCallbacks
    def setUp(self):
        yield common.TestCase.setUp(self)
        self.driver = driver.Driver(jourfile=self.jourfile)
        yield self.driver.initiate()
        yield self.prolog()

    def prolog(self):
        pass

    def process(self, script):
        d = self.cb_after(None, self.driver._parser, 'on_finish')
        self.driver.process(script)
        return d

    def get_local(self, *names):
        results = map(lambda name: self.driver._parser.get_local(name), names)
        if len(results) == 1:
            return results[0]
        else:
            return tuple(results)

    def set_local(self, name, value):
        self.driver._parser.set_local(value, name)

    @defer.inlineCallbacks
    def tearDown(self):
        for x in self.driver.iter_agents():
            yield x._cancel_long_running_protocols()
            yield x.wait_for_protocols_finish()

        yield common.TestCase.tearDown(self)
        try:
            yield self._check_replayability()
        finally:
            self.revert_overrides()

    @defer.inlineCallbacks
    def _check_replayability(self):
        if not self.skip_replayability:
            self.info("Test finished, now validating replayability.")
            histories = yield self.driver._journaler.get_histories()
            for history in histories:
                entries = yield self.driver._journaler.get_entries(history)
                self._validate_replay_on_agent(history, entries)
        else:
            msg = ("\n\033[91mFIXME: \033[0mReplayability test "
                  "skipped: %s\n" % self.skip_replayability)
            print msg

    def _validate_replay_on_agent(self, history, entries):
        aid = history.agent_id
        agent = self.driver.find_agent(aid)
        if agent is None:
            self.warning(
                'Agent with id %r not found. '
                'This usually means it was terminated, during the test.', aid)
            return
        if agent._instance_id != history.instance_id:
            self.warning(
                'Agent instance id is %s, the journal entries are for '
                'instance_id %s. This history will not get validated, as '
                'now we dont have the real instance to compare the result '
                'with.', agent._instance_id, history.instance_id)
            return

        self.log("Validating replay of %r with id: %s",
                 agent.agent.__class__.__name__, aid)

        self.log("Found %d entries of this agent.", len(entries))
        r = replay.Replay(iter(entries), aid)
        for entry in r:
            entry.apply()

        agent_snapshot, listeners = agent.snapshot_agent()
        self.log("Replay complete. Comparing state of the agent and his "
                 "%d listeners.", len(listeners))
        if agent_snapshot._get_state() != r.agent._get_state():
            res = repr(pytree.freeze(agent_snapshot._get_state()))
            exp = repr(pytree.freeze(r.agent._get_state()))
            diffs = text_helper.format_diff(exp, res, "\n               ")
            self.fail("Agent snapshot different after replay:\n"
                      "  SNAPSHOT:    %s\n"
                      "  EXPECTED:    %s\n"
                      "  DIFFERENCES: %s\n"
                      % (res, exp, diffs))

        self.assertEqual(agent_snapshot._get_state(), r.agent._get_state())

        listeners_from_replay = [obj for obj in r.registry.values()
                                 if obj.type_name.endswith('-medium')]

        self.assertEqual(len(listeners_from_replay), len(listeners))
        for from_snapshot, from_replay in zip(listeners,
                                              listeners_from_replay):
            self.assertEqual(from_snapshot._get_state(),
                             from_replay._get_state())

    @defer.inlineCallbacks
    def wait_for_idle(self, timeout, freq=0.05):
        try:
            yield self.wait_for(self.driver.is_idle, timeout, freq)
        except FailTest:
            for agent in self.driver.iter_agents():
                activity = agent.show_activity()
                if activity is None:
                    continue
                self.info(activity)
            raise

    def count_agents(self, agent_type=None):
        return len([x for x in self.driver.iter_agents(agent_type)])

    def override_config(self, agent_type, config):
        if self.overriden_configs is None:
            self.overriden_configs = dict()
        factory = registry_lookup(agent_type)
        self.overriden_configs[agent_type] = factory.configuration_doc_id
        factory.configuration_doc_id = config.doc_id

    def revert_overrides(self):
        if self.overriden_configs is None:
            return
        for key, value in self.overriden_configs.iteritems():
            factory = registry_lookup(key)
            factory.configuration_doc_id = value
