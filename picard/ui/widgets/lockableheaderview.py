# -*- coding: utf-8 -*-
#
# Picard, the next-generation MusicBrainz tagger
#
# Copyright (C) 2019-2020, 2022 Philipp Wolfer
# Copyright (C) 2020-2025 Laurent Monin
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.


from PyQt6 import QtWidgets

from picard.i18n import gettext as _


class LockableHeaderView(QtWidgets.QHeaderView):
    """A QHeaderView implementation supporting locking/unlocking.

    A column can either be sorted ascending, descending or not sorted. The view
    toggles through these states by clicking on a section header.
    The header can be locked or unlocked.
    """

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent=parent)
        self.prelock_state = None
        self.lock(False)

    def mouseReleaseEvent(self, event):
        if self.is_locked:
            tooltip = _(
                "The table is locked. To enable sorting and column resizing\n"
                "unlock the table in the table header's context menu."
            )
            QtWidgets.QToolTip.showText(event.globalPosition().toPoint(), tooltip, self)
            return

        # Normal handling of events
        super().mouseReleaseEvent(event)

    def lock(self, is_locked):
        self.is_locked = is_locked
        if is_locked:
            self.prelock_state = self.saveState()
            self.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Fixed)
        else:
            if self.prelock_state is not None:
                self.restoreState(self.prelock_state)
                self.prelock_state = None

        self.setSectionsClickable(not is_locked)
        self.setSectionsMovable(not is_locked)
        self.setSortIndicatorClearable(True)
