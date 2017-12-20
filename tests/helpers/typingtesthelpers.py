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
