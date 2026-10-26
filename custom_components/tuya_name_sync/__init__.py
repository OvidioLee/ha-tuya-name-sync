"""Copy device names from the Tuya cloud integration to Tuya Local.

Devices are matched by Tuya device ID: the cloud integration registers
devices with identifier ("tuya", <id>) and Tuya Local with
("tuya_local", <id>). The cloud name (or the name you set in Home Assistant
for the cloud device), with an optional prefix such as "TL_" in front, is
written to the Tuya Local device as its user name, and optionally to the
Tuya Local config entry title.

Socket names you set in Home Assistant on the cloud device's switches (e.g.
"Socket 1" renamed to "Fan") are copied the same way to the matching Tuya
Local switch, paired by socket number. Entity IDs are not changed, so
automations keep working.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DRY_RUN,
    CONF_AUTO_SYNC,
    CONF_PREFIX,
    CONF_SYNC_ENTITY_NAMES,
    CONF_SYNC_ENTRY_TITLE,
    DEFAULT_AUTO_SYNC,
    DEFAULT_PREFIX,
    DEFAULT_SYNC_ENTITY_NAMES,
    DEFAULT_SYNC_ENTRY_TITLE,
    DOMAIN,
    SERVICE_SYNC,
    SOURCE_DOMAIN,
    TARGET_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SYNC_SCHEMA = vol.Schema({vol.Optional(ATTR_DRY_RUN, default=False): cv.boolean})


@dataclass
class Change:
    """A single rename performed (or planned) by a sync."""

    device_id: str
    kind: str
    old: str | None
    new: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "tuya_device_id": self.device_id,
            "kind": self.kind,
            "old": self.old,
            "new": self.new,
        }


def _all_devices(registry: dr.DeviceRegistry) -> list[dr.DeviceEntry]:
    # Newer HA yields DeviceEntry objects when iterating registry.devices and
    # deprecates .values(); older HA is a plain mapping of id -> DeviceEntry.
    devices = registry.devices
    first = next(iter(devices), None)
    if first is None or isinstance(first, dr.DeviceEntry):
        return list(devices)
    return list(devices.values())


def _tuya_id(device: dr.DeviceEntry, domain: str) -> str | None:
    for ident_domain, ident in device.identifiers:
        if ident_domain == domain:
            return ident
    return None


def _local_name(cloud_name: str, prefix: str) -> str:
    # Don't double up when the cloud name already carries the prefix.
    if not prefix or cloud_name.startswith(prefix):
        return cloud_name
    return f"{prefix}{cloud_name}"


# Socket keys are ("socket" | "usb", number). Cloud switches are named by DP
# code (switch_1, switch_usb1); Tuya Local by its device config (outlet_1,
# switch_2, usb_switch, or a bare "outlet" for a single plug).
_CLOUD_SOCKET = re.compile(r"^switch(?:_(\d+))?$")
_CLOUD_USB = re.compile(r"^switch_usb(\d*)$")
_LOCAL_SOCKET = re.compile(r"^(?:outlet|switch|socket)(?:_(\d+))?$")
_LOCAL_USB = re.compile(r"^(?:usb|usb_switch|switch_usb)(?:_?(\d+))?$")


def _socket_key(
    name: str, socket: re.Pattern[str], usb: re.Pattern[str]
) -> tuple[str, int] | None:
    if match := socket.match(name):
        return ("socket", int(match.group(1) or 1))
    if match := usb.match(name):
        return ("usb", int(match.group(1) or 1))
    return None


def _switches_by_key(
    entities: er.EntityRegistry,
    device: dr.DeviceEntry,
    platform: str,
    uid_prefix: str,
    socket: re.Pattern[str],
    usb: re.Pattern[str],
) -> dict[tuple[str, int], er.RegistryEntry]:
    """Map socket key -> switch entity of one device; ambiguous keys are dropped."""
    found: list[tuple[tuple[str, int], er.RegistryEntry]] = []
    for entity in er.async_entries_for_device(
        entities, device.id, include_disabled_entities=True
    ):
        if entity.platform != platform or entity.domain != "switch":
            continue
        if not entity.unique_id.startswith(uid_prefix):
            continue
        name = entity.unique_id[len(uid_prefix) :].lstrip("_")
        if (key := _socket_key(name, socket, usb)) is not None:
            found.append((key, entity))
    counts = Counter(key for key, _ in found)
    return {key: entity for key, entity in found if counts[key] == 1}


@callback
def async_sync_names(
    hass: HomeAssistant,
    *,
    prefix: str,
    sync_entry_title: bool,
    sync_entity_names: bool,
    dry_run: bool = False,
) -> list[Change]:
    """Copy cloud Tuya names, with prefix, onto matching Tuya Local devices."""
    registry = dr.async_get(hass)
    entities = er.async_get(hass)
    devices = _all_devices(registry)

    cloud_names: dict[str, str] = {}
    cloud_devices: dict[str, dr.DeviceEntry] = {}
    for device in devices:
        if (tuya_id := _tuya_id(device, SOURCE_DOMAIN)) is None:
            continue
        cloud_devices[tuya_id] = device
        if name := device.name_by_user or device.name:
            cloud_names[tuya_id] = _local_name(name, prefix)

    changes: list[Change] = []

    for device in devices:
        tuya_id = _tuya_id(device, TARGET_DOMAIN)
        if tuya_id is None or (new := cloud_names.get(tuya_id)) is None:
            continue
        current = device.name_by_user or device.name
        if current != new:
            changes.append(Change(tuya_id, "device", current, new))
            if not dry_run:
                registry.async_update_device(device.id, name_by_user=new)

        if not sync_entity_names:
            continue
        cloud_switches = _switches_by_key(
            entities,
            cloud_devices[tuya_id],
            SOURCE_DOMAIN,
            f"tuya.{tuya_id}",
            _CLOUD_SOCKET,
            _CLOUD_USB,
        )
        local_switches = _switches_by_key(
            entities,
            device,
            TARGET_DOMAIN,
            f"{tuya_id}-switch",
            _LOCAL_SOCKET,
            _LOCAL_USB,
        )
        for key, cloud_entity in cloud_switches.items():
            # Only names you set on the cloud switch; its default name
            # ("Socket 1") carries nothing worth copying.
            if not cloud_entity.name or (local := local_switches.get(key)) is None:
                continue
            new_entity_name = _local_name(cloud_entity.name, prefix)
            if local.name != new_entity_name:
                changes.append(
                    Change(tuya_id, local.entity_id, local.name, new_entity_name)
                )
                if not dry_run:
                    entities.async_update_entity(
                        local.entity_id, name=new_entity_name
                    )

    if sync_entry_title:
        for entry in hass.config_entries.async_entries(TARGET_DOMAIN):
            tuya_id = entry.data.get("device_id")
            if (new := cloud_names.get(tuya_id)) is None or entry.title == new:
                continue
            changes.append(Change(tuya_id, "entry_title", entry.title, new))
            if not dry_run:
                hass.config_entries.async_update_entry(entry, title=new)

    for change in changes:
        _LOGGER.info(
            "%s %s name of %s: %r -> %r",
            "Would change" if dry_run else "Changed",
            change.kind,
            change.device_id,
            change.old,
            change.new,
        )
    return changes


@dataclass
class Settings:
    """Options of the config entry, with defaults filled in."""

    auto_sync: bool = DEFAULT_AUTO_SYNC
    sync_entry_title: bool = DEFAULT_SYNC_ENTRY_TITLE
    sync_entity_names: bool = DEFAULT_SYNC_ENTITY_NAMES
    prefix: str = DEFAULT_PREFIX

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> Settings:
        # A prefix saved as "" means "no prefix"; only a missing key gets the default.
        return cls(
            auto_sync=entry.options.get(CONF_AUTO_SYNC, DEFAULT_AUTO_SYNC),
            sync_entry_title=entry.options.get(
                CONF_SYNC_ENTRY_TITLE, DEFAULT_SYNC_ENTRY_TITLE
            ),
            sync_entity_names=entry.options.get(
                CONF_SYNC_ENTITY_NAMES, DEFAULT_SYNC_ENTITY_NAMES
            ),
            prefix=entry.options.get(CONF_PREFIX, DEFAULT_PREFIX),
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the manual sync service."""

    async def handle_sync(call: ServiceCall) -> ServiceResponse:
        entries = hass.config_entries.async_loaded_entries(DOMAIN)
        settings = Settings.from_entry(entries[0]) if entries else Settings()
        changes = async_sync_names(
            hass,
            prefix=settings.prefix,
            sync_entry_title=settings.sync_entry_title,
            sync_entity_names=settings.sync_entity_names,
            dry_run=call.data[ATTR_DRY_RUN],
        )
        return {"changes": [change.as_dict() for change in changes]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC,
        handle_sync,
        schema=SYNC_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up automatic syncing."""
    settings = Settings.from_entry(entry)

    @callback
    def run_sync() -> None:
        async_sync_names(
            hass,
            prefix=settings.prefix,
            sync_entry_title=settings.sync_entry_title,
            sync_entity_names=settings.sync_entity_names,
        )

    # Sync once Home Assistant (and with it Tuya / Tuya Local) has started.
    # Must be a @callback so it runs on the event loop, not in an executor.
    @callback
    def on_started(_: HomeAssistant) -> None:
        run_sync()

    entry.async_on_unload(async_at_started(hass, on_started))

    if settings.auto_sync:
        debouncer = Debouncer(
            hass, _LOGGER, cooldown=2, immediate=False, function=run_sync
        )
        entry.async_on_unload(debouncer.async_cancel)
        registry = dr.async_get(hass)

        @callback
        def on_device_update(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
            if event.data["action"] == "remove":
                return
            device = registry.async_get(event.data["device_id"])
            if device is None:
                return
            if _tuya_id(device, SOURCE_DOMAIN) or _tuya_id(device, TARGET_DOMAIN):
                debouncer.async_schedule_call()

        entry.async_on_unload(
            hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, on_device_update)
        )

        if settings.sync_entity_names:
            entities = er.async_get(hass)

            @callback
            def on_entity_update(
                event: Event[er.EventEntityRegistryUpdatedData],
            ) -> None:
                if event.data["action"] == "remove":
                    return
                entity = entities.async_get(event.data["entity_id"])
                if entity is not None and entity.platform in (
                    SOURCE_DOMAIN,
                    TARGET_DOMAIN,
                ):
                    debouncer.async_schedule_call()

            entry.async_on_unload(
                hass.bus.async_listen(
                    er.EVENT_ENTITY_REGISTRY_UPDATED, on_entity_update
                )
            )

    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return True
