"""This module handle the user interface."""
import threading
import logging
import os

import gtk
import gobject

import protocol.thread
from utils import handle_except

gobject.threads_init()


def get_selection(treeview, column):
    """
    Return the selection of the given tree view.

    Args:
        treeview (gtk.TreeView): The tree view containing the selection.
        column (int, optional): The column containing the value.

    Returns:
        object: The Value in the selected row, in the given column,
                or "None", if none of the rows are selected.
    """
    selection = treeview.get_selection()
    selection_store, selection_iter = selection.get_selected()
    if selection_iter is not None:
        return selection_store.get_value(selection_iter, column)
    else:
        return None


def size_format(num):
    """
    Return human readable display of memory quantaties.

    Args:
        num (int): Number of bytes

    Returns:
        str: String representation of the bytes.
    """
    unit_list = ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']
    for unit in unit_list:
        if num < 1024.0:
            return "%3.1f%sB" % (num, unit)
        num /= 1024.0
    return "%.1f%sB" % (num, 'Y')


class Gui(object):
    """
    The class of the user interface.

    Attributes:
        block_dict (dict): Contains information about the distributed blocks.
        builder (gtk.Builder): The builder of the gui.
        gui_queue (Queue.Queue): The queue of the thread.
        logic_queue (Queue.Queue): The queue of the logic thread.
        logger (logging.Logger): The logger of the class.
    """

    def __init__(self, gui_queue, logic_queue, file_name='gui.xml'):
        """
        Initialize the gui thread.

        Args:
            gui_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
            file_name (str, optional): The XML file that describes the gui.
        """
        self.logger = logging.getLogger('gui')

        self.gui_queue = gui_queue
        self.logic_queue = logic_queue

        # the builder is used to access the different widgets of the gui
        self.builder = gtk.Builder()
        self.builder.add_from_file(file_name)

        # block dict containing information about the block.
        # the keys are the clients' ip, and the values are list
        # of block records
        self.block_dict = {}

        gtk.widget_set_default_direction(gtk.TEXT_DIR_LTR)

        # adjust the main window
        window = self.builder.get_object('main_window')
        window.set_border_width(10)
        window.resize(700, 600)

        # add padding to the notebook tabs
        notebook = self.builder.get_object('main_notebook')
        for frame in notebook:
            label = notebook.get_tab_label(frame)
            label_text = label.get_text()
            label.set_property('width-chars', len(label_text) - 1)

        # add spacial column data rendering to the tree views
        self.add_tree_view_data_renderers()

        # The handler of the signals
        handlers = {
            'gtk_main_quit':
                self.exit,
            'on_file_system_download_clicked':
                self.file_system_download_clicked,
            'on_file_system_upload_clicked':
                self.file_system_upload_clicked,
            'on_upload_window_delete_event':
                self.upload_window_delete_event,
            'on_upload_ok_button_clicked':
                self.upload_ok_button_clicked,
            'on_upload_cancel_button_clicked':
                self.upload_cancel_button_clicked,
            'on_file_system_reconstruct_clicked':
                self.file_system_reconstruct_clicked,
            'on_file_system_delete_clicked':
                self.file_system_delete_clicked,
            'on_waiting_files_cancel_clicked':
                self.waiting_files_cancel_clicked,
            'on_file_status_files_tree_view_cursor_changed':
                self.file_status_callback,
            'on_clients_clients_tree_view_cursor_changed':
                self.clients_callback,
            'on_clients_refresh_clicked':
                self.clients_refresh_clicked,
            'on_clients_delete_clicked':
                self.clients_delete_clicked
        }

        self.builder.connect_signals(handlers)

        window.show_all()

    def add_tree_view_data_renderers(self):
        """Add functions that render the spacial data of the tree view."""
        def set_view_func(cell_name, column_name, callback, data=None):
            """
            Set a function to render a column.

            Args:
                cell_name (str): The cell name in self.builder.
                column_name (str): The column name in self.builder.
                callback (function): The renderer function.
                data (object, optional): Data that is passed to the callback.
            """
            cell = self.builder.get_object(cell_name)
            column = self.builder.get_object(column_name)
            column.set_cell_data_func(cell, callback, data)

        @handle_except('gui')
        def format_size_callback(column, cell, model, row_iter, data):
            """
            Format a column that display a size in bytes, to be human readable.

            Args:
                column (gtk.TreeViewColumn): The column.
                cell (gtk.CellRenderer): The cell renderer.
                model (gtk.TreeStore): The tree model.
                row_iter (gtk.TreeIter): The Iter of the current row.
                data (object): Additional data.
            """
            value = model.get_value(row_iter, data)
            cell.set_property('text', size_format(value))

        set_view_func('file_system_size_cell', 'file_system_size_column',
                      format_size_callback, 1)

        @handle_except('gui')
        def set_thread_type_callback(column, cell, model, row_iter, data=None):
            """
            Set the icon in row in the 'waiting files' view.

            Args:
                column (gtk.TreeViewColumn): The column.
                cell (gtk.CellRenderer): The cell renderer.
                model (gtk.TreeStore): The tree model.
                row_iter (gtk.TreeIter): The Iter of the current row.
                data (object): Additional data.
            """
            model_index = 0 if data is None else data
            value = model.get_value(row_iter, model_index).lower()

            if value == 'distribute':
                stock_id = gtk.STOCK_GO_UP
            elif value == 'restore':
                stock_id = gtk.STOCK_GO_DOWN
            elif value == 'reconstruct':
                stock_id = gtk.STOCK_CLEAR
            else:
                stock_id = gtk.STOCK_CANCEL

            cell.set_property('stock-id', stock_id)

        set_view_func('waiting_files_type_cell', 'waiting_files_type_column',
                      set_thread_type_callback)

        set_view_func('waiting_files_size_cell', 'waiting_files_size_column',
                      format_size_callback, 2)

        @handle_except('gui')
        def set_block_type_callback(column, cell, model, row_iter, data=None):
            """
            Set the icon in a row in several block displays.

            Args:
                column (gtk.TreeViewColumn): The column.
                cell (gtk.CellRenderer): The cell renderer.
                model (gtk.TreeStore): The tree model.
                row_iter (gtk.TreeIter): The Iter of the current row.
                data (object): Additional data.
            """
            model_index = 0 if data is None else data
            value = model.get_value(row_iter, model_index).lower()

            if value == 'data':
                stock_id = gtk.STOCK_FILE
            elif value == 'metadata':
                stock_id = gtk.STOCK_FIND_AND_REPLACE
            else:
                stock_id = gtk.STOCK_CANCEL

            cell.set_property('stock-id', stock_id)

        set_view_func('file_status_type_cell', 'file_status_type_column',
                      set_block_type_callback)

        @handle_except('gui')
        def disk_state_callback(column, cell, model, row_iter, data=None):
            """
            Calculate and display the disk state of a client.

            Args:
                column (gtk.TreeViewColumn): The column.
                cell (gtk.CellRenderer): The cell renderer.
                model (gtk.TreeStore): The tree model.
                row_iter (gtk.TreeIter): The Iter of the current row.
                data (object): Additional data.
            """
            total = model.get_value(row_iter, 1)
            free = model.get_value(row_iter, 2)
            if total != 0:
                disk_state = 100 * (free / (total * 1.0))
            else:
                disk_state = 0
            cell.set_property('value', disk_state)

        set_view_func('clients_disk_state_cell', 'clients_disk_state_column',
                      disk_state_callback)

        set_view_func('clients_used_space_cell', 'clients_used_space_column',
                      format_size_callback, 2)

        set_view_func('clients_total_space_cell', 'clients_total_space_column',
                      format_size_callback, 1)

        @handle_except('gui')
        def free_space_callback(column, cell, model, row_iter, data=None):
            """
            Calculate and display the free space of a client.

            Args:
                column (gtk.TreeViewColumn): The column.
                cell (gtk.CellRenderer): The cell renderer.
                model (gtk.TreeStore): The tree model.
                row_iter (gtk.TreeIter): The Iter of the current row.
                data (object): Additional data.
            """
            total = model.get_value(row_iter, 1)
            free = model.get_value(row_iter, 2)
            cell.set_property('text', size_format(total - free))

        set_view_func('clients_free_space_cell', 'clients_free_space_column',
                      free_space_callback)

        set_view_func('clients_blocks_type_cell', 'clients_blocks_type_column',
                      set_block_type_callback)

    @handle_except('gui')
    def process_message(self, message):
        """
        Process received messages.

        Args:
            message (dict): The received message.
        """
        message_type = message['type']
        self.logger.debug('received message of type %s' % message_type)

        # if the message is 'file_list', update the display
        if message_type == 'file_list':
            files = message['files']
            file_system_store = self.builder.get_object('file_system_store')
            file_system_store.clear()
            for f in files:
                file_system_store.append(None, f)

        # if the message is 'thread_list', update the gui.
        elif message_type == 'thread_list':
            waiting_files_store = self.builder.get_object(
                'waiting_files_store')
            waiting_files_store.clear()

            threads = message['thread_list']
            for ident in threads:
                thread = threads[ident]

                record = (thread['thread_type'], thread['name'],
                          thread['file_size'], thread['block_number'],
                          thread['duplication'], thread['validation'])
                waiting_files_store.append(None, record)

        # if the message is 'storage_state', update the display
        elif message_type == 'storage_state':
            client = message['client']
            self.block_dict[client] = message['blocks']
            self.logger.debug(
                'list of blocks and clients:\n%s' % self.block_dict)

        # if the message is 'client_list', update the gui.
        elif message_type == 'client_list':
            clients_store = self.builder.get_object('clients_store')
            clients_store.clear()
            self.builder.get_object('clients_blocks_store').clear()

            clients = message['clients']

            # if no clients are connected, lock the gui, else release it
            buttons_state = len(clients) != 0
            self.control_buttons(buttons_state)

            for client in clients:
                clients_store.append(None, (client, 0, 0))
            self.block_dict = {
                k: v for k, v in self.block_dict.iteritems() if k in clients}

        # if the message is 'disk_state', update the display
        elif message_type == 'disk_state':
            clients_store = self.builder.get_object('clients_store')
            for client in clients_store:
                client_iter = client.iter
                client_ip = clients_store.get(client_iter, 0)[0]

                if client_ip == message['client']:

                    total = message['total']
                    free = message['free']
                    clients_store.set(
                        client_iter, 1, total, 2, total - free)

        # if the message is 'error', display error message.
        elif message_type == 'error':
            self.display_error(message['message'])

        # else, log warning
        else:
            self.logger.warning('unknown message type: ' + message_type)

    def display_error(self, message):
        """
        Display an error message.

        Args:
            message (str): The error message to display.
        """
        self.logger.debug('display error: %s' % message)
        dialog = gtk.MessageDialog(
            type=gtk.MESSAGE_ERROR,
            buttons=gtk.BUTTONS_CLOSE)
        dialog.set_markup(message)

        dialog.run()
        dialog.destroy()

    def control_buttons(self, enable):
        """
        Enable / disable the buttons.

        Args:
            enable (bool): True to enable, False to disable.
        """
        for button in self.builder.get_object('file_system_toolbar'):
            button.set_sensitive(enable)
        for button in self.builder.get_object('waiting_files_toolbar'):
            button.set_sensitive(enable)
        for button in self.builder.get_object('clients_toolbar'):
            button.set_sensitive(enable)

    def hide_upload_window(self):
        """Hide the upload window."""
        self.builder.get_object('upload_window').hide()

    @handle_except('gui')
    def file_system_download_clicked(self, widget, data=None):
        """
        Download a file form the storage.

        This method retieve the name of the specified file,
        open a file chooser, and start a restore thread.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        file_system_tree_view = self.builder.get_object(
            'file_system_tree_view')
        virtual_file_name = get_selection(file_system_tree_view, 0)

        if virtual_file_name is not None:
            dialog = gtk.FileChooserDialog(
                title='download file',
                action=gtk.FILE_CHOOSER_ACTION_SAVE,
                buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_default_response(gtk.RESPONSE_OK)

            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                real_file_name = unicode(dialog.get_filename())

                restore = protocol.thread.restore(
                    real_file=real_file_name,
                    virtual_file=virtual_file_name)
                self.logic_queue.put(restore)
            dialog.destroy()

    @handle_except('gui')
    def file_system_upload_clicked(self, widget, data=None):
        """
        Display the upload window.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        upload_window = self.builder.get_object('upload_window')
        upload_window.resize(600, 500)
        upload_window.show_all()

    @handle_except('gui')
    def upload_window_delete_event(self, widget, data=None):
        """
        Hide the upload window when closed instead of destorying it.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        self.hide_upload_window()
        return True

    @handle_except('gui')
    def upload_ok_button_clicked(self, widget, data=None):
        """
        Upload a file to the storage.

        This method retrieves the distribution parameters from the window,
        Checks if the name of the file don't collide with an existing file
        in the storage, and if so, it starts a distribution thread.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        file_path = unicode(self.builder.get_object(
            'upload_file_chooser').get_file().get_path())

        block_size = os.path.getsize(file_path) / int(self.builder.get_object(
            'block_number_scale').get_value())

        validation = int(self.builder.get_object(
            'validation_scale').get_value())

        duplication = int(self.builder.get_object(
            'duplication_scale').get_value())

        can_distribute = True
        file_system_store = self.builder.get_object('file_system_store')
        base_name = os.path.basename(file_path)
        for i in file_system_store:
            if i[0] == base_name:
                can_distribute = False
                self.display_error(
                    'The file already exists in the storage.')

        if can_distribute:
            distribute = protocol.thread.distribute(
                file_path=file_path,
                block_size=block_size,
                validation=validation,
                duplication=duplication)

            self.logic_queue.put(distribute)
            self.hide_upload_window()

    @handle_except('gui')
    def upload_cancel_button_clicked(self, widget, data=None):
        """
        Hide the uplaod window when the cancel button clicked.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        self.hide_upload_window()

    @handle_except('gui')
    def file_system_reconstruct_clicked(self, widget, data=None):
        """
        Start a reconstruction thread.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        file_system_tree_view = self.builder.get_object(
            'file_system_tree_view')
        name = get_selection(file_system_tree_view, 0)
        if name is not None:
            self.logic_queue.put(protocol.thread.reconstruct(name=name))

    @handle_except('gui')
    def file_system_delete_clicked(self, widget, data=None):
        """
        Delete a file from the storage.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        file_system_tree_view = self.builder.get_object(
            'file_system_tree_view')
        file_name = get_selection(file_system_tree_view, 0)
        if file_name is not None:
            message = protocol.thread.delete(file_name)
            self.logic_queue.put(message)

    @handle_except('gui')
    def waiting_files_cancel_clicked(self, widget, data=None):
        """
        Cancel a thread of file that is currently is busy.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        waiting_files_view = self.builder.get_object('waiting_files_tree_view')
        selection = get_selection(waiting_files_view, 1)
        if selection is not None:
            message = protocol.thread.kill_thread(name=selection)
            self.logic_queue.put(message)

    @handle_except('gui')
    def file_status_callback(self, widget, data=None):
        """
        Callback for changing the blocks displayed in the file status.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        file_status_files_tree_view = self.builder.get_object(
            'file_status_files_tree_view')
        selection = get_selection(file_status_files_tree_view, 0)
        file_status_blocks_tree_view = self.builder.get_object(
            'file_status_blocks_tree_view')
        store = file_status_blocks_tree_view.get_model()
        store.clear()

        for client in self.block_dict:
            for block in self.block_dict[client]:
                if block['name'] == selection:
                    store.append(None, (block['block_type'],
                                        int(block['number']),
                                        client))

    @handle_except('gui')
    def clients_callback(self, widget, data=None):
        """
        Callback for changing the displayed blocks in the client view.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        selection = get_selection(
            self.builder.get_object('clients_clients_tree_view'), 0)
        store = self.builder.get_object('clients_blocks_store')
        store.clear()

        # if client is connected and send storage_state message,
        # his ip will appear in the blocks_dict variable
        if selection in self.block_dict:
            for block in self.block_dict[selection]:
                block_record = (block['block_type'],
                                block['name'],
                                int(block['number']))
                store.append(None, block_record)

    @handle_except('gui')
    def clients_refresh_clicked(self, widget, data=None):
        """
        Refresh the display.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        message = protocol.thread.refresh()
        self.logic_queue.put(message)

    @handle_except('gui')
    def clients_delete_clicked(self, widget, data=None):
        """
        DIsconnect a client.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        clients_tree_view = self.builder.get_object(
            'clients_clients_tree_view')
        client = get_selection(clients_tree_view, 0)
        if client is not None:
            self.logic_queue.put(protocol.thread.kill(client=client))

    @handle_except('gui')
    def exit(self, widget, data=None):
        """
        Close the program.

        Args:
            widget (gtk.Widget): The widget that fired the event
            data (object, optional): Additional data.
        """
        # exit the event loop
        gtk.main_quit()

        message = protocol.thread.exit()
        # send an exit message the the rest of the program
        self.logic_queue.put(message)
        # send an exit message to the helper thread
        self.gui_queue.put(message)

    @handle_except('gui')
    def main(self):
        """Start the main event loop."""
        helper = GuiHelperThread(
            queue=self.gui_queue,
            callback=self.process_message)
        helper.start()
        gtk.main()


class GuiHelperThread(threading.Thread):
    """
    This thread helps the gui process incoming messages.

    The gui can't process messages in his main loop, because
    it will block the gui. This helper thread receive the messages,
    and then add a one time callback to each message to process it.

    Attributes:
        callback (function): The callback to be called.
        logger (logging.Logger): The logger of the class.
        queue (Queue.Queue): The queue to get messages from.
    """

    def __init__(self, queue, callback):
        """
        Initialize the helper thread.

        Args:
            callback (function): The callback to be called.
            queue (Queue.Queue): The queue to get messages from.
        """
        current_class = self.__class__
        thread_name = current_class.__name__
        super(current_class, self).__init__(name=thread_name)
        self.logger = logging.getLogger('gui')

        self.queue = queue
        self.callback = callback

    @handle_except('gui')
    def run(self):
        """Execute the helper thread."""
        running = True
        while running:
            message = self.queue.get()
            if message['type'] == 'exit':
                running = False
            else:
                gobject.idle_add(self.callback, message)
