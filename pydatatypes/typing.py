"""
Work with the built-in :mod:`typing` module, specifically to convert to or
check membership of generic parameterized types like ``List[float]`` or
``Mapping[str, int]``.

Most class conversions are not actually implemented, objects already of the
correct type are passed through while others raise an exception.

The following conversions are implemented:

	* Mappings to dict, if dict < dest_type < Mapping.
	* Non-string sequences to list, if list < dest_type < Sequence.
	* Generic integral types to ``int``.
	* Generic real number types to ``float``.

.. data:: default_converter

	Default instance of :class:`.TypeConverter` to use at module level.

.. function:: astype

	Alias for :meth:`.TypeConverter.convert` method of :data:`.default_converter`.

.. function:: isinstance_ext

	Alias for :meth:`.TypeConverter.isinstance` method of
	:data:`.default_converter`.

.. function:: ensure_isinstance_ext

	Alias for :meth:`.TypeConverter.ensure_isinstance` method of
	:data:`.default_converter`.
"""

import sys
import typing
import numbers
from weakref import WeakKeyDictionary


__all__ = ['astype', 'isinstance_ext', 'ensure_isinstance_ext']


NoneType = type(None)


class TypeConversionError(TypeError):
	"""Raised when it is not possible to convert a value to the specified type.
	"""
	def __init__(self, msg=None, value=None, type=None, *, path=None):

		self.value = value
		self.type = type
		self.path = path

		if msg is not None:
			TypeError.__init__(self, msg)


def _is_py37():
	"""
	Check if python version is 3.7 or above.

	This is relevant because the typing module was significantly reworked in 3.7.
	"""
	return sys.version_info[1] >= 7

def _is_generic_py37(type_, origin=None):
	"""
	In Python >= 3.7, checks if ``type`` is an instance of ``typing._GenericAlias`` and optionally
	if its ``__origin__`` attribute matches ``origin``.
	"""
	return isinstance(type_, typing._GenericAlias) and (origin is None or type_.__origin__ is origin)


def issubclass_(t1, t2):
	"""
	Version of builtin ``issubclass`` but doesn't throw error when the first argument is not a class.
	"""
	if _is_py37() and _is_generic_py37(t1):
		t1 = t1.__origin__
	if not isinstance(t1, type):
		return False
	return issubclass(t1, t2)


def is_valid_annotation(x):
	"""Check if argument is a value that can be used with a type annotation.

	param x: Type object to check.
	:rtype: bool
	"""
	if _is_py37():
		return isinstance(x, (type, typing._Final))  # This isn't quite right but works
	else:
		return isinstance(x, (type, typing._TypingBase))


def is_generic_type(type_):
	"""Check if the given type is a generic type (parameters may be specified or not).

	Tuple and Union types are excluded.

	param type_: Type object to check.
	:rtype: bool
	"""
	if _is_py37():
		return _is_generic_py37(type_) and not is_union_type(type_) and not _is_generic_py37(type_, tuple)
	else:
		return isinstance(type_, type) and typing.Generic in type_.__mro__  # Don't all support issubclass()


def is_parameterized_type(type_):
	"""
	Check if a type object is a parameterized generic type from the
	``typing`` module.

	param type_: Type object to check.
	:rtype: bool

	>>> from typing import List
	>>> is_parameterized_type(List[int])
	True
	>>> is_parameterized_type(List)
	False
	>>> is_parameterized_type(list)
	False
	"""
	if _is_py37():
		return _is_generic_py37(type_) and \
			not is_union_type(type_) and \
			not any(isinstance(a, typing.TypeVar) for a in type_.__args__)
	else:
		return isinstance(type_, typing.GenericMeta) and type_.__args__ is not None


def is_structured_tuple_type(type_):
	"""
	Check if a type object is a structured (non-variadic) version of
	:class:`typing.Tuple`.

	param type_: Type object to check.
	:rtype: bool

	>>> from typing import Tuple
	>>> is_structured_tuple_type(Tuple[int, str])
	True
	>>> is_structured_tuple_type(Tuple)
	False
	>>> is_structured_tuple_type(Tuple[int, ...])
	False
	"""
	if _is_py37():
		return _is_generic_py37(type_, tuple) and \
		       type_.__args__ != () and \
		       type_.__args__[-1] is not Ellipsis
	else:
		return issubclass_(type_, typing.Tuple) and \
			type_.__args__ is not None and \
			type_.__args__[-1] is not Ellipsis


