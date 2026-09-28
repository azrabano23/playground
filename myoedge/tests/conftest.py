import pytest

from myoedge.data import available

real = pytest.mark.skipif(not available(), reason="run `myoedge fetch` for the real dataset")
