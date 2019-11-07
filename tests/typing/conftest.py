import pytest

from pydatatypes.typing import default_converter


@pytest.fixture()
def converter():
	return default_converter