def is_union_type(type_):
	"""Check if a type is :data:`typing.Union` or a parameterized version of it.

	param type_: Type object to check.
	:type: bool

	>>> from typing import Union
	>>> is_union_type(Union)
	True
	>>> is_union_type(Union[int, str])
	True
	>>> is_union_type(Union[int])  # just returns int
	False
	>>> is_union_type(int)
	False
	"""
	if _is_py37():
		return type_ is typing.Union or _is_generic_py37(type_, typing.Union)
	else:
		return isinstance(type_, type(typing.Union))


def is_collection_type(type_):
	"""Check if a type is a collection (sized, iterable, container).

	3.6 has :class:`typing.Collection` and :class:`collection.abc.Collection`,
	3.5 doesn't.

	>>> is_collection_type(list)
	True

	>>> is_collection_type(dict)
	True

	# Generators are iterable but not sized
	>>> generator = (x**2 for x in range(10))
	>>> is_collection_type(type(generator))
	False
	"""
	return issubclass_(type_, typing.Sized) and \
		issubclass_(type_, typing.Iterable) and \
		issubclass_(type_, typing.Container)


class _TypeHandler:
	"""Converts to and performs instance checks for a specific set of types.

	:param converter: Parent TypeConverter instance to use for recursion.
	"""

	def __init__(self, converter):
		self.converter = converter

	def isinstance(self, value, type_, path):
		"""Check if a value is an instance of the type."""
		raise NotImplementedError()

	def ensure_isinstance(self, value, type_, path):
		"""Raise a TypeConversionError if value is not an instance of type."""
		if not self.isinstance(value, type_, path):
			self._raise_typeconversionerror(value, type_, path)

	def convert(self, value, type_, path):
		"""Convert a value to the specified type."""
		self.ensure_isinstance(value, type_, path)
		return value

	def _raise_typeconversionerror(self, value, type_, path):
		raise TypeConversionError(
			'Expected instance of {!r}, got {!r}'.format(type_, value),
			value,
			type_,
			path=path
		)


class _TrivialTypeHandler(_TypeHandler):
	"""Use built-in instance check and convert just passes instances through.

	Used for all types not derived from the built-in :mod:`typing` module,
	barring any custom handlers being added to the converter.
	"""

	def isinstance(self, value, type_, path):
		return isinstance(value, type_)


class _IntTypeHandler(_TypeHandler):
	"""Subclass of :class:`types.Integral`.

	Can convert Numpy integer objects and the like to regular Python ints.
	"""

	def isinstance(self, value, type_, path):
		return isinstance(value, type_)

	def convert(self, value, type_, path):
		"""Convert a value to the specified type."""
		self.ensure_isinstance(value, numbers.Integral, path)
		return int(value)


class _FloatTypeHandler(_TypeHandler):
	"""Subclass of :class:`types.Real`.

	Can convert Numpy float objects and the like to regular Python floats.
	"""

	def isinstance(self, value, type_, path):
		return isinstance(value, type_)

	def convert(self, value, type_, path):
		"""Convert a value to the specified type."""
		self.ensure_isinstance(value, numbers.Real, path)
		return float(value)


class _AnyTypeHandler(_TypeHandler):
	"""Handle :class:`typing.Any`.

	Everything is an instance and conversion returns same value.
	"""

	def isinstance(self, value, type_, path):
		return True


class _UnionTypeHandler(_TypeHandler):
	"""Handle subclasses of :class:`typing.Union`."""

	def isinstance(self, value, type_, path):
		args = type_.__args__

		for t in args:
			if not self.converter._isinstance_recursive(value, t, path=path):
				return False

		return True

	def convert(self, value, type_, path):
		# Assume no overlap  - TODO: handle overlaps
		args = type_.__args__
		for t in args:
			if self.converter._isinstance_recursive(value, t, path=path):
				return self.converter._convert_recursive(value, t, path=path)

		self._raise_typeconversionerror(value, type_, path)


class _MappingTypeHandler(_TypeHandler):
	"""parameterized subclass of :class:`typing.Mapping`."""

	def isinstance(self, value, type_, path):
		base = type_.__origin__ or type_

		if not isinstance(value, base):
			return False

		if type_.__args__ is not None:
			return self._isinstance_parameterized(value, type_, path)

		return True

	def _isinstance_parameterized(self, value, type_, path):
		keytype, valtype = type_.__args__

		for k, v in value.items():
			itempath = path + (k,)

			if not self.converter._isinstance_recursive(k, keytype, path=itempath):
				return False

			if not self.converter._isinstance_recursive(v, valtype, path=itempath):
				return False

		return True


