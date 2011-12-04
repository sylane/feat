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

import json
import types

from zope.interface import implements

from feat.common import defer, serialization
from feat.common.serialization import json as feat_json
from feat.models import reference
from feat.web import http, document

from feat.models.interface import *

MIME_TYPE = "application/json"


class ActionPayload(dict):
    implements(IActionPayload)


def render_metadata(obj):
    result = []
    if IMetadata.providedBy(obj):
        metadata = IMetadata(obj)
        for metaitem in metadata.iter_meta():
            m = {"name": metaitem.name,
                 "value": metaitem.value}
            if metaitem.scheme is not None:
                m["scheme"] = metaitem.scheme
            result.append(m)
    return result


@defer.inlineCallbacks
def render_items(obj, context):
    result = {}
    items = yield obj.fetch_items()
    for item in items:
        result[item.name] = yield render_item(item, context)
    defer.returnValue(result)


@defer.inlineCallbacks
def render_actions(obj, context):
    result = {}
    actions = yield obj.fetch_actions()
    for action in actions:
        result[action.name] = yield render_action(action, context)
    defer.returnValue(result)


@defer.inlineCallbacks
def render_item(item, context):
    result = {}
    model = yield item.fetch()
    yield update_attribute(result, model, context)
    if item.label is not None:
        result["label"] = item.label
    if item.desc is not None:
        result["desc"] = item.desc
    metadata = yield render_metadata(item)
    if metadata:
        result["metadata"] = metadata
    ref = item.reference
    if ref is not None:
        result["href"] = ref.resolve(context)
    defer.returnValue(result)


@defer.inlineCallbacks
def update_attribute(result, model, context):
    if IAttribute.providedBy(model):
        subcontext = context.descend(model)
        attr = IAttribute(model)
        if attr.is_readable:
            value = yield attr.fetch_value()
            result["value"] = render_value(value, subcontext)
        result["type"] = render_value_info(attr.value_info)
        if attr.is_writable:
            result["writable"] = True
        if attr.is_deletable:
            result["deletable"] = True


@defer.inlineCallbacks
def render_action(action, context):
    result = {}
    if action.label is not None:
        result["label"] = action.label
    if action.desc is not None:
        result["desc"] = action.desc
    metadata = yield render_metadata(action)
    if metadata:
        result["metadata"] = metadata
    result["method"] = context.get_action_method(action).name
    result["idempotent"] = bool(action.is_idempotent)
    result["category"] = action.category.name
    if action.result_info is not None:
        result["result"] = render_value_info(action.result_info)
    params = render_params(action.parameters)
    if params:
        result["params"] = params
    ref = action.reference
    if ref is not None:
        result["href"] = ref.resolve(context)
    defer.returnValue(result)


def render_value_info(value):
    result = {}
    result["type"] = value.value_type.name
    if value.use_default:
        result["default"] = value.default
    if value.label is not None:
        result["label"] = value.label
    if value.desc is not None:
        result["desc"] = value.desc
    metadata = render_metadata(value)
    if metadata:
        result["metadata"] = metadata
    if IValueCollection.providedBy(value):
        coll = IValueCollection(value)
        result["allowed"] = [render_value_info(v) for v in coll.allowed_types]
        result["ordered"] = coll.is_ordered
        if coll.min_size is not None:
            result["min_size"] = coll.min_size
        if coll.max_size is not None:
            result["max_size"] = coll.max_size
    if IValueRange.providedBy(value):
        vrange = IValueRange(value)
        result["minimum"] = vrange.minimum
        result["maximum"] = vrange.maximum
        if vrange.increment is not None:
            result["increment"] = vrange.increment
    if IValueOptions.providedBy(value):
        options = IValueOptions(value)
        result["restricted"] = options.is_restricted
        result["options"] = [{"label": o.label, "value": o.value}
                             for o in options.iter_options()]
    return result


def render_params(params):
    return dict([(p.name, render_param(p)) for p in params])


