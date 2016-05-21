"""This module contains functions to create messages between threads."""
import copy


def send(message, client='*'):
    """
    Create send message.

    Args:
        message (str): The message to be sent.
        client (str, optional): The client to send to.

    Returns:
        dict: Send message.
    """
    return {'type': 'send',
            'client': client,
            'message': message
            }


def distribute(file_path, block_size, duplication, validation):
    """
    Create distribute message.

    Args:
        file_path (str): The name of the file.
        block_size (int): The size of the blocks.
        duplication (int): The duplication level.
        validation (int): The validation level.

    Returns:
        dict: Distribute message.
    """
    return {'type': 'distribute',
            'file_path': file_path,
            'block_size': block_size,
            'duplication': duplication,
            'validation': validation
            }


def restore(real_file, virtual_file):
    """
    Create restore message.

    Args:
        real_file (str): The path to restore the file into.
        virtual_file (str): The name of the file in the storage.

    Returns:
        dict: Restore message.
    """
    return {'type': 'restore',
            'real_file': real_file,
            'virtual_file': virtual_file,
            }


def reconstruct():
    """
    Create reconstruct message.

    Returns:
        dict: Reconstruct message.
    """
    return {'type': 'reconstruct'}


def delete(virtual_file='*'):
    """
    Create delete message.

    Args:
        virtual_file (str): The name of the file to be deleted.

    Returns:
        dict: Delete message.
    """
    return {'type': 'delete',
            'virtual_file': virtual_file
            }


def connected(ip):
    """
    Create connected message.

    Args:
        ip (str): The client ip address.

    Returns:
        dict: Connected message.
    """
    return {'type': 'connected',
            'ip': ip
            }


def new_socket(socket):
    """
    Create new_socket message.

    Args:
        socket (socket.socket): The new socket.

    Returns:
        dict: New_socket message.
    """
    return {'type': 'new_socket',
            'socket': socket
            }


def received(message, client):
    """
    Create received message.

    Args:
        message (dict): The received message.
        client (str): The client ip address.

    Returns:
        dict: Received message.
    """
    return {'type': 'received',
            'message': copy.deepcopy(message),
            'client': client
            }


def ask_thread_list():
    """
    Create ask_thread_list message.

    Returns:
        dict: Ask_thread_list message.
    """
    return {'type': 'ask_thread_list'}


def thread_list(threads):
    """
    Create thread_list message.

    Args:
        threads (list): The list of threads and their details.
    Returns:
        dict: Thread_list message.
    """
    return {'type': 'thread_list',
            'thread_list': copy.deepcopy(threads)
            }


def refresh():
    """
    Create refresh message.

    Returns:
        dict Refresh message.
    """
    return {'type': 'refresh'}


def kill(client):
    """
    Create kill message.

    Args:
        client (str): The client to kill.
    Returns:
        dict: Kill message.
    """
    return {'type': 'kill',
            'client': client
            }


def kill_thread(name):
    """
    Create kill_thread message.

    Args:
        name (str): The name of the file asociated with this thread.
    Returns:
        dict: Kill_thread message.
    """
    return {'type': 'kill_thread',
            'name': name
            }


def disconnected(client):
    """
    Create diconnected message.

    Args:
        client (str): The client who disconnected.
    Returns:
        dict: Diconnected message.
    """
    return {'type': 'disconnected',
            'client': client
            }


def file_list(files):
    """
    Create file_list message.

    Args:
        files (list of str): List of files.

    Returns:
        dict: File_list message.
    """
    return {'type': 'file_list',
            'files': copy.deepcopy(files)
            }


def client_list(clients):
    """
    Create client_list message.

    Args:
        clients (list of str): List of clients.

    Returns:
        dict: Client_list message.
    """
    return {'type': 'client_list',
            'clients': copy.deepcopy(clients)
            }


def storage_state(blocks, client):
    """
    Create storage_state message.

    Args:
        blocks (list of str): List of blocks.
        client (str): The client ip address.

    Returns:
        dict: Storage_state message.
    """
    return {'type': 'storage_state',
            'blocks': copy.deepcopy(blocks),
            'client': client
            }


def disk_state(client, total, free):
    """
    Create disk_state message.

    Args:
        client (str): The client ip address.
        total (int): Total bytes in the disk.
        free (int): Free bytes in the disk.

    Returns:
        dict: Disk_state message.
    """
    return {'type': 'disk_state',
            'total': total,
            'free': free,
            'client': client
            }


def error(thread_id, message):
    """
    Create disk_state message.

    Args:
        thread_id (int): The thread id.
        message (str): Short description of the error.

    Returns:
        dict: Error message.
    """
    return {'type': 'error',
            'thread_id': thread_id,
            'message': message
            }


def lock_gui():
    """
    Create lock_gui message.

    Returns:
        dict: Lock_gui message.
    """
    return {'type': 'lock_gui'}


def release_gui():
    """
    Create release_gui message.

    Returns:
        dict: Release_gui message.
    """
    return {'type': 'release_gui'}


def thread_exit(thread_id, success):
    """
    Create thread_exit message.

    Args:
        thread_id (int): The thread id.
        success (bool): True if the thread filled his goal, else False.

    Returns:
        dict: Thread_exit message.
    """
    return {'type': 'thread_exit',
            'thread_id': thread_id,
            'success': success
            }


def exit():
    """
    Create exit message.

    Returns:
        dict: Exit message.
    """
    return {'type': 'exit'}
