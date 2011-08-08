import socket

from twisted.internet import defer

from feat import everything
from feat.test.integration import common

from feat.agents.base import agent, descriptor, document, replay, resource
from feat.agents.common import host
from feat.common.text_helper import format_block
from feat.common import first

from feat.interface.recipient import IRecipient
from feat.interface.agent import Access, Address, Storage


@common.attr(timescale=0.05)
class HostAgentTests(common.SimulationTest):

    NUM_PORTS = 999

    def prolog(self):
        setup = format_block("""
        agency = spawn_agency()
        agency.disable_protocol('setup-monitoring', 'Task')
        desc = descriptor_factory('host_agent', doc_id='test.host.lan')
        medium = agency.start_agent(desc, run_startup=False)
        agent = medium.get_agent()
        """)
        return self.process(setup)

    def testValidateProlog(self):
        agents = [x for x in self.driver.iter_agents()]
        self.assertEqual(1, len(agents))

    def testDefaultResources(self):
        agent = self.get_local('agent')
        totals = agent._get_state().resources.get_totals()
        self.assertTrue("host" in totals)
        self.assertTrue("bandwidth" in totals)
        self.assertTrue("epu" in totals)
        self.assertTrue("core" in totals)
        self.assertTrue("mem" in totals)

    def testDefaultRequeriments(self):
        agent = self.get_local('agent')
        cats = agent._get_state().categories
        self.assertTrue("access" in cats)
        self.assertTrue("storage" in cats)
        self.assertTrue("address" in cats)

    def testHostname(self):
        expected = 'test.host.lan'
        expected_ip = socket.gethostbyname(socket.gethostname())
        self.assertEqual(self.get_local('desc').hostname, expected)
        agent = self.get_local('agent')
        self.assertEqual(agent.get_hostname(), expected)
        self.assertEqual(agent.get_ip(), expected_ip)

    @defer.inlineCallbacks
    def testAllocatePorts(self):
        agent = self.get_local('agent')
        ports = yield agent.allocate_ports(10)
        self.assertEqual(agent.get_num_free_ports(), self.NUM_PORTS - 10)
        self.assertEqual(len(ports), 10)

    @defer.inlineCallbacks
    def testAllocatePortsAndRelease(self):
        agent = self.get_local('agent')
        ports = yield agent.allocate_ports(10)
        self.assertEqual(agent.get_num_free_ports(), self.NUM_PORTS - 10)
        agent.release_ports(ports)
        self.assertEqual(agent.get_num_free_ports(), self.NUM_PORTS)

    def testSetPortsUsed(self):
        agent = self.get_local('agent')
        ports = range(5000, 5010)
        agent.set_ports_used(ports)
        self.assertEqual(agent.get_num_free_ports(), self.NUM_PORTS - 10)
        agent.release_ports(ports)
        self.assertEqual(agent.get_num_free_ports(), self.NUM_PORTS)


@common.attr(timescale=0.05)
class HostAgentRestartTest(common.SimulationTest):

    NUM_PORTS = 999

    @defer.inlineCallbacks
    def prolog(self):
        setup = format_block("""
        agency = spawn_agency()
        agency.disable_protocol('setup-monitoring', 'Task')
        desc = descriptor_factory('host_agent', doc_id='test.host.lan')
        medium = agency.start_agent(desc)
        agent = medium.get_agent()
        wait_for_idle()
        """)
        yield self.process(setup)

    @defer.inlineCallbacks
    def testKillHost(self):
        self.assertEqual(1, self.count_agents('host_agent'))
        self.assertEqual(1, self.count_agents('shard_agent'))
        self.assertEqual(1, self.count_agents('raage_agent'))
        self.assertEqual(1, self.count_agents('monitor_agent'))
        medium = self.get_local('medium')
        desc = medium.get_descriptor()
        yield medium.terminate_hard()
        self.assertEqual(0, self.count_agents('host_agent'))
        agency = self.get_local('agency')
        self.assertEqual(1, desc.instance_id)

        yield agency.start_agent(desc)
        yield self.wait_for_idle(10)
        new_desc = yield self.driver._database_connection.get_document(
            desc.doc_id)
        self.assertEqual(2, new_desc.instance_id)
        self.assertEqual(1, self.count_agents('shard_agent'))
        self.assertEqual(1, self.count_agents('raage_agent'))
        self.assertEqual(1, self.count_agents('monitor_agent'))

        monitor = first(self.driver.iter_agents('monitor_agent')).get_agent()
        hosts = yield monitor.query_partners('hosts')
        self.assertEqual(2, hosts[0].instance_id)


