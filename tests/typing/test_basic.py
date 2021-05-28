"""Tests of basic functions in typing submodule."""

import typing
from typing import Tuple, Union, Any
from pydatatypes.typing import is_valid_annotation, is_generic_type, is_parameterized_type, \
	is_structured_tuple_type, is_union_type, is_collection_type


def test_is_valid_annotation():
	assert is_valid_annotation(typing.List)
	assert is_valid_annotation(typing.List[int])
	assert is_valid_annotation(typing.Tuple)
	assert is_valid_annotation(typing.Tuple[int, str])
	assert is_valid_annotation(typing.Tuple[int, ...])
	assert is_valid_annotation(typing.Union)
	assert is_valid_annotation(typing.Union[int, str])
	assert is_valid_annotation(typing.Any)
	assert is_valid_annotation(typing.Iterable)
	assert is_valid_annotation(typing.Callable)
	assert is_valid_annotation(list)
	assert is_valid_annotation(str)
	assert not is_valid_annotation(1)
	assert not is_valid_annotation('foo')

def test_is_generic_type():
	assert is_generic_type(typing.List)
	assert is_generic_type(typing.List[int])
	assert is_generic_type(typing.Mapping)
	assert is_generic_type(typing.Mapping[str, int])
	assert not is_generic_type(Tuple)
	assert not is_generic_type(Tuple[int, str])
	assert not is_generic_type(Union)
	assert not is_generic_type(Union[int, str])
	assert not is_generic_type(Tuple)
	assert not is_generic_type(Tuple[int, str])
	assert not is_generic_type(Any)
	assert not is_generic_type(list)

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
