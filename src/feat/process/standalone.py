# F3AT - Flumotion Asynchronous Autonomous Agent Toolkit
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

# See "LICENSE.GPL" in the source distribution for more information.

# Headers in this file shall remain intact.
from feat.process import base
from feat.agents.base import replay


class Process(base.Base):

    def initiate(self, command, args, env):
        self.command = command
        self.args = args
        self.env = env

    def started_test(self):
        # Process should deamonize itself.
        return True

    def restart(self):
        d = base.Base.restart(self)
        # This fakes process output and is needed because it might deamonize
        # itself without puting anything to stdout.
        self._control.outReceived("")
        return d

    @replay.side_effect
    def on_finished(self, e):
        base.Base.on_finished(self, e)
