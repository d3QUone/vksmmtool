__author__ = 'vladimir'

import pytest

from server import wrap_value, unwrap_value, short_value


def test_wrapping():
    val1 = "'test"
    val2 = wrap_value(val1)
    val3 = "&#39;test"
    assert val2 == val3


def test_unwrapping():
    val1 = "&#39;test"
    val2 = unwrap_value(val1)
    val3 = "'test"
    assert val2 == val3


def test_shortener():
    val1 = "test1test2test3"
    val2 = short_value(val1, 13)
    val3 = "test1test2..."
    assert val2 == val3
