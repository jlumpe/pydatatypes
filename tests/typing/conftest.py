from functools import partial

import pytest

from pydatatypes.typing import default_converter


# Quick examples for type checking and conversion (mutually exclusive partitions)
EXAMPLES = {
	'int': [0, 1, -1, 42],
	'float': [1.0, 5.234, -2342.333],
	'bool': [True, False],
	'string': ['foo', ''],
	'mapping': [{}, {'foo': 1, 'bar': 'baz'}],
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


class ExampleValues:
	"""Helps to iterate over groups of example values."""

	def __init__(self, groups, aliases):
		self.groups = dict(groups)
		self.aliases = dict(aliases)

	def iter_group_values(self, keys, complement=False):
		keys = self.expand_example_aliases(keys)

		if complement:
			keys = self.groups.keys() - keys

		for key in keys:
			yield from self.groups[key]

	def expand_example_aliases(self, keys):
		keys = set(keys)

		for key in list(keys):
			try:
				alias_keys = self.aliases[key]
			except KeyError:
				continue

			keys.remove(key)
			keys.update(alias_keys)

		return keys

	def check_group_conversion(self, converter, type_, keys, omit=None, eq=True):
		"""
		Check conversion of all example values to type_. Examples from keys in
		keys are expected to work, the others are expected to fail.
		"""

		keys = self.expand_example_aliases(keys)
		omit = self.expand_example_aliases(omit or [])

		# Expected to work
		for val in self.iter_group_values(keys):
			assert_convert_success(converter, val, type_, eq=eq)

		# Expected to fail
		for val in self.iter_group_values(EXAMPLES.keys() - keys - omit):
			assert_convert_failure(converter, val, type_)


@pytest.fixture()
def converter():
	return default_converter


@pytest.fixture(scope='module', name='assert_convert_success')
def _assert_convert_success_fixture(converter):
	return partial(assert_convert_success, converter)


@pytest.fixture(scope='module', name='assert_convert_failure')
def _assert_convert_failure_fixture(converter):
	return partial(assert_convert_failure, converter)
