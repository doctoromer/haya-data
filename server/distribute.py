"""The file distribution module.
"""
import os
import threading
import logging

from utils import handle_except
import encrypt
import protocol.server
import protocol


class Validator(object):
    """The validator class creates validation blocks.
    """

    def __init__(self):
        """Initialize the validator class.
        """
        self.__data = None
        self.__blocks = {}

    def update(self, block_data, number, fillvalue='\x00'):
        """
        Update the internal state of the validator.

        Args:
            block_data (str): Data block to be added to the xor.
            number (int): Number of the Block.
            fillvalue (str, optional): Value to pad shorter blocks.
        """
        if self.__data is None:
            self.__data = block_data
        else:
            self.__data = encrypt.xor_strings(self.__data, block_data)
        self.__blocks[number] = encrypt.hash_string(block_data)

    def reset(self):
        """Reset the internal state of the validator.
        """
        self.__data = None
        self.__blocks = {}

    def get_data(self):
        """
        Build and return the final validation block in format.

        Returns:
            str: the metadata block.
        """
        file_dict = {
            'hashes': self.__blocks,
            'xor': self.__data
        }
        return protocol.build(file_dict)


class DistributeThread(threading.Thread):
    """
    The distribution thread handles the file distribution to the clients.

    Attributes:
        block_size (int): The size of the blocks.
        callback (func, optional): A callback to be called
                after the thread finished
        clients (list of str): List of the clients.
        distribute_queue (Queue.Queue): The queue of the thread.
        duplication_level (int): How many times each block is duplicated.
        file_path (str): The path to target file.
        key (str): The encryption key.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        validation_level (int): The number of data block that each
            metadata block is covering.
    """

    def __init__(self, file_path,
                 block_size,
                 duplication_level,
                 validation_level,
                 clients,
                 key,
                 distribute_queue,
                 logic_queue,
                 callback=lambda: None):
        """
        Initialize the distribution thread.

        Args:
            file_path (str): The path to target file.
            block_size (int): The size of the blocks.
            duplication_level (int): How many times each block is duplicated.
            validation_level (int): The number of data block that each
            clients (list of str): List of the clients.
            key (str): The encryption key.
            distribute_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            callback (func, optional): A callback to be called
                after the thread finished
            metadata block is covering.
        """
        # initialize the thread class
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('distribute')

        # initialize the class variables
        self.file_path = file_path
        self.block_size = block_size
        self.duplication_level = duplication_level
        self.validation_level = validation_level
        self.clients = clients
        self.key = key
        self.distribute_queue = distribute_queue
        self.logic_queue = logic_queue
        self.callback = callback

    def send_block(self, client, block_type, name, number, content):
        """
        Send block to the logic thread.

        Args:
            client (str): The client ip address.
            block_type (str): The type of the block.
            name (str): The name of the file
            number (int): The number of the block.
            content (str): The content of the block.
        """
        log_params = (block_type, number, client)
        self.logger.debug('%s block number %s sent to %s' % log_params)

        encrypted = encrypt.encrypt(self.key, content)

        net_message = protocol.server.send_block(
            block_type=block_type,
            name=os.path.basename(self.file_path),
            number=number,
            content=encrypted
        )
        message = protocol.thread.send(message=net_message, client=client)
        self.logic_queue.put(message)

    def exit_thread(self, success=True):
        """Send exit message to the logic thread.

        Args:
            success (bool, optional): Description
        """
        exit_message = protocol.thread.thread_exit(
            thread_id=self.ident, success=success)
        self.logic_queue.put(exit_message)

        self.logger.info(self.name + ' thread ended')

    @handle_except('distribute')
    def run(self):
        """Execute the distribution thread."""
        self.logger.info(self.name + ' thread has started')

        # if file doesn't exist, report and exit
        if not os.path.exists(self.file_path):
            self.logger.error('file doesn\'t exist. exiting...')
            message = protocol.thread.error(
                thread_id=self.ident,
                message='file \'%s\' doesn\'t exist, distribution failed'
                % self.file_path)
            self.logic_queue.put(message)
            self.exit_thread()
            return

        # initialize variables for distributing the file
        file_size = os.stat(self.file_path).st_size
        block_size = self.block_size
        base_name = os.path.basename(self.file_path)

        # opening the target file for reading
        target_file = open(self.file_path, 'rb')

        self.logger.debug('"%s" opened, size is %s' %
                          (self.file_path, file_size))
        self.logger.info('distributing file %s' % base_name)

        # calculating several parameters
        block_number = file_size / self.block_size
        if file_size % self.block_size != 0:
            block_number += 1
        self.logger.info('calculated block number is %s' % block_number)

        # initialize the loop variables
        count = 1
        validation_count = 1
        data_client_pointer = 0
        metadata_client_pointer = 0
        running = True
        data = None
        validator = Validator()

        while running:

            # non block receive message
            try:
                message = self.distribute_queue.get(timeout=0.1)
            except:
                pass
            else:
                if message['type'] == 'exit':
                    self.exit_thread(success=False)
                    return

            # creating the block
            data = target_file.read(block_size)

            # if no data left, exit the loop
            if data == '':
                running = False
                break

            self.logger.debug('adding block %s to validation block %s' %
                              (count, validation_count))
            validator.update(data, count)

            # if the enough blocks sent, create and send validation block
            if count % self.validation_level == 0:

                self.send_block(
                    client=self.clients[data_client_pointer],
                    block_type=protocol.METADATA_BLOCK,
                    name=base_name,
                    number=validation_count,
                    content=validator.get_data()
                )
                validator.reset()
                self.logger.debug('resetting validation block %s' %
                                  validation_count)
                metadata_client_pointer += 1
                validation_count += 1

            if metadata_client_pointer >= len(self.clients):
                metadata_client_pointer = 0

            # duplicate the block to different clients
            for i in xrange(self.duplication_level):
                self.send_block(
                    client=self.clients[data_client_pointer],
                    block_type=protocol.DATA_BLOCK,
                    name=base_name,
                    number=count,
                    content=data
                )
                data_client_pointer += 1

                if data_client_pointer >= len(self.clients):
                    data_client_pointer = 0

            count += 1

        # if the last blocks aren't validated, create validation block
        if file_size % self.block_size != 0:
            self.send_block(
                client=self.clients[metadata_client_pointer],
                block_type=protocol.METADATA_BLOCK,
                name=base_name,
                number=validation_count,
                content=validator.get_data()
            )

        # executing exit operations
        target_file.close()

        self.callback()
        self.exit_thread()