def render_param(param):
    result = {}
    result["required"] = param.is_required
    result["value"] = render_value_info(param.value_info)
    if param.label is not None:
        result["label"] = param.label
    if param.desc is not None:
        result["desc"] = param.desc
    return result


def render_value(value, context):
    if IReference.providedBy(value):
        return value.resolve(context)
    return value


@defer.inlineCallbacks
def render_verbose(model, context):
    result = {}
    result["identity"] = model.identity
    name = model.name
    if name is not None:
        result["name"] = name
    label = model.label
    if label is not None:
        result["label"] = label
    desc = model.desc
    if desc is not None:
        result["desc"] = desc
    if model.reference is not None:
        result["href"] = model.reference.resolve(context)

    yield update_attribute(result, model, context)

    metadata = render_metadata(model)
    items = yield render_items(model, context)
    actions = yield render_actions(model, context)
    if metadata:
        result["metadata"] = metadata
    if items:
        result["items"] = items
    if actions:
        result["actions"] = actions

    defer.returnValue(result)


@defer.inlineCallbacks
def render_compact(model, context):
    if IAttribute.providedBy(model):
        attr = IAttribute(model)
        if attr.is_readable:
            value = yield attr.fetch_value()
            result = render_value(value, context)
            defer.returnValue(result)
        defer.returnValue(None)

    result = {}
    if model.reference is not None:
        result["href"] = model.reference.resolve(context)
    items = yield model.fetch_items()
    for item in items:
        submodel = yield item.fetch()
        if IAttribute.providedBy(submodel):
            attr = IAttribute(submodel)
            if attr.is_readable:
                value = yield attr.fetch_value()
                subcontext = context.descend(submodel)
                result[attr.name] = render_value(value, subcontext)
        else:
            ref = item.reference
            if ref is not None:
                result[item.name] = ref.resolve(context)
    defer.returnValue(result)


@defer.inlineCallbacks
def write_model(doc, obj, *args, **kwargs):
    context = kwargs["context"]

    verbose = "format" in kwargs and "verbose" in kwargs["format"]

    if verbose:
        result = yield render_verbose(obj, context)
    else:
        result = yield render_compact(obj, context)

    enc = CustomJSONEncoder(encoding=doc.encoding)
    doc.write(enc.encode(result))


def write_reference(doc, obj, *args, **kwargs):
    context = kwargs["context"]
    return obj.resolve(context)


def write_error(doc, obj, *args, **kwargs):
    result = {}
    if obj.code is not None:
        result["code"] = obj.code
    if obj.message is not None:
        result["message"] = obj.message
    if obj.debug is not None:
        result["debug"] = obj.debug
    if obj.trace is not None:
        result["trace"] = obj.trace
    enc = CustomJSONEncoder(encoding=doc.encoding)
    doc.write(enc.encode(result))


def write_anything(doc, obj, *args, **kwargs):
    enc = CustomJSONEncoder(encoding=doc.encoding)
    doc.write(enc .encode(obj))


def read_action(doc, *args, **kwargs):
    data = doc.read()
    if not data:
        return ActionPayload()
    params = json.loads(data)
    if not isinstance(params, dict):
        return ActionPayload([(u"value", params)])
    return ActionPayload(params)


document.register_writer(write_model, MIME_TYPE, IModel)
document.register_writer(write_reference, MIME_TYPE, IReference)
document.register_writer(write_error, MIME_TYPE, IErrorPayload)
document.register_writer(write_anything, MIME_TYPE, None)

document.register_reader(read_action, MIME_TYPE, IActionPayload)


### private ###

class CustomJSONEncoder(json.JSONEncoder):

    def __init__(self, context=None, encoding=None):
        kwargs = {"indent": 2}
        if encoding is not None:
            kwargs["encoding"] = encoding
        json.JSONEncoder.__init__(self, **kwargs)
        self._serializer = feat_json.PreSerializer()

    def default(self, obj):
        if serialization.ISerializable.providedBy(obj):
            return self._serializer.convert(obj)
        if serialization.ISnapshotable.providedBy(obj):
            return self._serializer.freeze(obj)
        return json.JSONEncoder.default(self, obj)
