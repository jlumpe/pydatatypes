"""Helper functions for testing pydatatypes.typing."""

import pytest

from pydatatypes.typing import TypeConversionError


def assert_convert_success(converter, value, type_, eq=True):
	converted = converter.convert(value, type_)
	assert converter.isinstance(converted, type_)

	if eq:
		assert converted == value


def assert_convert_failure(converter, value, type_):
	with pytest.raises(TypeConversionError):
		converter.convert(value, type_)


class ExampleValues:
	"""A set of test examples divided into groups."""

	def __init__(self, groups, aliases):
		self.groups = dict(groups)
		self.aliases = dict(aliases)

	def expand_aliases(self, keys):
		keys = set(keys)

		for key in list(keys):
			try:
				alias_keys = self.aliases[key]
			except KeyError:
				continue

			keys.remove(key)
			keys.update(alias_keys)

		return keys

	def getkeys(self, keys, complement=False, omit=None):
		keys = self.expand_aliases(keys)

		if complement:
			keys = self.groups.keys() - keys

		if omit is not None:
			omit = self.expand_aliases(omit)
			keys -= omit

		return keys

	def values(self, keys, complement=False, omit=None):
		for key in self.getkeys(keys, complement, omit):
			yield from self.groups[key]
