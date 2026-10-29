"""Provision private access on the restored TEST MODE instance, never on source."""
import json
import os
from pathlib import Path

from django.db import transaction
from django_scopes import scopes_disabled
from pretix.base.models import Event, Team, TeamAPIToken, User


credentials = json.loads(Path(os.environ["PRETIX_PROVISION_FILE"]).read_text())
with scopes_disabled(), transaction.atomic():
    event = Event.objects.select_for_update().get(
        organizer__slug="hackertours", slug="39c3ht"
    )
    if not event.testmode:
        raise ValueError("Refusing to provision test credentials on a live event")
    team, _ = Team.objects.get_or_create(
        organizer=event.organizer, name="Private console readers"
    )
    team.all_events = False
    team.all_event_permissions = False
    team.all_organizer_permissions = False
    team.limit_event_permissions = {}
    team.limit_organizer_permissions = {}
    team.save()
    team.limit_events.set([event])
    token, _ = TeamAPIToken.objects.get_or_create(
        team=team, name="Private consoles",
        defaults={"token": credentials["console_token"]},
    )
    if token.token != credentials["console_token"] or not token.active:
        raise ValueError("Existing console token differs; rotate it explicitly")
    TeamAPIToken.objects.filter(team__organizer=event.organizer).exclude(
        pk=token.pk
    ).update(active=False)
    admin = User.objects.get(email="admin@local.test", is_staff=True, is_active=True)
    if not admin.check_password(credentials["admin_password"]):
        admin.set_password(credentials["admin_password"])
        admin.save(update_fields=["password"])
print("Private event-read token provisioned; source import tokens revoked and administrator password rotated.")
