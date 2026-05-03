#!/usr/bin/env python3

import json
import os
import plistlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

APP_DIR = Path(
    os.environ.get(
        "TAHOE_AERIAL_APP_DIR",
        str(Path.home() / "Library" / "Application Support" / "TahoeAerialScheduler"),
    )
)
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
AERIAL_VIDEOS_DIR = (
    Path.home()
    / "Library"
    / "Application Support"
    / "com.apple.wallpaper"
    / "aerials"
    / "videos"
)
WALLPAPER_SETTINGS_URL = "x-apple.systempreferences:com.apple.Wallpaper-Settings.extension"
LIVE_PLIST = (
    Path.home()
    / "Library"
    / "Application Support"
    / "com.apple.wallpaper"
    / "Store"
    / "Index_v2.plist"
)
LEGACY_PLIST = (
    Path.home()
    / "Library"
    / "Application Support"
    / "com.apple.wallpaper"
    / "Store"
    / "Index.plist"
)

WALLPAPER_AGENT_LABEL = f"gui/{os.getuid()}/com.apple.wallpaper.agent"
AERIAL_EXTENSION_PROCESS = "WallpaperAerialsExtension"
AERIAL_PROVIDER = "com.apple.wallpaper.choice.aerials"
LEGACY_CONVERTIBLE_PROVIDERS = {"default", "com.apple.wallpaper.choice.image"}

DEFAULT_ASSETS = {
    "tahoe_night": {
        "label": "Tahoe Night",
        "asset_id": "CF6347E2-4F81-4410-8892-4830991B6C5A",
    },
    "tahoe_morning": {
        "label": "Tahoe Morning",
        "asset_id": "B2FC91ED-6891-4DEB-85A1-268B2B4160B6",
    },
    "tahoe_day": {
        "label": "Tahoe Day",
        "asset_id": "4C108785-A7BA-422E-9C79-B0129F1D5550",
    },
    "tahoe_evening": {
        "label": "Tahoe Evening",
        "asset_id": "52ACB9B8-75FC-4516-BC60-4550CFF3B661",
    },
}

PERIODS = ("morning", "day", "evening", "night")

DEFAULT_CONFIG = {
    "version": 1,
    "assets": DEFAULT_ASSETS,
    "schedule": [
        {"start": "20:00", "asset": "tahoe_night", "period": "night"},
        {"start": "05:00", "asset": "tahoe_morning", "period": "morning"},
        {"start": "09:00", "asset": "tahoe_day", "period": "day"},
        {"start": "17:00", "asset": "tahoe_evening", "period": "evening"},
    ],
}


@dataclass(frozen=True)
class Slot:
    start: str
    minutes: int
    asset_key: str
    period: str


def ensure_app_dir() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    ensure_app_dir()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def ensure_default_config() -> None:
    if not CONFIG_PATH.exists():
        write_json(CONFIG_PATH, DEFAULT_CONFIG)


def load_config() -> dict:
    ensure_default_config()
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    migrate_config(config)
    validate_config(config)
    return config


def parse_time(value: str) -> int:
    hour_str, minute_str = value.strip().split(":", 1)
    hour = int(hour_str)
    minute = int(minute_str)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"Invalid time: {value}")
    return hour * 60 + minute


def infer_period_for_minutes(minutes: int) -> str:
    if 5 * 60 <= minutes < 9 * 60:
        return "morning"
    if 9 * 60 <= minutes < 17 * 60:
        return "day"
    if 17 * 60 <= minutes < 20 * 60:
        return "evening"
    return "night"


def validate_config(config: dict) -> None:
    if "assets" not in config or "schedule" not in config:
        raise ValueError("Config must contain 'assets' and 'schedule'.")

    assets = config["assets"]
    seen_times = set()
    for item in config["schedule"]:
        start = item["start"]
        asset_key = item["asset"]
        period = item.get("period")
        if asset_key not in assets:
            raise ValueError(f"Unknown asset key in schedule: {asset_key}")
        if period not in PERIODS:
            raise ValueError(f"Unknown period in schedule: {period}")
        minutes = parse_time(start)
        if minutes in seen_times:
            raise ValueError(f"Duplicate schedule start time: {start}")
        seen_times.add(minutes)


def migrate_config(config: dict) -> None:
    schedule = config.get("schedule", [])
    missing_period = any("period" not in item for item in schedule)
    if not missing_period:
        return

    ordered = sorted(schedule, key=lambda item: parse_time(item["start"]))
    for item in ordered:
        if "period" not in item:
            item["period"] = infer_period_for_minutes(parse_time(item["start"]))
    write_json(CONFIG_PATH, config)