class _DictTypeHandler(_MappingTypeHandler):
	"""Subclass of :class:`typing.Mapping` and superclass of dict.

	Allows conversion of any mapping type to a dict, as long as keys and values
	can be converted.
	"""

	def convert(self, value, type_, path):
		if not isinstance(value, typing.Mapping):
			self._raise_typeconversionerror(value, typing.Mapping, path)

		if type_.__args__ is None:
			if isinstance(value, dict):
				return value

			else:
				return dict(value)

		else:
			return self._convert_parameterized(value, type_, path)

	def _convert_parameterized(self, value, type_, path):
		keytype, valtype = type_.__args__

		converted = dict()

		for k, v in value.items():
			itempath = path + (k,)

			kc = self.converter._convert_recursive(k, keytype, itempath)
			vc = self.converter._convert_recursive(v, valtype, itempath)

			converted[kc] = vc

		return converted


class _CollectionTypeHandler(_TypeHandler):
	"""Non-mapping subclass of :class:`typing.Collection`."""

	def isinstance(self, value, type_, path):
		base = type_.__origin__ or type_

		if not isinstance(value, base):
			return False

		if type_.__args__ is not None:
			return self._isinstance_parameterized(self, value, type_, path)

		return True

	def _isinstance_parameterized(self, value, type_, path):
		elemtype, = type_.__args__

		for i, elem in enumerate(value):
			elempath = path + (i,)
			if not self.converter._isinstance_recursive(elem, elemtype, path=elempath):
				return False

		return True


class _ListTypeHandler(_CollectionTypeHandler):
	"""parameterized subclass of :class:`typing.Sequence` and superclass of list.

	Allows conversion of any non-string sequence type to a dict, as long as
	its elements can be converted.
	"""

	def convert(self, value, type_, path):

		if not isinstance(value, typing.Sequence) or isinstance(value, str):
			self._raise_typeconversionerror(value, typing.Sequence, path)

		if type_.__args__ is None:
			if isinstance(value, list):
				return value

			else:
				return list(value)

		else:
			return self._convert_parameterized(value, type_, path)

	def _convert_parameterized(self, value, type_, path):
		elemtype, = type_.__args__

		converted = list()

		for i, elem in enumerate(value):
			elempath = path + (i,)
			ec = self.converter._convert_recursive(elem, elemtype, path=elempath)
			converted.append(ec)

		return converted


