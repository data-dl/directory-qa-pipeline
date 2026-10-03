import random

from synth.npi import is_valid_npi, luhn_check_digit, make_npi


def test_known_valid_npi_passes():
    # A widely published example NPI whose check digit is correct.
    assert is_valid_npi("1234567893")


def test_wrong_check_digit_fails():
    assert not is_valid_npi("1234567890")


def test_shape_is_enforced():
    assert not is_valid_npi("123")
    assert not is_valid_npi("12345678AB")
    assert not is_valid_npi("12345678931")


def test_luhn_on_prefix_only():
    # 80840 + 123456789 -> check digit 3 (the example above, worked by hand).
    assert luhn_check_digit("80840123456789") == 3


def test_generated_npis_are_valid_and_well_formed():
    rng = random.Random(1)
    for _ in range(2000):
        npi = make_npi(rng)
        assert len(npi) == 10 and npi.isdigit()
        assert npi[0] in "12"
        assert is_valid_npi(npi)