def sorted_slots(config: dict) -> list[Slot]:
    items = []
    for entry in config["schedule"]:
        items.append(
            Slot(
                start=entry["start"],
                minutes=parse_time(entry["start"]),
                asset_key=entry["asset"],
                period=entry["period"],
            )
        )
    return sorted(items, key=lambda slot: slot.minutes)


def slot_for_now(config: dict, now: datetime | None = None) -> Slot:
    current = now or datetime.now()
    current_minutes = current.hour * 60 + current.minute
    slots = sorted_slots(config)

    selected = slots[-1]
    for slot in slots:
        if slot.minutes <= current_minutes:
            selected = slot
        else:
            break
    return selected


def next_slot(config: dict, current_slot: Slot) -> Slot:
    slots = sorted_slots(config)
    for index, slot in enumerate(slots):
        if slot == current_slot:
            return slots[(index + 1) % len(slots)]
    return slots[0]


def asset_from_key(config: dict, asset_key: str) -> dict:
    return config["assets"][asset_key]


def scheduled_asset_keys(config: dict) -> list[str]:
    return list(dict.fromkeys(item["asset"] for item in config["schedule"]))


def asset_video_path(asset_id: str) -> Path:
    return AERIAL_VIDEOS_DIR / f"{asset_id}.mov"


def missing_asset_entry(config: dict, asset_key: str) -> dict | None:
    asset = asset_from_key(config, asset_key)
    video_path = asset_video_path(asset["asset_id"])
    if video_path.exists():
        return None
    return {
        "asset_key": asset_key,
        "label": asset["label"],
        "asset_id": asset["asset_id"],
        "video_path": str(video_path),
    }


def missing_assets(config: dict) -> list[dict]:
    results = []
    for asset_key in scheduled_asset_keys(config):
        missing = missing_asset_entry(config, asset_key)
        if missing:
            results.append(missing)
    return results


def current_missing_assets(config: dict, now: datetime | None = None) -> list[dict]:
    slot = slot_for_now(config, now)
    missing = missing_asset_entry(config, slot.asset_key)
    if missing:
        return [missing]
    return []


def missing_assets_message(items: list[dict]) -> str:
    labels = ", ".join(item["label"] for item in items)
    return (
        "Tahoe Aerial downloads still needed: "
        f"{labels}. Open System Settings > Wallpaper and click the download "
        "button for those Tahoe Aerials."
    )


def ensure_asset_is_downloaded(asset: dict) -> None:
    video_path = asset_video_path(asset["asset_id"])
    if video_path.exists():
        return
    raise RuntimeError(
        f"{asset['label']} is not downloaded yet. Open System Settings > Wallpaper "
        "and download that Tahoe Aerial before using it."
    )


def load_plist(path: Path) -> dict:
    with path.open("rb") as handle:
        return plistlib.load(handle)


def decode_asset_id(choice: dict) -> str | None:
    if choice.get("Provider") != AERIAL_PROVIDER:
        return None
    configuration = choice.get("Configuration")
    if not configuration:
        return None
    payload = plistlib.loads(configuration)
    return payload.get("assetID")


def current_asset_id() -> str | None:
    try:
        store = load_plist(LIVE_PLIST)
        choice = store["AllSpacesAndDisplays"]["Desktop"]["Content"]["Choices"][0]
        return decode_asset_id(choice)
    except Exception:
        return None


def legacy_asset_id() -> str | None:
    try:
        store = load_plist(LEGACY_PLIST)
        section = store["AllSpacesAndDisplays"]
        for child_key in ("Linked", "Idle", "Desktop"):
            child = section.get(child_key)
            if not isinstance(child, dict):
                continue
            choice = child["Content"]["Choices"][0]
            asset_id = decode_asset_id(choice)
            if asset_id:
                return asset_id
    except Exception:
        return None
    return None


def configuration_blob(asset_id: str) -> bytes:
    return plistlib.dumps({"assetID": asset_id}, fmt=plistlib.FMT_BINARY)


def update_choice(
    choice: dict,
    asset_id: str,
    allow_provider_conversion: bool = False,
) -> bool:
    provider = choice.get("Provider")
    changed = False
    if provider != AERIAL_PROVIDER:
        if (
            not allow_provider_conversion
            or provider not in LEGACY_CONVERTIBLE_PROVIDERS
        ):
            return False
        choice["Provider"] = AERIAL_PROVIDER
        changed = True

    configuration = configuration_blob(asset_id)
    if choice.get("Configuration") != configuration:
        choice["Configuration"] = configuration
        changed = True

    if choice.get("Files") != []:
        choice["Files"] = []
        changed = True

    return changed


