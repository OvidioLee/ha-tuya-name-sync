"""Constants for Tuya Name Sync."""

DOMAIN = "tuya_name_sync"

SOURCE_DOMAIN = "tuya"
TARGET_DOMAIN = "tuya_local"

CONF_AUTO_SYNC = "auto_sync"
CONF_SYNC_ENTRY_TITLE = "sync_entry_title"
CONF_PREFIX = "prefix"
CONF_SYNC_ENTITY_NAMES = "sync_entity_names"

DEFAULT_AUTO_SYNC = True
DEFAULT_SYNC_ENTRY_TITLE = True
DEFAULT_PREFIX = "TL_"
DEFAULT_SYNC_ENTITY_NAMES = True

SERVICE_SYNC = "sync"
ATTR_DRY_RUN = "dry_run"
