from zope.interface import implements

from feat.common import log, defer
from feat.models import reference
from feat.web import document
from feat.web.markup import html

from feat.models.interface import ActionCategories, ValueTypes
from feat.models.interface import IModel, IAttribute, IMetadata
from feat.models.interface import IValueOptions, IErrorPayload


MIME_TYPE = "text/html"


class BaseLayout(html.Document):

    def __init__(self, title, context):
        html.Document.__init__(self, html.StrictPolicy(), title)
        self._link_static_files(context)

    def _link_static_files(self, context):
        url = self._local_url(context, 'static', 'feat.css')
        self.head.content.append(
            html.tags.link(type='text/css', rel='stylesheet', href=url)())

        scripts = [('http://ajax.googleapis.com/ajax/libs/'
                   'jquery/1.6/jquery.min.js'),
                   self._local_url(context, 'static', 'script', 'json2.js'),
                   self._local_url(context, 'static', 'script', 'feat.js'),
                   self._local_url(context, 'static', 'script', 'form.js'),
                   self._local_url(context, 'static', 'script',
                                   'jquery.cseditable.js')]
        for url in scripts:
            self.head.content.append(
                html.tags.script(src=url, type='text/javascript'))

    def _local_url(self, context, *parts):
        return reference.Local(*parts).resolve(context)


class ModelLayout(BaseLayout):

    def __init__(self, title, context):
        BaseLayout.__init__(self, title, context)
        self.div(_class='header')(*self._render_header(context)).close()
        self.h1()(title).close()
        self.content = self.div(_class='content')()

    def _render_header(self, context):
        res = list("History: ")
        host, port = context.names[0]
        root_url = reference.Local().resolve(context)
        res.append(html.tags.a(href=root_url)("%s:%d" % (host, port)))
        for index in range(1, len(context.names)):
            name = context.names[index]
            path = context.names[1:index+1]
            url = reference.Local(*path).resolve(context)
            res.append("/")
            res.append(html.tags.a(href=url)(name))
        return res


class ErrorLayout(BaseLayout):
    pass


def parse_meta(meta_items):
    return [i.strip() for i in meta_items.value.split(",")]


def html_order(meta):
    if not IMetadata.providedBy(meta):
        return []
    meta = (parse_meta(i) for i in meta.get_meta('html-order'))
    return [v for m in meta for v in m]


def render_array(meta):
    if not IMetadata.providedBy(meta):
        return False
    meta = (parse_meta(i) for i in meta.get_meta('html-render'))
    for fields in meta:
        if fields[0] == "array":
            return int(fields[1])
    return None


def html_links(meta):
    if not IMetadata.providedBy(meta):
        return set()
    return set(str(m.value) for m in meta.get_meta('html-link'))


