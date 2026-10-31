import pytest


@pytest.fixture(autouse=True)
async def french(hass):
    hass.config.language = "fr"
    yield
