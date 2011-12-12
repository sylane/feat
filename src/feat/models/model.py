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

import types

from zope.interface import implements

from feat.common import error, annotate, container, mro, defer, error, log
from feat.models import utils, value
from feat.models import meta as models_meta
from feat.models import reference as models_reference
from feat.models import action as models_action

from feat.models.interface import ActionCategories, ModelError, NotSupported
from feat.models.interface import IModel, IModelItem
from feat.models.interface import IActionFactory, IModelFactory
from feat.models.interface import IAspect, IReference, IContextMaker


### Annotations ###


meta = models_meta.meta


def item_meta(item_name, name, value, scheme=None):
    """
    Adds meta information to an already defined item
    of the model being defined.
    @param item_name: name of the model item the meta data should be added to.
    @type item_name: str or unicode
    @param name: name of the meta data class
    @type name: str or unicode
    @param value: metadata value
    @type value: str or unicode
    @param scheme: format information about the value
    @type scheme: str or unicode or None
    """
    _annotate("item_meta", item_name, name, value, scheme=scheme)


def identity(identity):
    """
    Annotates the identity of the model being defined.
    @param identity: model unique identity
    @type identity: str or unicode
    """
    _annotate("identity", identity)


def reference(effect):
    """
    Annotate the reference for the model being defined.
    @param effect: a reference or an effect to retrieve it.
    @type effect: IReference or callable
    """
    _annotate("reference", effect)


def view(effect_or_value):
    """
    Annotates the model view.
    @param effect_or_value: effect to retrieve the view or the view itself.
    @type effect_or_value: callable or object
    """
    _annotate("view", effect_or_value)


def attribute(name, value, getter=None, setter=None,
              label=None, desc=None, meta=None):
    """
    Annotates a model attribute.
    @param name: attribute name, unique for a model.
    @type name: str or unicode
    @param value: attribute type information.
    @type value: IValueInfo
    @param getter: an effect or None if the attribute is write-only;
                   the retrieved value that will be validated;
                   see feat.models.call for effect information.
    @type getter: callable or None
    @param setter: an effect or None if the attribute is read-only;
                   the new value will be validated, possibly converted
                   and returned;
                   see feat.models.call for effect information.
    @type setter: callable or None
    @param label: the attribute label or None.
    @type label: str or unicode or None
    @parama desc: the description of the attribute or None if not documented.
    @type desc: str or unicode or None
    @param meta: model item metadata atoms.
    @type meta: list of tuple
    """
    _annotate("attribute", name, value, getter=getter, setter=setter,
              label=label, desc=desc, meta=meta)


def child(name, source=None, view=None, model=None,
          enabled=None, fetch=None, browse=None,
          label=None, desc=None, meta=None):
    """
    Annotate a sub-model to the one being defined.
    @param name: item name unique for the model being defined.
    @type name: str or unicode
    @param source: an effect to retrieve the sub-model source
                   or None to use the same source;
                   see feat.models.call for effect information.
    @type source: callable or None
    @param view: view value or an effect to retrieve it;
                 see feat.models.call for effect information.
    @type view: callable or object()
    @param model: the model identity, model factory or effect to get it,
                  or None to use IModel adapter.
    @type model: str or unicode or callable or IModelFactory or None
    @param enabled: an effect defining if the model is enabled
    @type enabled: bool or callable
    @param browse: an effect filtering the source when browsing to child.
    @type browse: callable
    @param fetch: an effect filtering the source when fetching child.
    @type fetch: callable
    @param label: the sub-model label or None.
    @type label: str or unicode or None
    @parama desc: the description of the sub-model or None if not documented.
    @type desc: str or unicode or None
    @param meta: model item metadata atoms.
    @type meta: list of tuple
    """
    _annotate("child", name, source=source, view=view, model=model,
              enabled=enabled, fetch=fetch, browse=browse,
              label=label, desc=desc, meta=meta)


def command():
    raise NotImplementedError("model.command() is not implemented yet")


def create(name, *effects, **kwargs):
    """
    Annotate a non-idempotent create action to the model being defined.
    Should really be:
      create(name, *effects, value=None, params=None, label=None, desc=None)
    but it is not supported by python < 3.
    @param name: item name unique for the model being defined.
    @type name: str or unicode
    @param effects:
    @type effects: str or unicode
    @param value: input value information or None if not required.
    @type value: IValuInfo or None
    @param params: action paremeter or list of action parameters.
    @type params: IActionPram or list of IActionParam
    @param label: the action label or None.
    @type label: str or unicode or None
    @parama desc: the action  description or None if not documented.
    @type desc: str or unicode or None
    """
    value_info = kwargs.pop("value", None)
    params = kwargs.pop("params", None)
    label = kwargs.pop("label", None)
    desc = kwargs.pop("desc", None)
    if kwargs:
        raise TypeError("create() got an unexpected keyword '%s'"
                        % kwargs.keys()[0])
    _annotate("create", name, value_info=value_info, params=params,
              effects=effects, label=label, desc=desc)


