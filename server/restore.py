"""The restore thread module."""
import os
import threading
import logging
import pprint
import time

from utils import handle_except
from utils import build_file_name, parse_file_name, glob
import encrypt
import protocol


class RestoreThread(threading.Thread):
    """
    The restore thread class.

    Attributes:
        block_number (int): The number of the blocks in the file.
        clients (list of str): List of the clients.
        key (TYPE): Description
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        real_file (str): The path that the file will be restored into.
        restore_queue (Queue.Queue): The queue of the thread.
        temp (str): The path of the temporary directory.
        validation_level (int): The number of data block that each
            metadata block is covering.
        validation_number (int): The number of metadata blocks.
        virtual_file (str): the name of the file in the virtual storage.
    """

    def __init__(self,
                 real_file,
                 virtual_file,
                 block_number,
                 validation_level,
                 clients,
                 key,
                 restore_queue,
                 logic_queue,
                 temp='temp'):
        """
        Initialize the restore thread.

        Args:
            real_file (str): The path that the file will be restored into.
            virtual_file (str): the name of the file in the virtual storage.
            block_number (int): The number of the blocks in the file.
            validation_level (int): The number of data block that each
                metadata block is covering.
            clients (list of str): List of the clients.
            key (TYPE): Description
            restore_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            temp (str, optional): The path of the temporary directory.
        """
        # initialize the thread class
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('restore')

        # initialize the class variable
        self.real_file = real_file
        self.virtual_file = virtual_file
        self.block_number = block_number
        self.validation_level = validation_level

        # calculate the number of metadata blocks from the validation level
        self.validation_number = block_number / validation_level
        if block_number % validation_level != 0:
            self.validation_number += 1

        self.clients = dict((client, False) for client in clients)
        self.key = key
        self.restore_queue = restore_queue
        self.logic_queue = logic_queue
        self.temp = temp

    @handle_except('restore')
    def received_block(self, message):
        """
        Handle received block.

        Args:
            message (dict): The received message to process.
        """
        client = message['client']
        self.logger.debug('received %s block %s of file %s from %s' %
                          (message['block_type'],
                           message['number'],
                           message['name'],
                           client))

        # build the new block path
        file_path = os.path.join('%s', '%s', '%s') % \
            (self.temp, client,
             build_file_name(
                 block_type=message['block_type'],
                 name=message['name'],
                 number=message['number'])
             )

        # if temporary directory doesn't exist, create it
        if not os.path.exists(self.temp):
            os.mkdir(self.temp)

        # if clients' temporary directory doesn't exist, create them
        for client in self.clients:
            client_dir = os.path.join(self.temp, client)
            if not os.path.exists(client_dir):
                os.mkdir(client_dir)

        decrypted = encrypt.decrypt(self.key, message['content'])
        # write the content to file
        with open(file_path, 'wb') as f:
            f.write(decrypted)

    def get_blocks_names(self, client='*', block_type='*', number='*'):
        """
        Return list of paths of blocks matching the given arguments.

        Args:
            client (str, optional): The client directory.
            block_type (str, optional): The required block type.
            number (str, optional): The required block number.

        Returns:
            list of str: list of matching paths.
        """
        file_name = build_file_name(
            block_type=block_type,
            name=self.virtual_file,
            number=number)
        return glob(self.temp, client, file_name)

    def exit_thread(self, success=True):
        """Send exit message to the logic thread."""
        map(os.remove, self.get_blocks_names())

        exit_message = protocol.thread.thread_exit(
            thread_id=self.ident, success=success)
        self.logic_queue.put(exit_message)
        self.logger.info(self.name + ' thread end')

    @handle_except('restore')
    def run(self):
        """
        Execute the restore thread.

        The thread first collect all blocks from the clients.
        Then, It maps the received blocks to a giant dict.

        Example:
            {1:
                {blocks: {1: ['10.0.0.9/file.dat_1.data',
                             '10.0.0.10/file.dat_1.data',
                             '10.0.0.11/file.dat_1.data'],
                          2: ['10.0.0.9/file.dat_2.data',
                             '10.0.0.10/file.dat_2.data',
                             '10.0.0.11/file.dat_2.data'],
                          3: ['10.0.0.9/file.dat_3.data',
                             '10.0.0.10/file.dat_3.data',
                             '10.0.0.11/file.dat_3.data']},
                'path': '10.0.0.10/file.dat_1.metadata'},

        2:
                {blocks: {4: ['10.0.0.9/file.dat_4.data',
                             '10.0.0.10/file.dat_4.data',
                             '10.0.0.11/file.dat_4.data'],
                          5: ['10.0.0.9/file.dat_5.data',
                             '10.0.0.10/file.dat_5.data',
                             '10.0.0.11/file.dat_5.data'],
                          6: ['10.0.0.9/file.dat_6.data',
                             '10.0.0.10/file.dat_6.data',
                             '10.0.0.11/file.dat_6.data']},
                'path': '10.0.0.9/file.dat_2.metadata'}
            }

            After every block is mapped, the thread exemine if
            the file can be restored. If the file can be restored,
            the thread create missing parts and write the data to
            the path in 'self.real_file'.

        Raises:
            Exception: Description
        """
        self.logger.info(self.name + ' thread started')

        # receiving all blocks until the clients finished sending.
        start_time = time.time()
        while not all(self.clients.values()) and time.time() < start_time + 30:
            try:
                message = self.restore_queue.get(timeout=3)
            except:
                self.logger.debug('waiting for blocks...')
            else:
                # if received a massage, reset timeout
                start_time = time.time()

                message_type = message['type']
                self.logger.debug(
                    'received message of type \'%s\'' % message_type)

                if message_type == 'block':
                    self.received_block(message)
                elif message_type == 'file_sent':
                    self.clients[message['client']] = True
                elif message_type == 'exit':
                    self.exit_thread(success=False)
                    return
                else:
                    log = 'unknown message type: %s. message not processed'
                    self.logger.warning(log % message_type)

        self.logger.info('finished collecting blocks of file %s' %
                         self.virtual_file)

        # mapping the restored file blocks
        mapping = {}
        for path in self.get_blocks_names(block_type=protocol.METADATA_BLOCK):
            basename = os.path.basename(path)
            file_info = parse_file_name(basename)

            number = file_info['number']
            if number.isdigit():
                number = int(number)
                mapping[number] = {'path': path, 'blocks': {}}

        # insert records for missing metadata blocks into the mapping
        for metadata_number in xrange(1, self.validation_number + 1):
            if metadata_number not in mapping:
                mapping[metadata_number] = {'path': None, 'blocks': {}}

            start_number = 1 + self.validation_level * (metadata_number - 1)
            end_number = self.validation_level * metadata_number

            # insert paths of data blocks matching he missing metadata block
            for data_number in xrange(start_number, end_number + 1):
                blocks = mapping[metadata_number]['blocks']
                if data_number <= self.block_number:
                    blocks[data_number] = self.get_blocks_names(
                        block_type=protocol.DATA_BLOCK, number=data_number)

        self.logger.debug('file blocks mapping:\n' + pprint.pformat(mapping))

        # mapping missing / corrupted blocks
        valid_blocks = {}
        missing_data = {}
        missing_metadata = []
        validation_warning = True

        for metadata_number in mapping:
            metadata_path = mapping[metadata_number]['path']
            blocks_dict = mapping[metadata_number]['blocks']

            missing_data[metadata_number] = []

            # check if the metadata can be used
            valid_metadata = True
            if metadata_path is not None:
                try:
                    f = open(metadata_path, 'rb')
                    metadata = protocol.parse(f.read())
                    f.close()

                    if type(metadata) != dict:
                        raise Exception()

                except:
                    valid_metadata = False
            else:
                valid_metadata = False

            if valid_metadata:
                # if the metadata can be used, validate the blocks against it
                for block_number in blocks_dict:

                    if 'hashes' in metadata:
                        hashes = metadata['hashes']
                        if block_number in hashes:
                            block_hash = hashes[block_number]

                    block_list = blocks_dict[block_number]

                    if block_list == []:
                        missing_data[metadata_number].append(block_number)

                    for path in block_list:
                        f = open(path, 'rb')
                        content = f.read()
                        f.close()

                        validated_hash = encrypt.hash_string(content)
                        if validated_hash.lower() == block_hash.lower():
                            valid_blocks[block_number] = path
                            break

                '''
                if all variant of the blocks were tested against the metadata
                and none of them are valid, then add the block to the missing
                data. Later, try to recreate them
                '''
                for block_number in blocks_dict:
                    if block_number not in valid_blocks:
                        if block_number not in missing_data[metadata_number]:
                            missing_data[metadata_number].append(block_number)
            else:
                # if the metadata is not usable, choose the most common block
                missing_metadata.append(metadata_number)

                for block_number in blocks_dict:
                    if blocks_dict[block_number] != []:
                        content = []
                        for path in blocks_dict[block_number]:
                            f = open(path, 'rb')
                            content.append((path, f.read()))
                            f.close()

                        path, _ = max(set(content), key=content.count)
                        basename = os.path.basename(path)
                        number = parse_file_name(basename)['number']
                        number = int(number)
                        valid_blocks[number] = path
                    else:
                        missing_data[metadata_number].append(block_number)

                if validation_warning:
                    self.logger.warning('some blocks are not validated')
                    validation_warning = False

        self.logger.debug('valid blocks: %s' % pprint.pformat(valid_blocks))
        self.logger.debug('missing data: %s' % pprint.pformat(missing_data))
        self.logger.debug('missing metadata: %s' %
                          pprint.pformat(missing_metadata))

        # check if file can be restored, and recreate missing parts
        corrupted = False
        for metadata_number in missing_data:
            missing_count = len(missing_data[metadata_number])
            # if more then one block is missing per metadata block,
            # the file cannot be restored
            if missing_count > 1:
                corrupted = True
                break
            elif missing_count == 1:
                # if only one block is missing per metadata block, rebuild it
                if metadata_number not in missing_metadata:
                    # read metadata block
                    with open(mapping[metadata_number]['path'], 'rb') as f:
                        metadata = protocol.parse(f.read())

                    # calculate the first and last number of data block
                    # of the current metadata block
                    start_number = 1 + (self.validation_level *
                                        (metadata_number - 1))
                    end_number = self.validation_level * metadata_number
                    if end_number > self.block_number:
                        end_number = self.block_number

                    # restore the missing block using the metadata
                    restored = metadata['xor']
                    missing_block_number = missing_data[metadata_number][0]

                    for block_number in xrange(start_number, end_number + 1):
                        if block_number != missing_block_number:
                            with open(valid_blocks[block_number], 'rb') as f:
                                content = f.read()
                            restored = encrypt.xor_strings(restored, content)

                    # if the hash of the block is valid, write it to file
                    restored_hash = encrypt.hash_string(restored)
                    metadata_hash = metadata['hashes'][missing_block_number]

                    if restored_hash.lower() == metadata_hash.lower():
                        file_name = build_file_name(
                            block_type=protocol.DATA_BLOCK,
                            name=self.virtual_file,
                            number=missing_block_number)
                        path = os.path.join(self.temp, file_name)
                        restored_block = open(path, 'wb')
                        restored_block.write(restored)
                        restored_block.close()

                        valid_blocks[missing_block_number] = path
                    else:
                        corrupted = True
                        break
                else:
                    corrupted = True
                    break

        # if file can be restored, restore it
        if not corrupted:
            real_file = open(self.real_file, 'wb')
            for block_number in xrange(1, self.block_number + 1):
                path = valid_blocks[block_number]
                f = open(path, 'rb')
                real_file.write(f.read())
                f.close()
            real_file.close()
            self.logger.info('\'%s\' restored successfully' %
                             self.virtual_file)

        # else, tell the logic thread
        else:
            err = '\'%s\' is corrupted, could not restore' % self.virtual_file
            self.logger.error(err)
            message = protocol.thread.error(thread_id=self.ident, message=err)
            self.logic_queue.put(message)

        # executing exit operations
        self.exit_thread(success=not corrupted)
