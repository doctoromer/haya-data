"""
This module handles the connections of the server.

Attributes:
    receiver_running (bool): Flag to kill the receiver thread
"""
import socket
import threading
import logging
import select

import protocol
import protocol.thread
from utils import handle_except


receiver_running = True


class NetworkReceiverThread(threading.Thread):
    """
    This module handles receiving data from the clients.

    Attributes:
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        messages (dict): Dict of messages that wasn't fully received.
        network_queue (Queue.Queue): The queue of the thread.
        port (int): The connection port.
        server (socket.socket): The main socket of the server.
        sockets (dict): The sockets of the clients.
    """

    def __init__(self,
                 network_queue,
                 logic_queue,
                 port):
        """
        Initialize the receiver thread.

        Args:
            network_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            port (int): The connection port.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('network')

        self.network_queue = network_queue
        self.logic_queue = logic_queue
        self.port = port

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sockets = {}

        # dict to store incomplete messages
        # keys are sockets, values ar pairs of:
        # (received data (str), number of missing bytes (int))
        self.messages = {}

    def receive(self, sock, bytes):
        """
        Receive a bytes from socket.

        If the socket fail, then it is removed from the socket list,
        and returns empty string.

        Args:
            sock (socket.socket): The socket to receive bytes from.
            bytes (int): The number of bytes to receive.

        Returns:
            str: The received string.
        """
        try:
            received = sock.recv(bytes)
        except:
            received = ''

        # if connection is closed, remove it
        if received == '':
            ip = sock.getpeername()[0]
            message = protocol.thread.disconnected(
                client=ip)
            self.logic_queue.put(message)
            self.network_queue.put(message)
            del self.sockets[ip]

        return received

    @handle_except('network')
    def run(self):
        """Execute the network receiver thread."""
        self.logger.info('NetworkReceiverThread thread started')
        global receiver_running

        self.server.bind(('', self.port))
        self.server.listen(5)

        while receiver_running:
            # test which socket sent data
            all_sockets = self.sockets.values() + [self.server]
            recv_from_sockets, _, _ = select.select(all_sockets, [], [], 0.6)

            for s in recv_from_sockets:
                # if new client trying to connect, accept it
                if s is self.server:
                    new_socket, address = s.accept()
                    ip = new_socket.getpeername()[0]
                    self.sockets[ip] = new_socket
                    message = protocol.thread.new_socket(
                        socket=new_socket)
                    self.network_queue.put(message)

                # if a connected client send a message, receive it
                else:
                    # if this is a part of a message that alreay begun to send,
                    # add it to the messages dict
                    if s in self.messages:

                        content, missing_bytes = self.messages[s]
                        received = self.receive(s, missing_bytes)

                        content += received
                        missing_bytes -= len(received)

                        self.messages[s] = content, missing_bytes
                        # if no bytes are missing, the message is received
                        # pass it to the logic thread, and remove from queue
                        if missing_bytes == 0:
                            message = protocol.thread.received(
                                message=content, client=s.getpeername()[0])
                            self.logic_queue.put(message)
                            del self.messages[s]
                            self.logger.debug(
                                'received a message from %s: %s...'
                                % (s.getpeername()[0], repr(content[:5])))
                        else:
                            self.logger.debug('received part of message. ' +
                                              'total bytes: %s, left %s.' %
                                              (len(received), missing_bytes))

                    # if this is the first part of a message,
                    # add it to the message dict
                    else:
                        size_str = self.receive(s, 4)

                        # if connection is closed, remove it
                        if size_str != '':
                            size = protocol.get_size(size_str)
                            self.messages[s] = ('', size)
                            self.logger.debug('new message of size %s' % size)

        self.server.close()
        self.logger.info('NetworkReceiverThread thread ended')


class NetworkSenderThread(threading.Thread):
    """
    This module handles sending data to the clients.

    Attributes:
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        network_queue (Queue.Queue): The queue of the thread.
        running (bool): The flag of the main loop.
        sockets (dict): Dict of the connections.
    """

    def __init__(self,
                 network_queue,
                 logic_queue,
                 port):
        """
        Initialize the sender thread.

        Args:
            logic_queue (Queue.Queue): The queue of the logic thread.
            network_queue (Queue.Queue): The queue of the thread.
            port (int): The connection port.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('network')

        self.network_queue = network_queue
        self.logic_queue = logic_queue

        self.sockets = {}

        self.running = True

    def send(self, sock, message):
        """
        Send a message a client.

        if the send fails, the client removed from the client list.

        Args:
            sock (socket.socket): The client.
            message (str): The message
        """
        try:
            sock.send(message)
        except:
            ip = sock.getpeername()[0]
            thread_message = protocol.thread.disconnected(
                client=ip)
            self.logic_queue.put(thread_message)
            del self.sockets[ip]

    @handle_except('network')
    def run(self):
        """Execute the network sender thread."""
        self.logger.info('NetworkThread thread started')
        global receiver_running

        while self.running:
            # get a message from the queue
            message = self.network_queue.get()
            message_type = message['type']

            # send a message to the clients
            if message_type == 'send':

                client = message['client']
                net_message = message['message']

                if client == '*':
                    for ip in self.sockets:
                        self.send(self.sockets[ip], net_message)
                else:
                    self.send(self.sockets[client], net_message)

            # add new socket to the list
            elif message_type == 'new_socket':
                s = message['socket']
                ip = s.getpeername()[0]
                self.sockets[ip] = s
                message = protocol.thread.connected(ip=ip)
                self.logic_queue.put(message)

            # remove a socket from the list
            elif message_type == 'disconnected':
                ip = message['client']
                try:
                    self.sockets[ip].close()
                except:
                    pass
                del self.sockets[ip]

            # thread exit
            elif message_type == 'exit':
                self.running = False
                receiver_running = False
                for s in self.sockets.values():
                    s.close()

        self.logger.info('NetworkThread thread ended')