def put():
    raise NotImplementedError("model.put() is not implemented yet")


def update():
    raise NotImplementedError("model.update() is not implemented yet")


def delete(name, *effects, **kwargs):
    """
    Annotate a delete action to the model being defined.
    Should be delete(name, *effects, label=None, desc=None)
    but it is not supported by python < 3.
    @param name: item name unique for the model being defined.
    @type name: str or unicode
    @param effects:
    @type effects: str or unicode
    @param label: the action label or None.
    @type label: str or unicode or None
    @parama desc: the action  description or None if not documented.
    @type desc: str or unicode or None
    """
    label = kwargs.pop("label", None)
    desc = kwargs.pop("desc", None)
    if kwargs:
        raise TypeError("delete() got an unexpected keyword '%s'"
                        % kwargs.keys()[0])
    _annotate("delete", name, effects=effects, label=label, desc=desc)


def action(name, factory, label=None, desc=None):
    """
    Annotate a model's action.
    @param name: the name of the model's action.
    @type name: str or unicode
    @param factory: a factory to create actions.
    @type factory: IActionFactory
    @param label: the action label if specified.
    @type label: str or unicode or None
    @param desc: the action description if specified.
    @type desc: str or unicode or None
    """
    _annotate("action", name, factory,
              label=label, desc=desc)


def collection(name, child_names=None, child_source=None,
               child_view=None, child_model=None, child_label=None,
               child_desc=None, child_meta=None,
               label=None, desc=None, meta=None, model_meta=None):
    """
    Annotate a dynamic collection of sub-models.
    @param name: the name of the collection model containing the sub-models.
    @type name: str or unicode
    @param child_names: an effect that retrieve all sub-models names or
                        None if sub-models are not iterable.
    @type child_source: callable
    @param child_source: an effect that retrieve a sub-model source.
    @type child_source: callable
    @param child_view: an effect that retrieve a sub-model view.
    @type child_view: callable
    @param child_model: the model identity, model factory or effect to get it,
                        or None to use IModel adapter.
    @type child_model: str or unicode or callable or IModelFactory or None
    @param child_label: the model items label or None.
    @type child_label: str or unicode or None
    @param child_desc: the model items description or None.
    @type child_desc: str or unicode or None
    @param child_meta: collection model's items metadata.
    @type child_meta: list of tuple
    @param label: the collection label or None.
    @type label: str or unicode or None
    @param desc: the collection description or None.
    @type desc: str or unicode or None
    @param meta: item metadata.
    @type meta: list of tuple
    @param model_meta: collection model metadata.
    @type model_meta: list of tuple
    """
    _annotate("collection", name, child_names=child_names,
              child_source=child_source, child_view=child_view,
              child_model=child_model, child_label=child_label,
              child_desc=child_desc, child_meta=child_meta,
              label=label, desc=desc, meta=meta, model_meta=model_meta)


def child_model(model_factory):
    """
    Annotate the effect used to retrieve the model's children names.
    @param model: the child's model identity, model factory or effect
                  to get it, or None to use IModel adapter.
    @type model: str or unicode or callable or IModelFactory or None
    """
    _annotate("child_model", model_factory)


def child_label(label):
    """
    Annotate child items label.
    @param label: the model items label or None.
    @type label: str or unicode or None
    """
    _annotate("child_label", label)


def child_desc(desc):
    """
    Annotate child items description.
    @param desc: the model items description or None.
    @type desc: str or unicode or None
    """
    _annotate("child_desc", desc)


def child_meta(name, value, scheme=None):
    """
    Annotate child items metadata.
    @param name: name of the meta data class
    @type name: str or unicode
    @param value: metadata value
    @type value: str or unicode
    @param scheme: format information about the value
    @type scheme: str or unicode or None
    """
    _annotate("child_meta", name, value, scheme=scheme)


def child_names(effect):
    """
    Annotate the effect used to retrieve the model's children names.
    @param effect: an effect to retrieve the names.
    @type effect: callable
    """
    _annotate("child_names", effect)


def child_source(effect):
    """
    Annotate the effect used to retrieve a sub-model's source by name.
    @param effect: an effect to retrieve a source from name.
    @type effect: callable
    """
    _annotate("child_source", effect)


