"""
Extension to the :mod:`attr` package with features such as type checking and
JSON conversion.
"""

import typing

import attr

from .abc import Jsonable, JsonConstructible
from .typing import astype
from .json import from_json, to_json


__all__ = ['field', 'dataclass', 'array_field']


def validate_field_type(instance, attribute, value):
	"""Validator function which ensures a value matches a fields's type.

	:param instance: Instance of a dataclass object.
	:param attribute: Attribute created by :func:`.field`.
	:type attribute: attr.Attribute
	:param value: Value to check.

	:raises TypeError: If ``value`` is not an instance of ``attribute.type``.
	"""
	if attribute.type is not None and not isinstance(value, attribute.type):
		raise TypeError(
			'{} must be of type {!r}, got {!r}'
			.format(attribute.name, attribute.type, type(value))
		)


def make_type_converter(type_):
	"""Make a converter function which converts is argument to the given type.

	:param type type_: Type to convert to.
	:returns: Function which takes single argument and returns instance of
		```type_`` or raises :exc:`TypeError`.
	:rtype: callable
	"""
	def convert(value):
		return astype(value, type_)

	return convert


def field(type=None,
          default=attr.NOTHING,
          *,
          validator=None,
          convert=None,
          metadata=None,
          optional=False,
          validate_type=True,
          convert_type=True,
          json=True,
          set_default_optional=True,
          **kwargs
	):
	"""Slightly extended verions of :func:`attr.attrib`.

	:param type type: Same as in :func:`attr.attrib`. Just put it as first
		positional argument because it's commonly used.
	:param default: Same as in :func:`attr.attrib`.
	:param validator: Same as in :func:`attr.attrib`.
	:param convert: Same as in :func:`attr.attrib`.
	:param metadata: Same as in :func:`attr.attrib`.
	:param bool optional: If True the field will also accept None as well as any
		other valid values. In this case if the field is initialized with a
		value of None all other validators and converters will be bypassed. The
		``default`` argument will also be set to None, if it has not been set
		already.
	:param bool validate_type: If True will add an additional validator that
		checks that the value is an instance of ``type``.
	:param bool convert_type: If True and ``convert`` is None will add a
		convert function that converts its argument to ``type`` where possible.
		This overrides ``validate_type``, as the converter will also raise a
		:exc:`TypeError` if its argument is an incompatible type.
	:param bool json: If True include in JSON output of class. Only has an
		effect when :func:`.dataclass` is called with ``jsonable=True``.
	:param bool set_default_optional: Hack to allow use of ``default`` decorator
		on field marked with ``default=True``. If False doesn't set default
		to None on optional fields, which would prevent you using the default
		decorator later.
	:param \\**kwargs: Remaining keyword arguments to :func:`attr.attrib`.

	:returns: The intermediate type returned by :func:`attr.attrib`. This will
		be turned into a proper :class:`attr.Attribute` by the
		:func:`attr.attributes` function.
	"""

	# Union type
	if isinstance(type, tuple):
		type = typing.Union[type]

	# Add type validator
	if validate_type and not convert_type:
		if validator is not None:
			validator = attr.validators.and_(validate_field_type, validator)
		else:
			validator = validate_field_type

	# Add type converter
	if convert_type and not convert and type is not None:
		convert = make_type_converter(type)

	# Fix validator, converter, and default for optional
	if optional:
		if validator is not None:
			validator = attr.validators.optional(validator)

		if convert is not None:
			convert = attr.converters.optional(convert)

		if default is attr.NOTHING and set_default_optional:
			default = None

	# Add custom arguments metadata
	if metadata is None:
		metadata = {}

	metadata.update(
		optional=optional,
		validate_type=validate_type,
		convert_type=convert_type,
		json=json,
	)

	# Create attribute object
	attrib = attr.attrib(
		default=default,
		validator=validator,
		type=type,
		convert=convert,
		metadata=metadata,
		**kwargs,
	)

	return attrib


def field_to_json(field, value):
	"""Convert field value to JSON equivalent.

	:param field: dataclass attribute created with :func:`.field`.
	:type field: attr.Attribute
	:param value: Value of attribute to convert.
	:returns: Converted value that can be passed to :func:`json.dump`.
	"""
	return to_json(value)


def field_from_json(field, data):
	"""Convert JSON data to field value.

	:param field: dataclass attribute created with :func:`.field`.
	:type field: attr.Attribute
	:param data: JSON data from :func:`json.load`.
	:returns: Converted value suitable for initialization of attribute.
	"""
	if data is None and field.metadata['optional']:
		return None

	return from_json(data, field.type)


def fail_dataclass_from_json(cls, data):
	"""``to_json`` method for data classes which do not support it.

	Used to monkey-patch this attribute when a data class does not support
	creation from JSON but inherits from a class which does.
	"""
	raise TypeError('Instances of {!r} cannot be created from JSON'.format(cls))


def fail_dataclass_to_json(self):
	"""``to_json`` method for data classes which do not support it.

	Used to monkey-patch this attribute when a data class does not support
	conversion to JSON but inherits from a class which does.
	"""
	raise TypeError('Instances of {!r} cannot be converted to JSON'.format(type(self)))


