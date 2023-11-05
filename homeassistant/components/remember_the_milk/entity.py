"""Support to interact with Remember The Milk."""

import logging

from aiortm import AioRTMClient, AioRTMError

from homeassistant.const import CONF_ID, CONF_NAME, STATE_OK
from homeassistant.core import ServiceCall
from homeassistant.helpers.entity import Entity

from .storage import RememberTheMilkConfiguration

_LOGGER = logging.getLogger(__name__)


class RememberTheMilk(Entity):
    """Representation of an interface to Remember The Milk."""

    def __init__(
        self, name: str, client: AioRTMClient, storage: RememberTheMilkConfiguration
    ) -> None:
        """Create new instance of Remember The Milk component."""
        self._name = name
        self._rtm_config = storage
        self._client = client

    async def create_task(self, call: ServiceCall) -> None:
        """Create a new task on Remember The Milk.

        You can use the smart syntax to define the attributes of a new task,
        e.g. "my task #some_tag ^today" will add tag "some_tag" and set the
        due date to today.
        """
        try:
            task_name: str = call.data[CONF_NAME]
            hass_id: str | None = call.data.get(CONF_ID)
            rtm_id: tuple[int, int, int] | None = None
            if hass_id is not None:
                rtm_id = await self.hass.async_add_executor_job(
                    self._rtm_config.get_rtm_id, self._name, hass_id
                )
            timeline_response = await self._client.rtm.timelines.create()
            timeline = timeline_response.timeline

            if hass_id is None or rtm_id is None:
                add_response = await self._client.rtm.tasks.add(
                    timeline=timeline, name=task_name, parse=True
                )
                _LOGGER.debug(
                    "Created new task '%s' in account %s", task_name, self.name
                )
                task_list = add_response.task_list
                taskseries = task_list.taskseries[0]
                await self.hass.async_add_executor_job(
                    self._rtm_config.set_rtm_id,
                    self._name,
                    hass_id,
                    task_list.id,
                    taskseries.id,
                    taskseries.task[0].id,
                )
            else:
                await self._client.rtm.tasks.set_name(
                    name=task_name,
                    list_id=rtm_id[0],
                    taskseries_id=rtm_id[1],
                    task_id=rtm_id[2],
                    timeline=timeline,
                )
                _LOGGER.debug(
                    "Updated task with id '%s' in account %s to name %s",
                    hass_id,
                    self.name,
                    task_name,
                )
        except AioRTMError as rtm_exception:
            _LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    async def complete_task(self, call: ServiceCall) -> None:
        """Complete a task that was previously created by this component."""
        hass_id = call.data[CONF_ID]
        rtm_id = await self.hass.async_add_executor_job(
            self._rtm_config.get_rtm_id, self._name, hass_id
        )
        if rtm_id is None:
            _LOGGER.error(
                (
                    "Could not find task with ID %s in account %s. "
                    "So task could not be closed"
                ),
                hass_id,
                self._name,
            )
            return
        try:
            result = await self._client.rtm.timelines.create()
            timeline = result.timeline
            await self._client.rtm.tasks.complete(
                list_id=rtm_id[0],
                taskseries_id=rtm_id[1],
                task_id=rtm_id[2],
                timeline=timeline,
            )
            await self.hass.async_add_executor_job(
                self._rtm_config.delete_rtm_id, self._name, hass_id
            )
            _LOGGER.debug(
                "Completed task with id %s in account %s", hass_id, self._name
            )
        except AioRTMError as rtm_exception:
            _LOGGER.error(
                "Error creating new Remember The Milk task for account %s: %s",
                self._name,
                rtm_exception,
            )

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return STATE_OK