def child_view(effect):
    """
    Annotate the effect used to retrieve a sub-model's view.
    @param effect: an effect to retrieve a source from name.
    @type effect: callable
    """
    _annotate("child_view", effect)


def is_detached(flag=True):
    """
    Annotate the model being defined as being detached.
    @param flag: if the model is detached.
    @type flag: bool
    """
    _annotate("is_detached", flag)


def _annotate(name, *args, **kwargs):
    method_name = "annotate_" + name
    annotate.injectClassCallback(name, 4, method_name, *args, **kwargs)


### Registry ###


def register_factory(identity, factory):
    global _model_factories
    identity = unicode(identity)
    if identity in _model_factories:
        raise KeyError("Factory already registered for %s: %r"
                       % (identity, _model_factories[identity]))
    _model_factories[identity] = IModelFactory(factory)


def get_factory(identity):
    global _model_factories
    return _model_factories.get(unicode(identity))


def snapshot_factories():
    global _model_factories
    return dict(_model_factories)


def restore_factories(snapshot):
    global _model_factories
    _model_factories = dict(snapshot)


### Classes ###


class MetaModel(type(models_meta.Metadata)):
    implements(IModelFactory)


class AbstractModel(models_meta.Metadata, mro.DeferredMroMixin):
    """
    Base class for models, it DOES NOT IMPLEMENTE IModel.
    All what define models are defined at class level,
    instance only hold a reference to the source the model
    applies on and an aspect defined by its parent model.
    """

    __metaclass__ = MetaModel
    __slots__ = ("source", "aspect", "view", "reference")

    implements(IModel, IContextMaker)

    _model_identity = None
    _model_view = None
    _model_reference = None
    _model_is_detached = False

    ### class methods ###

    @classmethod
    def create(cls, source, aspect=None, view=None, parent=None):
        m = cls(source)
        return m.initiate(aspect=aspect, view=view, parent=parent)

    ### public ###

    def __init__(self, source):
        self.source = source
        self.aspect = None
        self.view = None
        self.reference = None

    def __repr__(self):
        return "<%s %s '%s'>" % (type(self).__name__,
                                 self.identity, self.name)

    def __str__(self):
        return repr(self)

    ### virtual ###

    def init(self):
        """Override in sub-classes to initiate the model.
        All sub-classes init() methods are called in MRO order.
        Can return a deferred."""

    ### IContextMaker ###

    def make_context(self, key=None, view=None, action=None):
        return {"model": self,
               "view": view if view is not None else self.view,
               "key": unicode(key) if key is not None else self.name,
               "action": action}

    ### IModel ###

    @property
    def identity(self):
        return self._model_identity

    @property
    def name(self):
        return self.aspect.name if self.aspect is not None else None

    @property
    def label(self):
        return self.aspect.label if self.aspect is not None else None

    @property
    def desc(self):
        return self.aspect.desc if self.aspect is not None else None

    def initiate(self, aspect=None, view=None, parent=None):
        """Do not keep any reference to its parent,
        this way it can be garbage-collected."""

        def got_view(view):
            if view is None:
                return None
            return init(view)

        def init(view):
            self.view = view
            d = self.call_mro("init")
            d.addCallback(retrieve_reference)
            d.addCallback(update_reference)
            return d

        def retrieve_reference(_param):
            if callable(self._model_reference):
                context = self.make_context()
                return self._model_reference(self.source, context)
            return self._model_reference

        def update_reference(reference):
            self.reference = reference
            return self

        self.aspect = IAspect(aspect) if aspect is not None else None
        if self._model_view is not None:
            if callable(self._model_view):
                context = self.make_context(view=view)
                d = self._model_view(None, context)
                return d.addCallback(got_view)
            return init(self._model_view)
        return init(view)

    def perform_action(self, name, **kwargs):
        d = self.fetch_action(name)
        d.addCallback(defer.call_param, 'perform', **kwargs)
        return d

    # provides_item() should be implemented by sub-classes

    # count_items() should be implemented by sub-classes

    # fetch_item() should be implemented by sub-classes

    # fetch_items() should be implemented by sub-classes

    # query_items() should be implemented by sub-classes

    # provides_action() should be implemented by sub-classes

    # count_actions() should be implemented by sub-classes

    # fetch_action() should be implemented by sub-classes

    # fetch_actions() should be implemented by sub-classes

    ### annotations ###

    @classmethod
    def annotate_identity(cls, identity):
        """@see: feat.models.model.identity"""
        cls._model_identity = _validate_str(identity)
        register_factory(cls._model_identity, cls)

    @classmethod
    def annotate_is_detached(cls, flag):
        """@see: feat.models.model.is_detached"""
        cls._model_is_detached= _validate_flag(flag)

    @classmethod
    def annotate_reference(cls, effect):
        """@see: feat.models.model.reference"""
        cls._model_reference = _validate_effect(effect)

    @classmethod
    def annotate_view(cls, effect_or_value):
        """@see: feat.models.model.view"""
        cls._model_view = _validate_effect(effect_or_value)


