"""The Remember The Milk integration."""

from __future__ import annotations

from aiortm import AioRTMClient, Auth
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ID,
    CONF_NAME,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import CONF_SHARED_SECRET, DOMAIN, LOGGER
from .entity import RememberTheMilk
from .storage import RememberTheMilkConfiguration

DEFAULT_NAME = DOMAIN

RTM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_SHARED_SECRET): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [RTM_SCHEMA])}, extra=vol.ALLOW_EXTRA
)

SERVICE_CREATE_TASK = "create_task"
SERVICE_COMPLETE_TASK = "complete_task"

SERVICE_SCHEMA_CREATE_TASK = vol.Schema(
    {vol.Required(CONF_NAME): cv.string, vol.Optional(CONF_ID): cv.string}
)

SERVICE_SCHEMA_COMPLETE_TASK = vol.Schema({vol.Required(CONF_ID): cv.string})

DATA_COMPONENT = "component"
DATA_ENTITY_ID = "entity_id"
DATA_STORAGE = "storage"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Remember the milk component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_COMPONENT] = EntityComponent[RememberTheMilk](
        LOGGER, DOMAIN, hass
    )
    storage = hass.data[DOMAIN][DATA_STORAGE] = RememberTheMilkConfiguration(hass)
    await hass.async_add_executor_job(storage.setup)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remember The Milk from a config entry."""
    component: EntityComponent[RememberTheMilk] = hass.data[DOMAIN][DATA_COMPONENT]
    storage: RememberTheMilkConfiguration = hass.data[DOMAIN][DATA_STORAGE]

    rtm_config = entry.data
    account_name: str = rtm_config[CONF_USERNAME]
    LOGGER.debug("Adding Remember the milk account %s", account_name)
    api_key: str = rtm_config[CONF_API_KEY]
    shared_secret: str = rtm_config[CONF_SHARED_SECRET]
    token: str = rtm_config[CONF_TOKEN]
    client = AioRTMClient(
        Auth(
            client_session=async_get_clientsession(hass),
            api_key=api_key,
            shared_secret=shared_secret,
            auth_token=token,
            permission="delete",
        )
    )

    token_valid = True
    if not await client.rtm.api.check_token():
        token_valid = False

    if entity_id := hass.data[DOMAIN].get(DATA_ENTITY_ID):
        await component.async_remove_entity(entity_id)

    entity = RememberTheMilk(
        name=account_name,
        client=client,
        config_entry_id=entry.entry_id,
        storage=storage,
        token_valid=token_valid,
    )
    await component.async_add_entities([entity])
    hass.data[DOMAIN][DATA_ENTITY_ID] = entity.entity_id

    # The services are registered here for now because they need the account name.
    # The services will be deprecated when a todo platform is added.
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_create_task",
        entity.create_task,
        schema=SERVICE_SCHEMA_CREATE_TASK,
    )
    hass.services.async_register(
        DOMAIN,
        f"{account_name}_complete_task",
        entity.complete_task,
        schema=SERVICE_SCHEMA_COMPLETE_TASK,
    )

    if not token_valid:
        raise ConfigEntryAuthFailed

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[RememberTheMilk] = hass.data[DOMAIN][DATA_COMPONENT]
    await component.async_remove_entity(hass.data[DOMAIN][DATA_ENTITY_ID])
    return True
