"""
Work with the built-in :mod:`typing` module, specifically to convert to or
check membership of generic parametrized types like ``List[float]`` or
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


def is_parametrized_type(type_):
	"""
	Check if a type object is a parametrized generic type from the
	``typing`` module.

	:type type_: type
	:rtype: bool

	>>> from typing import List
	>>> is_parametrized_type(List[int])
	True
	>>> is_parametrized_type(List)
	False
	>>> is_parametrized_type(list)
	False
	"""
	return isinstance(type_, typing.GenericMeta) and type_.__args__ is not None


def is_structured_tuple_type(type_):
	"""
	Check if a type object is a structured (non-homogenous) version of
	:class:`typing.Tuple`.

	:type type_: type
	:rtype: bool

	>>> from typing import Tuple
	>>> is_structured_tuple_type(Tuple[int, str])
	True
	>>> is_structured_tuple_type(Tuple)
	False
	>>> is_structured_tuple_type(Tuple[int, ...])
	False
	"""
	return issubclass(type_, typing.Tuple) and \
		type_.__args__ is not None and \
		type_.__args__[-1] is not Ellipsis


def is_union_type(type_):
	"""Check if a type is :data:`typing.Union` or a parametrized version of it.

	param type_: Type object to check (but positives won't actually be instance
		of :class:`type`, confusing).
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
	return isinstance(type_, type(typing.Union))


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
	"""Parametrized subclass of :class:`typing.Mapping`."""

	def isinstance(self, value, type_, path):
		base = type_.__origin__ or type_

		if not isinstance(value, base):
			return False

		if type_.__args__ is not None:
			return self._isinstance_parametrized(value, type_, path)

		return True

	def _isinstance_parametrized(self, value, type_, path):
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
			return self._convert_parametrized(value, type_, path)

	def _convert_parametrized(self, value, type_, path):
		keytype, valtype = type_.__args__

		converted = dict()

		for k, v in value.items():
			itempath = path + (k,)

			kc = self.converter._convert_recursive(k, keytype, itempath)
			vc = self.converter._convert_recursive(v, valtype, itempath)

			converted[kc] = vc

		return converted


class _CollectionTypeHandler(_TypeHandler):
	"""Non-mapping subclass of :class:`Collection`."""

	def isinstance(self, value, type_, path):
		base = type_.__origin__ or type_

		if not isinstance(value, base):
			return False

		if type_.__args__ is not None:
			return self._isinstance_parametrized(self, value, type_, path)

		return True

	def _isinstance_parametrized(self, value, type_, path):
		elemtype, = type_.__args__

		for i, elem in enumerate(value):
			elempath = path + (i,)
			if not self.converter._isinstance_recursive(elem, elemtype, path=elempath):
				return False

		return True


class _ListTypeHandler(_CollectionTypeHandler):
	"""Parametrized subclass of :class:`typing.Sequence` and superclass of list.

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
			return self._convert_parametrized(value, type_, path)

	def _convert_parametrized(self, value, type_, path):
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

	Checks and converts parametrized types recursively.
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
			handler = self._handler_cache[type_]

		# TypeError raised when value not weak-referencable, seems to only
		# when mistakenly passed *instance* of builtin classes as the type
		except TypeError:
			raise TypeError('{!r} is not a valid type'.format(type_)) from None

		# Not available, get it
		except KeyError:

			# Get handler instance for type
			handler = self._find_handler(type_)

			# Default handler
			if handler is None:
				handler = self._get_handler_instance(_TrivialTypeHandler)

			assert type_ not in (list, dict)

			# Add to cache
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

		# typing.Any not a type, for some reason
		if type_ == typing.Any:
			return self._get_handler_instance(_AnyTypeHandler)

		# Unions also not instance of type
		if is_union_type(type_):
			return self._get_handler_instance(_UnionTypeHandler)

		# From here on, should be a type
		if not isinstance(type_, type):
			raise TypeError('Expect type_ to be instance of type, Any, or Union')

		# Generic types from typing module
		if typing.Generic in type_.__mro__:  # Don't all support issubclass()
			return self._find_generic_handler(type_)

		# Numeric types
		if not issubclass(type_, bool):
			if issubclass(type_, numbers.Integral):
				return self._get_handler_instance(_IntTypeHandler)

			if issubclass(type_, numbers.Real):
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
		if issubclass(base, typing.Mapping):
			return self._find_mapping_handler(type_)

		# Sequence
		if issubclass(base, typing.Sequence):
			return self._find_sequence_handler(type_)

		# Other collection type
		if issubclass(base, typing.Collection):
			return self._find_collection_handler(type_)

		return None

	def _find_tuple_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Tuple`."""

		base = type_.__origin__ or type_

		# Structured tuple
		if is_structured_tuple_type(base):
			raise NotImplementedError('Structured Tuple[] types not implemented')

		# Homogeneous parametrized tuple
		if issubclass(base, typing.Tuple) and type_.__args__:
			raise NotImplementedError('Homogeneous Tuple[] types not implemented')

		# Non-parametrized tuple
		return None

	def _find_mapping_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Mapping`."""

		base = type_.__origin__ or type_

		# Superclass of dict
		if issubclass(dict, base):
			return self._get_handler_instance(_DictTypeHandler)

		# Parametrized mappings not compatible with dict
		if type_.__args__:
			return self._get_handler_instance(_MappingTypeHandler)

		return None

	def _find_sequence_handler(self, type_):
		"""Get handler for subclass of :class:`typing.Sequence`."""

		base = type_.__origin__ or type_

		# Superclass of list
		if issubclass(list, base):
			return self._get_handler_instance(_ListTypeHandler)

		# Treat other parametrized sequences as generic collection types
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

		# Parametrized collections
		if type_.__args__:
			return self._get_handler_instance(_CollectionTypeHandler)

		return None


# Converter with default options
default_converter = TypeConverter()

# Aliases for default converter methods
astype = default_converter.convert
isinstance_ext = default_converter.isinstance
ensure_isinstance_ext = default_converter.ensure_isinstance