class NoChildrenMixin(object):
    """Mix with BaseModel for models without sub-model."""

    __slots__ = ()

    ### IModel ###

    def provides_item(self, name):
        return defer.succeed(False)

    def count_items(self):
        return defer.succeed(0)

    def fetch_item(self, name):
        return defer.succeed(None)

    def fetch_items(self):
        return defer.succeed(iter([]))

    def query_items(self, **kwargs):
        return defer.fail(NotSupported("Model do not support item queries"))


class NoActionsMixin(object):
    """Mix with BaseModel for models without actions."""

    __slots__ = ()

    ### IModel ###

    def provides_action(self, name):
        return defer.succeed(False)

    def count_actions(self):
        return defer.succeed(0)

    def fetch_action(self, name):
        return defer.succeed(None)

    def fetch_actions(self):
        return defer.succeed(iter([]))


class EmptyModel(AbstractModel, NoChildrenMixin, NoActionsMixin):
    """A model without any items or actions."""

    __slots__ = ()


class StaticChildrenMixin(object):

    _model_items = container.MroDict("_mro_model_items")

    __slots__ = ()

    ### IModel ###

    def provides_item(self, name):
        d = self._do_fetch_item(name, "Error fetching %s model %s item %s",
                                self.identity, self.name, name)
        return d.addCallback(lambda i: i is not None)

    def count_items(self):
        d = self._do_fetch_items("Error counting %s model "
                                 "%s items", self.identity, self.name)
        return d.addCallback(len)

    def fetch_item(self, name):
        return self._do_fetch_item(name, "Error fetching %s model %s item %s",
                                   self.identity, self.name, name)

    def fetch_items(self):
        return self._do_fetch_items("Error fetching %s model "
                                    "%s items", self.identity, self.name)

    def query_items(self, **kwargs):
        return defer.fail(NotSupported("%s model %s do not support "
                                       "item queries" % (self.identity,
                                                         self.name)))

    ### private ###

    def _do_fetch_items(self, error_tmpl, *error_args):

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        def extract_items(param):
            # Only return model items whose initiate method
            # returns a non None value
            return [i for s, i in param if s and i is not None]

        def extract_first_failure(failure):
            failure.trap(defer.FirstError)
            return failure.subFailure

        items = [item(self).initiate().addErrback(filter_error)
                 for item in self._model_items.itervalues()]
        d = defer.DeferredList(items,
                               fireOnOneErrback=True,
                               consumeErrors=True)
        d.addCallbacks(extract_items, extract_first_failure)
        return d

    def _do_fetch_item(self, name, error_tmpl, *error_args):

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        item = self._model_items.get(name)
        if item is not None:
            return item(self).initiate().addErrback(filter_error)

        return defer.succeed(None)

    ### annotations ###

    @classmethod
    def annotate_item_meta(cls, item_name, name, value, scheme=None):
        """@see: feat.models.model.item_meta"""
        cls._model_items[item_name].annotate_meta(name, value, scheme=scheme)

    @classmethod
    def annotate_child(cls, name, source=None, view=None, model=None,
                       enabled=None, browse=None, fetch=None,
                       label=None, desc=None, meta=None):
        """@see: feat.models.model.child"""
        name = _validate_str(name)
        item = MetaModelItem.new(name, source=source, view=view, model=model,
                                 enabled=enabled, browse=browse, fetch=fetch,
                                 label=label, desc=desc, meta=meta)
        cls._model_items[name] = item

    @classmethod
    def annotate_attribute(cls, name, value_info, getter=None, setter=None,
                           label=None, desc=None, meta=None, model_meta=None):
        """@see: feat.models.model.attribute"""
        from feat.models import attribute
        name = _validate_str(name)
        attr_ident = cls._model_identity + "." + name
        attr_cls = attribute.MetaAttribute.new(attr_ident, value_info,
                                               getter=getter, setter=setter,
                                               meta=model_meta)
        item = MetaModelItem.new(name, model=attr_cls,
                                 label=label, desc=desc, meta=meta)
        if meta:
            for decl in meta:
                item.annotate_meta(*decl)
        cls._model_items[name] = item

    @classmethod
    def annotate_collection(cls, name, child_names=None,
                            child_source=None, child_view=None,
                            child_model=None, child_label=None,
                            child_desc=None, child_meta=None,
                            label=None, desc=None, meta=None,
                            model_meta=None):
        """@see: feat.models.model.collection"""
        name = _validate_str(name)
        coll_cls = MetaCollection.new(cls._model_identity + "." + name,
                                      child_names=child_names,
                                      child_source=child_source,
                                      child_view=child_view,
                                      child_model=child_model,
                                      child_label=child_label,
                                      child_desc=child_desc,
                                      child_meta=child_meta,
                                      meta=model_meta)
        item = MetaModelItem.new(name, model=coll_cls,
                                 label=label, desc=desc, meta=meta)
        cls._model_items[name] = item


