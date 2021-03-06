from zope.interface import Interface, Attribute, implements

from twisted.internet import reactor
from twisted.internet.protocol import ClientFactory

from feat.common import defer, error, log, time
from feat.web import http, security


DEFAULT_CONNECT_TIMEOUT = 30


class RequestError(error.FeatError):
    pass


class RequestCanceled(RequestError):
    pass


class InvalidResponse(RequestError):
    pass


class RequestTimeout(RequestError):
    pass


class IHTTPClientOwner(Interface):

    response_timeout = Attribute("Maximum time waiting for a response")
    idle_timeout = Attribute("Maximum time waiting for response's body")

    def onClientConnectionFailed(reason):
        pass

    def onClientConnectionMade(protocol):
        pass

    def onClientConnectionLost(protocol, reason):
        pass


class Response(object):

    def __init__(self):
        self.status = None
        self.headers = {}
        self.length = None
        self.body = None


class Protocol(http.BaseProtocol):

    log_category = "http-client"

    owner = None

    def __init__(self, log_keeper, owner):
        if owner is not None:
            owner = IHTTPClientOwner(owner)

            if getattr(owner, "response_timeout", None) is not None:
                self.firstline_timeout = owner.response_timeout
                self.inactivity_timeout = owner.response_timeout

            if getattr(owner, "idle_timeout", None) is not None:
                self.idle_timeout = owner.idle_timeout

            self.owner = owner

        http.BaseProtocol.__init__(self, log_keeper)

        self._response = None
        self._requests = []

        self.debug("HTTP client protocol created")

    def is_idle(self):
        return http.BaseProtocol.is_idle(self) and not self._requests

    def request(self, method, location,
                protocol=None, headers=None, body=None):
        headers = dict(headers) if headers is not None else {}
        if body:
            # without typecast to str, in case of unicode input
            # the server just breaks connection with me
            # TODO: think if it cannot be fixed better
            body = str(body)
            headers["content-length"] = len(body)
        lines = []
        http.compose_request(method, location, protocol, buffer=lines)
        http.compose_headers(headers, buffer=lines)

        seq = []
        for line in lines:
            self.log("<<< %s", line)
            seq.append(line)
            seq.append("\r\n")
        seq.append("\r\n")

        if body:
            seq.append(body)

        d = defer.Deferred()
        self._requests.append(d)

        self.transport.writeSequence(seq)

        return d

    ### Overridden Methods ###

    def onConnectionMade(self):
        self.factory.onConnectionMade(self)

    def onConnectionLost(self, reason):
        self.factory.onConnectionLost(self, reason)
        self.owner = None

    def process_cleanup(self, reason):
        for d in self._requests:
            d.errback(RequestError())
        self._requests = None

    def process_reset(self):
        self._response = None

    def process_request_line(self, line):
        assert self._response is None, "Already handling response"
        parts = http.parse_response_status(line)
        if parts is None:
            error = InvalidResponse("Wrong response format: %r", line)
            self._client_error(error)
            return
        protocol, status = parts
        self._response = Response()
        self._response.protocol = protocol
        self._response.status = status

    def process_length(self, length):
        assert self._response is not None, "No response information"
        self._response.length = length

    def process_extend_header(self, name, values):
        assert self._response is not None, "No response information"
        res = self._response
        if name not in res.headers:
            res.headers[name] = []
        res.headers[name].extend(values)

    def process_set_header(self, name, value):
        assert self._response is not None, "No response information"
        self._response.headers[name] = value

    def process_body_data(self, data):
        assert self._response is not None, "No response information"
        if self._response.body is None:
            self._response.body = ''
        self._response.body += data

    def process_body_finished(self):
        d = self._requests.pop(0)
        d.callback(self._response)

    def process_timeout(self):
        self._client_error(RequestTimeout())

    def process_parse_error(self):
        self._client_error(InvalidResponse())

    ### Private Methods ###

    def _client_error(self, exception):
        d = self._requests.pop(0)
        d.errback(exception)
        self.transport.loseConnection()


