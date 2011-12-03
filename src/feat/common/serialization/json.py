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
from feat import hacks

json = hacks.import_json()

from feat.common import reflect
from feat.interface.serialization import *

from feat.common.serialization import base


TUPLE_ATOM = u".tuple"
BYTES_ATOM = u".bytes"
BYTES_ENCODING = "BASE64"
ENCODED_ATOM = u".enc"
SET_ATOM = u".set"
ENUM_ATOM = u".enum"
TYPE_ATOM = u".type"
EXTERNAL_ATOM = u".ext"
REFERENCE_ATOM = u".ref"
DEREFERENCE_ATOM = u".deref"

INSTANCE_TYPE_ATOM = u".type"
INSTANCE_STATE_ATOM = u".state"

DEFAULT_ENCODING = "UTF8"
ALLOWED_CODECS = set(["UTF8", "UTF-8", "utf8"])

JSON_CONVERTER_CAPS = set([Capabilities.int_values,
                           Capabilities.long_values,
                           Capabilities.enum_values,
                           Capabilities.float_values,
                           Capabilities.str_values,
                           Capabilities.unicode_values,
                           Capabilities.bool_values,
                           Capabilities.none_values,
                           Capabilities.tuple_values,
                           Capabilities.list_values,
                           Capabilities.set_values,
                           Capabilities.dict_values,
                           Capabilities.type_values,
                           Capabilities.instance_values,
                           Capabilities.external_values,
                           Capabilities.str_keys,
                           Capabilities.circular_references,
                           Capabilities.new_style_types,
                           Capabilities.meta_types])

JSON_FREEZER_CAPS = JSON_CONVERTER_CAPS \
                    | set([Capabilities.builtin_values,
                           Capabilities.function_values,
                           Capabilities.method_values])


class Serializer(base.Serializer):

    pack_dict = dict

    def __init__(self, indent=None, separators=None, force_unicode=False,
                 externalizer=None, source_ver=None, target_ver=None):
        base.Serializer.__init__(self, converter_caps=JSON_CONVERTER_CAPS,
                                 freezer_caps=JSON_FREEZER_CAPS,
                                 externalizer=externalizer,
                                 source_ver=source_ver,
                                 target_ver=target_ver)
        self._indent = indent
        self._separators = separators
        self._force_unicode = force_unicode

    ### Overridden Methods ###

    def post_convertion(self, data):
        return json.dumps(data, indent=self._indent,
                          separators=self._separators)

    def flatten_key(self, key, caps, freezing):
        if not isinstance(key, str):
            raise TypeError("Serializer %s is not capable of serializing "
                            "non-string dictionary keys: %r"
                            % (reflect.canonical_name(self), key))
        # Flatten it as unicode by using the selected encoding
        return self.pack_unicode, key.decode(DEFAULT_ENCODING)

    def pack_tuple(self, data):
        # JSON do not support tuple so we just fake it
        return [TUPLE_ATOM] + data

    def pack_str(self, data):
        # we try to decode the string from default encoding
        try:
            value = data.decode(DEFAULT_ENCODING)
            if self._force_unicode:
                return value
            return [ENCODED_ATOM, DEFAULT_ENCODING, value]
        except UnicodeDecodeError:
            # if it fail store it as base64 encoded bytes
            return [BYTES_ATOM, data.encode(BYTES_ENCODING).strip()]

    def pack_set(self, data):
        return [SET_ATOM] + data

    def pack_enum(self, data):

        return [ENUM_ATOM, reflect.canonical_name(data) + "." + data.name]

    def pack_type(self, data):
        return [TYPE_ATOM, reflect.canonical_name(data)]

    def pack_external(self, data):
        return [EXTERNAL_ATOM] + data

    def pack_instance(self, data):
        type_name, snapshot = data

        if isinstance(snapshot, dict):
            result = dict(snapshot) # Copy the dict to not modify the original
            assert INSTANCE_TYPE_ATOM not in result
            assert INSTANCE_STATE_ATOM not in result
            result[INSTANCE_TYPE_ATOM] = type_name
            return result

        return {INSTANCE_TYPE_ATOM: type_name,
                INSTANCE_STATE_ATOM: snapshot}

    def pack_reference(self, data):
        return [REFERENCE_ATOM] + data

    def pack_dereference(self, data):
        return [DEREFERENCE_ATOM, data]

    def pack_frozen_external(self, data):
        snapshot, = data
        return snapshot

    def pack_frozen_instance(self, data):
        snapshot, = data
        return snapshot

    def pack_frozen_function(self, data):
        return reflect.canonical_name(data)

    pack_frozen_builtin = pack_frozen_function
    pack_frozen_method = pack_frozen_function


