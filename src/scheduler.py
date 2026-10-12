#!/usr/bin/env python3

import json
import fcntl
import os
import plistlib
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(
    os.environ.get(
        "TAHOE_AERIAL_APP_DIR",
        str(Path.home() / "Library" / "Application Support" / "TahoeAerialScheduler"),
    )
)
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOG_PATH = APP_DIR / "scheduler.log"
MENU_LOG_PATH = APP_DIR / "menu-ui.log"
LOG_MAX_BYTES = 512 * 1024
LOG_BACKUPS = 3
RECOVERY_COOLDOWN_SECONDS = 300
VERIFY_TIMEOUT_SECONDS = 8
COMMAND_TIMEOUT_SECONDS = 3
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


def app_version() -> str:
    source_dir = Path(__file__).resolve().parent
    for path in (source_dir / "VERSION", source_dir.parent / "VERSION"):
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    return "unknown"

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


def atomic_write(path: Path, payload: bytes) -> None:
    # A failed/partial write must leave the previous settings intact. Use the
    # same directory so replacement is atomic on the destination filesystem.
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


@contextmanager
def scheduler_lock():
    ensure_app_dir()
    with (APP_DIR / "scheduler.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def rotate_log(path: Path) -> None:
    if not path.exists() or path.stat().st_size < LOG_MAX_BYTES:
        return
    for index in range(LOG_BACKUPS, 0, -1):
        destination = path.with_name(f"{path.name}.{index}")
        source = path if index == 1 else path.with_name(f"{path.name}.{index - 1}")
        if source.exists():
            os.replace(source, destination)
            if destination.stat().st_size > LOG_MAX_BYTES:
                with destination.open("rb") as handle:
                    handle.seek(-LOG_MAX_BYTES, os.SEEK_END)
                    tail = handle.read()
                boundary = tail.find(b"\n")
                atomic_write(destination, tail[boundary + 1:] if boundary >= 0 else tail)


def log_event(message: str, path: Path | None = None) -> None:
    ensure_app_dir()
    path = path or LOG_PATH
    rotate_log(path)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    message = str(message).replace("\n", " ").replace("\r", " ")[:2000]
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{app_version()}] {message}\n")


def write_json(path: Path, payload: dict) -> None:
    ensure_app_dir()
    atomic_write(path, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))


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
    if not isinstance(assets, dict) or not isinstance(config["schedule"], list):
        raise ValueError("Assets must be an object and schedule must be a list.")
    if not config["schedule"]:
        raise ValueError("The schedule must contain at least one time block.")
    for key, asset in assets.items():
        if not isinstance(asset, dict) or not all(
            isinstance(asset.get(field), str) and asset[field]
            for field in ("label", "asset_id")
        ):
            raise ValueError(f"Asset {key} must have a label and asset_id.")
        if Path(asset["asset_id"]).name != asset["asset_id"]:
            raise ValueError(f"Invalid asset ID for {key}.")
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


def asset_is_downloaded(asset_id: str) -> bool:
    try:
        path = asset_video_path(asset_id)
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def missing_asset_entry(config: dict, asset_key: str) -> dict | None:
    asset = asset_from_key(config, asset_key)
    video_path = asset_video_path(asset["asset_id"])
    if asset_is_downloaded(asset["asset_id"]):
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
    if asset_is_downloaded(asset["asset_id"]):
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
    try:
        payload = plistlib.loads(configuration)
    except (ValueError, TypeError, plistlib.InvalidFileException):
        return None
    if not isinstance(payload, dict):
        return None
    return payload.get("assetID")


def desktop_asset_id(store: dict) -> str | None:
    section = store.get("AllSpacesAndDisplays", {})
    for key in ("Desktop", "Linked"):
        choices = section.get(key, {}).get("Content", {}).get("Choices", [])
        if choices:
            return decode_asset_id(choices[0])
    return None


def current_asset_id() -> str | None:
    try:
        return desktop_asset_id(load_plist(LIVE_PLIST))
    except Exception:
        return None


def desktop_choices_match(store: dict, asset_id: str) -> bool:
    ids = []

    def visit(section):
        if not isinstance(section, dict):
            return
        for key, value in section.items():
            if key in ("Desktop", "Linked") and isinstance(value, dict):
                choices = value.get("Content", {}).get("Choices", [])
                if choices:
                    ids.extend(decode_asset_id(choice) for choice in choices)
            elif isinstance(value, dict):
                visit(value)

    for key in ("AllSpacesAndDisplays", "Displays", "Spaces"):
        visit(store.get(key))
    return bool(ids) and all(value == asset_id for value in ids)


