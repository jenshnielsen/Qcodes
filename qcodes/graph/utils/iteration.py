from typing import Iterable, Iterator, List, TypeVar

T = TypeVar("T")


class ReusableIterator:
    def __init__(self, iterable: Iterable[T]):
        self._iterator = iter(iterable)
        self._items: List = []

    def __iter__(self) -> Iterator[T]:
        if len(self._items) == 0:
            return self
        return iter(self._items)

    def __next__(self) -> T:
        self._items.append(next(self._iterator))
        return self._items[-1]


def lazy_product(*iterables: Iterable[T]) -> Iterable[Iterable[T]]:
    """
    Returns the Euclidean product of the set of iterables.
    Behavior is identical to `itertools.product`, except that
    `lazy_product` avoids evaluation of generators as much
    as possible.
    >>> list(lazy_product([1,2], [3,4]))
    [(1, 3), (1, 4), (2, 3), (2, 4)]
    """
    product = _recursive_lazy_product(*map(ReusableIterator, iterables))
    return map(tuple, product)


def _recursive_lazy_product(*iterables: Iterable[T]) -> Iterable[List[T]]:
    if len(iterables) == 0:
        yield []
    else:
        for element0 in iterables[0]:
            for remaining_elements in _recursive_lazy_product(*iterables[1:]):
                yield [element0] + remaining_elements
