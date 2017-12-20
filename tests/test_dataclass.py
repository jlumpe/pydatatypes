"""Test dataclass() and related from pydatatypes.dataclass module."""

import pytest
import attr

from pydatatypes.dataclass import dataclass, field
from pydatatypes.abc import Jsonable, JsonConstructible


@pytest.mark.parametrize('ordered', [False, True])
def test_ordered(ordered):
	"""Test the "ordered" argument to dataclass()."""

	@dataclass(cmp=True, ordered=ordered)
	class TestCls:
		x = field(int)
		y = field(int)

	# Check equality always works
	assert TestCls(1, 2) == TestCls(1, 2)
	assert TestCls(1, 2) != TestCls(1, 4)
	assert TestCls(0, 0) != 'foo'

	# Ordered comparisons should work
	if ordered:
		assert TestCls(1, 2) < TestCls(11, 12)
		assert TestCls(2, 1) > TestCls(1, 2)  # Lexicographic?
		assert not TestCls(0, 0) >= TestCls(1, 2)
		assert TestCls(0, 0) <= TestCls(0, 0)

	# Methods for ordered comparisons have been removed
	else:
		with pytest.raises(TypeError):
			TestCls(1, 2) < TestCls(3, 4)
		with pytest.raises(TypeError):
			TestCls(1, 2) > TestCls(3, 4)
		with pytest.raises(TypeError):
			TestCls(1, 2) <= TestCls(3, 4)
		with pytest.raises(TypeError):
			TestCls(1, 2) >= TestCls(3, 4)


@pytest.mark.parametrize('validate_type', [False, True])
@pytest.mark.parametrize('other_validator', [False, True])
def check_validate_field_type(validate_type, other_validator):
	"""Check automatic field type validation."""

	# Different validator for ints
	def not_three(instance, attribute, value):
		if value == 3:
			raise ValueError()

	@dataclass()
	class TestCls:
		x = field(
			int,
			validate_type=validate_type,
			convert_type=False,
			other_validator=not_three if other_validator else None,
		)

	# Try values of correct type
	assert TestCls(10).x == 10

	# Check incorrect type
	if validate_type:
		with pytest.raises(TypeError):
			TestCls('foo')

	else:
		assert TestCls('foo').x == 'foo'

	# Check that other validators still work
	if other_validator:
		with pytest.raises(ValueError):
			TestCls(3)


@pytest.mark.parametrize('other_validator', [False, True])
@pytest.mark.parametrize('convert', [False, True])
@pytest.mark.parametrize('default', [attr.NOTHING, 4])
def test_optional(other_validator, convert, default):
	"""Check "optional" argument to field() function."""

	def is_positive(instance, attribute, value):
		if value <= 0:
			raise ValueError('not a letter')

	@dataclass()
	class TestCls:
		x = field(
			int,
			optional=True,
			validator=is_positive if other_validator else None,
			convert=int if convert else None,
			default=default,
		)

	# Check standard value
	assert TestCls(10).x == 10

	# Check explicit None value is OK
	assert TestCls(None).x is None

	# Check default value is None if not set
	if default is attr.NOTHING:
		assert TestCls().x is None
	else:
		assert TestCls().x == default

	# Check type validation or conversion otherwise still performed
	if not convert:
		with pytest.raises(TypeError):
			TestCls('asdkj')

	else:
		assert TestCls('6').x == 6

	# Check other validators still work
	if other_validator:
		with pytest.raises(ValueError):
			TestCls(-1)


@pytest.mark.parametrize('to_json', [False, True])
@pytest.mark.parametrize('from_json', [False, True])
def test_dataclass_json_arg(to_json, from_json):
	"""Test "json" argument to dataclass()"""

	if to_json:
		json_arg = True if from_json else 'to'
	else:
		json_arg = 'from' if from_json else False

	@dataclass(json=json_arg)
	class TestCls:
		x = field(int)
		y = field(str)

	attrvals = dict(x=1, y='foo')
	obj = TestCls(**attrvals)

	# Convert to
	if to_json:
		assert issubclass(TestCls, Jsonable)
		assert isinstance(obj, Jsonable)
		assert obj.to_json() == attrvals

	else:
		assert not issubclass(TestCls, Jsonable)
		assert not isinstance(obj, Jsonable)
		assert not hasattr(obj, 'to_json')

	# Convert from
	if from_json:
		assert issubclass(TestCls, JsonConstructible)
		assert isinstance(obj, JsonConstructible)
		assert TestCls.from_json(attrvals) == obj

	else:
		assert not issubclass(TestCls, JsonConstructible)
		assert not isinstance(obj, JsonConstructible)
		assert not hasattr(TestCls, 'from_json')


@pytest.fixture()
def BasicJsonClass():
	"""JSONable dataclass with fields of all basic types."""

	@dataclass(json=True)
	class _BasicJsonClass:
		int_ = field(int)
		float_ = field(float)
		str_ = field(str)
		list_ = field(list)
		dict_ = field(dict)
		hasdefault = field(int, default=42)
		nojson = field(int, optional=True, json=False)

	return _BasicJsonClass


@pytest.fixture()
def basicdataclass_json():
	"""JSON data for BasicJsonClass."""
	return dict(
		int_=24,
		float_=2.34,
		str_='foo',
		list_=[1, 2, 3],
		dict_={'a': 4, 'b': 'bar'},
		hasdefault=10,
	)


def test_to_json_basic(BasicJsonClass, basicdataclass_json):
	"""Test basic conversion to JSON."""

	# Test basic
	data1 = BasicJsonClass(**basicdataclass_json)
	assert data1.to_json() == basicdataclass_json

	# Test with nojson attribute set.
	data2 = BasicJsonClass(**basicdataclass_json, nojson=1)
	assert data2.nojson == 1

	json2 = data2.to_json()
	assert 'nojson' not in json2
	assert json2 == basicdataclass_json

	# Test additional keys
	json3 = {'badkey': 123, **basicdataclass_json}

	with pytest.raises(KeyError):
		BasicJsonClass.from_json(json3)


def test_from_json_basic(BasicJsonClass, basicdataclass_json):
	"""Test basic creation from JSON."""

	# Basic
	data1 = BasicJsonClass.from_json(basicdataclass_json)

	for key, value in basicdataclass_json.items():
		assert getattr(data1, key) == value

	assert data1.nojson is None

	# Try with default omitted
	json2 = dict(basicdataclass_json)
	del json2['hasdefault']

	data2 = BasicJsonClass.from_json(json2)

	for key, value in json2.items():
		assert getattr(data2, key) == value

	assert data2.hasdefault == attr.fields(BasicJsonClass).hasdefault.default
	assert data2.nojson is None


def test_field_nojson():
	"""Test field(json=False)."""

	@dataclass(json=True)
	class TestCls:
		x = field(int)
		y = field(int, optional=True, json=False)

	# Test omitted from JSON output
	json1 = TestCls(0).to_json()
	assert json1 == dict(x=0)

	json2 = TestCls(0, 1).to_json()
	assert json2 == dict(x=0)

	# Check still takes attribute from json
	assert TestCls.from_json(dict(x=1)) == TestCls(1)
	assert TestCls.from_json(dict(x=1, y=2)) == TestCls(1, 2)
