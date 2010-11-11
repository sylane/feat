import types

from . import reflect

"""TODO: Better function mimicry."""


def simple(decorator):
    '''Decorator used to create decorators without arguments.
    Should be used with function returning another function
    that will be called with the original function has the first
    parameter.
    No difference are made between method and function,
    so the wrapper function will have to know if the first
    argument is an instance (self).

    Note that when using reflect or annotate module functions,
    depth should be incremented by one.

    Example::

        @decorator.simple
        def mydecorator(function_original):

            def wrapper(call, arguments):
                # processing
                return function_original(call, arguments)

            return wrapper

        @mydecorator
        def myfunction():
            pass

    '''

    def meta_decorator(function):
        return _function_mimicry(function, decorator(function))

    return meta_decorator


def simple_consistent(decorator):
    '''Decorator used to create consistent decorators.
    Consistent in the meaning that the wrapper do not have to
    care if the wrapped callable is a function or a method,
    it will always receive a valid callable.
    If the decorator is used with a function, the wrapper will
    receive the function itself, but if the decorator is used
    with a method, the wrapper will receive a bound method
    callable directly and the first argument (self) will be removed.
    This allows writing decorators behaving consistently
    with function and method.

    Note that when using reflect or annotate module functions,
    depth should be incremented by one.

    Example::

        @decorator.simple_consistent
        def mydecorator(original_function):

            def wrapper(callable, call, arguments):
                # processing
                return callable(call, arguments)

            return wrapper

        @mydecorator
        def myfunction():
            pass

    '''

    def meta_decorator(function):

        wrapper = decorator(function)

        if reflect.inside_class_definition(depth=2):

            def method_wrapper(*args, **kwargs):
                obj, args = args[0], args[1:]
                method = types.MethodType(function, obj, obj.__class__)
                return wrapper(method, *args, **kwargs)

            meta_wrapper = _function_mimicry(function, method_wrapper)

        else:

            def function_wrapper(*args, **kwargs):
                return wrapper(function, *args, **kwargs)

            meta_wrapper = _function_mimicry(function, function_wrapper)

        return meta_wrapper

    return meta_decorator


def parametrized(decorator):
    '''Decorator used to create decorators with arguments.
    Should be used with function returning another function
    that will be called with the original function has the first
    parameter.
    No difference are made between method and function,
    so the wrapper function will have to know if the first
    argument is an instance (self).

    Note that when using reflect or annotate module functions,
    depth should be incremented by one.

    Example::

        @decorator.with_args
        def mydecorator(function_original, decorator, arguments):

            def wrapper(call, arguments):
                # processing
                return function_original(call, arguments)

            return wrapper

        @mydecorator(decorator, arguments)
        def myfunction():
            pass

    '''

    def meta_decorator(*args, **kwargs):
        return _NormalMetaDecorator(decorator, args, kwargs)

    return meta_decorator


def parametrized_consistent(decorator):
    '''Decorator used to create consistent decorators with arguments.
    Consistent in the meaning that the wrapper do not have to
    care if the wrapped callable is a function or a method,
    it will always receive a valid callable.
    If the decorator is used with a function, the wrapper will
    receive the function itself, but if the decorator is used
    with a method, the wrapper will receive a bound method
    callable directly and the first argument (self) will be removed.
    This allows writing decorators behaving consistently
    with function and method.

    Note that when using reflect or annotate module functions,
    depth should be incremented by one.

    Example::

        @decorator.parametrized_consistent
        def mydecorator(original_function, decorator, arguments):

            def wrapper(callable, call, arguments):
                # processing
                return callable(call, arguments)

            return wrapper

        @mydecorator(decorator, arguments)
        def myfunction():
            pass

    '''

    def meta_decorator(*args, **kwargs):
        return _ConsistentMetaDecorator(decorator, args, kwargs)

    return meta_decorator


### Private ###


def _function_mimicry(original, mimic):
    #FIXME: We should do better and to copy function signature too
    mimic.__name__ = original.__name__
    mimic.__doc__ = original.__doc__
    return mimic


class _NormalMetaDecorator(object):
    '''Wrap a callable, no difference are made between function and method.
    The wrapper will have to know if the first argument is an instance.'''

    def __init__(self, decorator, args, kwargs):
        self.decorator = decorator
        self.args = args
        self.kwargs = kwargs

    def __call__(self, callable):

        wrapper = self.decorator(callable, *self.args, **self.kwargs)

        def meta_wrapper(*args, **kwargs):
            return wrapper(*args, **kwargs)

        return _function_mimicry(callable, meta_wrapper)


class _ConsistentMetaDecorator(object):
    '''Consistently wrap function of method,
    by giving a valid callable to the wrapper.'''

    def __init__(self, decorator, args, kwargs):
        self.decorator = decorator
        self.args = args
        self.kwargs = kwargs

    def __call__(self, callable):

        wrapper = self.decorator(callable, *self.args, **self.kwargs)

        if reflect.inside_class_definition(depth=2):

            def method_wrapper(*args, **kwargs):
                obj, args = args[0], args[1:]
                method = types.MethodType(callable, obj, obj.__class__)
                return wrapper(method, *args, **kwargs)

            meta_wrapper = _function_mimicry(callable, method_wrapper)

        else:

            def function_wrapper(*args, **kwargs):
                return wrapper(callable, *args, **kwargs)

            meta_wrapper = _function_mimicry(callable, function_wrapper)

        return meta_wrapper