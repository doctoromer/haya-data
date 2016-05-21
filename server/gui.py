"""This module handle the user interface."""
import logging
import os

import gobject
import gtk

import protocol.thread
from utils import handle_except

gobject.threads_init()


def get_selection(treeview, column=0):
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
        if abs(num) < 1024.0:
            return "%3.1f%sB" % (num, unit)
        num /= 1024.0
    return "%.1f%sB" % (num, 'Y')


class Gui(object):
    """
    The class of the user interface.

    Attributes:
        block_dict (dict): Contains the mapping of the storage.
        chosen_block_size (int): The current chosen block size.
        chosen_duplication_level (int): The current chosen duplication level.
        chosen_file (str): The current chosen file path.
        chosen_validation_level (int): The current chosen validation level.
        client_blocks_store (gtk.TreeStore): The store of the blocks
            in each client.
        client_blocks_view (gtk.TreeView): The view of the blocks
            in each client.
        clients_store (gtk.TreeStore): The store of the clients.
        clients_toolbar (TYPE): Description
        clients_view (gtk.TreeView): The clients view.
        file_blocks_store (gtk.TreeStore): The store of the blocks
            of each file.
        file_blocks_view (gtk.TreeView): The view of the blocks of each file.
        file_status_view (gtk.TreeView): The view of the file status.
        file_store (gtk.TreeStore): The store of the file status.
        file_system_toolbar (TYPE): Description
        file_system_view (gtk.TreeView): The store of the file system.
        gui_queue (Queue.Queue): The queue of the thread.
        logger (TYPE): Description
        logic_queue (Queue.Queue): The queue of the logic thread.
        page_dict (dict): The dictionary that contains the pages of the gui.
        waiting_files_store (TYPE): Description
        waiting_files_toolbar (TYPE): Description
        waiting_files_view (TYPE): Description
        window (gtk.Window): Description
    """

    @handle_except('gui')
    def __init__(self, gui_queue, logic_queue):
        """
        Initialize the gui thread.

        Args:
            gui_queue (Queue.Queue): The queue of the thread.
            logic_queue (Queue.Queue): The queue of the logic thread.
        """
        self.logger = logging.getLogger('gui')

        # create and configure the main window
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        gtk.widget_set_default_direction(gtk.TEXT_DIR_LTR)
        self.window.set_title('Haya data - Distirbuted storage of ' +
                              'data over network, made by omer sarig')
        self.window.set_border_width(10)
        self.window.connect('destroy', self.exit)
        self.window.resize(700, 600)

        # dict containing the different pages
        self.page_dict = {}

        # *** various TreeStore's and TreeView's for displaing the data ***

        # stores information on the files in the storage
        self.file_store = gtk.TreeStore(str, str, str, str, str)

        # stores information on the files currently being distributed
        self.waiting_files_store = gtk.TreeStore(
            gtk.gdk.Pixbuf, str, str, str, int, int)

        # stores information of the blocks of each file
        self.file_blocks_store = gtk.TreeStore(gtk.gdk.Pixbuf, str, str)

        # stores information of the connected clients
        self.clients_store = gtk.TreeStore(str, int, str, str, str)

        # stores information of the blocks of each client
        self.client_blocks_store = gtk.TreeStore(gtk.gdk.Pixbuf, str, str)

        # view the files in the storage
        self.file_system_view = gtk.TreeView(self.file_store)

        # view the files currently being distributed
        self.waiting_files_view = gtk.TreeView(self.waiting_files_store)

        # view the file list in the file status display
        self.file_status_view = gtk.TreeView(self.file_store)

        # view the blocks of each file
        self.file_blocks_view = gtk.TreeView(self.file_blocks_store)

        # view the connected clients
        self.clients_view = gtk.TreeView(self.clients_store)

        # view the blocks of each client
        self.client_blocks_view = gtk.TreeView(self.client_blocks_store)

        # the toolbars of the gui
        self.file_system_toolbar = gtk.Toolbar()
        self.waiting_files_toolbar = gtk.Toolbar()
        self.clients_toolbar = gtk.Toolbar()

        # block dict containing information about the block.
        # the keys are the clients' ip, and the values are list
        # of block records
        self.block_dict = {}

        # queues for communication with other threads
        self.gui_queue = gui_queue
        self.logic_queue = logic_queue

        # stores the current information about the file
        # the user is uploading to the storage
        self.chosen_block_size = None
        self.chosen_validation_level = None
        self.chosen_duplication_level = None
        self.chosen_file = None

        # add idle call for processing incoming messages from different thread
        gobject.idle_add(self.get_messages)

        # create the UI
        notebook = gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        self.window.add(notebook)

        page_names = ['file system', 'waiting files', 'file status', 'clients']

        for name in page_names:
            frame = gtk.Frame()
            frame.set_border_width(0)
            frame.set_size_request(100, 75)
            frame.set_shadow_type(gtk.SHADOW_NONE)
            frame.show()

            page_label = gtk.Label(name)
            page_label.set_property('width-chars', len(name) - 1)
            notebook.append_page(frame, page_label)

            self.page_dict[name] = frame

        self.create_file_status()
        self.create_waiting_files()
        self.create_file_system()
        self.create_clients()

        notebook.show()
        self.window.show()

    @handle_except('gui')
    def get_messages(self):
        """Get messages from the gui queue."""
        try:
            message = self.gui_queue.get(timeout=0.1)
        except:
            pass
        else:
            self.process_message(message)
        return True

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
            self.file_store.clear()
            for f in files:
                f = list(f)
                f[1] = size_format(f[1])
                self.file_store.append(None, f)

        # if the message is 'storage_state', update the display
        elif message_type == 'storage_state':
            client = message['client']
            self.block_dict[client] = message['blocks']
            self.logger.debug(
                'list of blocks and clients:\n%s' % self.block_dict)

        # if the message is 'disk_state', update the display
        elif message_type == 'disk_state':

            for client in self.clients_store:
                client_iter = client.iter
                client_ip = self.clients_store.get(client_iter, 0)[0]

                if client_ip == message['client']:

                    total = message['total']
                    free = message['free']

                    self.clients_store.set(
                        client_iter,
                        1, 100 * (1 - free / (total * 1.0)),
                        2, size_format(total),
                        3, size_format(total - free),
                        4, size_format(free))

        # if the message is 'lock_gui', lock the buttons.
        elif message_type == 'lock_gui':
            self.control_buttons(False)

        # if the message is 'release_gui', release the buttons.
        elif message_type == 'release_gui':
            self.control_buttons(True)

        # if the message is 'error', display error message.
        elif message_type == 'error':
            self.display_error(message['message'])

        # if the message is 'client_list', update the gui.
        elif message_type == 'client_list':
            self.clients_store.clear()
            self.client_blocks_store.clear()

            clients = message['clients']

            # if no clients are connected, lock the gui, else release it
            buttons_state = len(clients) != 0
            self.control_buttons(buttons_state)

            for client in clients:
                self.clients_store.append(None, (client, 0, 0, 0, 0))
            self.block_dict = {
                k: v for k, v in self.block_dict.iteritems() if k in clients}

        # if the message is 'thread_list', update the gui.
        elif message_type == 'thread_list':
            self.waiting_files_store.clear()

            threads = message['thread_list']
            restore = gtk.gdk.pixbuf_new_from_file('icons/upload.png')
            distribute = gtk.gdk.pixbuf_new_from_file('icons/download.png')

            for ident in threads:
                thread = threads[ident]
                thread_type = thread['thread_type']
                img = None
                if thread_type == 'restore':
                    img = restore
                elif thread_type == 'distribute':
                    img = distribute

                record = (img, thread['name'],
                          size_format(thread['file_size']),
                          thread['block_number'], thread['duplication'],
                          thread['validation'])
                self.waiting_files_store.append(None, record)

        # else, log warning
        else:
            self.logger.warning('unknown message type: ' + message_type)

    def control_buttons(self, enable):
        """
        Enable / disable the buttons.

        Args:
            enable (bool): True to enable, False to disable.
        """
        for button in self.file_system_toolbar:
            button.set_sensitive(enable)
        for button in self.waiting_files_toolbar:
            button.set_sensitive(enable)
        for button in self.clients_toolbar:
            button.set_sensitive(enable)

    def display_error(self, message):
        """
        Display an error message.

        Args:
            message (str): The error message to display.
        """
        dialog = gtk.MessageDialog(
            type=gtk.MESSAGE_ERROR,
            buttons=gtk.BUTTONS_CLOSE)
        dialog.set_markup(message)

        dialog.run()
        dialog.destroy()

    ##################################################

    def upload(self, data):
        """
        Callback for displaying the upload interface.

        Args:
            data (object): Additional data.
        """
        if len(self.block_dict) == 0:
            self.display_error(
                'There are no clients connected, can\'t distribute file.')
            return

        upload_window = gtk.Window()
        upload_window.set_title('upload file')
        self.window.set_border_width(10)

        vbox = gtk.VBox(spacing=3)

        # create block size field
        block_size_hbox = gtk.HBox()

        block_size_label = gtk.Label('block size: ')
        block_size_label.show()
        block_size_hbox.pack_start(block_size_label)

        block_size_adj = gtk.Adjustment(1.0, 16.0, 8192.0, 1.0, 5.0, 0.0)
        block_size_spinner = gtk.SpinButton(block_size_adj, 0, 0)
        block_size_spinner.set_wrap(True)
        block_size_spinner.show()
        block_size_hbox.pack_start(block_size_spinner, False, True, 0)

        block_size_hbox.show()
        vbox.pack_start(block_size_hbox)

        # create validation field
        validation_hbox = gtk.HBox()

        validation_label = gtk.Label('validation level: ')
        validation_label.show()
        validation_hbox.pack_start(validation_label)

        validation_adj = gtk.Adjustment(1.0, 2.0, 20.0, 1.0, 5.0, 0.0)
        validation_spinner = gtk.SpinButton(validation_adj, 0, 0)
        validation_spinner.set_wrap(True)
        validation_spinner.show()
        validation_hbox.pack_start(validation_spinner, False, True, 0)

        validation_hbox.show()
        vbox.pack_start(validation_hbox)

        # create duplication field
        duplication_hbox = gtk.HBox()

        duplication_label = gtk.Label('duplication level: ')
        duplication_label.show()
        duplication_hbox.pack_start(duplication_label)

        duplication_adj = gtk.Adjustment(1.0, 1.0, 20.0, 1.0, 5.0, 0.0)
        duplication_spinner = gtk.SpinButton(duplication_adj, 0, 0)
        duplication_spinner.set_wrap(True)
        duplication_spinner.show()
        duplication_hbox.pack_start(duplication_spinner, False, True, 0)

        duplication_hbox.show()
        vbox.pack_start(duplication_hbox)

        # create file choosing field
        file_hbox = gtk.HBox()

        file_label = gtk.Label('file level: ')
        file_label.show()
        file_hbox.pack_start(file_label)

        file_button = gtk.Button('choose file')
        file_button.connect('clicked', self.file_dialog, None)
        file_button.show()
        file_hbox.pack_start(file_button)

        file_hbox.show()
        vbox.pack_start(file_hbox)

        buttons_hbox = gtk.HBox()

        ok_button = gtk.Button('OK')
        cancel_button = gtk.Button('cancel')

        def get_settings(widget, data):
            """
            Callback for update the setting when th OK button is clicked.

            Args:
                widget (gtk.Widget): The widget fire the event
                data (object): Additional data.
            """
            self.chosen_block_size = int(block_size_spinner.get_value())
            self.chosen_validation_level = int(validation_spinner.get_value())
            self.chosen_duplication_level = int(
                duplication_spinner.get_value())

        ok_button.connect('clicked', get_settings, None)

        ok_button.connect('clicked', self.ok_button_callback, None)
        cancel_button.connect('clicked', self.cancel_button_callback, None)

        def close_upload(widget, data):
            """
            Callback for closing the upload interface.

            Args:
                widget (gtk.Widget): The widget fire the event
                data (object): Additional data.
            """
            upload_window.destroy()

        ok_button.connect('clicked', close_upload, None)
        cancel_button.connect('clicked', close_upload, None)

        ok_button.show()
        cancel_button.show()
        buttons_hbox.pack_start(ok_button)
        buttons_hbox.pack_start(cancel_button)

        buttons_hbox.show()
        vbox.pack_start(buttons_hbox)

        vbox.show()
        upload_window.add(vbox)
        upload_window.show()

    def file_dialog(self, widget, data):
        """
        Display upload file dialog.

        Args:
            widget (gtk.Widget): The widget fired the event.
            data (object): Additional data.
        """
        dialog = gtk.FileChooserDialog(
            title='upload file',
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                     gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.chosen_file = unicode(dialog.get_filename())
        dialog.destroy()

    def ok_button_callback(self, widget, data):
        """
        Callback for starting the distribution thread.

        Args:
            widget (gtk.Widget): The widget fire the event
            data (object): Additional data.
        """
        if self.chosen_file is not None:

            can_distribute = True
            for i in self.file_store:
                if i[0] == os.path.basename(self.chosen_file):
                    can_distribute = False
                    self.display_error(
                        'The file already exists in the storage.')

            if can_distribute:
                distribute = protocol.thread.distribute(
                    file_path=self.chosen_file,
                    block_size=self.chosen_block_size,
                    duplication=self.chosen_duplication_level,
                    validation=self.chosen_validation_level)

                self.logic_queue.put(distribute)

    def cancel_button_callback(self, widget, data):
        """
        Callback for canceling file upload.

        Args:
            widget (gtk.Widget): The widget fire the event
            data (object): Additional data.
        """
        self.chosen_file = None

    ##################################################

    def download(self, data):
        """
        Callback for downloading a file.

        Args:
            data (object): Additional data.
        """
        virtual_file_name = get_selection(self.file_system_view)
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

    ##################################################

    def delete(self, data):
        """
        Callback for delete a file.

        Args:
            data (object): Additional data.
        """
        file_name = get_selection(self.file_system_view)
        if file_name is not None:
            message = protocol.thread.delete(file_name)
            self.logic_queue.put(message)

    def create_file_system(self):
        """Create the file system display."""
        self.file_system_view.set_property('enable-grid-lines', True)
        column_names = ['file name', 'file size',
                        'block number', 'duplication_level',
                        'validation level']

        for index, name in enumerate(column_names):
            column = gtk.TreeViewColumn(name)
            if index == 0:
                column.set_sort_column_id(0)
            self.file_system_view.append_column(column)

            cell = gtk.CellRendererText()
            color = '#EEE8AA' if index % 2 == 0 else '#FFEFD5'
            cell.set_property('cell-background', color)
            column.pack_start(cell, True)
            column.add_attribute(cell, 'text', index)

        self.file_system_toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.file_system_toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.file_system_toolbar.set_border_width(5)

        buttons = {'upload': self.upload,
                   'download': self.download,
                   'delete': self.delete}
        for name in buttons:
            icon = gtk.Image()
            icon.set_from_file('icons/' + name + '.png')
            self.file_system_toolbar.append_item(
                name, name, None, icon, buttons[name])
            self.file_system_toolbar.append_space()

        vbox = gtk.VBox()
        vbox.pack_start(self.file_system_toolbar, False, False, 0)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(0)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add_with_viewport(self.file_system_view)
        vbox.pack_start(scrolled_window, True, True, 0)

        self.file_system_toolbar.show()
        scrolled_window.show()
        self.file_system_view.show()
        vbox.show()
        self.page_dict['file system'].add(vbox)

    ##################################################

    def kill_thread_callback(self, data):
        """
        Called when the kill button in the waiting thread display is called.

        Kill a running thread.

        Args:
            data (object): Additional data.
        """
        selection = get_selection(self.waiting_files_view, column=1)
        if selection is not None:
            message = protocol.thread.kill_thread(name=selection)
            self.logic_queue.put(message)

    def create_waiting_files(self):
        """Create the waiting files display."""
        self.waiting_files_view.set_property('enable-grid-lines', True)
        column_names = ['type', 'file name', 'file size',
                        'block number', 'duplication_level',
                        'validation level']

        for index, name in enumerate(column_names):
            column = gtk.TreeViewColumn(name)
            if index == 0:
                column.set_sort_column_id(0)

                cell = gtk.CellRendererPixbuf()
                column.pack_start(cell, expand=True)
                column.add_attribute(cell, 'pixbuf', index)

            else:
                cell = gtk.CellRendererText()
                column.pack_start(cell, expand=True)
                column.add_attribute(cell, 'text', index)

            color = '#EEE8AA' if index % 2 == 0 else '#FFEFD5'
            cell.set_property('cell-background', color)

            self.waiting_files_view.append_column(column)

        self.waiting_files_toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.waiting_files_toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.waiting_files_toolbar.set_border_width(5)

        icon = gtk.Image()
        icon.set_from_file('icons/delete.png')
        self.waiting_files_toolbar.append_item(
            'cancel', 'cancel', None, icon, self.kill_thread_callback)

        vbox = gtk.VBox()
        vbox.pack_start(self.waiting_files_toolbar, False, False, 0)

        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_border_width(0)
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.add_with_viewport(self.waiting_files_view)
        vbox.pack_start(scrolled_window, True, True, 0)

        self.waiting_files_toolbar.show()
        scrolled_window.show()
        self.waiting_files_view.show()
        vbox.show()

        self.page_dict['waiting files'].add(vbox)

    ##################################################

    def file_status_view_callback(self, widget, data):
        """
        Callback for changing the blocks displayed in the file status.

        Args:
            widget (gtk.Widget): The widget fired the event.
            data (object): Additional data.
        """
        selection = get_selection(self.file_status_view)
        store = self.file_blocks_view.get_model()
        store.clear()

        data = gtk.gdk.pixbuf_new_from_file('icons/file.png')
        metadata = gtk.gdk.pixbuf_new_from_file('icons/metadata.png')

        for client in self.block_dict:
            for block in self.block_dict[client]:
                if block['name'] == selection:
                    image = data if block['block_type'] == 'data' else metadata
                    store.append(None, (image, block['number'], client))

    def create_file_status(self):
        """Create the file status display."""
        paned = gtk.HPaned()
        paned.set_property('position', 200)

        files_scrolled_window = gtk.ScrolledWindow()
        blocks_scrolled_window = gtk.ScrolledWindow()

        files_scrolled_window.set_policy(
            gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)
        blocks_scrolled_window.set_policy(
            gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)

        paned.add1(files_scrolled_window)
        paned.add2(blocks_scrolled_window)

        self.file_blocks_view.set_property('enable-grid-lines', True)

        block_column = gtk.TreeViewColumn('block')
        self.file_blocks_view.append_column(block_column)

        icon_cell = gtk.CellRendererPixbuf()
        icon_cell.set_property('cell-background', '#FFEFD5')
        block_column.pack_start(icon_cell, expand=False)
        block_column.add_attribute(icon_cell, 'pixbuf', 0)

        text_cell = gtk.CellRendererText()
        text_cell.set_property('cell-background', '#EEE8AA')
        block_column.pack_start(text_cell, expand=True)
        block_column.add_attribute(text_cell, 'text', 1)

        client_cell = gtk.CellRendererText()
        client_cell.set_property('cell-background', '#FFEFD5')
        client_column = gtk.TreeViewColumn('client', client_cell)
        client_column.set_sort_column_id(0)
        client_column.add_attribute(client_cell, 'text', 2)
        self.file_blocks_view.append_column(client_column)

        self.file_blocks_view.show()

        ###################################################################

        self.file_status_view.set_property('enable-grid-lines', True)
        self.file_status_view.connect(
            'cursor-changed', self.file_status_view_callback, None)

        files_column = gtk.TreeViewColumn('file name')
        file_name_cell = gtk.CellRendererText()

        file_name_cell.set_property('cell-background', '#EEE8AA')
        files_column.pack_start(file_name_cell, expand=True)
        files_column.add_attribute(file_name_cell, 'text', 0)

        self.file_status_view.append_column(files_column)
        self.file_status_view.show()

        files_scrolled_window.add_with_viewport(self.file_status_view)
        blocks_scrolled_window.add_with_viewport(self.file_blocks_view)

        files_scrolled_window.show()
        blocks_scrolled_window.show()
        paned.show()
        self.page_dict['file status'].add(paned)

    @handle_except('gui')
    def clients_view_callback(self, widget, data):
        """
        Callback for changing the displayed blocks in the client view.

        Args:
            widget (gtk.Widget): The widget that fired the event.
            data (object): Additional data.
        """
        selection = get_selection(self.clients_view)
        store = self.client_blocks_view.get_model()
        store.clear()

        data = gtk.gdk.pixbuf_new_from_file('icons/file.png')
        metadata = gtk.gdk.pixbuf_new_from_file('icons/metadata.png')

        # if client has connected and send storage_state message,
        # his ip will be in the blocks_dict variable
        if selection in self.block_dict:
            for block in self.block_dict[selection]:
                image = data if block['block_type'] == 'data' else metadata
                block_record = (image, block['name'], block['number'])
                store.append(None, block_record)

    def clients_kill_callback(self, data):
        """
        Kill a client.

        Args:
            data (object): Additional data.
        """
        client = get_selection(self.clients_view)
        if client is not None:
            message = protocol.thread.kill(client=client)
            self.logic_queue.put(message)

    def clients_refresh_callback(self, data):
        """
        Refresh the display.

        Args:
            data (object): Additional data.
        """
        message = protocol.thread.refresh()
        self.logic_queue.put(message)

    def clients_reconstruct_callback(self, data):
        """
        Called when the user hit the 'reconstruct' button.

        Triger system reconstruction.

        Args:
            data (object): Additional data.
        """
        dialog = gtk.MessageDialog(
            type=gtk.MESSAGE_QUESTION, buttons=gtk.BUTTONS_YES_NO)
        dialog.set_markup(
            'Are you sure? System reconstruction may take some time.')
        response = dialog.run()
        dialog.destroy()
        if response == -8:
            message = protocol.thread.reconstruct()
            self.logic_queue.put(message)

    def create_clients(self):
        """Create the client display."""
        paned = gtk.HPaned()
        paned.set_property('position', 400)
        clients_scrolled_window = gtk.ScrolledWindow()
        details_scrolled_window = gtk.ScrolledWindow()

        clients_scrolled_window.set_policy(
            gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)
        details_scrolled_window.set_policy(
            gtk.POLICY_AUTOMATIC,
            gtk.POLICY_AUTOMATIC)

        paned.add1(clients_scrolled_window)
        paned.add2(details_scrolled_window)

        file_column = gtk.TreeViewColumn('file name')
        self.client_blocks_view.append_column(file_column)

        block_column = gtk.TreeViewColumn('block')
        self.client_blocks_view.append_column(block_column)

        icon_cell = gtk.CellRendererPixbuf()
        icon_cell.set_property('cell-background', '#EEE8AA')
        file_column.pack_start(icon_cell, expand=False)
        file_column.add_attribute(icon_cell, 'pixbuf', 0)

        file_name_cell = gtk.CellRendererText()
        file_name_cell.set_property('cell-background', '#EEE8AA')
        file_column.pack_start(file_name_cell, expand=False)
        file_column.add_attribute(file_name_cell, 'text', 1)

        block_number_cell = gtk.CellRendererText()
        block_number_cell.set_property('cell-background', '#FFEFD5')
        block_column.pack_start(block_number_cell, expand=True)
        block_column.add_attribute(block_number_cell, 'text', 2)

        #########################################################
        client_columns = ['client', 'disk state',
                          'total space', 'used space',
                          'free space'
                          ]

        self.clients_view.connect(
            'cursor-changed', self.clients_view_callback, None)

        for index, name in enumerate(client_columns):
            if index == 1:
                space_cell = gtk.CellRendererProgress()
                space_column = gtk.TreeViewColumn(
                    'disk state',
                    space_cell,
                    value=index)

                self.clients_view.append_column(space_column)
                space_column.set_min_width(70)
            else:
                column = gtk.TreeViewColumn(name)
                self.clients_view.append_column(column)
                cell = gtk.CellRendererText()
                column.pack_start(cell, True)
                column.add_attribute(cell, 'text', index)
                color = '#EEE8AA' if index % 2 == 0 else '#FFEFD5'
                cell.set_property('cell-background', color)
                column.set_min_width(70)

        self.clients_view.show()
        self.client_blocks_view.show()

        ###########################################################

        self.clients_toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        self.clients_toolbar.set_style(gtk.TOOLBAR_BOTH)
        self.clients_toolbar.set_border_width(5)

        buttons = {
            'delete': self.clients_kill_callback,
            'refresh': self.clients_refresh_callback,
            'reconstruct': self.clients_reconstruct_callback
        }
        for name in buttons:
            icon = gtk.Image()
            icon.set_from_file('icons/' + name + '.png')
            self.clients_toolbar.append_item(
                name, name, None, icon, buttons[name])
            self.clients_toolbar.append_space()

        clients_scrolled_window.add_with_viewport(self.clients_view)
        details_scrolled_window.add_with_viewport(self.client_blocks_view)

        clients_scrolled_window.show()
        details_scrolled_window.show()
        self.clients_toolbar.show()
        paned.show()

        vbox = gtk.VBox()
        vbox.pack_start(self.clients_toolbar, False, False, 0)
        vbox.pack_start(paned, True, True, 0)
        vbox.show()
        self.page_dict['clients'].add(vbox)

    def exit(self, data):
        """
        Callback for closing the program.

        Args:
            data (object): Additional data.
        """
        gtk.main_quit()
        self.logic_queue.put(protocol.thread.exit())

    def main(self):
        """Execute the main event loop."""
        gtk.main()
