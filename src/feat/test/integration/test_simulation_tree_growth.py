# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
from twisted.internet import defer

from feat.common import format_block
from feat.test.integration import common

from feat.agents.host import host_agent
from feat.agents.shard import shard_agent


class TreeGrowthSimulation(common.SimulationTest):

    timeout = 6
    hosts_per_shard = 10
    children_per_shard = 2

    start_host_agent = format_block("""
        start_agent(spawn_agency(), descriptor_factory('host_agent'))
        """)

    def prolog(self):
        setup = format_block("""
        agency = spawn_agency()
        shard_desc = descriptor_factory('shard_agent', 'root')
        host_desc = descriptor_factory('host_agent')
        start_agent(agency, shard_desc)
        start_agent(agency, host_desc)
        """)
        return self.process(setup)

    def testValidateProlog(self):
        agency = self.get_local('agency')
        self.assertEqual(2, len(agency._agents))
        self.assertIsInstance(agency._agents[0].agent, shard_agent.ShardAgent)
        self.assertIsInstance(agency._agents[1].agent, host_agent.HostAgent)

        self.assert_all_agents_in_shard(agency, 'root')

    @defer.inlineCallbacks
    def testFillUpTheRootShard(self):
        shard_agent = self.get_local('agency')._agents[0].agent
        for i in range(2, self.hosts_per_shard + 1):
            yield self.process(self.start_host_agent)
            self.assertEqual(i, shard_agent.resources.allocated()['hosts'])

        self.assertEqual(self.hosts_per_shard, len(self.driver._agencies))
        for agency in self.driver._agencies[1:]:
            self.assert_all_agents_in_shard(agency, 'root')

    @defer.inlineCallbacks
    def testStartNewShard(self):
        fillup_root_shard = self.start_host_agent * (self.hosts_per_shard - 1)
        yield self.process(fillup_root_shard)
        yield self.process(self.start_host_agent)

        last_agency = self.driver._agencies[-1]
        self.assertEqual(2, len(last_agency._agents))
        self.assertIsInstance(last_agency._agents[0].agent,
                              host_agent.HostAgent)
        self.assertIsInstance(last_agency._agents[1].agent,
                              shard_agent.ShardAgent)
        host = last_agency._agents[0].agent
        shard = (host.medium.get_descriptor()).shard
        self.assert_all_agents_in_shard(last_agency, shard)

    @defer.inlineCallbacks
    def testFillupTwoShards(self):
        fillup_two_shards = self.start_host_agent *\
                            (2 * self.hosts_per_shard - 1)
        yield self.process(fillup_two_shards)

        last_agency = self.driver._agencies[-1]
        shard = (last_agency._agents[0].get_descriptor()).shard
        agency_for_second_shard = self.driver._agencies[-self.hosts_per_shard:]
        for agency in agency_for_second_shard:
            self.assert_all_agents_in_shard(agency, shard)

    def assert_all_agents_in_shard(self, agency, shard):
        expected_bindings_to_shard = {
            host_agent.HostAgent: 1,
            shard_agent.ShardAgent: 2}
        expected_bindings_to_lobby = {
            host_agent.HostAgent: 0,
            shard_agent.ShardAgent:\
                lambda desc: (desc.parent is None and 1) or 0}

        for agent in agency._agents:
            desc = agent.get_descriptor()
            self.assertEqual(shard, desc.shard)
            m = agent._messaging
            agent_type = agent.agent.__class__

            expected = expected_bindings_to_shard[agent_type]
            if callable(expected):
                expected = expected(agent.get_descriptor())
            got = len(m.get_bindings(shard))
            self.assertEqual(expected, got,
                        '%r should have %d bindings to shard: %s but had %d' %\
                        (agent_type.__name__, expected, shard, got, ))

            expected = expected_bindings_to_lobby[agent_type]
            if callable(expected):
                expected = expected(agent.get_descriptor())
            got = len(m.get_bindings('lobby'))
            self.assertEqual(expected, got,
                            '%r living in shard: %r should have %d '
                             'bindings to "lobby" but had %d' %\
                            (agent_type.__name__, shard, expected, got, ))