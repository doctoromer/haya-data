"""
This module contains function to get the disk usage details
without needing c extensions. The module is platform indepentent,
and can be used on windows and unix systems.
"""
import os

__root = os.path.abspath(os.sep)


# unix
if hasattr(os, 'statvfs'):

    def total():
        """
        Return the total size of the disk in bytes.

        Returns:
            (long): The size of the disk in bytes.
        """
        st = os.statvfs(__root)
        total = st.f_blocks * st.f_frsize
        return total

    def free():
        """
        Return the free space of the disk in bytes.

        Returns:
            (long): The free space of the disk in bytes.
        """
        st = os.statvfs(__root)
        return st.f_bavail * st.f_frsize


# windows
elif os.name == 'nt':
    import ctypes
    import sys

    if isinstance(__root, unicode) or sys.version_info >= (3,):
        win_function = ctypes.windll.kernel32.GetDiskFreeSpaceExW
    else:
        win_function = ctypes.windll.kernel32.GetDiskFreeSpaceExA

    def total():
        """
        Return the total size of the disk in bytes.

        Returns:
            (long): The size of the disk in bytes.
        """
        _, _ = ctypes.c_ulonglong(), ctypes.c_ulonglong()
        total = ctypes.c_ulonglong()

        code = win_function(
            __root, ctypes.byref(_), ctypes.byref(total), ctypes.byref(_))

        if code == 0:
            raise ctypes.WinError()

        return total.value

    def free():
        """
        Return the free space of the disk in bytes.

        Returns:
            (long): The free space of the disk in bytes.
        """
        _, _ = ctypes.c_ulonglong(), ctypes.c_ulonglong()
        free = ctypes.c_ulonglong()

        code = win_function(
            __root, ctypes.byref(_), ctypes.byref(_), ctypes.byref(free))

        if code == 0:
            raise ctypes.WinError()

        return free.value

# platform not supported
else:
    raise NotImplementedError('unknown platform')
