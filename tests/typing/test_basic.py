"""Tests of basic functions in typing submodule."""

import typing
from typing import Tuple, Union, Any
from pydatatypes.typing import is_parameterized_type, is_structured_tuple_type, is_union_type, is_collection_type


def test_is_parameterized_type():
	assert is_parameterized_type(typing.List[int])
	assert is_parameterized_type(typing.List[typing.Any])
	assert is_parameterized_type(typing.Mapping[str, typing.Any])
	assert not is_parameterized_type(typing.List)
	assert not is_parameterized_type(Union[int, str])
	assert not is_parameterized_type(list)

def test_is_structured_tuple_type():
	assert is_structured_tuple_type(Tuple[int, str])
	assert is_structured_tuple_type(Tuple[Any, Any, Any])
	assert is_structured_tuple_type(Tuple[()])
	assert not is_structured_tuple_type(Tuple)
	assert not is_structured_tuple_type(Tuple[int, ...])
	assert not is_structured_tuple_type(typing.List)
	assert not is_structured_tuple_type(typing.List[int])
	assert not is_structured_tuple_type(Union[int, str])
	assert not is_structured_tuple_type(list)
	assert not is_structured_tuple_type(Any)

def test_is_union_type():
	assert is_union_type(Union)
	assert is_union_type(Union[int, str])
	assert not is_union_type(int)

def test_is_collection_type():
	assert is_collection_type(list)
	assert is_collection_type(typing.List)
	assert is_collection_type(dict)
	assert is_collection_type(typing.Mapping)
	assert not is_collection_type(int)
	assert not is_collection_type(Any)
