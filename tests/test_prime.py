import pytest

from app.prime import PrimeTester


@pytest.fixture(scope="module")
def tester():
    t = PrimeTester(1000)
    t.warm_up()
    return t


def test_warm_up_reports_prime_count():
    t = PrimeTester(100)
    assert t.warm_up() == 25
    assert t.ready


def test_smallest_factor_requires_warm_up():
    t = PrimeTester(100)
    with pytest.raises(RuntimeError):
        t.smallest_factor(7)


@pytest.mark.parametrize("n", [2, 3, 5, 7, 13, 97, 991])
def test_known_primes_inside_the_sieve(tester, n):
    assert tester.is_prime(n)


@pytest.mark.parametrize("n", [0, 1, 4, 9, 100, 999])
def test_known_composites_inside_the_sieve(tester, n):
    assert not tester.is_prime(n)


@pytest.mark.parametrize("n", [1009, 7919, 104729])
def test_known_primes_above_the_sieve(tester, n):
    assert tester.is_prime(n)


@pytest.mark.parametrize("n", [1001, 7917, 104730])
def test_known_composites_above_the_sieve(tester, n):
    assert not tester.is_prime(n)


def test_smallest_factor_returns_the_smallest(tester):
    assert tester.smallest_factor(360) == 2
    assert tester.smallest_factor(1001) == 7


def test_primes_return_no_factor(tester):
    assert tester.smallest_factor(991) is None


def test_max_n_is_the_square_of_the_sieve_limit(tester):
    assert tester.max_n == 1000000


def test_beyond_max_n_is_rejected(tester):
    with pytest.raises(ValueError):
        tester.smallest_factor(tester.max_n + 1)
