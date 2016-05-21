"""This module handle the database."""
import sqlite3
import logging


class Database(object):
    """Database class provide inteface to the database.

    Attributes:
        conn (TYPE): Description
        file_name (TYPE): Description
        logger (TYPE): Description
    """

    def __init__(self, file_name):
        """
        Initialize the Database class.

        Creates the database file and scheme if necessery.

        Args:
            file_name (str): The database file name.
        """
        self.logger = logging.getLogger('database')

        self.file_name = file_name
        self.conn = sqlite3.connect(self.file_name)
        self.conn.execute('''
        CREATE TABLE IF NOT EXISTS files
        (NAME TEXT,
        FILE_SIZE INT,
        BLOCK_NUMBER INT,
        DUPLICATION_LEVEL INT,
        VALIDATION_LEVEL INT,
        KEY BLOB);''')

        self.logger.debug('connected to database')

    def insert(self, record):
        """
        Insert new record to the database.

        Args:
            record (tuple): The record to insert to the database.
        """
        cursor = self.conn.cursor()
        record = list(record)
        record[0] = unicode(record[0])
        record[5] = sqlite3.Binary(record[5])
        cursor.execute('INSERT INTO files VALUES(?, ?, ?, ?, ?, ?)', record)
        self.conn.commit()
        self.logger.debug('record %s inserted' % repr(record))

    def query(self, file_name):
        """
        Query record from database by file name.

        Args:
            file_name (str): The file name.

        Returns:
            tuple: The required record.
        """
        cursor = self.conn.cursor()
        file_name = unicode(file_name)
        cursor.execute('SELECT * FROM files WHERE NAME=?', (file_name,))
        self.logger.debug('queried record of file \'%s\'' % file_name)
        return cursor.fetchone()

    def query_all(self):
        """
        Query all records from database.

        Returns:
            list of tuple: The required records.
        """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM files')
        self.logger.debug('queried all record')
        return list(cursor)

    def delete(self, file_name):
        """
        Delete record from database by file name.

        Args:
            file_name (str): The file name.
        """
        cursor = self.conn.cursor()
        file_name = unicode(file_name)
        cursor.execute('DELETE FROM files WHERE NAME=?', (file_name,))
        self.conn.commit()
        self.logger.debug('record of file \'%s\' deleted' % file_name)

    def delete_all(self):
        """Delete all records from database."""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM files')
        self.conn.commit()
        self.logger.debug('all records deleted from database')

    def close(self):
        """Close the connection to the database."""
        self.conn.close()
        self.logger.debug('database closed')