def update_content_container(
    container: dict,
    asset_id: str,
    applied_at: datetime,
    allow_provider_conversion: bool = False,
) -> bool:
    content = container.get("Content", {})
    choices = content.get("Choices", [])
    changed = False
    has_managed_choice = False
    for choice in choices:
        changed = update_choice(choice, asset_id, allow_provider_conversion) or changed
        has_managed_choice = choice.get("Provider") == AERIAL_PROVIDER or has_managed_choice

    if has_managed_choice and "EncodedOptionValues" in content:
        content.pop("EncodedOptionValues", None)
        changed = True

    if changed:
        container["LastSet"] = applied_at
        container["LastUse"] = applied_at
    return changed


def update_store_sections(
    store: dict,
    asset_id: str,
    applied_at: datetime,
    allow_provider_conversion: bool = False,
) -> bool:
    def update_nested_sections(section: dict) -> bool:
        changed = False
        for child_key in ("Desktop", "Idle", "Linked"):
            child = section.get(child_key)
            if isinstance(child, dict):
                changed = (
                    update_content_container(
                        child,
                        asset_id,
                        applied_at,
                        allow_provider_conversion,
                    )
                    or changed
                )

        for value in section.values():
            if isinstance(value, dict):
                changed = update_nested_sections(value) or changed

        return changed

    changed = False
    for root_key in ("AllSpacesAndDisplays", "SystemDefault", "Displays", "Spaces"):
        root = store.get(root_key)
        if not isinstance(root, dict):
            continue
        changed = update_nested_sections(root) or changed

    return changed


def write_updated_plist(
    path: Path,
    asset_id: str,
    applied_at: datetime,
    allow_provider_conversion: bool = False,
) -> bool:
    if not path.exists():
        return False

    store = load_plist(path)
    changed = update_store_sections(store, asset_id, applied_at, allow_provider_conversion)
    if not changed:
        return False

    with path.open("wb") as handle:
        plistlib.dump(store, handle, fmt=plistlib.FMT_BINARY, sort_keys=False)
    return True


def write_store(asset_id: str, applied_at: datetime | None = None) -> None:
    applied_at = applied_at or datetime.now()
    updated_any = False
    updated_any = write_updated_plist(LIVE_PLIST, asset_id, applied_at) or updated_any
    updated_any = (
        write_updated_plist(
            LEGACY_PLIST,
            asset_id,
            applied_at,
            allow_provider_conversion=True,
        )
        or updated_any
    )
    if not updated_any:
        raise RuntimeError("Could not find any native Aerial wallpaper entries to update.")


def slot_started_at(current: datetime, slot: Slot) -> datetime:
    started_at = current.replace(
        hour=slot.minutes // 60,
        minute=slot.minutes % 60,
        second=0,
        microsecond=0,
    )
    if started_at > current:
        return started_at - timedelta(days=1)
    return started_at


def active_desktop_last_set_at() -> datetime | None:
    try:
        store = load_plist(LIVE_PLIST)
        last_set = store["AllSpacesAndDisplays"]["Desktop"].get("LastSet")
        if isinstance(last_set, datetime):
            if last_set.tzinfo is not None:
                return last_set.astimezone().replace(tzinfo=None)
            return last_set
    except Exception:
        return None
    return None


def active_store_needs_refresh(slot: Slot, current: datetime, last_set: datetime | None) -> bool:
    if last_set is None:
        return True
    return last_set < slot_started_at(current, slot)


def parse_state_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def state_refreshed_current_slot(
    slot: Slot,
    current: datetime,
    desired_asset_id: str,
    state: dict,
) -> bool:
    if state.get("last_applied_asset_id") != desired_asset_id:
        return False

    last_applied_at = parse_state_timestamp(state.get("last_applied_at"))
    if last_applied_at is None:
        return False

    return last_applied_at >= slot_started_at(current, slot)


def asset_id_from_video_path(path: str) -> str | None:
    video_path = Path(path)
    if video_path.parent == AERIAL_VIDEOS_DIR and video_path.suffix == ".mov":
        return video_path.stem
    return None


def active_aerial_video_id() -> str | None:
    pgrep_result = subprocess.run(
        ["pgrep", AERIAL_EXTENSION_PROCESS],
        capture_output=True,
        text=True,
        check=False,
    )
    if pgrep_result.returncode != 0:
        return None

    for pid in pgrep_result.stdout.split():
        lsof_result = subprocess.run(
            ["lsof", "-Fn", "-p", pid],
            capture_output=True,
            text=True,
            check=False,
        )
        if lsof_result.returncode != 0:
            continue

        for line in lsof_result.stdout.splitlines():
            if not line.startswith("n"):
                continue
            asset_id = asset_id_from_video_path(line[1:])
            if asset_id:
                return asset_id
    return None


