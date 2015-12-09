__author__ = 'vladimir'

import pytest

from server import wrap_value, unwrap_value

def test_wrapping():
    val1 = "'test"
    val2 = wrap_value(val1)
    val3 = "&#39;"
    assert val2 == val3
