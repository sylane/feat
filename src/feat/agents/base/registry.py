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
from feat.common import decorator, serialization

registry = dict()


@decorator.parametrized_class
def register(klass, name, configuration_id=None):
    klass = override(name, klass, configuration_id)
    return klass


def registry_lookup(name):
    global registry
    return registry.get(name, None)


def override(name, klass, configuration_id=None):
    global registry
    registry[name] = klass
    doc_id = configuration_id or name + "_conf"
    klass.descriptor_type = name
    klass.type_name = name + ":data"
    klass.configuration_doc_id = doc_id
    serialization.register(klass)
    return klass
