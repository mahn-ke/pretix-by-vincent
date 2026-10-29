# pretix.by.vincent.mahn.ke

Hosts the container serving [pretix.by.vincent.mahn.ke](https://pretix.by.vincent.mahn.ke).

## Public testing shop

The [Hackertours shop](https://pretix.by.vincent.mahn.ke/hackertours/39c3ht/)
is a **TEST MODE** copy of the complete local testing instance, not a real
ticket sale. Day 0 is November 1, 2026; Days 1-3 are November 2-4.
Times remain local to Europe/Berlin. Organizer/event slugs remain unchanged.

The migration preserves all 39 products, four categories, 38 quotas, four
questions, 18 existing orders, 14 existing cart positions and the matching
media/private documents. Carts may subsequently expire normally. Prices,
active flags and purchase restrictions are unchanged. Three preregistration
products retain their relative sales cutoff, now October 23 at 23:59 local
time, and are no longer listed after that cutoff. Together with the already
inactive product, this leaves 35 publicly listed products, including donations.

Mail is captured by Mailpit; no email is delivered externally. Bank-transfer
instructions are fictional and must not be used to send money. Only the gateway
has an external network; Pretix, PostgreSQL, Redis and Mailpit use an internal
Docker network. Mailpit, PostgreSQL and Redis have no published ports.
The host's existing HTTPS nginx forwards to `127.0.0.1:8081`.

All container images are pinned to the source instance's immutable digests,
including Pretix 2026.8.0 and PostgreSQL 17. This migration does not install
the historical congressschedule plugin or perform a PostgreSQL major upgrade.
The active runtime files are
[`public-test.cfg`](docker/pretix/public-test.cfg),
[`public-gateway.conf`](docker/pretix/public-gateway.conf) and
[`pretixtask.conf`](docker/pretix/pretixtask.conf).
The older custom Dockerfile/configuration is not used by this Compose stack.

## Operations

The database password must be supplied as `PRETIX_DB_PASSWORD`, privately.
The application receives it as `PRETIX_DATABASE_PASSWORD`; no real password is
stored in the checked-in configuration. A future Actions deployment can use
a repository secret named `PRETIX_DB_PASSWORD`.

For manual deployment on the Windows host, the protected runtime credential
file is outside the checkout, under `C:\Users\vm\pretix-runtime\`. Run:

```powershell
.\scripts\Deploy-TestInstance.ps1
docker compose ps
docker compose logs --tail 50 app gateway
```

The script loads the private database password and uses already provisioned
images. All services restart automatically with Docker. The initial manual
deployment uses the persistent `C:\Users\vm\pretix-public-code` directory.
Repository Actions were disabled at migration time; they are not required
for this running stack and were not enabled as a side effect.

The four external volumes must already be restored/provisioned:

- `pretix_public_2026_database`
- `pretix_public_2026_data`
- `pretix_public_2026_redis`
- `pretix_public_2026_mail`

Missing volumes fail startup rather than silently serving an empty database.
Do not delete these volumes or run destructive restore operations. The old
`pretix_postgres_data` and `pretix_pretix_data` volumes are retained untouched:
they contain unrelated historical test events and were not merged or replaced.
Their isolated preflight database clone is separate from the public service.

## Migration and rollback

Migration backups are private; never commit dumps, `/data/.secret`, captured
mail, private documents, credential files or credential-bearing console builds.
Take a PostgreSQL logical dump while application/worker writes are frozen,
alongside matching `/data`, mail and Redis snapshots. A live filesystem copy
of a PostgreSQL volume alone is not a consistent logical backup.

The original source exports disagree with the event bounds by one day.
[`migrate_test_dates.py`](scripts/migrate_test_dates.py) explicitly maps
category Day 0 to November 1 and Days 1-3 to November 2-4, changes localized
tour dates and shifts item sales/validity windows relative to the tour dates.
Event bounds are normalized separately. It does not rewrite order, payment
or audit timestamps, extend carts, or reset quotas. It requires TEST MODE,
expected source dates and four categories; a persisted marker makes reruns
a no-op. Use it through `pretix shell` on an isolated restored database first:

```sh
python3 -m unittest discover -s scripts -p 'test_migrate_test_dates.py'
docker compose run --rm --no-deps -T -e AUTOMIGRATE=skip app shell < scripts/migrate_test_dates.py
docker compose run --rm --no-deps -T -e AUTOMIGRATE=skip -e PRETIX_MIGRATION_APPLY=1 app shell < scripts/migrate_test_dates.py
```

[`provision_test_access.py`](scripts/provision_test_access.py) runs only against
the restored test event, using `PRETIX_PROVISION_FILE` to locate protected
generated credentials. It creates an event-limited, read-only console team,
revokes the copied privileged import token and rotates the administrator
password. Console tokens cannot read orders or write event settings.
Copied sessions/cache are invalidated when changing origin.

Before cutover, compare exact table counts and hashes of order/position/answer/
payment/refund/invoice/cart/voucher/audit rows against the frozen source.
Verify media archives, both widget languages, category dates, trusted HTTPS,
private-document restrictions, captured email and read-only authorization.
The source Mac instance remains available as a stopped rollback copy, not a
second writable authority. The normalized supplementary schedule is stored
alongside the original source exports as `schedule-november-2026.json`.

For rollback, stop new writers and preserve any post-cutover orders before
switching database/media snapshots or routing. Keep source and historical
destination volumes intact; do not overwrite either as a rollback shortcut.

## Verification on 2026-10-29

- Public storefront and both widget languages return HTTP 200 over trusted
  HTTPS. All 35 currently listed product images match their source SHA-256.
- All 155 database table counts were checked after restore, accounting only
  for the migration marker, restricted access rows and password history.
  Nine order/payment/answer/cart/invoice/voucher/audit tables matched source
  row hashes exactly before cutover.
- The private console token can read the event and quotas, but receives
  HTTP 403 for order reads and event-setting writes.
- Simulated free and EUR 21 paid checkout passed using the deployed API.
  No new orders, reservations or email were created; all 18 orders remain.
- Both console builds and focused configuration/parser tests passed.
  Both retained shared-highscore OAuth clients authenticated successfully.
- Emulator integration remains **unverified**: the isolated Azahar launch
  produced no app log, the established screenshot harness timed out, and
  Xenia stopped progressing during XUI initialization. These are not evidence
  of a successful console run. Final artifacts were rebuilt without the
  temporary harness. Real-console network/checkout testing is still needed.