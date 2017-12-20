"""Abstract base classes."""

from abc import ABCMeta, abstractmethod


__all__ = ['Jsonable', 'JsonConstructible']


class Jsonable(metaclass=ABCMeta):
	"""ABC for a class whose instances can be converted to JSON."""

	@abstractmethod
	def to_json(self):
		"""Convert to a value serializable as JSON.

		:returns: Value which can be passed to :func:`json.dump`.
		:rtype: Union[int, float, str, list, dict, None]
		"""
		pass


class JsonConstructible(metaclass=ABCMeta):
	"""ABC for a class which can be instantiated from JSON data."""

	@classmethod
	@abstractmethod
	def from_json(cls, data):
		"""Create an instance of the class from JSON data.

		:param data: JSON data as returned by :func:`json.load`.
		:type data: Union[int, float, str, list, dict, None]
		:returns: Class instance.
		"""
		pass