@common.attr(timescale=0.05)
class HostAgentDefinitionTests(common.SimulationTest):

    def prolog(self):
        setup = format_block("""
        agency1 = spawn_agency()
        agency1.disable_protocol('setup-monitoring', 'Task')
        desc1 = descriptor_factory('host_agent')
        medium1 = agency1.start_agent(desc1, hostdef=hostdef, \
        run_startup=False)
        agent1 = medium1.get_agent()

        agency2 = spawn_agency()
        agency2.disable_protocol('setup-monitoring', 'Task')
        desc2 = descriptor_factory('host_agent')
        medium2 = agency2.start_agent(desc2, hostdef=hostdef_id, \
        run_startup=False)
        agent2 = medium2.get_agent()
        """)

        hostdef = host.HostDef()
        hostdef.doc_id = "someid"
        hostdef.resources = {"spam": 999, "bacon": 42, "eggs": 3, "epu": 10}

        self.driver.save_document(hostdef)
        self.set_local("hostdef", hostdef)
        self.set_local("hostdef_id", "someid")

        return self.process(setup)

    def testValidateProlog(self):
        agents = [x for x in self.driver.iter_agents()]
        self.assertEqual(2, len(agents))

    def testDefaultResources(self):

        def check_resources(resc):
            totals = resc.get_totals()
            self.assertTrue("spam" in totals)
            self.assertTrue("bacon" in totals)
            self.assertTrue("eggs" in totals)
            self.assertEqual(totals["spam"], 999)
            self.assertEqual(totals["bacon"], 42)
            self.assertEqual(totals["eggs"], 3)

        agent1 = self.get_local('agent1')
        check_resources(agent1._get_state().resources)

        agent2 = self.get_local('agent2')
        check_resources(agent2._get_state().resources)


@common.attr(timescale=0.05)
class HostAgentRequerimentsTest(common.SimulationTest):

    def prolog(self):
        setup = format_block("""
            agency = spawn_agency()
            agency.disable_protocol('setup-monitoring', 'Task')
            desc = descriptor_factory('host_agent')
            medium = agency.start_agent(desc, hostdef=hostdef,\
                                        run_startup=False)
            agent = medium.get_agent()
            """)

        hostdef = host.HostDef()
        hostdef.doc_id = "someid"
        hostdef.categories = {"access": Access.private,
                                "address": Address.fixed,
                                "storage": Storage.static}
        self.driver.save_document(hostdef)
        self.set_local("hostdef", hostdef)

        return self.process(setup)

    def testValidateProlog(self):
        agents = [x for x in self.driver.iter_agents()]
        self.assertEqual(1, len(agents))

    def testDefaultRequeriments(self):
        agent = self.get_local('agent')
        cats = agent._get_state().categories
        self.assertTrue("access" in cats)
        self.assertTrue("storage" in cats)
        self.assertTrue("address" in cats)
        self.assertEqual(cats["access"], Access.private)
        self.assertEqual(cats["address"], Address.fixed)
        self.assertEqual(cats["storage"], Storage.static)


@agent.register('condition-agent')
class ConditionAgent(agent.BaseAgent):

    categories = {'access': Access.private,
                  'address': Address.fixed,
                  'storage': Storage.static}


@document.register
class Descriptor(descriptor.Descriptor):

    document_type = 'condition-agent'


@agent.register('conditionerror-agent')
class ConditionAgent2(agent.BaseAgent):

    categories = {'access': Access.none,
                  'address': Address.dynamic,
                  'storage': Storage.none}


@document.register
class Descriptor2(descriptor.Descriptor):

    document_type = 'conditionerror-agent'


