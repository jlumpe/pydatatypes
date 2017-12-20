"""Test conversion to non-parametrized types in pydatatypes.typing module."""

from typing import Any, List, Dict, Collection, Mapping, Sequence
from collections import OrderedDict

import pytest

from pydatatypes.typing import TypeConversionError, NoneType
from typingtesthelpers import assert_convert_success, assert_convert_failure


# Quick examples for type checking and conversion (mutually exclusive partitions)
EXAMPLES = {
	'int': [0, 1, -1, 42],
	'float': [1.0, 5.234, -2342.333],
	'bool': [True, False],
	'string': ['foo', ''],
	'mapping': [{}, {'foo': 1, 'bar': 'baz'}, OrderedDict({1: 'a', 2: 'b'})],
	'sequence': [[], [1, 2, 'x'], (), ('a', None), range(10)],
	'set': [set(), {1, 2, 'x'}, frozenset(), frozenset({1, 2, 'x'})],
	'none': [None],
	'other': [slice(1, 3), Exception("Shouldn't work"), lambda x: x + 1],
}

# Aliases for groups of EXAMPLES keys
EXAMPLE_ALIASES = {
	'collection': {'mapping', 'sequence', 'set'},
	'all': set(EXAMPLES.keys()),
}


def expand_example_aliases(keys):
	keys = set(keys)

	for key in list(keys):
		try:
			alias_keys = EXAMPLE_ALIASES[key]
		except KeyError:
			continue

		keys.remove(key)
		keys.update(alias_keys)

	return keys


def iter_example_values(keys, complement=False):
	keys = expand_example_aliases(keys)

	if complement:
		keys = EXAMPLES.keys() - keys

	for key in keys:
		yield from EXAMPLES[key]


def check_convert_examples(converter, type_, keys, *, omit=None, eq=True):
	"""
	Check conversion of all example values to type_. Examples from keys in
	"keys" are expected to work, the others are expected to fail.
	"""

	keys = expand_example_aliases(keys)
	omit = expand_example_aliases(omit or [])

	# Expected to work
	for val in iter_example_values(keys):
		assert_convert_success(converter, val, type_, eq=eq)

	# Expected to fail
	for val in iter_example_values(EXAMPLES.keys() - keys - omit):
		assert_convert_failure(converter, val, type_)


def check_isinstance_examples(converter, type_, keys, *, omit=None, eq=True):
	"""
	Test instance checking for all example values to type_. Examples from keys
	in "keys" are expected to work, the others are expected to fail.
	"""

	keys = expand_example_aliases(keys)
	omit = expand_example_aliases(omit or [])

	# Expected to work
	for val in iter_example_values(keys):
		assert converter.isinstance(val, type_)
		converter.ensure_isinstance(val, type_)

	# Expected to fail
	for val in iter_example_values(EXAMPLES.keys() - keys - omit):
		assert not converter.isinstance(val, type_)

		with pytest.raises(TypeConversionError):
			converter.ensure_isinstance(val, type_)


def test_any(converter):
	check_isinstance_examples(converter, Any, ['all'])

	# Conversion should return exact same object
	for value in iter_example_values(['all']):
		assert converter.convert(value, Any) is value


def test_none(converter):
	check_isinstance_examples(converter, NoneType, ['none'])
	check_convert_examples(converter, NoneType, ['none'])


def test_int(converter):
	check_isinstance_examples(converter, int, ['int', 'bool'])
	check_convert_examples(converter, int, ['int', 'bool'])


def test_float(converter):
	check_isinstance_examples(converter, float, ['float'])
	check_convert_examples(converter, float, ['float'], omit=['int', 'bool'])


def test_bool(converter):
	check_isinstance_examples(converter, bool, ['bool'])
	check_convert_examples(converter, bool, ['bool'])


def test_str(converter):
	check_isinstance_examples(converter, str, ['string'])
	check_convert_examples(converter, str, ['string'])


@pytest.mark.parametrize('type_', [list, List, Sequence])
def test_convert_list(converter, type_):

	# Check conversion failure on all non-sequences
	check_convert_examples(converter, type_, [], omit=['sequence'])

	# Check sequence conversion
	for value in iter_example_values(['sequence']):
		converted = converter.convert(value, type_)
		assert isinstance(converted, list)
		assert converted == list(value)


@pytest.mark.parametrize('type_', [dict, Dict, Mapping])
def test_convert_dict(converter, type_):

	# Check conversion failure on all non-mappings
	check_convert_examples(converter, type_, [], omit=['mapping'])

	# Check mapping conversion
	for value in iter_example_values(['mapping']):
		converted = converter.convert(value, type_)
		assert isinstance(converted, dict)
		assert converted == dict(value)


def test_is_collection_type(converter):

	from collections import OrderedDict

	types = [list, List, dict, Dict, Sequence, Mapping, Collection]

	values = [[], [1, 2], range(3), dict(x=3), OrderedDict(), set()]

	# Non-parametrized types, should mirror builtin isinstance()
	for type_ in types:
		for value in values:
			assert converter.isinstance(value, type_) == isinstance(value, type_)


def test_convert_numpy(converter):
	"""Test conversion of numpy scalars to Python ints and floats."""
	import numpy as np

	for inttype in [np.int8, np.int16, np.int32, np.int64]:
		np_n = inttype(3)
		n = converter.convert(np_n, int)
		assert isinstance(n, int)
		assert n == np_n

	for floattype in [np.float32, np.float64]:
		np_x = floattype(3)
		x = converter.convert(np_x, float)
		assert isinstance(x, float)
		assert x == np_x
