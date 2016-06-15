"""The logic thread module."""
import threading
import logging
import Queue
import os

import protocol.thread
import database
from distribute import DistributeThread
from restore import RestoreThread
from reconstruct import ReconstructThread
from utils import handle_except


class LogicThread(threading.Thread):
    """
    The logic thread handles the buisness logic.

    Attributes:
        clients (list): List of connected clients.
        db_name (str): The path to the db file.
        gui_queue (Queue.Queue): The queue of the gui thread.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        network_queue (Queue.Queue): The queue of the network thread.
        reconstruct_queue (Queue.Queue): The queue of the reconstruct thread.
        reconstruct_thread_id (int): The id of the reconstruct thread.
        running (bool): The flag of the main loop of the thread.
        running_threads (dict): Dict of the current running thread of
            type 'restore' or 'deistribute'. Described in more details in
            the docs of 'add_running_thread' method.
    """

    def __init__(self, logic_queue, gui_queue, network_queue):
        """
        Initialize the logic thread.

        Args:
            logic_queue (Queue.Queue): The queue of the logic thread.
            gui_queue (Queue.Queue): The queue of the gui thread.
            network_queue (Queue.Queue): The queue of the network thread.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('logic')

        # initialize the class variables
        self.logic_queue = logic_queue
        self.gui_queue = gui_queue
        self.network_queue = network_queue

        # variables for the system reconstruct mechanism
        self.reconstruct_queue = None
        self.reconstruct_thread_id = None

        self.db_name = 'files.db'
        self.clients = []
        self.running_threads = {}
        self.running = True

    def add_running_thread(self,
                           ident,
                           thread_type,
                           name,
                           file_size,
                           block_number,
                           duplication_level,
                           validation_level,
                           key,
                           queue):
        """
        Add a thread to the 'running_threads' dict.

        Args:
            ident (int): The id of the thread.
            thread_type (str): The type of the thread.
                can be 'restore' or 'distribute'.
            name (str): The name of the file of the thread.
                In 'restore' thread, this is the name of the file
                restored from the storage. In 'distribute',
                This is the name of the file uploaded to the storage.
            file_size (int): The size of the file in bytes.
            block_number (int): The number of data blocks of the file.
            duplication_level (int): The duplication level of the file.
            validation_level (int): The validation level of the file.
            key (str): The encryption key of the file.
            queue (Queue.Queue): The queue of the thread.
        """
        self.running_threads[ident] = {
            'thread_type': thread_type,
            'name': name,
            'file_size': file_size,
            'block_number': block_number,
            'duplication': duplication_level,
            'validation': validation_level,
            'key': key,
            'queue': queue
        }

        self.update_thread_list()

    def update_thread_list(self):
        """
        Send information about the running thread.

        The information is sent to the gui, and to the distribution protocol,
        if running.
        """
        # copy the thread dict
        thread_list = {}
        for ident in self.running_threads:
            thread_list[ident] = self.running_threads[ident].copy()

        # remove information that shouln't be visible to other threads
        for ident in thread_list:
            del thread_list[ident]['queue']
            del thread_list[ident]['key']

        # create the message
        message = protocol.thread.thread_list(
            threads=thread_list)
        self.gui_queue.put(message)

        if self.reconstruct_queue is not None:
            self.reconstruct_queue.put(message)

    def update_storage_state(self):
        """
        Triger the update of the interface.

        The method do three tasks:
            * Send an updated list of the files in the storage to the gui.
            * Ask the clients to report which blocks they contain.
            * Ask the clients to report the usage of their disks.

            The only real update happens in the first task, The other
            task only cause the client to return information.
            When they will return the information, the real update will accure.
        """
        # query the db about the files in the storage, and report to the gui
        db = database.Database(self.db_name)
        file_list = db.query_all()
        file_list = map(lambda x: x[:-1], file_list)
        db.close()
        message = protocol.thread.file_list(file_list)
        self.gui_queue.put(message)

        # ask the clients to report which blocks they contain
        storage_net_message = protocol.server.ask_storage_state()
        storage_thread_message = protocol.thread.send(
            message=storage_net_message)
        self.network_queue.put(storage_thread_message)

        # ask the clients to report the usage of their disks
        disk_net_message = protocol.server.ask_disk_state()
        disk_thread_message = protocol.thread.send(message=disk_net_message)
        self.network_queue.put(disk_thread_message)

    def update_client_state(self):
        """Send the gui an updated list of the connected clients."""
        message = protocol.thread.client_list(
            clients=self.clients)
        self.gui_queue.put(message)

        self.update_storage_state()

    def send_message(self, received):
        """
        Send message to client.

        Args:
            received (dict): Message from the queue.
        """
        self.network_queue.put(received)

    def distribute(self, received):
        """
        Distribute a file.

        Args:
            received (dict): The distribute message.
        """
        # get relevant parameters
        file_path = received['file_path']
        block_size = received['block_size']
        duplication = received['duplication']
        validation = received['validation']

        # generate encryption key
        key = os.urandom(16)
        distribute_queue = Queue.Queue()

        # create the thread
        distribute = DistributeThread(file_path=file_path,
                                      block_size=block_size,
                                      duplication_level=duplication,
                                      validation_level=validation,
                                      clients=list(self.clients),
                                      distribute_queue=distribute_queue,
                                      key=key,
                                      logic_queue=self.logic_queue)
        distribute.start()
        # calculate the number of blocks
        file_size = os.stat(file_path).st_size
        block_number = file_size / block_size
        if file_size % block_size != 0:
            block_number += 1

        file_name = os.path.basename(file_path)

        # add the thread to the list of the running threads
        self.add_running_thread(
            thread_type='distribute',
            ident=distribute.ident,
            name=file_name,
            file_size=file_size,
            block_number=block_number,
            duplication_level=duplication,
            validation_level=validation,
            key=key,
            queue=distribute_queue)

    def restore(self, received):
        """
        Restore a file.

        Args:
            received (dict): The restore message.
        """
        # get relevant parameters from the message of the db
        real_file = received['real_file']
        virtual_file = received['virtual_file']

        db = database.Database(self.db_name)
        query = db.query(virtual_file)
        block_number = query[2]
        validation_level = query[4]
        key = query[5]
        restore_queue = Queue.Queue()

        # create the thread
        restore = RestoreThread(real_file=real_file,
                                virtual_file=virtual_file,
                                block_number=block_number,
                                validation_level=validation_level,
                                clients=self.clients,
                                key=key,
                                restore_queue=restore_queue,
                                logic_queue=self.logic_queue)
        restore.start()
        # add the thread to the list of the running threads
        self.add_running_thread(
            thread_type='restore',
            ident=restore.ident,
            name=virtual_file,
            file_size=query[1],
            block_number=block_number,
            duplication_level=query[3],
            validation_level=validation_level,
            key=key,
            queue=restore_queue)

        # ask the blocks of the files from the clients
        message = protocol.server.ask_block(name=virtual_file)
        for client in self.clients:
            net_message = protocol.thread.send(client=client, message=message)
            self.network_queue.put(net_message)

    def reconstruct(self, received):
        """
        Triger system reconstruction.

        This method starts a thread that restores all the files,
        delete them from the storage, and redistribute them.
        This act clean the storage and repair all files that can
        be repaired.

        The reconstruction locks the gui to prevet the user to perform
        actions the can currupt the process.

        Args:
            received (dict): The reconstruct message.
        """
        # query all records from the db
        db = database.Database(self.db_name)
        records = db.query_all()
        db.close()
        self.reconstruct_queue = Queue.Queue()

        # create the thread
        reconstruct = ReconstructThread(
            file_records=records,
            reconstruct_queue=self.reconstruct_queue,
            logic_queue=self.logic_queue
        )
        reconstruct.start()

        self.reconstruct_thread_id = reconstruct.ident

        # lock the gui
        message = protocol.thread.lock_gui()
        self.gui_queue.put(message)

    def delete(self, received):
        """
        Delete a file.

        This method send a delete method to the clients,
        remove it from the db, and inform the gui.

        unlike other file operations, the delete mechanism doesn't
        have 'Action -> Acknowledgment -> Display' mechanism. If
        The client fails to delete the file, then the server treat
        it as file doesn't exists.

        Args:
            received (dict): The delete message.
        """
        file_name = received['virtual_file']

        # send delete message to the clients
        net_message = protocol.server.delete_block(file_name)
        message = protocol.thread.send(net_message)
        self.network_queue.put(message)

        # delete file from the db
        db = database.Database(self.db_name)
        if file_name == '*':
            db.delete_all()
        else:
            db.delete(file_name)
        db.close()

        # update the gui
        self.update_storage_state()

    def connected(self, received):
        """
        Handle new client.

        Args:
            received (dict): The connected message.
        """
        # add the client to the client list
        ip = received['ip']
        self.clients.append(ip)

        self.logger.info('new client: ' + ip)

        # update the client view
        self.update_client_state()

    def disconnected(self, received):
        """
        Handle client disconnection.

        Args:
            received (dict): The disconnect message.
        """
        # remove client from the clients list
        ip = received['client']
        if ip in self.clients:
            self.clients.remove(ip)

        # a generator object for all distribute threads
        distribute_threads = (thread for ident, thread
                              in self.running_threads
                              if thread['thread_type'] == 'distribute')

        if len(distribute_threads) != 0:
            failed_files = []
            message = protocol.thread.exit()
            for thread in distribute_threads:
                thread['queue'].put(message)
                failed_files.append(thread['name'])

            failed_files_str = ', '.join(failed_files)
            error_message = protocol.thread.error(
                thread_id=None,
                message='failed distributing files: %s' % failed_files_str)
            self.gui_queue.put(error_message)

        # update the client view
        self.update_client_state()

    def received(self, received):
        """
        Handle new message from a client.

        Args:
            received (dict): The received message.
        """
        # the message from the client
        malformed = False
        try:
            message = protocol.parse(received['message'])
        except:
            malformed = True

        if type(message) is not dict:
            malformed = True

        if malformed:
            self.logger.warning('received malformed message')
            return

        message['client'] = received['client']
        message_type = message['type']
        self.logger.debug('received message of type %s' % message_type)

        if message_type == 'block' or message_type == 'file_sent':

            # if a thread waiting to this message, pass the message to it
            for key in self.running_threads:
                thread = self.running_threads[key]
                thread_type = thread['thread_type']
                message_name = message['name']
                if thread['name'] == message_name and thread_type == 'restore':
                    self.running_threads[key]['queue'].put(message)

        # if the message is a 'disk_state' message, update the gui
        elif message_type == 'disk_state':
            total = message['total']
            free = message['free']
            gui_message = protocol.thread.disk_state(
                client=received['client'], total=total, free=free)
            self.gui_queue.put(gui_message)

        # if the message is a 'storage_state' message, update the gui
        elif message_type == 'storage_state':
            self.gui_queue.put(message)
        else:
            log = 'unknown message type: %s. message not processed'
            self.logger.warning(log % message_type)

    def exit(self, received):
        """
        Triger global system exit.

        Args:
            received (dict): The exit message.
        """
        self.logger.info('shutting down the system')
        self.running = False

        # send exit message to all other main threads
        exit_message = protocol.thread.exit()
        self.network_queue.put(exit_message)

        for key in self.running_threads:
            self.running_threads[key]['queue'].put(exit_message)

    def thread_exit(self, received):
        """
        Handle exit of a thread.

        This method handles olny the exit of 'restore', 'distribute'
        or 'reconstruct' threads, which start and exit during the lifetime
        of the program.

        Args:
            received (dict): The exit_thread message.
        """
        thread_id = received['thread_id']

        # if the thread is 'restore' or 'distribute'
        if thread_id != self.reconstruct_thread_id:
            thread_dict = self.running_threads[thread_id]
            thread_type = thread_dict['thread_type']

            # if the thread type is 'distribute', it means that the system
            # finished distributing a file, then add it to the db
            if thread_type == 'distribute':
                if received['success']:
                    record = (
                        thread_dict['name'],
                        thread_dict['file_size'],
                        thread_dict['block_number'],
                        thread_dict['duplication'],
                        thread_dict['validation'],
                        thread_dict['key']
                    )

                    db = database.Database(self.db_name)
                    db.insert(record)
                    db.close()

                else:
                    self_message = protocol.thread.delete(
                        virtual_file=thread_dict['name'])
                    self.delete(self_message)

            del self.running_threads[thread_id]

        else:
            # if the thread is the reconstruction thread,
            # then remove it's thread_id and the queue
            self.reconstruct_thread_id = None
            self.reconstruct_queue = None

            # release the gui
            message = protocol.thread.release_gui()
            self.gui_queue.put(message)

        self.update_storage_state()
        self.update_thread_list()

    def kill_thread(self, received):
        """
        Kill a running thread, by the associated file name.

        Args:
            received (dict): The kill_thread message.
        """
        name = received['name']
        message = protocol.thread.exit()
        for ident in self.running_threads:
            thread = self.running_threads[ident]
            if thread['name'] == name:
                thread['queue'].put(message)

    def error(self, received):
        """
        Handle error from one of the running threads.

        When an error message is received from a thread,
        it is sent to the gui to display an error dialog.

        Args:
            received (dict): The error message.
        """
        self.gui_queue.put(received)

    def kill(self, received):
        """
        Kill a client.

        Args:
            received (dict): The kill message.
        """
        client = received['client']
        net_message = protocol.server.kill()
        message = protocol.thread.send(
            client=client, message=net_message)
        self.network_queue.put(message)

    @handle_except('logic')
    def run(self):
        """Execute the restore thread."""
        self.logger.info(self.name + ' thread started')

        # the dict dispatch a message type to a handler
        command_dict = {
            'send': self.send_message,
            'ask_thread_list': lambda x: self.update_thread_list(),
            'distribute': self.distribute,
            'restore': self.restore,
            'reconstruct': self.reconstruct,
            'connected': self.connected,
            'received': self.received,
            'refresh': lambda x: self.update_storage_state(),
            'delete': self.delete,
            'exit': self.exit,
            'thread_exit': self.thread_exit,
            'kill_thread': self.kill_thread,
            'disconnected': self.disconnected,
            'error': self.error,
            'kill': self.kill
        }

        # wrap the body to the main loop in a fucntion,
        # to apply it the 'handle_except' decorator.
        # this way, no matter what, the thread won't fail.
        @handle_except('logic')
        def do_loop():
            """Execute one step of the main loop of the thread."""
            received = self.logic_queue.get()
            command = received['type']

            if command in command_dict:
                command_dict[command](received)
            else:
                log = 'unknown message type: %s. message not processed'
                self.logger.warning(log % command)

        self.update_client_state()
        while self.running:
            do_loop()

        self.logger.info(self.name + ' thread ended')
