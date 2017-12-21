"""Convert data to and from JSON mostly automatically.

.. data:: default_json_converter

	Default instance of :class:`.JsonConverter` to use at module level.

.. function:: to_json

	Alias for :meth:`.JsonConverter.to_json` method of
	:data:`.default_json_converter`.

.. function:: from_json

	Alias for :meth:`.JsonConverter.from_json` method of
	:data:`.default_json_converter`.
"""

import typing
import numbers

from .abc import Jsonable, JsonConstructible
from .typing import TypeConversionError, TypeConverter, NoneType, is_collection_type


__all__ = ['JsonTypeError', 'to_json', 'from_json']


class JsonTypeError(TypeConversionError):
	pass


class JsonTypeConverter(TypeConverter):
	"""TypeConverter which converts objects from JSON data."""

	def __init__(self, **kwargs):
		TypeConverter.__init__(self, **kwargs)

	def _convert_recursive(self, data, type_, path):

		# Special case - convert integer mapping keys from strings and continue
		# with converted dict
		if issubclass(type_, typing.Mapping) and \
			issubclass(dict, type_) and \
			type_.__args__ and \
			type_.__args__[0] == str:

			try:
				data = {int(k): v for k, v in data.items()}

			except ValueError:
				raise JsonTypeError(
					msg='Cannot convert JSON object keys to integers',
					value=data,
					type=type_,
					path=path,
				)

		# If subclass of JsonConstructible short-circuit to from_json()
		if issubclass(type_, JsonConstructible):
			return type_.from_json(data)

		# Just use the standard method
		return TypeConverter._convert_recursive(self, data, type_, path)


class JsonConverter:
	"""Converts objects to/from JSON recursively."""

	def __init__(self, typeconverter):
		self.typeconverter = typeconverter

	def from_json(self, type_, data):
		"""Convert JSON data to type_.

		:param data: Parsed JSON data returned from :func:`json.load`.
		:param type type_: Type to convert to.
		:returns: Instance of ``type_``.

		:raises .TypeConversionError: If the data cannot be converted to ``type_``.
		"""
		return self.typeconverter.convert(type_, data)

	def to_json(self, value):
		"""Convert a value to a JSON-equivalent object.

		:param value: Object to be converted to JSON.
		:returns: Value which can be passed to :func:`json.dump`.

		:raises JsonTypeError: If ``value`` can't be converted to JSON.
		"""
		return self._to_json(value, path=())

	def _to_json(self, value, path):
		"""Recursive implementation of :meth:`to_json`."""

		# Check if already standard JSON scalar type
		if isinstance(value, (int, float, str, NoneType,)):
			return value

		# Instance of Jsonable
		if isinstance(value, Jsonable):
			return value.to_json()

		# Generic integer
		if isinstance(value, numbers.Integral):
			return int(value)

		# Generic real number
		if isinstance(value, numbers.Real):
			return float(value)

		# Generic mapping
		if isinstance(value, typing.Mapping):
			return self._mapping_to_json(value, path)

		# Generic non-mapping collection
		if is_collection_type(type(value)):
			return [
				self._to_json(v, path + (i,))
				for i, v in enumerate(value)
			]

		raise JsonTypeError(
			"Cant' convert {} to JSON.".format(value),
			value=value,
			path=path,
		)

	def _mapping_to_json(self, value, path):
		"""Convert a mapping to a JSON dict.

		Checks for proper key type, converts integer keys to strings.
		"""

		converted = dict()
		keytype = None

		for k, v in value.items():

			# First key seen, figure out type
			if keytype is None:
				if isinstance(k, str):
					keytype = 'str'
				elif isinstance(k, int):
					keytype = 'int'

			# Convert key if needed
			if keytype == 'str' and isinstance(k, str):
				kc = k

			elif keytype == 'int' and isinstance(k, int):
				kc = str(k)

			else:
				raise JsonTypeError(
					'Mapping keys must be str or int',
					path=path,
				)

			# Convert value
			vc = self._to_json(v, path=path + (k,))

			converted[kc] = vc

		return converted


# Default JsonConverter instance
default_json_converter = JsonConverter(JsonTypeConverter())

# Alises for default json converter methods
to_json = default_json_converter.to_json
from_json = default_json_converter.from_json
