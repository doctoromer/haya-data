#!/usr/bin/env python
"""This module is executed by the user to start the program."""

import Queue
import logging
import logging.config
import optparse
import json

import sys
sys.dont_write_bytecode = True

import logic
import network
import gui

from utils import handle_except


@handle_except('other')
def main():
    """The main function of the server."""
    # parsing command line argumants
    parser = optparse.OptionParser()
    parser.add_option('-c', '--config', dest='config_file',
                      default='logging.json',
                      help='change the logging configuration file')
    parser.add_option('-p', '--port', dest='port', default='2048', type='int',
                      help='set custom connection port')

    options, args = parser.parse_args()

    # configurate the loggers of the threads
    with open(options.config_file, 'rb') as f:
        config = json.loads(f.read())
        logging.config.dictConfig(config)

    logger = logging.getLogger('other')
    logger.info('main thread started')

    logic_queue = Queue.Queue()
    gui_queue = Queue.Queue()
    network_queue = Queue.Queue()

    network_receiver_thread = network.NetworkReceiverThread(
        network_queue=network_queue,
        logic_queue=logic_queue,
        port=options.port
    )

    network_sender_thread = network.NetworkSenderThread(
        network_queue=network_queue,
        logic_queue=logic_queue,
        port=options.port)

    logic_thread = logic.LogicThread(
        logic_queue=logic_queue,
        gui_queue=gui_queue,
        network_queue=network_queue)

    gui_thread = gui.Gui(
        gui_queue=gui_queue,
        logic_queue=logic_queue)

    network_receiver_thread.start()
    network_sender_thread.start()
    logic_thread.start()
    gui_thread.main()

    logger.info('main thread ended')


if __name__ == '__main__':
    main()
