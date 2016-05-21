"""The reconstruct thread module."""
import threading
import logging
import os

import protocol.thread
from utils import handle_except, glob


class ReconstructThread(threading.Thread):
    """
    The reconstruction thread handles the reconstruction of the system.

    Attributes:
        file_records (list of tuple): Records of all the files in the database.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        reconstruct_queue (Queue.Queue): The queue of the thread.
        temp (str): Temporary directory to store the restored files.
    """

    def __init__(self,
                 file_records,
                 reconstruct_queue,
                 logic_queue,
                 temp='temp'):
        """
        Initialize the system reconstruction thread.

        Args:
            file_records (list of tuple): Records of all the files in
                the database.
            reconstruct_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            temp (str): Temporary directory to store the restored files.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('reconstruct')

        self.file_records = file_records
        self.reconstruct_queue = reconstruct_queue
        self.logic_queue = logic_queue
        self.temp = temp

    @handle_except('reconstruct')
    def run(self):
        """Execute the system reconstruction thread."""
        reconstruct_dir = os.path.join(self.temp, 'reconstruct')

        # if the temporary directory doesn't exist, create it
        if not os.path.exists(self.temp):
            os.mkdir(self.temp)

        # if the reconstruction directory doesn't exist, create it
        if not os.path.exists(reconstruct_dir):
            os.mkdir(reconstruct_dir)

        # restore all files in the database
        for record in self.file_records:
            name = record[0]
            message = protocol.thread.restore(
                real_file=os.path.join(reconstruct_dir, name),
                virtual_file=name)
            self.logic_queue.put(message)

        self.logger.info('start restoring the files')

        # waiting for all files to be restored
        self.logic_queue.put(
            protocol.thread.ask_thread_list())

        still_restoring = True
        while still_restoring:
            try:
                message = self.reconstruct_queue.get(timeout=0.1)
            except:
                self.logic_queue.put(
                    protocol.thread.ask_thread_list())
            else:
                thread_list = message['thread_list']
                still_restoring = 'restore' in map(
                    lambda x: thread_list[x]['thread_type'], thread_list)

        self.logger.info('all files restored')

        # delete all files from storage
        message = protocol.thread.delete()
        self.logic_queue.put(message)

        self.logger.info('all files deleted from storage')

        # remove corrupted files from the list
        restored_files = glob(reconstruct_dir, '*')
        restored_files = map(os.path.basename, restored_files)
        self.file_records = filter(
            lambda x: x[0] in restored_files, self.file_records)

        # redistribute all the files
        for record in self.file_records:
            name, file_size, block_number, duplication, validation, _ = record

            file_path = os.path.join(reconstruct_dir, name)
            block_size = file_size / block_number
            if file_size % block_number != 0:
                block_size += 1

            distribute = protocol.thread.distribute(
                file_path=file_path,
                block_size=block_size,
                duplication=duplication,
                validation=validation)

            self.logic_queue.put(distribute)

        self.logger.info('start redistributing the files')

        # check that all files redistributed
        self.logic_queue.put(
            protocol.thread.ask_thread_list())

        still_distributing = True
        while still_distributing:
            message = self.reconstruct_queue.get()
            thread_list = message['thread_list']
            still_distributing = 'distribute' in map(
                lambda x: thread_list[x]['thread_type'], thread_list)

        self.logger.info('all files redistributed')

        for record in self.file_records:
            name = os.path.join(reconstruct_dir, record[0])
            os.remove(name)

        message = protocol.thread.thread_exit(
            thread_id=self.ident, success=True)
        self.logic_queue.put(message)

        self.logger.info(self.name + ' thread end')
