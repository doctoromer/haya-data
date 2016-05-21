"""This module contains encryption functions."""
import hashlib
import itertools

import pyaes


block_size = 32


def xor_strings(*strings):
    """
    Xor multiple strings.

    Padding shorter strings to match to the longest string.

    Args:
        *strings: Strings to be xored.

    Returns:
        str: The xor of the strings.
    """
    data_zip = list(itertools.izip_longest(*strings, fillvalue='\x00'))

    def xor_line(line):
        """Auxillary function to xor strings.

        Args:
            line (str): on line of the string.

        Returns:
            TYPE: Xor of a line.
        """
        return reduce(lambda a, b: chr(ord(a) ^ ord(b)), line)

    char_list = map(lambda x: xor_line(x), data_zip)
    return ''.join(char_list)


def hash_string(string):
    """
    Hash a string.

    Args:
        string (str): String for hashing.

    Returns:
        str: Hash of the string.
    """
    return hashlib.sha256(string).hexdigest()


def digest_key(key):
    """
    Hash a key to match to the block size.

    Args:
        key (str): The given key.

    Returns:
        str: The digested string.
    """
    return hash_string(key)[:block_size]


def encrypt(key, value):
    """
    Encrypt a string by key in AES256 cipher.

    Args:
        key (str): The encryption key.
        value (str): The plain text.

    Returns:
        str: The cipher text.
    """
    key = digest_key(key)
    cipher = pyaes.AESModeOfOperationCTR(key)
    crypted = cipher.encrypt(value)
    return crypted


def decrypt(key, value):
    """
    decrypt a string by key in AES256 cipher.

    Args:
        key (str): The decryption key.
        value (str): The cipher text.

    Returns:
        str: The plain text.
    """
    key = digest_key(key)
    cipher = pyaes.AESModeOfOperationCTR(key)
    return cipher.decrypt(value)
