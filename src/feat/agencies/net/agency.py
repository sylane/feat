import re

from twisted.internet import reactor, defer

from feat.agents.base.agent import registry_lookup
from feat.agents.base import recipient
from feat.agencies import agency
from feat.agencies.net import ssh, broker
from feat.common import manhole, journal, text_helper
from feat.interface import agent
from feat.process import standalone

from feat.agencies.net import messaging
from feat.agencies.net import database


class Agency(agency.Agency, journal.DummyRecorderNode):

    spawns_processes = True

    def __init__(self, msg_host='localhost', msg_port=5672, msg_user='guest',
                 msg_password='guest',
                 db_host='localhost', db_port=5984, db_name='feat',
                 public_key=None, private_key=None, authorized_keys=None,
                 manhole_port=None):


        self.config = dict()
        self.config['msg'] = dict(host=msg_host, port=msg_port,
                                  user=msg_user, password = msg_password)
        self.config['db'] = dict(host=db_host, port=db_port, name=db_name)
        self.config['manhole'] = dict(public_key=public_key,
                                      private_key=private_key,
                                      authorized_keys=authorized_keys,
                                      port=manhole_port)

        self._init_networking()

    def _init_networking(self):
        mesg = messaging.Messaging(
            self.config['msg']['host'], int(self.config['msg']['port']),
            self.config['msg']['user'], self.config['msg']['password'])
        db = database.Database(
            self.config['db']['host'], int(self.config['db']['port']),
            self.config['db']['name'])
        journal.DummyRecorderNode.__init__(self)
        agency.Agency.__init__(self, mesg, db)

        reactor.addSystemEventTrigger('before', 'shutdown',
                                      self.shutdown)

        self._ssh = ssh.ListeningPort(self, **self.config['manhole'])
        self._broker = broker.Broker(self,
                                on_master_cb=self._ssh.start_listening,
                                on_slave_cb=self._ssh.stop_listening,
                                on_disconnected_cb=self._ssh.stop_listening)
        return self._broker.initiate_broker()

    def full_shutdown(self):
        '''Terminate all the slave agencies and shutdown.'''
        d = self._broker.shutdown_slaves()
        d.addCallback(lambda _: self.shutdown())
        return d

    def shutdown(self):
        d = agency.Agency.shutdown(self)
        d.addCallback(lambda _: self._broker.disconnect())
        d.addCallback(lambda _: self._ssh.stop_listening())
        return d

    @manhole.expose()
    def start_agent(self, descriptor, *args, **kwargs):
        factory = agent.IAgentFactory(
            registry_lookup(descriptor.document_type))
        if self.spawns_processes and factory.standalone:
            return self.start_standalone_agent(descriptor, factory)
        else:
            return self.start_agent_locally(descriptor, *args, **kwargs)

    def start_agent_locally(self, descriptor, *args, **kwargs):
        return agency.Agency.start_agent(self, descriptor, *args, **kwargs)

    def start_standalone_agent(self, descriptor, factory):
        command, args, env = factory.get_cmd_line()
        env = self._store_config(env)
        env['FEAT_AGENT_ID'] = str(descriptor.doc_id)
        recp = recipient.Agent(descriptor.doc_id, descriptor.shard)

        d = self._broker.wait_event(recp.key, 'started')
        d.addCallback(lambda _: recp)

        p = standalone.Process(self, command, args, env)
        p.restart()

        return d

    # Manhole inspection methods

    @manhole.expose()
    @defer.inlineCallbacks
    def list_slaves(self):
        '''list_slaves() -> Print information about the slave agencies.'''
        num = len(self._broker.slaves)
        resp = []
        for slave, i in zip(self._broker.slaves, range(num)):
            resp += ["#### Slave %d ####" % i]
            table = yield slave.callRemote('list_agents')
            resp += [table]
            resp += []
        defer.returnValue("\n".join(resp))

    @manhole.expose()
    def get_nth_slave(self, n):
        '''get_nth_slave(n) -> Give the reference to the nth slave agency.'''
        return self._broker.slaves[n]

    # Config manipulation (standalone agencies receive the configuration
    # in the environment).

    def _store_config(self, env):
        '''
        Stores agency config into environment to be read by the
        standalone agency.'''
        for key in self.config:
            for kkey in self.config[key]:
                var_name = "FEAT_%s_%s" % (key.upper(), kkey.upper(), )
                env[var_name] = str(self.config[key][kkey])
        return env

    def _load_config(self, env):
        '''
        Loads config from environment.
        '''
        self.config = dict()
        matcher = re.compile('\AFEAT_([^_]+)_(.+)\Z')
        for key in env:
            res = matcher.search(key)
            if res:
                c_key = res.group(1).lower()
                c_kkey = res.group(2).lower()
                value = str(env[key])
                if value == 'None':
                    value = None
                if c_key in self.config:
                    self.config[c_key][c_kkey] = value
                else:
                    self.config[c_key] = {c_kkey: value}