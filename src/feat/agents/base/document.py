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
# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
from feat.common import formatable, serialization

documents = dict()


def register(klass):
    global documents
    if klass.document_type in documents:
        raise ValueError('document_type %s already registered!' %
                         klass.document_type)
    documents[klass.document_type] = klass
    klass.type_name = klass.document_type
    serialization.register(klass)
    return klass


def lookup(document_type):
    global documents
    return documents.get(document_type)


field = formatable.field


@serialization.register
class Document(formatable.Formatable):

    field('doc_id', None, '_id')
    field('rev', None, '_rev')