class Factory(ClientFactory):

    protocol = Protocol

    def __init__(self, log_keeper, owner, deferred):
        self.owner = IHTTPClientOwner(owner)
        self.log_keeper = log_keeper
        self._deferred = deferred

    def buildProtocol(self, addr):
        return self.create_protocol(self.log_keeper, self.owner)

    def create_protocol(self, *args, **kwargs):
        proto = self.protocol(*args, **kwargs)
        proto.factory = self
        time.call_next(self._deferred.callback, proto)
        del self._deferred
        return proto

    def clientConnectionFailed(self, connector, reason):
        time.call_next(self._deferred.errback, reason)
        del self._deferred
        if self.owner:
            self.owner.onClientConnectionFailed(reason)
        self._cleanup()

    def onConnectionMade(self, protocol):
        if self.owner:
            self.owner.onClientConnectionMade(protocol)

    def onConnectionLost(self, protocol, reason):
        if self.owner:
            self.owner.onClientConnectionLost(protocol, reason)
        self._cleanup()

    ### private ###

    def _cleanup(self):
        self.log_keeper = None
        self.owner = None


class Connection(log.LogProxy, log.Logger):

    implements(IHTTPClientOwner)

    factory = Factory

    default_http_protocol = http.Protocols.HTTP11

    connect_timeout = DEFAULT_CONNECT_TIMEOUT
    response_timeout = None # Default factory one
    idle_timeout = None # Default factory one

    bind_address = None

    def __init__(self, host, port=None, protocol=None,
                 security_policy=None, logger=None):
        logger = logger if logger is not None else log.FluLogKeeper()
        log.LogProxy.__init__(self, logger)
        log.Logger.__init__(self, logger)

        self._host = host
        self._port = port
        self._security_policy = security.ensure_policy(security_policy)

        if self._security_policy.use_ssl:
            self._http_scheme = http.Schemes.HTTPS
        else:
            self._http_scheme = http.Schemes.HTTP

        if self._port is None:
            if self._http_scheme is http.Schemes.HTTP:
                self._port = 80
            if self._http_scheme is http.Schemes.HTTPS:
                self._port = 443

        proto = self.default_http_protocol if protocol is None else protocol
        self._http_protocol = proto

        self._protocol = None
        self._pending = 0

    ### public ###

    def is_idle(self):
        return self._protocol is None or self._protocol.is_idle()

    def request(self, method, location, headers=None, body=None):
        if self._protocol is None:
            d = self._connect()
            d.addCallback(self._on_connected)
        else:
            d = defer.succeed(self._protocol)

        d.addCallback(self._request, method, location, headers, body)
        return d

    def disconnect(self):
        if self._protocol:
            self._protocol.transport.loseConnection()

    ### virtual ###

    def create_protocol(self, deferred):
        return self.factory(self, self, deferred)

    def onClientConnectionFailed(self, reason):
        pass

    def onClientConnectionMade(self, protocol):
        pass

    def onClientConnectionLost(self, protocol, reason):
        self._protocol = None

    ### private ###

    def _connect(self):
        d = defer.Deferred()
        factory = self.create_protocol(d)

        kwargs = {}
        if self.connect_timeout is not None:
            kwargs['timeout'] = self.connect_timeout
        kwargs['bindAddress'] = self.bind_address

        if self._security_policy.use_ssl:
            context_factory = self._security_policy.get_ssl_context_factory()
            reactor.connectSSL(self._host, self._port,
                               factory, context_factory, **kwargs)
            return d

        reactor.connectTCP(self._host, self._port, factory, **kwargs)
        return d

    def _on_connected(self, protocol):
        self._protocol = protocol
        return protocol

    def _request(self, protocol, method, location, headers, body):
        self._pending += 1
        headers = dict(headers) if headers is not None else {}
        if "host" not in headers:
            headers["host"] = self._host
        d = protocol.request(method, location,
                             self._http_protocol,
                             headers, body)
        d.addBoth(self._request_done)
        return d

    def _request_done(self, param):
        self._pending -= 1
        return param
