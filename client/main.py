"""
This module is the main module of the client, and contains
almost all the necessery classes needed to run it.
"""

import Queue
import logging
import optparse
import json
import os

import sys
sys.dont_write_bytecode = True

import network
import logic


def main():
    """The main function of the client."""

    # parsing command line argumants
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config',
                      dest='config_file', default='logging.json',
                      help='set the logging configuration file.')
    parser.add_option('-d', '--datapath',
                      dest='data_path', default='data',
                      help='set the path of the data directory. ' +
                      'default is \'data\'.')
    parser.add_option('-s', '--server',
                      dest='server_ip', default='127.0.0.1',
                      help='set the server IP address. default is localhost.')
    parser.add_option('-p', '--port',
                      dest='port', default='2048', type='int',
                      help='set custom connection port.')

    options, args = parser.parse_args()

    # configurate the loggers of the threads
    with open(options.config_file, 'rb') as f:
        config = json.loads(f.read())
        logging.config.dictConfig(config)

    if not os.path.exists(options.data_path):
        os.mkdir(options.data_path)

    logic_queue = Queue.Queue()
    network_queue = Queue.Queue()

    network_receiver_thread = network.NetworkReceiverThread(
        server_ip=options.server_ip,
        port=options.port,
        network_queue=network_queue,
        logic_queue=logic_queue)

    network_sender_thread = network.NetworkSenderThread(
        network_queue=network_queue)

    logic_thread = logic.LogicThread(
        data_path=options.data_path,
        logic_queue=logic_queue,
        network_queue=network_queue)

    network_receiver_thread.start()
    network_sender_thread.start()
    logic_thread.start()

if __name__ == '__main__':
    main()
