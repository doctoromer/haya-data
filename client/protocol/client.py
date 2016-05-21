"""This module contains functions to create the messages from the client."""
from protocol import __message


def block(block_type, name, number, content):
    """
    Create block message.

    Args:
        block_type (str): The block type.
        name (str): The file name.
        number (int): The block number.
        content (str): The block content.

    Returns:
        str: Block message.
    """
    return __message('block',
                     block_type=block_type,
                     name=name,
                     number=number,
                     content=content)


def file_sent(name):
    """
    Create file_sent message.

    Args:
        name (str): The file name.

    Returns:
        str: File_sent message.
    """
    return __message('file_sent', name=name)


def disk_state(total, free):
    """
    Create disk_state message.

    Args:
        total (int): Total bytes in the disk.
        free (int): Free bytes in the disk.

    Returns:
        str: Disk_state message.
    """
    return __message('disk_state',
                     total=total,
                     free=free)


def storage_state(blocks):
    """
    Create disk_state message.

    Args:
        blocks (list of dict): List of blocks information.
        client (str): The client.

    Returns:
        str: Storage_state message.
    """
    return __message('storage_state',
                     blocks=blocks)
