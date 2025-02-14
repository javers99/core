"""Config flow for Remember The Milk integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiortm import AioRTMClient, Auth, AuthError, ResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SHARED_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)

TOKEN_TIMEOUT_SEC = 30

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_SHARED_SECRET): str,
    }
)


class RTMConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remember The Milk."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client: AioRTMClient | None = None
        self._url: str | None = None
        self._frob: str | None = None
        self._auth_data: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._auth_data = user_input
            client = self._client = AioRTMClient(
                Auth(
                    client_session=async_get_clientsession(self.hass),
                    api_key=user_input[CONF_API_KEY],
                    shared_secret=user_input[CONF_SHARED_SECRET],
                    permission="delete",
                )
            )
            auth = client.rtm.api
            try:
                self._url, self._frob = await auth.authenticate_desktop()
            except AuthError:
                errors["base"] = "invalid_auth"
            except ResponseError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return await self.async_step_auth()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authorize the application."""
        assert self._url is not None
        if user_input is not None:
            return await self.async_step_token()

        return self.async_show_form(
            step_id="auth", description_placeholders={"url": self._url}
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Get token and create config entry."""
        assert self._client is not None
        assert self._frob is not None
        assert self._auth_data is not None
        try:
            async with asyncio.timeout(TOKEN_TIMEOUT_SEC):
                token = await self._client.rtm.api.get_token(self._frob)
        except TimeoutError:
            return self.async_abort(reason="timeout")
        except AuthError:
            return self.async_abort(reason="invalid_auth")
        except ResponseError:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(token["user"]["id"])
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=token["user"]["fullname"],
            data={
                **self._auth_data,
                CONF_TOKEN: token["token"],
                CONF_USERNAME: token["user"]["username"],
            },
        )