class Unserializer(base.Unserializer):

    pass_through_types = set([str, unicode, int, long,
                              float, bool, type(None)])

    def __init__(self, registry=None, externalizer=None,
                 source_ver=None, target_ver=None):
        base.Unserializer.__init__(self, converter_caps=JSON_CONVERTER_CAPS,
                                   registry=registry,
                                   externalizer=externalizer,
                                   source_ver=source_ver,
                                   target_ver=target_ver)

    ### Overridden Methods ###

    def pre_convertion(self, data):
        return json.loads(unicode(data))

    def analyse_data(self, data):
        if isinstance(data, dict):
            if INSTANCE_TYPE_ATOM in data:
                return data[INSTANCE_TYPE_ATOM], Unserializer.unpack_instance
            return dict, Unserializer.unpack_dict

        if isinstance(data, list):
            default = list, Unserializer.unpack_list
            if not data:
                # Empty list
                return default
            key = data[0]
            if isinstance(key, unicode):
                return self._list_unpackers.get(key, default)
            # Just a list
            return default

    ### Private Methods ###

    def unpack_instance(self, data, *args):
        data = dict(data)
        type_name = data.pop(INSTANCE_TYPE_ATOM)
        if INSTANCE_STATE_ATOM in data:
            snapshot = data.pop(INSTANCE_STATE_ATOM)
        else:
            snapshot = data
        return self.restore_instance(type_name, snapshot, *args)

    def unpack_external(self, data):
        _, identifier = data
        return self.restore_external(identifier)

    def unpack_reference(self, data):
        _, refid, value = data
        return self.restore_reference(refid, value)

    def unpack_dereference(self, data):
        _, refid = data
        return self.restore_dereference(refid)

    def unpack_enum(self, data):
        _, full_name = data
        parts = full_name.encode(DEFAULT_ENCODING).split('.')
        type_name = ".".join(parts[:-1])
        enum = self.restore_type(type_name)
        return enum.get(parts[-1])

    def unpack_type(self, data):
        _, type_name = data
        return self.restore_type(type_name)

    def unpack_encoded(self, data):
        _, codec, bytes = data
        if codec not in ALLOWED_CODECS:
            raise ValueError("Unsupported codec: %r" % codec)
        return bytes.encode(codec)

    def unpack_bytes(self, data):
        _, bytes = data
        return bytes.decode(BYTES_ENCODING)

    def unpack_tuple(self, data):
        return tuple([self.unpack_data(d) for d in data[1:]])

    def unpack_list(self, container, data):
        container.extend([self.unpack_data(d) for d in data])

    def unpack_set(self, container, data):
        container.update(self.unpack_unordered_values(data[1:]))

    def unpack_dict(self, container, data):
        items = [(k.encode(DEFAULT_ENCODING), v)for k, v in data.iteritems()]
        container.update(self.unpack_unordered_pairs(items))

    _list_unpackers = {BYTES_ATOM: (None, unpack_bytes),
                       ENCODED_ATOM: (None, unpack_encoded),
                       ENUM_ATOM: (None, unpack_enum),
                       TYPE_ATOM: (None, unpack_type),
                       TUPLE_ATOM: (None, unpack_tuple),
                       SET_ATOM: (set, unpack_set),
                       EXTERNAL_ATOM: (None, unpack_external),
                       REFERENCE_ATOM: (None, unpack_reference),
                       DEREFERENCE_ATOM: (None, unpack_dereference)}


class PaisleyUnserializer(Unserializer):
    '''Hack to cope with Paisley performing json.loads on its own.'''

    def pre_convertion(self, data):
        return data


def serialize(value):
    global _serializer
    return _serializer.convert(value)


def freeze(value):
    global _serializer
    return _serializer.freeze(value)


def unserialize(data):
    global _unserializer
    return _unserializer.convert(data)


### Private Stuff ###

_serializer = Serializer()
_unserializer = Unserializer()