class TypeConverter(_TypeHandler):
	"""
	Object which handles conversion to and type checking for advanced generic
	types from the built-in :mod:`typing` module.

	Checks and converts parameterized types recursively.
	"""

	def __init__(self):
		# No customizable settings implemented yet

		self._handler_instances = dict()

		# Mapping from types already seen to their handlers
		self._handler_cache = WeakKeyDictionary()

		# Replace keys with values when handling types
		self._type_aliases = {
			list: typing.List,
			dict: typing.Dict,
			tuple: typing.Tuple,
			set: typing.Set,
		}

	def isinstance(self, value, type_):
		"""Check if value is an instance of type.

		:param value: Arbitrary Python object to check.
		:param type_: Type to check.
		:returns: Whether ``value`` is an instance of ``type_``.
		:rtype: bool
		"""
		type_ = self._resolve_alias(type_)
		return self._isinstance_recursive(value, type_, path=())

	def ensure_isinstance(self, value, type_):
		"""Raise an exception if a value is not an instance of a type.

		:param value: Arbitrary Python object to check.
		:param type_: Type to check.
		:raises .TypeConversionError: If``value`` is not an instance of ``type_``.
		"""
		type_ = self._resolve_alias(type_)
		self._ensure_isinstance_recursive(value, type_, path=())

	def convert(self, value, type_):
		"""Convert a value to another type.

		In nearly all cases does no actual conversion and raises an exception if
		``value`` is not already an instance of ``type_``. Exceptions are
		converting compatible mapping types to ``dict`` and compatible sequence
		types to ``list`` (recursively).

		:param value: Arbitrary Python object to convert.
		:param type_: Type to convert to.
		:returns: Instance of ``type_`` equivalent to ``value``.

		:raises .TypeConversionError: If conversion is not possible.
		"""
		type_ = self._resolve_alias(type_)
		return self._convert_recursive(value, type_, path=())

	def _isinstance_recursive(self, value, type_, path):
		"""Recursive implementation of isinstance() method."""
		handler = self._get_handler(type_)
		return handler.isinstance(value, type_, path=path)

	def _ensure_isinstance_recursive(self, value, type_, path):
		"""Recursive implementation of ensure_isinstance() method."""
		handler = self._get_handler(type_)
		handler.ensure_isinstance(value, type_, path=path)

	def _convert_recursive(self, value, type_, path):
		"""Recursive implementation of convert() method."""
		handler = self._get_handler(type_)
		return handler.convert(value, type_, path=path)

	def _resolve_alias(self, type_):
		return self._type_aliases.get(type_, type_)

	def _get_handler(self, type_):
		"""Get the handler instance for a given type."""

		# Use cached handler if available
		try:
			return self._handler_cache[type_]

		# typing.Any and typing.Union will fail here because they are not weak-referenceable
		except TypeError:
			can_cache = False

		# Not yet created
		except KeyError:
			can_cache = True

		# Get handler instance for type
		handler = self._find_handler(type_)

		# Default handler
		if handler is None:
			handler = self._get_handler_instance(_TrivialTypeHandler)

		assert type_ not in (list, dict)

		# Add to cache
		if can_cache:
			self._handler_cache[type_] = handler

		return handler

	def _get_handler_instance(self, handler_cls):
		"""Get instance for a given handler class."""

		# Recycle existing instances
		try:
			return self._handler_instances[handler_cls]

		except KeyError:
			pass

		# Create and store so that it doesn't need to be created again
		instance = handler_cls(self)
		self._handler_instances[handler_cls] = instance

		return instance

	def _find_handler(self, type_):
		"""Get handler for the given type for the first time.

		:returns: _TypeHandler for the type, or None if no specific solution
			could be found and most generic default should be used (happens for
			all builtin and unknown types).
		"""
		if not is_valid_annotation(type_):
			raise TypeError('%r is not a valid type annotation' % type_)

		if type_ == typing.Any:
			return self._get_handler_instance(_AnyTypeHandler)

		if is_union_type(type_):
			return self._get_handler_instance(_UnionTypeHandler)

		# Generic types from typing module
		if is_generic_type(type_):
			return self._find_generic_handler(type_)

		# Numeric types
		if not issubclass_(type_, bool):
			if issubclass_(type_, numbers.Integral):
				return self._get_handler_instance(_IntTypeHandler)

			if issubclass_(type_, numbers.Real):
				return self._get_handler_instance(_FloatTypeHandler)

		# Remaining are builtin scalar types or unknown types, don't do anything
		# special
		return None

	def _find_generic_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Generic`."""

		base = type_.__origin__ or type_

		# Tuples are different from other sequences
		if issubclass(base, typing.Tuple):
			return self._find_tuple_handler(type_)

		# Mapping
		if issubclass_(base, typing.Mapping):
			return self._find_mapping_handler(type_)

		# Sequence
		if issubclass_(base, typing.Sequence):
			return self._find_sequence_handler(type_)

		# Other collection type
		if is_collection_type(base):
			return self._find_collection_handler(type_)

		return None

	def _find_tuple_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Tuple`."""

		base = type_.__origin__ or type_

		# Structured tuple
		if is_structured_tuple_type(base):
			raise NotImplementedError('Structured Tuple[] types not implemented')

		# Homogeneous parameterized tuple
		if issubclass(base, typing.Tuple) and type_.__args__:
			raise NotImplementedError('Homogeneous Tuple[] types not implemented')

		# Non-parameterized tuple
		return None

	def _find_mapping_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Mapping`."""

		base = type_.__origin__ or type_

		# Superclass of dict
		if issubclass(dict, base):
			return self._get_handler_instance(_DictTypeHandler)

		# parameterized mappings not compatible with dict
		if type_.__args__:
			return self._get_handler_instance(_MappingTypeHandler)

		return None

	def _find_sequence_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Sequence`."""

		base = type_.__origin__ or type_

		# Superclass of list
		if issubclass(list, base):
			return self._get_handler_instance(_ListTypeHandler)

		# Treat other parameterized sequences as generic collection types
		# because we can't convert and ordering doesn't matter for checking
		# items
		if type_.__args__:
			return self._get_handler_instance(_CollectionTypeHandler)

		return None

	def _find_collection_handler(self, type_):
		"""
		Get handler for subclass of :class:`typing.Collection` which is not a
		mapping or sequence.
		"""

		# parameterized collections
		if type_.__args__:
			return self._get_handler_instance(_CollectionTypeHandler)

		return None


# Converter with default options
default_converter = TypeConverter()

# Aliases for default converter methods
astype = default_converter.convert
isinstance_ext = default_converter.isinstance
ensure_isinstance_ext = default_converter.ensure_isinstance
