# Delegated Groups

This project provides a small toolkit for populating and querying a PostgreSQL-backed Delegated Group Management schema for Jira and Confluence. It reads delegated group ownership exported from CSV, normalizes the data into PostgreSQL tables, and offers sample queries for inspecting ownership relationships.

## Repository layout

- **database/psql_models.py** — SQLAlchemy models and engine/session configuration for the PostgreSQL schema. Defines the core tables (`dg_user`, `dg_managed_group`, `dg_group_owner`) and creates them if they do not exist.
- **import/import_delegated_data.py** — CSV import utility that builds unique users, groups, and ownership relationships from delegated ownership exports and persists them via the SQLAlchemy models.
- **services/credentials/tokens.py** — Lightweight helper for retrieving application-specific credentials from S3 (used to fetch the PostgreSQL password).
- **tests/test_queries.py** — Example query helpers that demonstrate how to fetch groups for a user and ownership details for a group using SQLAlchemy Core select statements.

## Database schema

All tables live under the `atlassian-admin.dev` schema configured in `database/psql_models.py`. Relationships are modeled with cascading foreign keys to keep ownership records in sync when users or groups are removed.

### `dg_user`
Represents a unique Jira/Confluence account.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `user_key` | `Text` | Unique, product-agnostic identifier. |
| `username` | `Text` | Display/user name. |
| `email` | `Text` | Optional email address. |
| `lower_username` | `Text` | Lowercase username for case-insensitive lookups. |
| `lower_email` | `Text` | Lowercase email for case-insensitive lookups. |

Relationships: one-to-many with `dg_group_owner` via `DgUser.owners`.

### `dg_managed_group`
Tracks a group whose ownership is delegated.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `app` | `Text` | Required; either `jira` or `confluence`. |
| `group_name` | `Text` | Original group name. |
| `lower_group_name` | `Text` | Lowercase group name for unique constraint. |
| `delegation_id` | `BigInteger` | Identifier from the source system. |

Constraints: unique on (`app`, `lower_group_name`) via `uq_app_group` to avoid duplicate groups per product. Relationship: one-to-many with `dg_group_owner` via `DgManagedGroup.owners`.

### `dg_group_owner`
Join table capturing delegated ownership of managed groups.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `managed_group_id` | `BigInteger` | FK to `dg_managed_group.id`, cascade on delete. |
| `user_id` | `BigInteger` | FK to `dg_user.id`, cascade on delete. |
| `source_type` | `Text` | Ownership type (e.g., `USER_OWNER` or `GROUP_OWNER`). |
| `via_group_name` | `Text` | Populated when ownership is inherited through another group. |
| `created_at` | `DateTime(timezone=True)` | Defaults to `NOW()` on insert. |

Constraints: composite uniqueness (`managed_group_id`, `user_id`, `source_type`, `via_group_name`) enforced by `uq_owner_row` to prevent duplicate ownership records. Relationships back to `dg_managed_group` and `dg_user` keep ownership rows aligned with their parent entities.

## Data import flow

1. Configure credentials: `services/credentials/tokens.AtlassianToken` loads the PostgreSQL password from S3 using bucket `atlassian-bucket` and key `passwords.json`.
2. Establish database engine and create tables: `database/psql_models.py` builds an engine using the fetched credentials, initializes the declarative models, and runs `Base.metadata.create_all` to ensure tables exist.
3. Run the importer: `import/import_delegated_data.py` reads delegated ownership CSVs (`effective_owners_jira.csv`, `effective_owners_conf.csv`), normalizes casing, deduplicates users and groups, inserts them, and then inserts unique ownership rows. A summary of inserted counts is printed upon completion.

## Example queries

`tests/test_queries.py` contains two reusable helpers:
- `get_my_groups(username)` returns each managed group a user owns along with the source type and any intermediary group. Results are ordered by application and group name.
- `get_group_owners(app, group_name)` returns the owners of a specific group, ordered by source type, via-group, and username.

The module can be executed directly for ad hoc inspection:

```bash
python -m tests.test_queries
```

## Getting started

1. Ensure access to the S3 bucket containing the PostgreSQL credentials and verify the connection details in `database/psql_models.py`.
2. Place exported delegated ownership CSVs at the paths expected by `import/import_delegated_data.py`, or adjust `CSV_PATH_JIRA`/`CSV_PATH_CONF` accordingly.
3. Run the importer to populate the database:

```bash
python -m import.import_delegated_data
```

4. Use the query helpers (or SQLAlchemy directly) to explore delegated ownership relationships once the data is loaded.