@common.attr(timescale=0.05)
class HostAgentCheckTest(common.SimulationTest):

    def prolog(self):
        setup = format_block("""
            agency = spawn_agency()
            agency.disable_protocol('setup-monitoring', 'Task')

            host_desc = descriptor_factory('host_agent')
            test_desc = descriptor_factory('condition-agent')
            error_desc = descriptor_factory('conditionerror-agent')

            host_medium = agency.start_agent(host_desc, hostdef=hostdef, \
                                             run_startup=False)
            host_agent = host_medium.get_agent()

            host_agent.start_agent(test_desc)
            host_agent.start_agent(error_desc)
            """)

        hostdef = host.HostDef()
        hostdef.doc_id = "someid"
        hostdef.categories = {"access": Access.private,
                                "address": Address.fixed,
                                "storage": Storage.static}
        hostdef.resources = {"epu": 10}
        self.driver.save_document(hostdef)
        self.set_local("hostdef", hostdef)

        return self.process(setup)

    def testValidateProlog(self):
        agents = [x for x in self.driver.iter_agents()]
        self.assertEqual(2, len(agents))

    @defer.inlineCallbacks
    def testCheckRequeriments(self):

        def check_requeriments(categories):
            self.assertTrue("access" in categories)
            self.assertTrue("storage" in categories)
            self.assertTrue("address" in categories)
            self.assertEqual(categories["access"],
                             Access.private)
            self.assertEqual(categories["address"], Address.fixed)
            self.assertEqual(categories["storage"], Storage.static)

        host_agent = self.get_local('host_agent')
        check_requeriments(host_agent._get_state().categories)
        test_medium = yield self.driver.find_agent(self.get_local('test_desc'))
        test_agent = test_medium.get_agent()
        check_requeriments(test_agent.categories)


@agent.register('contract-running-agent')
class RequestingAgent(agent.BaseAgent):

    @replay.mutable
    def request(self, state, shard, resc=dict()):
        desc = Descriptor3()
        if resc:
            desc.resources = resource.ScalarResource(**resc)
        f = self.save_document(desc)
        f.add_callback(lambda desc:
                       host.start_agent_in_shard(self, desc, shard))
        return f


@descriptor.register('contract-running-agent')
class Descriptor3(descriptor.Descriptor):
    pass


@common.attr(timescale=0.05)
class SimulationStartAgentContract(common.SimulationTest):

    @defer.inlineCallbacks
    def prolog(self):
        setup = format_block("""
        test_desc = descriptor_factory('contract-running-agent')

        agency = spawn_agency()
        agency.disable_protocol('setup-monitoring', 'Task')
        agency.start_agent(descriptor_factory('host_agent', shard='s1'), \
                           run_startup=False)

        agency = spawn_agency()
        agency.disable_protocol('setup-monitoring', 'Task')
        agency.start_agent(descriptor_factory('host_agent', shard='s1'), \
                           run_startup=False)

        agency = spawn_agency()
        agency.disable_protocol('setup-monitoring', 'Task')
        agency.start_agent(descriptor_factory('host_agent', shard='s1'), \
                           run_startup=False)
        agent = _.get_agent()
        agent.wait_for_ready()
        agent.start_agent(test_desc)
        """)
        yield self.process(setup)
        medium = first(self.driver.iter_agents('contract-running-agent'))
        self.agent = medium.get_agent()

    @defer.inlineCallbacks
    def testRunningContract(self):
        self.assertEqual(3, self.count_agents('host_agent'))
        self.assertEqual(1, self.count_agents('contract-running-agent'))
        shard = self.agent.get_own_address().shard
        yield self.agent.request(shard)
        self.assertEqual(2, self.count_agents('contract-running-agent'))

    def testNonexistingShard(self):
        d = self.agent.request('some shard')
        self.assertFailure(d, host.NoHostFound)
        return d

    @defer.inlineCallbacks
    def testRunningWithSpecificResource(self):
        shard = self.agent.get_own_address().shard
        res = dict(epu=20, core=1)
        recp = yield self.agent.request(shard, res)
        doc = yield self.driver._database_connection.get_document(
            IRecipient(recp).key)
        self.assertIsInstance(doc.resources, resource.ScalarResource)
        self.assertEqual(res, doc.resources.values)
        host_id = doc.partners[0].recipient.key
        host_medium = yield self.driver.find_agent(host_id)
        host = host_medium.get_agent()
        _, allocated = yield host.list_resource()
        self.assertEqual(1, allocated['core'])

        # now use start_agent directly
        desc = Descriptor3(resources=resource.ScalarResource(core=1))
        desc = yield self.driver._database_connection.save_document(desc)
        self.info('starting')
        recp = yield host.start_agent(desc)
        desc = yield self.driver._database_connection.reload_document(desc)
        self.assertIsInstance(desc.resources, resource.ScalarResource)
        self.assertEqual({'core': 1}, desc.resources.values)
        _, allocated = yield host.list_resource()
        self.assertEqual(2, allocated['core'])
