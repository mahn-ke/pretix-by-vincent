"""Run with `pretix shell < scripts/migrate_test_dates.py`; dry-run by default."""
import copy
import json
import os
import re
from datetime import date, timedelta


TARGET_START = date(2026, 11, 1)
SOURCE_START = date(2026, 12, 26)
TOUR_SHIFT = TARGET_START - SOURCE_START
MARKER = "hackertours_november_2026_migration"


def rewrite_text(text):
    def dotted(match):
        old = date(2026, 12, int(match.group(1)))
        new = old + TOUR_SHIFT
        year = "2026" if match.group(2) else ""
        return f"{new.day:02d}.{new.month:02d}.{year}"

    text = re.sub(r"\b(26|27|28|29|30)\.12\.(2026)?(?!\d)", dotted, text)
    return re.sub(
        r"2026-12-(26|27|28|29|30)",
        lambda match: (date(2026, 12, int(match.group(1))) + TOUR_SHIFT).isoformat(),
        text,
    )


def localized(value):
    return {language: rewrite_text(text) for language, text in value.items()}


def shift_wall_time(value, delta, timezone):
    return (value.astimezone(timezone) + delta) if value is not None else None


def migrate_schedule(document):
    result = copy.deepcopy(document)
    conference = result["schedule"]["conference"]
    days = []
    for day in conference["days"]:
        old_date = date.fromisoformat(day["date"])
        target = old_date + TOUR_SHIFT
        if target > date(2026, 11, 4):
            if any(day["rooms"].values()):
                raise ValueError("Unexpected tours outside confirmed Days 0-3")
            continue
        day["date"] = target.isoformat()
        for entries in day["rooms"].values():
            for entry in entries:
                for key in ("date", "start", "end"):
                    if isinstance(entry.get(key), str):
                        entry[key] = rewrite_text(entry[key])
        days.append(day)
    conference["days"] = days
    conference["start"] = "2026-11-01"
    conference["end"] = "2026-11-04"
    conference["daysCount"] = 4
    return result


def migrate():
    from django.db import transaction
    from django_scopes import scopes_disabled
    from pretix.base.models import Event

    apply = os.environ.get("PRETIX_MIGRATION_APPLY") == "1"
    changes = {"categories": 0, "items": 0, "date_windows": 0}
    with scopes_disabled(), transaction.atomic():
        event = Event.objects.select_for_update().get(
            organizer__slug="hackertours", slug="39c3ht"
        )
        if not event.testmode:
            raise ValueError("Refusing to migrate a non-test event")
        timezone = event.timezone
        if event.settings.get(MARKER, default=False, as_type=bool):
            if event.date_from.astimezone(timezone).date() != TARGET_START:
                raise ValueError("Migration marker and event bounds disagree")
            print("November migration already applied; no changes.")
            return
        if event.date_from.astimezone(timezone).date() != date(2026, 12, 27):
            raise ValueError("Unexpected source event start; inspect before migration")
        if event.date_to.astimezone(timezone).date() != date(2026, 12, 30):
            raise ValueError("Unexpected source event end; inspect before migration")
        categories = list(event.categories.select_for_update())
        if len(categories) != 4 or event.subevents.exists():
            raise ValueError("Unexpected event/category structure")
        seen_days = set()
        for category in categories:
            names = category.name.data
            match = re.fullmatch(r"Day ([0-3])", names.get("en", ""))
            if not match:
                raise ValueError(f"Unexpected category {category.pk}")
            day = int(match.group(1))
            seen_days.add(day)
            source_date = SOURCE_START + timedelta(days=day)
            for text in category.description.data.values():
                if source_date.strftime("%d.%m.%Y") not in text:
                    raise ValueError(f"Unexpected source category date {category.pk}")
            category.description = localized(category.description.data)
            category.save(update_fields=["description"])
            changes["categories"] += 1
        if seen_days != set(range(4)):
            raise ValueError("Missing or repeated day category")
        for item in event.items.select_for_update(of=("self",)):
            fields = []
            description = localized(item.description.data)
            if description != item.description.data:
                item.description = description
                fields.append("description")
            for field in (
                "available_from", "available_until",
                "validity_fixed_from", "validity_fixed_until",
            ):
                value = getattr(item, field)
                if value is not None:
                    if value.astimezone(timezone).year != 2026:
                        raise ValueError(f"Unexpected item date window {item.pk}.{field}")
                    setattr(item, field, shift_wall_time(value, TOUR_SHIFT, timezone))
                    fields.append(field)
                    changes["date_windows"] += 1
            if fields:
                item.save(update_fields=fields)
                changes["items"] += 1
        event_shift = TARGET_START - date(2026, 12, 27)
        event_fields = []
        for field in ("date_from", "date_to", "date_admission", "presale_start", "presale_end"):
            value = getattr(event, field)
            if value is not None:
                setattr(event, field, shift_wall_time(value, event_shift, timezone))
                event_fields.append(field)
        event.save(update_fields=event_fields)
        banner = event.settings.get("banner_text")
        event.settings.set("banner_text", {
            language: text.replace("LOCAL TEST ONLY", "PUBLIC TEST ONLY")
            .replace("NUR LOKALER TEST", "NUR TESTBETRIEB")
            for language, text in banner.data.items()
        })
        event.settings.set(MARKER, True)
        event.cache.clear()
        if not apply:
            transaction.set_rollback(True)
        print(json.dumps({"applied": apply, **changes}, sort_keys=True))


if __name__ in ("__main__", "django.core.management.commands.shell"):
    migrate()
