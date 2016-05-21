import threading
import logging
import logging.config
import os

import sys
sys.dont_write_bytecode = True

import protocol
import protocol.client
import protocol.thread
import diskutil
from utils import handle_except, build_file_name, glob
from utils import parse_file_name


class LogicThread(threading.Thread):
    """
    Summary

    Attributes:
        data_path (str): The path of the saved blocks.
        logger (logging.Logger): The logger of the thread.
        logic_queue (Queue.Queue): The queue of the thread.
        network_queue (Queue.Queue): The queue of the reciever thread.
        running (bool): The flag of the main loop.
    """

    def __init__(self, data_path, logic_queue, network_queue):
        """
        Initialize the logic thread.

        Args:
            data_path (str): The path of the saved blocks.
            logic_queue (Queue.Queue): The queue of the thread.
            network_queue (Queue.Queue): The queue of the reciever thread.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('logic')

        self.data_path = data_path
        self.logic_queue = logic_queue
        self.network_queue = network_queue

        self.running = True

    @handle_except('logic')
    def run(self):
        """Execute the logic thread."""
        while self.running:
            message = self.logic_queue.get()
            message_type = message['type']

            self.logger.info(
                'received message of type %s' % message_type)

            # store a block
            if message_type == 'send_block':
                file_name = build_file_name(
                    name=message['name'],
                    number=message['number'],
                    block_type=message['block_type'])

                file_path = os.path.join(self.data_path, file_name)

                content = message['content']

                try:
                    with open(file_path, 'wb') as f:
                        f.write(content)
                except:
                    self.logger.exception(
                        'an error acurred while trying to write to file:\n')

            # send a block to the server
            elif message_type == 'ask_block':
                file_name = build_file_name(
                    name=message['name'],
                    number=message['number'],
                    block_type=message['block_type'])

                for block in glob(self.data_path, file_name):
                    try:
                        with open(block, 'rb') as f:
                            content = f.read()
                    except:
                        self.logger.exception(
                            'an error acurred while reading file: %s' % block)
                    else:
                        real_file = os.path.basename(block)
                        block_info = parse_file_name(real_file)

                        net_message = protocol.client.block(
                            block_type=block_info['block_type'],
                            name=block_info['name'],
                            number=block_info['number'],
                            content=content)

                        thread_message = protocol.thread.send(
                            message=net_message)
                        self.network_queue.put(thread_message)

                # announce the server that all block were sent
                name = message['name']
                net_message_finished = protocol.client.file_sent(name)
                thread_message_finished = protocol.thread.send(
                    message=net_message_finished)
                self.network_queue.put(thread_message_finished)

            # delete blocks
            elif message_type == 'delete_block':
                file_name = file_name = build_file_name(
                    name=message['name'],
                    number=message['number'],
                    block_type=message['block_type'])

                block_list = glob(self.data_path, file_name)
                for file in block_list:
                    os.remove(file)

            # send the disk state to the server
            elif message_type == 'ask_disk_state':
                total = diskutil.total()
                free = diskutil.free()

                net_message = protocol.client.disk_state(
                    total=total, free=free)
                message = protocol.thread.send(
                    message=net_message)

                self.network_queue.put(message)

            # send the storage state to the server
            elif message_type == 'ask_storage_state':
                block_list = glob(self.data_path, '*_*.*')
                block_list = map(os.path.basename, block_list)
                block_list = map(parse_file_name, block_list)
                net_message = protocol.client.storage_state(blocks=block_list)
                message = protocol.thread.send(
                    message=net_message)
                self.network_queue.put(message)

            # end the thread
            elif message_type == 'kill':
                self.network_queue.put(message)
                self.running = False