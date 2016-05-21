import socket
import threading
import logging
import logging.config
import time

import sys
sys.dont_write_bytecode = True

import protocol
import protocol.client
import protocol.thread
from utils import handle_except


class NetworkReceiverThread(threading.Thread):
    """
    This module handles receiving data from the clients.

    Attributes:
        connected (bool): Flag indicating if the client is
            connected to the server.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        network_queue (Queue.Queue): The queue of the network thread.
        port (int): The port of the connection.
        running (bool): The flag of the main loop.
        server_ip (str): The IP address of the server.
        socket (socket.socket): The socket connecte to the server.
    """

    def __init__(self, server_ip, port, network_queue, logic_queue):
        """
        Initialize the receiver thread.

        Args:
            server_ip (str): The IP address of the server.
            port (int): The port of the connection.
            network_queue (Queue.Queue): The queue of the network thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('network')

        self.server_ip = server_ip
        self.port = port
        self.network_queue = network_queue
        self.logic_queue = logic_queue

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running = True
        self.connected = False

    @handle_except('network')
    def run(self):
        """Execute the receiver thread."""
        while self.running:
            # repeatedly try to connect to server
            while not self.connected:
                self.logger.info('waiting for connection')
                try:
                    self.socket.connect((self.server_ip, self.port))
                except:
                    time.sleep(2)
                else:
                    self.connected = True
                    message = protocol.thread.new_socket(socket=self.socket)
                    self.network_queue.put(message)
            self.logger.info('connected to server')

            # loop running while the client is connected
            while self.connected:

                # if receive fail, go back to reconnection
                try:
                    size_str = self.socket.recv(4)
                except:
                    self.connected = False

                if size_str != '':
                    size = protocol.get_size(size_str)
                    received = ''

                    # receive until the whole message is received
                    while size != 0:

                        try:
                            part = self.socket.recv(size)
                        except:
                            part = ''

                        # if the connection is close,
                        # return to waiting to connection
                        if part == '':
                            self.connected = False
                            break

                        received += part
                        size -= len(part)

                    # if the messaged was received without failing,
                    # pass it to the logic
                    if self.connected:
                        self.logger.debug(
                            'received message. length: %s' % len(received))
                        message = protocol.parse(received)

                        self.logic_queue.put(message)

                        # if the message type is 'kill', the thread will exit
                        # this must happen here and not in the logic thread,
                        # because the logic thread has no way to send a message
                        # to this thread because it doesn't have a queue.
                        if message['type'] == 'kill':
                            self.socket.close()
                            self.connected = False
                            self.running = False
                            break
                else:
                    self.connected = False

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def split_string(string, n):
    """
    Return a generator of evenly sized part of a string.

    Args:
        string (str): The string to split.
        n (int): The size of the parts.

    Returns:
        generator: Generator of the part.
    """
    index = 0

    while True:
        part = string[index:index + n]
        index += n

        if part == '':
            break
        yield part


class NetworkSenderThread(threading.Thread):
    """
    This module handle sending messages to the server.

    Attributes:
        logger (logging.Logger): The logger of the thread.
        network_queue (Queue.Queue): The queue of the reciever thread.
        running (bool): The flag of the main loop.
        socket (socket.socket): The socket of the client.
    """

    def __init__(self, network_queue):
        """
        Initialize the sender thread.

        Args:
            network_queue (Queue.Queue): The queue of the reciever thread.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('network')

        self.network_queue = network_queue

        self.socket = None
        self.running = True

    @handle_except('network')
    def run(self):
        """Execute the sender thread."""
        while self.running:
            message = self.network_queue.get()
            message_type = message['type']

            if message_type == 'new_socket':
                self.socket = message['socket']

            elif message_type == 'send':
                net_message = message['message']

                self.logger.debug(
                    'sending message of length %s' % len(net_message))
                for part in split_string(net_message, 1024):
                    self.socket.send(part)

            elif message_type == 'kill':
                self.running = False

            else:
                self.logger.warning(
                    'unknown message type %s, ignoring' % message_type)
