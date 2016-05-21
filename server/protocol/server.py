"""This module contains functions to create the messages from the server."""
from protocol import __message


def ask_block(name, block_type='*', number='*'):
    """
    Create ask_block message.

    Args:
        name (str): The name of the file.
        block_type (str, optional): The block type.
        number (str, optional): The block number.

    Returns:
        str: Ask_block message.
    """
    return __message('ask_block',
                     block_type=block_type,
                     name=name,
                     number=number)


def send_block(block_type, name, number, content):
    """
    Create send_block message.

    Args:
        block_type (str): The block type.
        name (str): The name of the file.
        number (str, optional): The block number.
        content (str): The block content.

    Returns:
        str: Send_block message.
    """
    return __message('send_block',
                     block_type=block_type,
                     name=name,
                     number=number,
                     content=content)


def delete_block(name='*', block_type='*', number='*'):
    """
    Create delete_block message.

    Args:
        name (str): The name of the file.
        block_type (str, optional): The block type.
        number (str, optional): The block number.

    Returns:
        str: Delete_block message.
    """
    return __message('delete_block',
                     block_type=block_type,
                     name=name,
                     number=number)


def ask_disk_state():
    """
    Create ask_disk_state message.

    Returns:
        str: Ask_disk_state message.
    """
    return __message('ask_disk_state')


def ask_storage_state():
    """
    Create ask_storage_state message.

    Returns:
        str: Ask_storage_state message.
    """
    return __message('ask_storage_state')


def kill():
    """
    Create kill message.

    Returns:
        str: Kill message.
    """
    return __message('kill')