class StaticActionsMixin(object):

    __slots__ = ()

    _action_items = container.MroDict("_mro_action_items")

    ### IModel ###

    def provides_action(self, name):
        d = self._do_fetch_action(name, "Error checking if %s model "
                                  "%s provides action %s", self.identity,
                                  self.name, name)
        return d.addCallback(lambda a: a is not None)

    def count_actions(self):
        d = self._do_fetch_actions("Error counting %s model %s "
                                   "actions", self.identity, self.name)
        return d.addCallback(len)

    def fetch_action(self, name):
        return self._do_fetch_action(name, "Error fetching %s model %s "
                                     "action %s", self.identity,
                                     self.name, name)

    def fetch_actions(self):
        return self._do_fetch_actions("Error fetching %s model %s "
                                      "actions", self.identity, self.name)

    ### private ###

    def _do_fetch_action(self, name, error_tmpl, *error_args):

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        def action_initiated(action_item):
            # Only fetch action whose item initiate method returns
            # a non None value
            if action_item is not None:
                return action_item.fetch()
            return None

        item = self._action_items.get(name)
        if item is not None:
            d = item(self).initiate().addErrback(filter_error)
            d.addCallback(action_initiated)
            return d

        return defer.succeed(None)

    def _do_fetch_actions(self, error_tmpl, *error_args):

        def init_action(factory):
            d = factory(self).initiate()
            d.addCallbacks(action_initiated, filter_error)
            return d

        def action_initiated(action_item):
            # Only fetch action of items whose initiate method
            # returns a non None value
            if action_item is not None:
                return action_item.fetch()
            return None

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        def extract_actions(param):
            # Cleanup actions whose action item's initiate method
            # did not returns a non None value
            return [a for s, a in param if s and a is not None]

        def extract_first_failure(failure):
            failure.trap(defer.FirstError)
            return failure.value.subFailure

        actions = [init_action(f) for f in self._action_items.itervalues()]
        d = defer.DeferredList(actions,
                               fireOnOneErrback=True,
                               consumeErrors=True)
        d.addCallbacks(extract_actions, extract_first_failure)
        return d

    ### annotations ###

    @classmethod
    def annotate_action(cls, name, factory, label=None, desc=None):
        """@see: feat.models.model.action"""
        name = _validate_str(name)
        item = MetaActionItem.new(name, factory, label=label, desc=desc)
        cls._action_items[name] = item

    @classmethod
    def annotate_create(cls, name, effects, value_info=None,
                        params=None, label=None, desc=None):
        """@see: feat.models.model.create"""
        name = _validate_str(name)
        category=ActionCategories.create
        factory = models_action.MetaAction.new(name,
                                               category=category,
                                               value_info=value_info,
                                               result_info=value.Response(),
                                               is_idempotent=False,
                                               params=params,
                                               effects=effects)
        item = MetaActionItem.new(name, factory, label=label, desc=desc)
        cls._action_items[name] = item

    @classmethod
    def annotate_delete(cls, name, effects, label=None, desc=None):
        """@see: feat.models.model.delete"""
        name = _validate_str(name)
        category=ActionCategories.delete
        factory = models_action.MetaAction.new(name,
                                               category=category,
                                               result_info=value.Response(),
                                               is_idempotent=True,
                                               effects=effects)
        item = MetaActionItem.new(name, factory, label=label, desc=desc)
        cls._action_items[name] = item


class Model(AbstractModel, StaticChildrenMixin, StaticActionsMixin):
    """Static model with a known set of sub-models and actions."""

    __slots__ = ()


