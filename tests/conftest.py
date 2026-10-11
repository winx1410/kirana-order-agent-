import pytest

import order_engine


@pytest.fixture(autouse=True)
def isolated_engine_state():
    order_engine.reset_state()
    yield
    order_engine.reset_state()
