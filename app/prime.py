class PrimeTester:
    def __init__(self, sieve_limit):
        self.sieve_limit = sieve_limit
        self.primes = []
        self.prime_set = frozenset()
        self.ready = False

    def warm_up(self):
        flags = bytearray([1]) * (self.sieve_limit + 1)
        flags[0] = 0
        flags[1] = 0
        step = 2
        while step * step <= self.sieve_limit:
            if flags[step]:
                flags[step * step :: step] = bytearray(len(flags[step * step :: step]))
            step += 1
        self.primes = [i for i, flag in enumerate(flags) if flag]
        self.prime_set = frozenset(self.primes)
        self.ready = True
        return len(self.primes)

    @property
    def max_n(self):
        return self.sieve_limit * self.sieve_limit

    def smallest_factor(self, n):
        if not self.ready:
            raise RuntimeError("sieve has not been warmed up")
        if n > self.max_n:
            raise ValueError(f"n must be {self.max_n} or less for the sieve to prove primality")
        if n < 2:
            return None
        if n <= self.sieve_limit:
            return None if n in self.prime_set else next(p for p in self.primes if n % p == 0)
        for p in self.primes:
            if p * p > n:
                break
            if n % p == 0:
                return p
        return None

    def is_prime(self, n):
        return n >= 2 and self.smallest_factor(n) is None