def dataclass(
		cls=None,
		*,
		json=False,
		ordered=False,
		**kwargs
	):
	"""Add boilerplate for classes which exist to store data.

	Somewhat extended version of :func:`attr.attributes`. Use on classes with
	:func:`.field` attributes.

	Does not required the class be an instance of a metaclass or inherit from
	anything.

	:parma type cls: Class to update with boilerplate code. If None will return
		a decorator which takes a class.
	:param bool json: If True make the class a virtual subclass of
		:class:`pydatatypes.abc.Jsonable` and
		:class:`pydatatypes.abc.JsonConstructible`, and add the corresponding
		methods. May also have value of "to" or "from" to use only one or the
		other.
	:param bool ordered: If False and ``cmp`` is True, disable ordered
		comparison for the class (<, >, <=, and >= operators) and keep only
		equality comparisons.
	:param \\**kwargs: Remaining keyword arguments to :func:`attr.attributes`.

	:returns: If ``cls`` is not None returns the same class after modification.
		Otherwise returns a decorator which takes a class as its first argument,
		modifies it, and returns the same class.
	:rtype: type or callable
	"""

	if json not in (True, False, 'to', 'from'):
		raise ValueError('json argument must be boolean or one of {"to", "from"}')

	def decorator(cls):
		"""Decorator to transform class into a dataclass."""

		# Call the attr function
		attrcls = attr.attributes(cls, **kwargs)

		# If comparable but not orderable, remove ordering methods
		if kwargs.get('cmp', True) and not ordered:
			for method in ['__le__', '__ge__', '__lt__', '__gt__']:
				delattr(attrcls, method)

		# Add JSON methods and register as virtual subclass
		if json is True or json == 'to':
			if getattr(attrcls, 'to_json', None) is None:
				attrcls.to_json = dataclass_to_json

			Jsonable.register(attrcls)

		elif hasattr(cls, 'to_json'):
			cls.to_json = fail_dataclass_to_json

		if json is True or json == 'from':
			if getattr(attrcls, 'from_json', None) is None:
				attrcls.from_json = classmethod(dataclass_from_json)

			JsonConstructible.register(attrcls)

		elif hasattr(cls, 'from_json'):
			cls.from_json = classmethod(fail_dataclass_from_json)

		return attrcls

	# If passed class, call decorator now and return result.
	if cls is not None:
		return decorator(cls)

	return decorator


def dataclass_to_json(instance):
	"""Convert an instance of a dataclass to a JSON-able dict.

	:param instance: Instance of class modified by :func:`.dataclass`.
	:returns: Dict representing JSON object, which can be passed to
		:func:`json.dump`.
	:rtype dict:
	"""
	values = attr.asdict(instance, recurse=False)
	data = dict()

	for attrib in attr.fields(type(instance)):
		if attrib.metadata['json']:
			data[attrib.name] = field_to_json(attrib, values[attrib.name])

	return data


def dataclass_from_json(cls, data, ignore_extra_keys=False):
	"""Convert parsed JSON data to a dataobject instance.

	:param type cls: Class modified by :func:`.dataclass`.
	:param dict data: Parsed JSON data as returned by :func:`json.load`.
	:returns: Instance of ``cls``.

	:raises KeyError: If ``data`` has any additional keys.
	"""
	if not isinstance(data, dict):
		raise TypeError('Expected data to be dict, not {!r}'.format(type(data)))

	data = dict(data)
	values = dict()

	for attrib in attr.fields(cls):
		try:
			data_val = data.pop(attrib.name)
		except KeyError:
			continue

		values[attrib.name] = field_from_json(attrib, data_val)

	if data and not ignore_extra_keys:
		key = next(iter(data))
		raise KeyError('Unknown key {!r} in data'.format(key))

	return cls(**values)


def array_field(dtype=None, ndim=None, shape=None, **kwargs):
	"""Creates a field which stores a Numpy array.

	:param dtype: Numpy dtype or value which can be converted to one.
	:param int ndim: Expected number of dimensions of array.
	:param tuple shape: Tuple of ints describing expected shape of array.
		Dimesions with unspecified size can have a None in the corresponding
		position.
	:param \\**kwargs: Additional keyword arguments to pass to :func:`.field`.

	:returns: See return value of :func:`.field`.
	"""
	import numpy as np

	if dtype is not None:
		dtype = np.dtype(dtype)

	if shape is not None:
		shape = tuple(shape)

		if ndim is not None:
			raise TypeError('ndim and shape cannot both be non-None')

		ndim = len(shape)

	metadata = dict(np_dtype=dtype, np_ndim=ndim, np_shape=shape)

	def convert_array(value):

		if not isinstance(value, np.ndarray):
			value = np.asarray(value, dtype=dtype)

		if ndim is not None:
			if value.ndim != ndim:
				raise ValueError('Expected array of dimension {}'.format(ndim))

		if shape is not None:
			for i, (s1, s2) in enumerate(zip(value.shape, shape)):
				if s2 is not None and s1 != s2:
					raise ValueError('Axis {} must be of size {}'.format(i, s2))

		return value

	return field(np.ndarray, convert=convert_array, metadata=metadata, **kwargs)
