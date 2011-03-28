import sys
import yarp

from morse.core.request_manager import RequestManager, MorseRPCInvokationError
from morse.core import status


class YarpRequestManager(RequestManager):
    """Implements services to control the MORSE simulator over YARP

    The syntax of requests is:
    >>> id component_name service [params with Python syntax]

    'id' is an identifier set by the client to conveniently identify
    the request. It must be less that 80 chars in [a-zA-Z0-9].

    The server answers:
    >>> id OK|FAIL result_in_python|error_msg

    """

    def __str__(self):
        return "Yarp service manager"

    def _initialization(self):

        # Create dictionaries for the input and output ports
        self._yarp_request_ports = dict()
        self._yarp_reply_ports = dict()
        # Create a dictionary for the port names
        self._component_ports = dict()

        # For asynchronous request, this holds the mapping between a
        # request_id and the socket which requested it.
        self._pending_ports = dict()

        # Stores for each port the pending results to write back.
        self._results_to_output = dict()

        # Create a dictionary for the evailable bottles
        self._in_bottles = dict()
        self._reply_bottles = dict()

        return True


    def _finalization(self):
        print("Closing yarp request ports...")
        for port in self._yarp_request_ports.values():
            port.close()

        return True


    def _on_service_completion(self, request_id, results):
        port = None

        try:
            port, id = self._pending_ports[request_id]
        except KeyError:
            print(str(self) + ": ERROR: I can not find the port which requested " + request_id)
            return

        if port in self._results_to_output:
            self._results_to_output[port].append((id, results))
        else:
            self._results_to_output[port] = [(id, results)]


    def _post_registration(self, component, service, is_async):
        """ Register a connection of a service with YARP """
        # Get the Network attribute of yarp,
        #  then call its init method
        self._yarp_module = sys.modules['yarp']
        self.yarp_object = self._yarp_module.Network()

        # Create the names of the ports
        port_name = '/{0}/{1}'.format(component, service)
        request_port_name = '/ors/services{0}/request'.format(port_name)
        reply_port_name = '/ors/services{0}/reply'.format(port_name)

        # Create the ports to accept and reply to requests
        request_port = self._yarp_module.BufferedPortBottle()
        reply_port = self._yarp_module.BufferedPortBottle()
        request_port.open(request_port_name)
        reply_port.open(reply_port_name)
        self._yarp_request_ports[port_name] = request_port
        self._yarp_reply_ports[port_name] = reply_port
        
        # Create bottles to use in the responses
        bottle_in = self._yarp_module.Bottle()
        self._in_bottles[port_name] = bottle_in
        bottle_reply = self._yarp_module.Bottle()
        self._reply_bottles[port_name] = bottle_reply

        print("Yarp service manager now listening on port " + request_port_name + ".")
        print("Yarp service manager will reply on port " + reply_port_name + ".")

        return True


    def _main(self):
        """ Read commands from the ports, and prepare the response""" 
        # Read data from available ports
        for port_name, port in self._yarp_request_ports.items():
            # Get the bottles to read and write
            bottle_in = self._in_bottles[port_name] 
            bottle_reply = self._reply_bottles[port_name] 
            bottle_in = port.read(False)
            if bottle_in != None:
                print("Received command from port '%s'" % (port_name))

                try:
                    try:
                        id, component, service, params = self.parse_request(bottle_in)
                    except ValueError: # Request contains < 2 tokens.
                        id = req
                        raise MorseRPCInvokationError("Malformed request! ")

                    print("Got '%s | %s | %s' (id = %s) from %s" % (component, service, params, id, port_name))

                    # _on_incoming_request returns either 
                    #(True, result) if it's a synchronous
                    # request that has been immediately executed, or
                    # (False, request_id) if it's an asynchronous request whose
                    # termination will be notified via
                    # _on_service_completion.
                    is_sync, value = self._on_incoming_request(component, service, params)

                    if is_sync:
                        if port in self._results_to_output:
                            self._results_to_output[port].append((id, value))
                        else:
                            self._results_to_output[port] = [(id, value)]
                    else:
                        # Stores the mapping request/socket to notify
                        # the right port when the service completes.
                        # (cf :py:meth:_on_service_completion)
                        # Here, 'value' is the internal request id while
                        # 'id' is the id used by the socket client.
                        self._pending_ports[value] = (port, id)


                except MorseRPCInvokationError as e:
                        if port in self._results_to_output:
                            self._results_to_output[port].append((id, (status.FAILED, e.value)))
                        else:
                            self._results_to_output[port] = [(id, (status.FAILED, e.value))]
        
        if self._results_to_output:
            for o in self._yarp_request_ports.values():
                if o in self._results_to_output:
                    for r in self._results_to_output[o]:
                        response = "%s %s %s" % (r[0], r[1][0], str(r[1][1]) if r[1][1] else "")
                        # Send the reply through the same yarp port
                        reply_port = self._yarp_reply_ports[port_name]
                        bottle_reply = reply_port.prepare()
                        bottle_reply.clear()
                        bottle_reply.addString(response)
                        reply_port.write()
                        print("Sent back " + response + " to " + str(o))
                            
                    del self._results_to_output[o]


    def parse_request(self, bottle):
        """
        Parse the incoming request.
        """
        try:
            id = bottle.get(0).asInt()
            component = bottle.get(1).toString()
            service = bottle.get(2).toString()
        except IndexError as e:
            raise MorseRPCInvokationError("Malformed request: at least 3 values and at most 4 are expected (id, component, service, [params])")

        try:
            params = bottle.get(3).toString()
            p =  eval(params, {"__builtins__": None},{})
        except (NameError, SyntaxError) as e:
            raise MorseRPCInvokationError("Invalid request syntax: error while parsing the parameters. " + str(e))

        return (id, component, service, p)