class BaseModelItem(models_meta.Metadata):

    __slots__ = ("model", )

    def __init__(self, model):
        self.model = model

    ### public ###

    def initiate(self):
        """If the returned deferred is fired with None,
        the item will be disabled as if did not exists."""
        return defer.succeed(self)

    ### virtual ###

    @property
    def name(self):
        """To be overridden by sub classes."""

    @property
    def aspect(self):
        """To be overridden by sub classes."""

    ### protected ###

    def _filter_key_errors(self, failure):
        failure.trap(KeyError)
        raise IgnoredError()

    def _filter_errors(self, failure):
        if failure.check(IgnoredError):
            return None
        error.handle_failure(None, failure,
                             "Failure creating model for '%s'", self.name)
        return failure

    def _create_model(self, view_getter=None, source_getters=None,
                      model_factory=None):

        if view_getter is not None:
            d = defer.succeed(view_getter)
            d.addCallback(self._retrieve_view)
            d.addCallback(self._check_view)
        else:
            # views are inherited
            d = defer.succeed(self.model.view)

        d.addErrback(self._filter_key_errors)
        d.addCallback(self._retrieve_model, source_getters, model_factory)

        d.addErrback(self._filter_errors)
        return d

    def _retrieve_view(self, view_getter=None):
        if callable(view_getter):
            context = self.model.make_context(key=self.name)
            return view_getter(None, context)

        return view_getter

    def _check_view(self, view):
        if view is None:
            raise ModelError("'%s' view not found" % (self.name, ))
        return view

    def _retrieve_model(self, view, source_getters, model_factory):
        d = defer.succeed(self.model.source)
        context = self.model.make_context(key=self.name, view=view)
        for getter in source_getters:
            d.addCallback(self._retrieve_source, getter, context)
        d.addErrback(self._filter_key_errors)
        d.addCallback(self._wrap_source, view, model_factory)
        return d

    def _retrieve_source(self, source, source_getter, context):
        if source_getter is not None:
            return source_getter(source, context)
        return source

    def _wrap_source(self, source, view, model_factory):
        if source is None:
            return source

        if IReference.providedBy(source):
            return source

        if IModel.providedBy(source):
            return self._init_model(source, view)

        if not IModelFactory.providedBy(model_factory):
            if callable(model_factory):
                ctx = self.model.make_context(key=self.name, view=view)
                d = model_factory(source, ctx)
                d.addCallback(self._got_model_factory, source, view)
                return d

        return self._got_model_factory(model_factory, source, view)

    def _got_model_factory(self, model_factory, source, view):
        model = source
        factory = None
        if IModelFactory.providedBy(model_factory):
            factory = IModelFactory(model_factory)
        elif isinstance(model_factory, str):
            factory = get_factory(model_factory)
        if factory is not None:
            model = factory(source)
        return self._init_model(model, view)

    def _init_model(self, model, view):
        return IModel(model).initiate(aspect=self.aspect,
                                      view=view, parent=self.model)


class MetaModelItem(type(BaseModelItem)):

    implements(IAspect)

    @staticmethod
    def new(name, source=None, view=None, model=None, enabled=None,
            browse=None, fetch=None, label=None, desc=None, meta=None):
        cls_name = utils.mk_class_name(name, "ModelItem")
        name = _validate_str(name)
        ref = models_reference.Relative(name)
        enabled = True if enabled is None else enabled
        cls = MetaModelItem(cls_name, (ModelItem, ),
                             {"__slots__": (),
                              "_name": name,
                              "_reference": ref,
                              "_source": _validate_effect(source),
                              "_fetch": _validate_effect(fetch),
                              "_browse": _validate_effect(browse),
                              "_factory": _validate_model_factory(model),
                              "_view": _validate_effect(view),
                              "_enabled": _validate_effect(enabled),
                              "_label": _validate_optstr(label),
                              "_desc": _validate_optstr(desc)})
        cls.apply_class_meta(meta)
        return cls

    ### IAspect ###

    @property
    def name(cls): #@NoSelf
        return cls._name

    @property
    def label(cls): #@NoSelf
        return cls._label

    @property
    def desc(cls): #@NoSelf
        return cls._desc


class ModelItem(BaseModelItem):

    __metaclass__ = MetaModelItem
    __slots__ = ()

    implements(IModelItem)

    _name = None
    _reference = None
    _source = None
    _fetch = None
    _browse = None
    _view = None
    _enabled = True
    _factory = None
    _label = None
    _desc = None

    def __init__(self, model):
        BaseModelItem.__init__(self, model)

    ### public ###

    def initiate(self):
        """If the returned deferred is fired with None,
        the item will be disabled as if did not exists."""
        if not callable(self._enabled):
            d = defer.succeed(self._enabled)
        else:
            context = self.model.make_context(key=self.name)
            d = self._enabled(None, context)
        return d.addCallback(lambda f: self if f else None)

    ### overridden ###

    @property
    def aspect(self):
        return type(self)

    ### IModelItem ###

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self._label

    @property
    def desc(self):
        return self._desc

    @property
    def reference(self):
        if self.model._model_is_detached:
            return None
        return self._reference

    def browse(self):
        return self._create_model(view_getter=self._view,
                                  source_getters=[self._source, self._browse],
                                  model_factory=self._factory)

    def fetch(self):
        return self._create_model(view_getter=self._view,
                                  source_getters=[self._source, self._fetch],
                                  model_factory=self._factory)


