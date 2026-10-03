"""Fake National Provider Identifiers that pass the real check-digit test.

A real NPI is ten digits. The tenth is a Luhn check digit computed over the
constant prefix ``80840`` (the ISO health-identifier prefix for the US) followed
by the first nine digits. Generating them this way means the demo data survives
the same validation a real feed would face, while every value is invented.
"""

from __future__ import annotations

import random

NPI_PREFIX = "80840"


def luhn_check_digit(digits: str) -> int:
    """Return the Luhn check digit for a string of digits (without the check digit)."""
    total = 0
    for position, char in enumerate(reversed(digits)):
        value = int(char)
        if position % 2 == 0:  # the digit nearest the check digit is doubled
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return (10 - total % 10) % 10


def is_valid_npi(npi: str) -> bool:
    """True if ``npi`` is ten digits whose last digit is the correct Luhn check digit."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    return luhn_check_digit(NPI_PREFIX + npi[:9]) == int(npi[9])


def make_npi(rng: random.Random) -> str:
    """Return a random, well-formed NPI. Real NPIs begin with 1 or 2."""
    base = rng.choice("12") + "".join(rng.choice("0123456789") for _ in range(8))
    return base + str(luhn_check_digit(NPI_PREFIX + base))