def restart_wallpaper_agent() -> None:
    result = subprocess.run(
        ["launchctl", "kickstart", "-k", WALLPAPER_AGENT_LABEL],
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["killall", AERIAL_EXTENSION_PROCESS],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0:
        subprocess.run(
            ["killall", "WallpaperAgent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def write_state(payload: dict) -> None:
    write_json(STATE_PATH, payload)


def apply_current_schedule() -> int:
    config = load_config()
    current = datetime.now()
    slot = slot_for_now(config, current)
    asset = asset_from_key(config, slot.asset_key)
    ensure_asset_is_downloaded(asset)
    desired_asset_id = asset["asset_id"]
    state = read_state()
    active_asset_id = current_asset_id()
    active_is_stale = active_store_needs_refresh(slot, current, active_desktop_last_set_at())
    stale_refresh_already_done = state_refreshed_current_slot(
        slot,
        current,
        desired_asset_id,
        state,
    )
    active_video_id = active_aerial_video_id()
    active_video_is_stale = active_video_id is not None and active_video_id != desired_asset_id

    # Only the live desktop choice should decide whether we need to restart the
    # wallpaper pipeline. Linked/idle stores can drift independently, and
    # forcing a full reapply for those mismatches causes unnecessary visible
    # resets on the desktop. A stale LastSet still gets one refresh per slot so
    # WallpaperAgent reloads after waking or cache drift, but state.json prevents
    # a stale plist timestamp from causing a visible restart every minute. The
    # Aerial extension can also keep playing its previous .mov after the plist
    # changes, so verify the actual player process when it is visible.
    if (
        active_asset_id == desired_asset_id
        and (not active_is_stale or stale_refresh_already_done)
        and not active_video_is_stale
    ):
        write_state(
            {
                "last_applied_asset": slot.asset_key,
                "last_applied_asset_id": desired_asset_id,
                "last_applied_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        print(f"Already active: {asset['label']} ({slot.asset_key})")
        return 0

    write_store(desired_asset_id, current)
    restart_wallpaper_agent()
    write_state(
        {
            "last_applied_asset": slot.asset_key,
            "last_applied_asset_id": desired_asset_id,
            "last_applied_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    action = "Refreshed" if active_asset_id == desired_asset_id else "Applied"
    print(f"{action} {asset['label']} ({slot.asset_key}) for schedule starting {slot.start}.")
    return 0


def print_schedule() -> int:
    config = load_config()
    slot = slot_for_now(config)
    following = next_slot(config, slot)

    print(f"Config: {CONFIG_PATH}")
    print("")
    for item in sorted_slots(config):
        asset = asset_from_key(config, item.asset_key)
        marker = "*" if item == slot else " "
        print(f"{marker} {item.start} -> {asset['label']} ({item.asset_key})")
    print("")
    print(f"Current slot: {slot.start} -> {asset_from_key(config, slot.asset_key)['label']}")
    print(f"Next slot: {following.start} -> {asset_from_key(config, following.asset_key)['label']}")
    return 0


def print_assets() -> int:
    config = load_config()
    for key, asset in config["assets"].items():
        print(f"{key}: {asset['label']} [{asset['asset_id']}]")
    return 0


def print_info_json() -> int:
    config = load_config()
    slot = slot_for_now(config)
    following = next_slot(config, slot)
    state = read_state()
    missing = missing_assets(config)
    current_missing = current_missing_assets(config)

    payload = {
        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_slot": {
            "start": slot.start,
            "asset_key": slot.asset_key,
            "label": asset_from_key(config, slot.asset_key)["label"],
            "period": slot.period,
        },
        "next_slot": {
            "start": following.start,
            "asset_key": following.asset_key,
            "label": asset_from_key(config, following.asset_key)["label"],
            "period": following.period,
        },
        "schedule": [
            {
                "start": item.start,
                "asset_key": item.asset_key,
                "label": asset_from_key(config, item.asset_key)["label"],
                "period": item.period,
            }
            for item in sorted_slots(config)
        ],
        "assets": config["assets"],
        "missing_assets": missing,
        "current_missing_assets": current_missing,
        "wallpaper_settings_url": WALLPAPER_SETTINGS_URL,
        "index_v2_asset_id": current_asset_id(),
        "index_asset_id": legacy_asset_id(),
        "active_aerial_video_id": active_aerial_video_id(),
        "last_applied_asset": state.get("last_applied_asset"),
        "last_applied_at": state.get("last_applied_at"),
    }
    print(json.dumps(payload))
    return 0


def print_status() -> int:
    config = load_config()
    slot = slot_for_now(config)
    asset = asset_from_key(config, slot.asset_key)
    active_asset = current_asset_id()
    legacy_asset = legacy_asset_id()
    active_video = active_aerial_video_id()
    state = read_state()
    missing = missing_assets(config)

    print(f"Config: {CONFIG_PATH}")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scheduled asset now: {asset['label']} ({slot.asset_key})")
    print(f"Scheduled start: {slot.start}")
    print(f"Index_v2 asset ID: {active_asset or 'unknown'}")
    print(f"Index asset ID: {legacy_asset or 'unknown'}")
    print(f"Active aerial video ID: {active_video or 'unknown'}")
    print(f"Last applied asset: {state.get('last_applied_asset', 'none')}")
    print(f"Last applied at: {state.get('last_applied_at', 'never')}")
    if missing:
        print(missing_assets_message(missing))
    return 0


def print_missing_assets() -> int:
    config = load_config()
    missing = missing_assets(config)
    if missing:
        print(missing_assets_message(missing))
    return 0


def print_current_missing_assets() -> int:
    config = load_config()
    missing = current_missing_assets(config)
    if missing:
        print(missing_assets_message(missing))
    return 0


def print_missing_assets_json() -> int:
    config = load_config()
    print(json.dumps(missing_assets(config)))
    return 0


def print_current_missing_assets_json() -> int:
    config = load_config()
    print(json.dumps(current_missing_assets(config)))
    return 0


def open_wallpaper_settings() -> int:
    subprocess.run(["open", WALLPAPER_SETTINGS_URL], check=False)
    print("Opened Wallpaper settings.")
    return 0


def set_slot(start: str, asset_key: str) -> int:
    config = load_config()
    if asset_key not in config["assets"]:
        raise ValueError(f"Unknown asset key: {asset_key}")

    minutes = parse_time(start)
    updated = False
    for item in config["schedule"]:
        if item["start"] == start:
            item["asset"] = asset_key
            updated = True
            break

    if not updated:
        config["schedule"].append(
            {
                "start": start,
                "asset": asset_key,
                "period": infer_period_for_minutes(minutes),
            }
        )

    config["schedule"] = [
        {"start": slot.start, "asset": slot.asset_key, "period": slot.period}
        for slot in sorted_slots(config)
    ]
    write_json(CONFIG_PATH, config)
    print(f"Updated {start} to use {asset_key}.")
    return 0


def set_start_time(old_start: str, new_start: str) -> int:
    config = load_config()
    parse_time(new_start)

    updated = False
    for item in config["schedule"]:
        if item["start"] == old_start:
            item["start"] = new_start
            updated = True
            break

    if not updated:
        raise ValueError(f"Unknown schedule start time: {old_start}")

    validate_config(config)
    config["schedule"] = [
        {"start": slot.start, "asset": slot.asset_key, "period": slot.period}
        for slot in sorted_slots(config)
    ]
    write_json(CONFIG_PATH, config)
    print(f"Moved slot {old_start} to start at {new_start}.")
    return 0


def main(argv: list[str]) -> int:
    ensure_default_config()

    if len(argv) < 2:
        print(
            "Usage: scheduler.py [apply|status|show-schedule|list-assets|info-json|"
            "missing-assets|missing-assets-json|current-missing-assets|"
            "current-missing-assets-json|open-wallpaper-settings|"
            "set-slot HH:MM asset_key|set-start-time OLD_HH:MM NEW_HH:MM]"
        )
        return 1

    command = argv[1]
    try:
        if command == "apply":
            return apply_current_schedule()
        if command == "status":
            return print_status()
        if command == "show-schedule":
            return print_schedule()
        if command == "list-assets":
            return print_assets()
        if command == "info-json":
            return print_info_json()
        if command == "missing-assets":
            return print_missing_assets()
        if command == "missing-assets-json":
            return print_missing_assets_json()
        if command == "current-missing-assets":
            return print_current_missing_assets()
        if command == "current-missing-assets-json":
            return print_current_missing_assets_json()
        if command == "open-wallpaper-settings":
            return open_wallpaper_settings()
        if command == "set-slot":
            if len(argv) != 4:
                print("Usage: scheduler.py set-slot HH:MM asset_key")
                return 1
            return set_slot(argv[2], argv[3])
        if command == "set-start-time":
            if len(argv) != 4:
                print("Usage: scheduler.py set-start-time OLD_HH:MM NEW_HH:MM")
                return 1
            return set_start_time(argv[2], argv[3])
        print("Unknown command.")
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
