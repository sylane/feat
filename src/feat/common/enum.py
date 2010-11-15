# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4


class MetaEnum(type):

    def __init__(cls, name, bases, namespace):
        type.__init__(cls, name, bases, namespace)
        cls._names = {}  # {str: Enum}
        cls._values = {} # {int: Enum}
        cls._items = {}  # {Enum: str}
        for key, value in namespace.items():
            if isinstance(value, int):
                cls.add(key, value)

    def add(cls, name, value):
        if not isinstance(value, int):
            raise TypeError("Enum value type must be int not %s"
                             % (value.__class__.__name__))
        if name in cls._names:
            raise ValueError("There is already an enum called %s" % (name, ))
        if value in cls._values:
            raise ValueError(
                "Error while creating enum %s of type %s, "
                "it has already been created as %s" % (
                value, cls.__name__, cls._values[value]))

        self = super(Enum, cls).__new__(cls, value)
        self.name = name

        cls._values[value] = self
        cls._names[name] = self
        cls._items[self] = name
        setattr(cls, name, self)

        return self

    def get(cls, key):
        """
        str, int or Enum => Enum
        """
        if isinstance(key, Enum) and not isinstance(key, cls):
            raise TypeError("Cannot type cast between enums")
        if isinstance(key, int):
            if not int(key) in cls._values:
                raise KeyError("There is no enum with key %d" % key)
            return cls._values[key]
        if isinstance(key, str):
            if not key in cls._names:
                raise KeyError("There is no enum with name %s" % key)
            return cls._names[key]
        raise TypeError("Invalid enum key type: %s"
                         % (key.__class__.__name__))

    __getitem__ = get

    def __contains__(cls, key):
        if isinstance(key, Enum) and not isinstance(key, cls):
            raise TypeError("Cannot type cast between enums")
        return int(key) in cls._values

    def __len__(cls):
        return len(cls._values)

    def __iter__(cls):
        return iter(cls._items)

    def items(cls):
        return cls._items.items()

    def iteritems(cls):
        return cls._items.iteritems()

    def values(cls):
        return cls._items.values()

    def itervalues(cls):
        return cls._items.itervalues()

    def keys(cls):
        return cls._items.keys()

    def iterkeys(cls):
        return cls._items.iterkeys()


class Enum(int):
    """
    enum is an enumered type implementation in python.

    To use it, define an enum subclass like this:

    >>> from feat.common.enum import Enum
    >>>
    >>> class Status(Enum):
    >>>     OPEN, CLOSE = range(2)
    >>> Status.OPEN
    '<Status value OPEN>'

    All the integers defined in the class are assumed to be enums and
    values cannot be duplicated
    """

    __metaclass__ = MetaEnum

    def __new__(cls, value):
        return cls.get(value)

    def __cmp__(self, value):
        if value is None:
            return NotImplemented
        if isinstance(value, Enum) and not isinstance(value, type(self)):
                raise TypeError("Cannot compare between enums")
        return super(Enum, self).__cmp__(value)

    def __str__(self):
        return '<%s value %s>' % (
            self.__class__.__name__, self.name)

    __repr__ = __str__