def desktop_store_matches(asset_id: str) -> bool:
    try:
        return desktop_choices_match(load_plist(LIVE_PLIST), asset_id)
    except (OSError, ValueError, TypeError, plistlib.InvalidFileException):
        return False


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

    if has_managed_choice and all(choice.get("Provider") == AERIAL_PROVIDER for choice in choices):
        if len(choices) > 1:
            content["Choices"] = choices[:1]
            changed = True
        if content.get("Shuffle") not in (None, "$null"):
            content["Shuffle"] = "$null"
            changed = True

    if has_managed_choice and "EncodedOptionValues" in content:
        content.pop("EncodedOptionValues", None)
        changed = True

    if changed:
        # Binary property-list dates are UTC, even when plistlib returns them
        # without a timezone. Never store local wall-clock time as UTC.
        timestamp = applied_at.astimezone(timezone.utc).replace(tzinfo=None)
        container["LastSet"] = timestamp
        container["LastUse"] = timestamp
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

    atomic_write(path, plistlib.dumps(store, fmt=plistlib.FMT_BINARY, sort_keys=False))
    return True


def write_store(asset_id: str, applied_at: datetime | None = None) -> bool:
    applied_at = applied_at or datetime.now()
    updated_any = False
    # Validate the live shape before writing either file. A legacy-only update
    # must never count as a successful desktop repair.
    if not LIVE_PLIST.exists():
        raise RuntimeError("The native desktop wallpaper store is missing. Open Wallpaper settings and select a Tahoe Aerial once.")
    live_store = load_plist(LIVE_PLIST)
    update_store_sections(live_store, asset_id, applied_at, allow_provider_conversion=True)
    if not desktop_choices_match(live_store, asset_id):
        raise RuntimeError("The active wallpaper format is not supported. Open Wallpaper settings and select a Tahoe Aerial once.")
    updated_any = write_updated_plist(
        LIVE_PLIST, asset_id, applied_at, allow_provider_conversion=True
    ) or updated_any
    updated_any = (
        write_updated_plist(
            LEGACY_PLIST,
            asset_id,
            applied_at,
            allow_provider_conversion=True,
        )
        or updated_any
    )
    # Already-correct settings are valid: a stuck player still needs a restart.
    return updated_any


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
            if last_set.tzinfo is None:
                last_set = last_set.replace(tzinfo=timezone.utc)
            return last_set.astimezone().replace(tzinfo=None)
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
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
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


@dataclass(frozen=True)
class Playback:
    asset_ids: tuple[str, ...] = ()
    available: bool = True
    reason: str = ""