class MetaActionItem(type):

    implements(IAspect)

    @staticmethod
    def new(name, factory, label=None, desc=None):
        cls_name = utils.mk_class_name(name, "Action")
        return MetaActionItem(cls_name, (ActionItem, ),
                              {"__slots__": (),
                               "_name": _validate_str(name),
                               "_factory": _validate_action_factory(factory),
                               "_label": _validate_optstr(label),
                               "_desc": _validate_optstr(desc)})

    ### IAspect ###

    @property
    def name(cls): #@NoSelf
        return cls._name

    @property
    def label(cls): #@NoSelf
        return cls._label

    @property
    def desc(cls): #@NoSelf
        return cls._desc


class ActionItem(object):

    __meta__ = MetaActionItem
    __slots__ = ("model", )

    _name = None
    _label = None
    _desc = None
    _factory = None

    def __init__(self, model):
        self.model = model

    def initiate(self):
        """If the returned deferred is fired with None,
        the action will be disabled as if did not exists."""
        return defer.succeed(self)

    ### public ###

    def fetch(self):
        return self._factory(self.model).initiate(aspect=type(self))


class DynamicItemsMixin(object):

    __slots__ = ()

    _fetch_names = None
    _fetch_source = None
    _fetch_view = None
    _item_label = None
    _item_desc = None
    _item_model = None
    _item_meta = container.MroList("_mro_item_meta")

    ### IModel ###

    def provides_item(self, name):
        d = self._do_fetch_item(name, "checking item availability",
                                "Error checking if %s model "
                                "%s item %s is provided",
                                self.identity, self.name, name)
        return d.addCallback(lambda i: i is not None)

    def count_items(self):
        d = self._do_fetch_items("counting items",
                                 "Error counting %s model %s items",
                                 self.identity, self.name)
        return d.addCallback(len)

    def fetch_item(self, name):
        return self._do_fetch_item(name, "fetching item",
                                   "Error fetching %s model %s item %s",
                                   self.identity, self.name, name)

    def fetch_items(self):
        d = self._do_fetch_items("fetching items", "Error fetching %s "
                                 "model %s items", self.identity, self.name)
        return d

    def query_items(self, **kwargs):
        return self._notsup("querying items")

    ### private ###

    def _notsup(self, feature_desc):
        msg = ("%s model %s does not support %s"
               % (self.identity, self.name, feature_desc, ))
        return defer.fail(NotSupported(msg))

    def _do_fetch_item_names(self, context):
        if self._fetch_names is None:
            return self._notsup("fetching items")

        def filter_error(failure):
            if failure.check(KeyError):
                return [] # nothing
            error.handle_failure(None, failure, "Error fetching %s model %s "
                                 "item names", self.identity, self.name)
            return failure

        d = defer.succeed(None)
        d.addCallback(self._fetch_names, context)
        return d.addErrback(filter_error)

    def _do_fetch_item(self, name, opname, error_tmpl, *error_args):
        if (self._fetch_source is None
            and self._fetch_view is None):
            return self._notsup(opname)

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        item = DynamicModelItem(self, name)
        return item.initiate().addErrback(filter_error)

    def _do_fetch_items(self, opname, error_tmpl, *error_args):
        if (self._fetch_names is None
            or (self._fetch_source is None
                and self._fetch_view is None)):
            return self._notsup(opname)

        def filter_error(failure):
            if failure.check(KeyError):
                return None
            error.handle_failure(None, failure, error_tmpl, *error_args)
            return failure

        def extract_items(param):
            # Only returns the item whose initiate method
            # returns a non None value
            return [v for s, v in param if s and v is not None]

        def extract_first_error(failure):
            failure.trap(defer.FirstError)
            return failure.value.subFailure

        def create_items(names):
            if not names:
                return []
            Item = DynamicModelItem
            items = [Item(self, n).initiate().addErrback(filter_error)
                     for n in names]
            d = defer.DeferredList(items,
                                   fireOnOneErrback=True,
                                   consumeErrors=True)
            d.addCallbacks(extract_items, extract_first_error)
            return d

        context = self.make_context()
        d = defer.succeed(context)
        d.addCallback(self._do_fetch_item_names)
        d.addCallback(create_items)
        return d

    ### annotations ###

    @classmethod
    def annotate_child_label(cls, label):
        """@see: feat.models.collection.child_label"""
        cls._item_label = _validate_optstr(label)

    @classmethod
    def annotate_child_desc(cls, desc):
        """@see: feat.models.collection.child_desc"""
        cls._item_desc = _validate_optstr(desc)

    @classmethod
    def annotate_child_meta(cls, name, value, scheme=None):
        """@see: feat.models.collection.child_meta"""
        cls._item_meta.append((name, value, scheme))

    @classmethod
    def annotate_child_model(cls, model_factory):
        """@see: feat.models.collection.child_model"""
        cls._item_model = _validate_model_factory(model_factory)

    @classmethod
    def annotate_child_names(cls, effect):
        """@see: feat.models.collection.child_names"""
        cls._fetch_names = _validate_effect(effect)

    @classmethod
    def annotate_child_source(cls, effect):
        """@see: feat.models.collection.child_source"""
        cls._fetch_source = _validate_effect(effect)

    @classmethod
    def annotate_child_view(cls, effect):
        """@see: feat.models.collection.child_view"""
        cls._fetch_view = _validate_effect(effect)


