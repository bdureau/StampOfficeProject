"""
UndoCommands Module
-------------------
Implements QUndoCommand classes for adding, updating, and deleting stamps.
"""

from PyQt6.QtGui import QUndoCommand


class UpdateStampCommand(QUndoCommand):
    """QUndoCommand implementation for stamp record modifications."""

    def __init__(self, main_window, stamp_key, old_data, new_data, description="Update Stamp Record"):
        super().__init__(description)
        self.main_window = main_window
        self.stamp_key = stamp_key
        self.old_data = old_data
        self.new_data = new_data

    def undo(self):
        self.main_window.apply_stamp_data(self.stamp_key, self.old_data)

    def redo(self):
        self.main_window.apply_stamp_data(self.stamp_key, self.new_data)


class AddStampCommand(QUndoCommand):
    """QUndoCommand implementation for adding a new stamp record."""

    def __init__(self, main_window, stamp_data, description="Add Stamp Record"):
        super().__init__(description)
        self.main_window = main_window
        self.stamp_data = stamp_data
        self.stamp_key = stamp_data[0]

    def undo(self):
        self.main_window.db_adapter.delete_stamp(self.stamp_key)
        self.main_window._refresh_table()

    def redo(self):
        self.main_window.db_adapter.insert_stamp(self.stamp_data)
        self.main_window._refresh_table()
        self.main_window._select_stamp_by_key_or_nbr(self.stamp_key, self.stamp_data[1])


class DeleteStampsCommand(QUndoCommand):
    """QUndoCommand implementation for deleting one or multiple stamp records."""

    def __init__(self, main_window, stamps_list, description="Delete Stamp Record(s)"):
        super().__init__(description)
        self.main_window = main_window
        self.stamps_list = stamps_list

    def undo(self):
        for stamp_data in self.stamps_list:
            self.main_window.db_adapter.insert_stamp(stamp_data)
        self.main_window._refresh_table()

    def redo(self):
        for stamp_data in self.stamps_list:
            stamp_key = stamp_data[0]
            self.main_window.db_adapter.delete_stamp(stamp_key)
        self.main_window._refresh_table()