def observe_playback() -> Playback:
    try:
        pgrep_result = subprocess.run(
            ["/usr/bin/pgrep", "-x", "-U", str(os.getuid()), AERIAL_EXTENSION_PROCESS],
            capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        if pgrep_result.returncode == 1:
            return Playback(reason="The wallpaper player is not running.")
        if pgrep_result.returncode != 0:
            return Playback(available=False, reason="The wallpaper player could not be inspected.")
        ids = []
        for pid in pgrep_result.stdout.split():
            result = subprocess.run(
                ["/usr/sbin/lsof", "-Fn", "-p", pid],
                capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT_SECONDS,
            )
            if result.returncode != 0:
                return Playback(available=False, reason="The playing wallpaper files could not be inspected.")
            for line in result.stdout.splitlines():
                asset_id = asset_id_from_video_path(line[1:]) if line.startswith("n") else None
                if asset_id and asset_id not in ids:
                    ids.append(asset_id)
        return Playback(tuple(ids), reason="" if ids else "The wallpaper player has no visible video file.")
    except (OSError, subprocess.TimeoutExpired):
        return Playback(available=False, reason="Wallpaper playback inspection failed or timed out.")


def active_aerial_video_id() -> str | None:
    playback = observe_playback()
    return playback.asset_ids[0] if len(playback.asset_ids) == 1 else None


def playing_label(config: dict, playback: Playback) -> str | None:
    if not playback.asset_ids:
        return None
    if len(playback.asset_ids) > 1:
        return "Multiple Aerial clips"
    asset_id = playback.asset_ids[0]
    for asset in config["assets"].values():
        if asset["asset_id"] == asset_id:
            return asset["label"]
    try:
        manifest = json.loads((AERIAL_VIDEOS_DIR.parent / "manifest" / "entries.json").read_text())
        for asset in manifest.get("assets", []):
            if asset.get("id") == asset_id:
                golden_gate = {
                    "GG_A_DAY": "Golden Gate Day", "GG_A_EVENING": "Golden Gate Evening",
                    "GG_A_NIGHT": "Golden Gate Night", "GG_A_SUNSET": "Golden Gate Sunset",
                }
                label = golden_gate.get(asset.get("shotID")) or asset.get("accessibilityLabel")
                return label if label and "_" not in label else "Another Aerial clip"
    except (OSError, ValueError):
        pass
    return "Another Aerial clip"


def playback_status(desired_asset_id: str, playback: Playback, store_matches: bool) -> str:
    if not store_matches:
        return "mismatch"
    if not playback.available or not playback.asset_ids:
        return "unverified"
    return "verified" if playback.asset_ids == (desired_asset_id,) else "mismatch"


def restart_wallpaper_agent() -> None:
    # Stop the old extension first, so the new agent cannot connect to a player
    # that we kill immediately afterward (which causes connection failures).
    subprocess.run(
        ["/usr/bin/killall", AERIAL_EXTENSION_PROCESS],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False, timeout=COMMAND_TIMEOUT_SECONDS,
    )
    result = subprocess.run(
        ["/bin/launchctl", "kickstart", "-k", WALLPAPER_AGENT_LABEL],
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        fallback = subprocess.run(
            ["/usr/bin/killall", "WallpaperAgent"],
            capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT_SECONDS,
        )
        if fallback.returncode != 0:
            raise RuntimeError("macOS did not allow the wallpaper renderer to restart.")


def verify_playback(asset_id: str) -> tuple[Playback, bool]:
    deadline = time.monotonic() + VERIFY_TIMEOUT_SECONDS
    while True:
        playback = observe_playback()
        store_matches = desktop_store_matches(asset_id)
        if playback_status(asset_id, playback, store_matches) == "verified":
            return playback, store_matches
        if not playback.available or time.monotonic() >= deadline:
            return playback, store_matches
        time.sleep(0.5)


def read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return state if isinstance(state, dict) else {}
    except json.JSONDecodeError:
        return {}


def write_state(payload: dict) -> None:
    write_json(STATE_PATH, payload)


def save_health(state: dict, status: str, error: str | None = None) -> None:
    previous = read_state()
    updated = dict(state, health=status, last_error=error, version=app_version())
    if updated != previous:
        if status != previous.get("health") or error != previous.get("last_error"):
            updated["last_status_change_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_state(updated)
        if error and error != previous.get("last_error"):
            log_event(error)


def recovery_attempt_is_recent(state: dict, asset_id: str, current: datetime) -> bool:
    if state.get("health") == "verified":
        return False
    if state.get("last_attempt_asset_id") != asset_id:
        return False
    attempted_at = parse_state_timestamp(state.get("last_attempt_at"))
    return attempted_at is not None and 0 <= (current - attempted_at).total_seconds() < RECOVERY_COOLDOWN_SECONDS


def apply_current_schedule(force: bool = False, quiet: bool = False) -> int:
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
    playback = observe_playback()
    store_matches = desktop_store_matches(desired_asset_id)
    status = playback_status(desired_asset_id, playback, store_matches)
    if (
        status == "verified"
        and (not active_is_stale or stale_refresh_already_done)
    ):
        # Keep application times honest and avoid rewriting state every minute.
        if (state.get("last_verified_asset_id") != desired_asset_id
                or state.get("health") != "verified" or state.get("version") != app_version()):
            state.update(last_verified_asset_id=desired_asset_id,
                         last_verified_at=current.astimezone().isoformat(timespec="seconds"))
            save_health(state, "verified")
            log_event(f"Verified {asset['label']} is playing.")
        if not quiet:
            print(f"Already playing: {asset['label']} ({slot.asset_key})")
        return 0

    if not force and store_matches and not playback.available and (not active_is_stale or stale_refresh_already_done):
        save_health(state, "unverified", playback.reason)
        if not quiet:
            print("Wallpaper settings match the schedule; playback could not be verified.")
        return 0

    if not force and recovery_attempt_is_recent(state, desired_asset_id, current):
        save_health(state, status, state.get("last_error") or "Waiting before retrying wallpaper recovery.")
        if not quiet:
            print("Waiting before retrying wallpaper recovery.")
        return 1 if status == "mismatch" else 0

    state.update(last_attempt_asset_id=desired_asset_id,
                 last_attempt_at=current.astimezone().isoformat(timespec="seconds"))
    write_state(state)
    observed = playing_label(config, playback) or playback.reason or "unknown playback"
    log_event(f"Restoring {asset['label']} for the {slot.start} block; observed {observed}.")
    write_store(desired_asset_id, current)
    restart_wallpaper_agent()
    playback, store_matches = verify_playback(desired_asset_id)
    status = playback_status(desired_asset_id, playback, store_matches)
    if status == "mismatch":
        raise RuntimeError(f"Wallpaper recovery is not yet confirmed; observed {playing_label(config, playback) or 'different wallpaper settings'}.")
    if status == "unverified":
        save_health(state, status, playback.reason)
        if not quiet:
            print("Wallpaper settings restored; playback is not yet verified.")
        return 0
    state.update(last_applied_asset=slot.asset_key, last_applied_asset_id=desired_asset_id,
                 last_applied_at=datetime.now().astimezone().isoformat(timespec="seconds"),
                 last_verified_asset_id=desired_asset_id,
                 last_verified_at=datetime.now().astimezone().isoformat(timespec="seconds"))
    save_health(state, "verified")
    action = "Refreshed" if active_asset_id == desired_asset_id else "Applied"
    message = f"{action} and verified {asset['label']} ({slot.asset_key}) for schedule starting {slot.start}."
    log_event(message)
    if not quiet:
        print(message)
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


def build_info() -> dict:
    config = load_config()
    current = datetime.now()
    slot = slot_for_now(config, current)
    following = next_slot(config, slot)
    state = read_state()
    missing = missing_assets(config)
    current_missing = current_missing_assets(config, current)
    playback = observe_playback()
    desired_asset_id = asset_from_key(config, slot.asset_key)["asset_id"]
    store_matches = desktop_store_matches(desired_asset_id)
    status = "missing_download" if current_missing else playback_status(desired_asset_id, playback, store_matches)

    payload = {
        "version": app_version(),
        "current_time": current.astimezone().isoformat(timespec="seconds"),
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
        "active_aerial_video_id": playback.asset_ids[0] if len(playback.asset_ids) == 1 else None,
        "playback": {
            "status": status,
            "label": playing_label(config, playback),
            "asset_ids": list(playback.asset_ids),
            "store_matches": store_matches,
            "reason": playback.reason or None,
        },
        "last_attempt_at": state.get("last_attempt_at"),
        "last_verified_at": state.get("last_verified_at"),
        "last_error": state.get("last_error"),
        "last_applied_asset": state.get("last_applied_asset"),
        "last_applied_at": state.get("last_applied_at"),
    }
    return payload


def print_info_json() -> int:
    print(json.dumps(build_info()))
    return 0


def print_status() -> int:
    info = build_info()

    print(f"Config: {CONFIG_PATH}")
    print(f"Version: {info['version']}")
    print(f"Current time: {info['current_time']}")
    print(f"Scheduled asset now: {info['current_slot']['label']} ({info['current_slot']['asset_key']})")
    print(f"Scheduled start: {info['current_slot']['start']}")
    print(f"Playing: {info['playback']['label'] or 'not yet verified'}")
    print(f"Playback status: {info['playback']['status']}")
    print(f"Index_v2 asset ID: {info['index_v2_asset_id'] or 'unknown'}")
    print(f"Index asset ID: {info['index_asset_id'] or 'unknown'}")
    print(f"Active aerial video ID: {info['active_aerial_video_id'] or 'unknown'}")
    print(f"Last applied asset: {info['last_applied_asset'] or 'none'}")
    print(f"Last applied at: {info['last_applied_at'] or 'never'}")
    if info['playback']['reason']:
        print(info['playback']['reason'])
    if info['last_error']:
        print(f"Last recovery error: {info['last_error']}")
    if info['missing_assets']:
        print(missing_assets_message(info['missing_assets']))
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
    validate_config(config)
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


def run_cli(argv: list[str]) -> int:
    ensure_default_config()

    if len(argv) < 2:
        print(
            "Usage: scheduler.py [apply [--quiet]|repair|status|show-schedule|list-assets|info-json|"
            "missing-assets|missing-assets-json|current-missing-assets|"
            "current-missing-assets-json|open-wallpaper-settings|"
            "set-slot HH:MM asset_key|set-start-time OLD_HH:MM NEW_HH:MM]"
        )
        return 1

    command = argv[1]
    if command == "apply":
        if argv[2:] not in ([], ["--quiet"]):
            raise ValueError("Usage: scheduler.py apply [--quiet]")
        return apply_current_schedule(quiet="--quiet" in argv)
    if command == "repair":
        return apply_current_schedule(force=True)
    if command == "log-menu" and len(argv) == 3:
        log_event(argv[2], MENU_LOG_PATH)
        return 0
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


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    try:
        if command in ("apply", "repair", "set-slot", "set-start-time", "log-menu"):
            with scheduler_lock():
                for name in ("scheduler-launch.log", "menu-launch.log", "menu-ui.log", "scheduler.log"):
                    rotate_log(APP_DIR / name)
                return run_cli(argv)
        return run_cli(argv)
    except Exception as exc:
        try:
            with scheduler_lock():
                save_health(read_state(), "error", str(exc))
        except OSError:
            pass
        if "--quiet" not in argv:
            print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
