"""This module contains functions that don't fit to any other module."""
import os
import logging
from glob import glob as old_glob


def handle_except(logger_name):
    """
    Wrap function in exception handler.

    Automatically catching exceptions and logging them in the given logger.

    Args:
        logger_name (str): The logger name.

    """
    def decorator(function):
        def inner(*args, **kwargs):

            logger = logging.getLogger(logger_name)
            try:
                return function(*args, **kwargs)
            except Exception:
                logger.exception('an exception was raised. traceback:')
        return inner
    return decorator


def build_file_name(name='*', number='*', block_type='*'):
    """
    Build file name by format.

    Args:
        name (str, optional): The file name.
        number (str, optional): The block number.
        block_type (str, optional): The block type.

    Returns:
        str: the file name.
    """
    return '%(name)s_%(number)s.%(block_type)s' % {
        'name': name,
        'number': number,
        'block_type': block_type
    }


def parse_file_name(file_name):
    """
    Parse file name by format.

    Args:
        file_name (str): The file name.

    Returns:
        dict: The parsed file name.
    """
    name, rest = file_name.rsplit('_', 1)
    number, block_type = rest.rsplit('.', 1)
    return {
        'name': name,
        'number': number,
        'block_type': block_type
    }


def glob(*path_parts):
    """
    Return list of files by pattern.

    This function wraps the standard module glob and adds some features.
    It receives parts of a path and concatenate
    it to  platform independent path.

    It also add built in unicode support.

    Args:
        *path_parts: list of path parts.

    Returns:
        list of matching paths.
    """
    path = unicode(os.path.join(*path_parts))
    return old_glob(path)
