"""The reconstruct thread module."""
import threading
import logging
import os

import protocol.thread
from utils import handle_except


class ReconstructThread(threading.Thread):
    """
    The reconstruction thread handles the reconstruction of the system.

    Attributes:
        virtual_file (str): The name of the file in the virtual storage.
        block_size (int): The size of the blocks.
        duplication_level (int): How many times each block is duplicated.
        validation_level (int): The number of data block that each
        clients (list of str): List of the clients.
        key (str): The encryption key.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        reconstruct_queue (Queue.Queue): The queue of the thread.
        callback (func, optional): A callback to be called
                after the thread finished
        temp (str): Temporary directory to store the restored files.
    """

    def __init__(self,
                 virtual_file,
                 block_size,
                 duplication_level,
                 validation_level,
                 clients,
                 key,
                 reconstruct_queue,
                 logic_queue,
                 callback=lambda: None,
                 temp='temp'):
        """
        Initialize the system reconstruction thread.

        Args:
            virtual_file (str): The name of the file in the virtual storage.
            block_size (int): The size of the blocks.
            duplication_level (int): How many times each block is duplicated.
            validation_level (int): The number of data block that each
            clients (list of str): List of the clients.
            key (str): The encryption key.
            reconstruct_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            callback (func, optional): A callback to be called
                after the thread finished
            temp (str): Temporary directory to store the restored files.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('reconstruct')

        self.virtual_file = virtual_file
        self.block_size = block_size
        self.duplication_level = duplication_level
        self.validation_level = validation_level
        self.clients = clients
        self.key = key

        self.reconstruct_queue = reconstruct_queue
        self.logic_queue = logic_queue
        self.callback = callback
        self.temp = temp

    @handle_except('reconstruct')
    def run(self):
        """Execute the system reconstruction thread."""
        reconstruct_dir = os.path.join(os.getcwdu(), self.temp, 'reconstruct')
        self.logger.debug(
            'reconstruction temporary directory: %s' % reconstruct_dir)

        # if the temporary directory doesn't exist, create it
        if not os.path.exists(self.temp):
            os.mkdir(self.temp)

        # if the reconstruction directory doesn't exist, create it
        if not os.path.exists(reconstruct_dir):
            os.mkdir(reconstruct_dir)

        file_path = os.path.join(reconstruct_dir, self.virtual_file)

        # event that will be used to block until the file is restored
        restored_event = threading.Event()

        # restore the file
        message = protocol.thread.restore(
            real_file=file_path,
            virtual_file=self.virtual_file,
            callback=restored_event.set)
        self.logic_queue.put(message)
        self.logger.info('start restoring the file')

        # block until the file is restored
        restored_event.wait()
        self.logger.info('the file is restored')

        # delete the file from storage
        message = protocol.thread.delete(virtual_file=self.virtual_file)
        self.logic_queue.put(message)

        self.logger.info('the file is deleted from storage')

        # event that will be used to block until the file is distributed
        distributed_event = threading.Event()

        # redistribute the file
        distribute = protocol.thread.distribute(
            file_path=file_path,
            block_size=self.block_size,
            duplication=self.duplication_level,
            validation=self.validation_level,
            callback=distributed_event.set)
        self.logic_queue.put(distribute)
        self.logger.info('start redistributing the file')

        # block until the file is distributed
        distributed_event.wait()
        self.logger.info('file redistributed')

        # remove the temporary file
        os.remove(file_path)

        self.callback()

        message = protocol.thread.thread_exit(
            thread_id=self.ident, success=True)
        self.logic_queue.put(message)

        self.logger.info(self.name + ' thread end')