class ModelWriter(log.Logger):
    implements(document.IWriter)

    def __init__(self, logger=None):
        log.Logger.__init__(self, logger)

    @defer.inlineCallbacks
    def write(self, doc, model, *args, **kwargs):
        self.log("Rendering html doc for a model: %r", model.identity)
        context = kwargs['context']

        title = model.label or model.name
        markup = ModelLayout(title, context)

        if IAttribute.providedBy(model):
            attr = self._format_attribute(model, context)
            markup.content.content.append(attr)
        else:
            yield self._render_items(model, markup, context)
            yield self._render_actions(model, markup, context)

        yield markup.render(doc)

    def _order_items(self, model, items):
        ordered = []
        lookup = dict((i.name, i) for i in items)
        order = html_order(model)
        for name in order:
            item = lookup.pop(name, None)
            if item is not None:
                ordered.append(item)
        ordered.extend(lookup.values())
        return ordered

    @defer.inlineCallbacks
    def _render_items(self, model, markup, context):
        items = yield model.fetch_items()
        if not items:
            return

        array_deepness = render_array(model)
        if array_deepness:
            markup.div(_class='array')(
                self._render_array(model, array_deepness, context)).close()
        else:
            ordered = self._order_items(model, items)
            ul = markup.ul(_class="items")
            for item in ordered:
                li = markup.li()

                url = item.reference.resolve(context)
                markup.span(_class='name')(
                    html.tags.a(href=url)(item.label or item.name)).close()

                #FIXME: shouldn't need to fetch the model for that
                m = yield item.fetch()
                if IAttribute.providedBy(m):
                    li.append(self._format_attribute_item(item, context))
                else:
                    markup.span(_class="value").close()

                if item.desc:
                    markup.span(_class='desc')(item.desc).close()

                array_deepness = render_array(item)
                if array_deepness:
                        submodel = yield item.fetch()
                        if IModel.providedBy(submodel):
                            array = self._render_array(submodel,
                                                       array_deepness,
                                                       context)
                            markup.div(_class='array')(array).close()
                li.close()
            ul.close()
        markup.hr()

    @defer.inlineCallbacks
    def _render_actions(self, model, markup, context):
        actions = yield model.fetch_actions()
        actions = [x for x in actions
                   if x.category != ActionCategories.retrieve]
        if not actions:
            return
        ul = markup.ul(_class="actions")
        for action in actions:
            li = markup.li()
            markup.span(_class='name')(action.label or action.name).close()
            if action.desc:
                markup.span(_class='desc')(action.desc).close()
            self._render_action_form(action, markup, context)
            li.close()
            actions
        ul.close()
        markup.hr()

    def _render_action_form(self, action, markup, context):
        method = context.get_action_method(action).name
        url = action.reference.resolve(context)
        form = markup.form(method=method, action=url, _class='action_form')
        div = markup.div()
        for param in action.parameters:
            self._render_param_field(markup, context, param)
        markup.input(type='submit', value='Perform')
        div.close()
        form.close()

    def _render_param_field(self, markup, context, param):
        default = param.value_info.use_default and \
                  param.value_info.default

        label = param.label or param.value_info.label or param.name
        markup.label()(label).close()
        text_types = [ValueTypes.integer, ValueTypes.number,
                      ValueTypes.string]
        v_t = param.value_info.value_type
        if v_t in text_types:
            if IValueOptions.providedBy(param.value_info):
                options = IValueOptions(param.value_info)
                select = markup.select(name=param.name)
                for o in options.iter_options():
                    option = markup.option(value=o.value)(o.label).close()
                    if o.value == default:
                        option["selected"] = None
                select.close()
            else:
                markup.input(type='text', default=default,
                             name=param.name)
        elif v_t == ValueTypes.boolean:
            extra = {}
            if default is True:
                extra['checked'] = '1'
            markup.input(type='checkbox', value='true',
                         name=param.name, **extra)
        else:
            msg = ("ValueType %s is not supported by HTML writer" %
                   (v_t.__name__))
            markup.span(_class='type_not_supported')(msg)
        if param.desc:
            markup.span(_class='desc')(param.desc).close()
        if not param.is_required:
            markup.span(_class='optional')("Optional").close()
        markup.br()

    @defer.inlineCallbacks
    def _format_attribute_item(self, item, context):
        model = yield item.fetch()
        if not IModel.providedBy(model):
            defer.returnValue("")
        result = yield self._format_attribute(model, context.descend(model),
                                              context, html_links(item))
        defer.returnValue(result)

    @defer.inlineCallbacks
    def _format_attribute(self, model, context,
                          supercontext=None, links=set()):
        set_action = yield model.fetch_action('set')
        classes = ['value']
        extra = dict()
        if set_action:
            classes.append('inplace')
            extra['rel'] = set_action.reference.resolve(context)

        value = ""
        get_action = yield model.fetch_action('get')
        if get_action is not None:
            value = yield get_action.perform()
            if supercontext and "owner" in links:
                url = reference.Relative().resolve(supercontext)
                value = html.tags.a(href=url)(value)

        defer.returnValue(
            html.tags.span(_class=" ".join(classes), **extra)(value))

    @defer.inlineCallbacks
    def _render_array(self, model, limit, context):
        tree = list()
        flattened = list()
        columns = list()

        if not context.models or model != context.models[-1]:
            # this fixes issue with the fact that write() method is passed
            # the context of the current model instead of the parrent
            context = context.descend(model)
        yield self._build_tree(tree, model, limit, context)
        self._flatten_tree(flattened, columns, dict(), tree[0], limit)

        headers = [html.tags.th()(x) for x, _ in columns]
        table = html.tags.table()(
            html.tags.thead()(*headers))
        tbody = html.tags.tbody()
        table.content.append(tbody)

        for row in flattened:
            tr = html.tags.tr()
            for column in columns:
                td = html.tags.td()
                value = row.get(column)
                if value:
                    item, cur_context = value
                    td.append(self._format_attribute_item(item, cur_context))
                tr.append(td)

            tbody.append(tr)

        defer.returnValue(table)

    @defer.inlineCallbacks
    def _build_tree(self, tree, model, limit, context):
        if not IModel.providedBy(model):
            return
        items = yield model.fetch_items()
        #FIXME: column ordering do not work
        ordered = self._order_items(model, items)
        # [dict of attributes added by this level, list of child rows]
        tree.append([dict(), list()])
        for item in ordered:
            #FIXME: should not need to fetch model for this
            m = yield item.fetch()
            if not IAttribute.providedBy(m):
                if limit > 0:
                    submodel = yield item.fetch()
                    if IModel.providedBy(submodel):
                        subcontext = context.descend(submodel)
                        yield self._build_tree(tree[-1][1], submodel,
                                               limit - 1, subcontext)
            else:
                column_name = item.label or item.name
                tree[-1][0][(column_name, limit)] = (item, context)

    def _flatten_tree(self, result, columns, current, tree, limit):
        current = dict(current)

        if tree[0]:
            current.update(tree[0])
            for column in tree[0].keys():
                if column not in columns:
                    columns.append(column)

        if not tree[1] and current:
            result.append(current)

        for subtree in tree[1]:
            if limit > 0:
                self._flatten_tree(result, columns, current, subtree,
                                   limit - 1)
            else:
                result.append(current)


class ErrorWriter(log.Logger):
    implements(document.IWriter)

    def __init__(self, logger=None):
        log.Logger.__init__(self, logger)

    def write(self, doc, obj, *args, **kwargs):
        self.log("Rendering html error: %s", obj.message)
        context = kwargs['context']
        markup = ErrorLayout("Error", context)

        s = markup.span(_class="error")("ERROR")
        if obj.code is not None:
            s.content.append(" ")
            s.content.append(str(obj.code))
        if obj.message is not None:
            s.content.append(": ")
            s.content.append(obj.message)
        s.close()

        if obj.debug is not None:
            markup.br()
            markup.span(_class="debug")(obj.debug).close()

        if obj.trace is not None:
            markup.br()
            markup.pre(_class="trace")(obj.trace).close()

        return markup.render(doc)


model_writer = ModelWriter()
error_writer = ErrorWriter()

document.register_writer(model_writer, MIME_TYPE, IModel)
document.register_writer(error_writer, MIME_TYPE, IErrorPayload)