class MetaCollection(type(AbstractModel)):

    @staticmethod
    def new(identity, child_names=None,
            child_source=None, child_view=None,
            child_model=None, child_label=None,
            child_desc=None, child_meta=None, meta=None):
        cls_name = utils.mk_class_name(identity)
        cls = MetaCollection(cls_name, (_DynCollection, ), {"__slots__": ()})
        cls.annotate_identity(identity)
        cls.annotate_child_label(child_label)
        cls.annotate_child_desc(child_desc)
        cls.annotate_child_model(child_model)
        if child_meta:
            for meta_item in child_meta:
                cls.annotate_child_meta(*meta_item)
        cls.annotate_child_names(child_names)
        cls.annotate_child_source(child_source)
        cls.annotate_child_view(child_view)
        cls.apply_class_meta(meta)
        return cls


class Collection(AbstractModel, StaticActionsMixin, DynamicItemsMixin):
    """
    A model with a static list of actions
    and a dynamic set of sub-models."""

    __metaclass__ = MetaCollection
    __slots__ = ()


class _DynCollection(Collection):

    __slots__ = ("parent", )

    ### IModel ###

    def initiate(self, aspect=None, view=None, parent=None):
        self.parent = parent
        return Collection.initiate(self, aspect=aspect,
                                   view=view, parent=parent)

    ### IContextMaker ###

    def make_context(self, key=None, view=None, action=None):
        model = self.parent or self
        return {"model": model,
                "view": view if view is not None else model.view,
                "key": unicode(key) if key is not None else self.name,
                "action": action}


class DynamicModelItem(BaseModelItem):

    __slots__ = ("_name", "_reference", "_child")

    implements(IModelItem, IAspect)

    def __init__(self, model, name):
        BaseModelItem.__init__(self, model)
        self._name = name
        self._reference = models_reference.Relative(name)
        self._child = None
        metadata = list(model._item_meta)
        if metadata:
            for meta in metadata:
                self.put_meta(*meta)

    ### overridden ###

    @property
    def aspect(self):
        return self

    def initiate(self):
        # We need to do it right away to be sure the source exists
        d = self._create_model(view_getter=self.model._fetch_view,
                               source_getters=[self.model._fetch_source],
                               model_factory=self.model._item_model)
        d.addCallback(self._got_model)
        return d

    ### IModelItem / IAspect ###

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        return self.model._item_label

    @property
    def desc(self):
        return self.model._item_desc

    @property
    def reference(self):
        if self.model._model_is_detached:
            return None
        return self._reference

    ### IModelItem ###

    def browse(self):
        return self._child

    def fetch(self):
        return self._child

    ### private ###

    def _got_model(self, model):
        if model is None:
            return None
        self._child = model
        return self


### private ###


_model_factories = {}


class IgnoredError(Exception):
    pass


def _validate_flag(value):
    return bool(value)


def _validate_str(value):
    return unicode(value)


def _validate_optstr(value):
    return unicode(value) if value is not None else None


def _validate_model_factory(factory):
    if (factory is None
        or isinstance(factory, str)
        or IModelFactory.providedBy(factory)):
        return factory
    if callable(factory):
        return staticmethod(factory)
    return IModelFactory(factory)


def _validate_action_factory(factory):
    return IActionFactory(factory)


def _validate_effect(effect):
    if isinstance(effect, types.FunctionType):
        return staticmethod(effect)
    return effect
