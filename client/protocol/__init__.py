"""
The __init__ module of the protocol package.

This module contains some fuctions common to all sub packages.

Attributes:
    DATA_BLOCK (str): Data block type string.
    METADATA_BLOCK (str): Metadata block type string.
    build (function): Message building function.
    parse (function): message parsing function.
"""

import msgpack
import struct
import zlib

DATA_BLOCK = 'data'
METADATA_BLOCK = 'metadata'


def parse(message):
    return msgpack.loads(zlib.decompress(message))


def build(message):
    return zlib.compress(msgpack.dumps(message))

# parse = msgpack.loads
# build = msgpack.dumps


def __message(message_type, **kwargs):
    """
    Return a message as string.

    Args:
        message_type (str): The message type.
        **kwargs: Keyword to create the message.

    Return:
        str: The message as a string.
    """
    kwargs['type'] = message_type
    return wrap(build(kwargs))


def wrap(string):
    """
    Wrap a string in a message frame for sending it in a socket.

    Args:
        string (str): The string to wrap.

    Returns:
        str: The wraped string.
    """
    return struct.pack('>L', len(string)) + string


def get_size(string):
    """
    Return the size of a message wraped by the wrap protocol

    Args:
        string (str): The wraped string.

    Returns:
        int: the size of the message.
    """
    return struct.unpack('>L', string[:4])[0]
