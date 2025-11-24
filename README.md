# In-House Delegated Groups Management

This project implements a custom, in-house version of Delegated Group Management for Jira and Confluence by:

- Importing delegated group ownership from SQL Server (Jira/Confluence databases)
- Normalizing and storing the data in PostgreSQL
- Providing helper functions to query:
    - All delegated groups and their owners in both Jira and Confluence
    - Who owns a given delegated group
    - Which groups a user owns

The application supports both Jira and Confluence using a unified schema.

## Project Structure

```
└── delegated-groups/
    ├── database/
    │   ├── __init__.py
    │   ├── psql_models.py      # SQLAlchemy database models for users, groups, and ownership
    │   └── psql_views.py       # SQLAlchemy database model for view
    ├── import/
    │   └── import_delegated_data.py      # Script to import CSV data into the database
    ├── services/
    │   ├── credentials/
    │   │   └── tokens.py      # Credential management for database access
    │   └── __init__.py
    ├── tests/
    │   └── test_queries.py      # Test queries for the database
    ├── __init__.py
    ├── README.md      # This file
    └── requirements.txt
```

## Files and Their Purpose

### 1. `database/psql_models.py`
- Contains SQLAlchemy ORM models for:
  - `DgUser`: Represents a user with identity information
  - `DgManagedGroup`: Tracks a group whose ownership is delegated
  - `DgGroupOwner`: Join table capturing delegated ownership of managed groups
- Sets up the PostgreSQL database connection using credentials from `services/credentials/tokens.py`
- Creates database tables if they don't exist

### 2. `import/import_delegated_data.py`
- Imports delegated group data from CSV files (`effective_owners_jira.csv` and `effective_owners_conf.csv`)
- Processes CSV data to create unique users and groups
- Inserts data into the database using the models from `psql_models.py`
- Tracks ownership relationships between users and groups

### 3. `services/credentials/tokens.py`
- Manages credentials for database access
- Reads credentials from an S3 bucket (`atlassian-bucket`)
- Provides the `AtlassianToken` class for secure credential access

### 4. `tests/test_queries.py`
- Contains test queries to verify database functionality
- Provides example queries:
  - `get_my_groups(username)`: Gets all groups for a specific user
  - `get_group_owners(app, group_name)`: Gets all owners for a specific group

## Database Schema
<details>
<summary><strong>View the Architecture</strong></summary>
<!--All you need is a blank line-->

     +---------------------+
     |       dg_user       |
     |---------------------|
     | id (PK)             |
     | username            |
     | email               |
     | lower_username      |
     | lower_email         |
     +---------▲-----------+
               │ (many ownership rows
               │ reference one user)
               │
     +---------┴-----------+
     |    dg_group_owner   |
     |---------------------|
     | id (PK)             |
     | user_id (FK)        |----> dg_user.id
     | managed_group_id(FK)|----> dg_managed_group.id
     | source_type         |
     | via_group_name      |
     | created_at          |
     +---------▲-----------+
               │
(many owners)  │
               │
     +---------┴-----------+
     |   dg_managed_group  |
     |---------------------|
     | id (PK)             |
     | app                 | ----> 'jira' / 'confluence'
     | group_name          |
     | lower_group_name    |
     +---------------------+

     Read-only View (joins the above)
     +-----------------------------------------------+
     | vw_delegated_group_owners                     |
     |-----------------------------------------------|
     | app                                           |
     | delegated_group                               |
     | delegated_group_lower                         |
     | owner_username                                |
     | owner_email                                   |
     | owner_type (USER_OWNER / GROUP_OWNER)         |
     | via_group_name                                |
     | owner_created_at                              |
     +-----------------------------------------------+


```text
     +---------------------+
     |       dg_user       |
     |---------------------|
     | id (PK)             |
     | username            |
     | email               |
     | lower_username      |
     | lower_email         |
     +---------▲-----------+
               | (many ownership rows
               | reference one user)
               |
     +---------┴-----------+
     |    dg_group_owner   |
     |---------------------|
     | id (PK)             |
     | user_id (FK)        |----> dg_user.id
     | managed_group_id(FK)|----> dg_managed_group.id
     | source_type         |    
     | via_group_name      |    
     | created_at          |    
     +---------▲-----------+    
               |                
(many owners)  |  
               |                
     +---------┴-----------+    
     |   dg_managed_group  |
     |---------------------|
     | id (PK)             |
     | app                 | ----> 'jira' / 'confluence'
     | group_name          |
     | lower_group_name    |
     +---------------------+
```
</details>

### Tables

#### `dg_user`
Represents a unique Jira/Confluence user and their information.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `username` | `Text` | Display/user name. |
| `email` | `Text` | Optional email address. |
| `lower_username` | `Text` | Lowercase username for case-insensitive lookups. |
| `lower_email` | `Text` | Lowercase email for case-insensitive lookups. |

**Relationships:** one-to-many with `dg_group_owner` via `DgUser.owners`

---

#### `dg_managed_group`
Tracks a group whose ownership is delegated.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `app` | `Text` | Required; either `jira` or `confluence`. |
| `group_name` | `Text` | Original group name. |
| `lower_group_name` | `Text` | Lowercase group name for unique constraint. |
| `delegation_id` | `BigInteger` | Identifier from the source system. |

**Constraints:** unique on (`app`, `lower_group_name`) via `uq_app_group` to avoid duplicate groups per product. 

**Relationships:** one-to-many with `dg_group_owner` via `DgManagedGroup.owners`.

---

#### `dg_group_owner`
Join table capturing delegated ownership of managed groups.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | `BigInteger` | Primary key, auto-incrementing. |
| `managed_group_id` | `BigInteger` | FK to `dg_managed_group.id`, cascade on delete. |
| `user_id` | `BigInteger` | FK to `dg_user.id`, cascade on delete. |
| `source_type` | `Text` | Ownership type (e.g., `USER_OWNER` or `GROUP_OWNER`). |
| `via_group_name` | `Text` | Populated when ownership is inherited through another group. |
| `created_at` | `DateTime(timezone=True)` | Defaults to `NOW()` on insert. |

**Constraints:** composite uniqueness (`managed_group_id`, `user_id`, `source_type`, `via_group_name`) enforced by `uq_owner_row` to prevent duplicate ownership records. 

**Relationships:** back to `dg_managed_group` and `dg_user` to keep ownership rows aligned with their parent entities.

---

>>> [!important] General Relationship Information
- A user can own multiple groups (many-to-many relationship)
- Relationships are modeled with cascading foreign keys to keep ownership records in sync when users or groups are removed
>>>
## Example queries

`tests/test_queries.py` contains two reusable helpers:
- `get_my_groups(username)` returns each managed group a user owns along with the source type and any intermediary group. Results are ordered by application and group name.
- `get_group_owners(app, group_name)` returns the owners of a specific group, ordered by source type, via-group, and username.

The module can be executed directly in the **CLI** for ad hoc inspection:

### Command-line Interface

```text
usage: test_queries.py [-h] {my-groups,group-owners} ...

Query delegated groups and their owners from the PostgreSQL DB.

options:
  -h, --help            show this help message and exit

commands:
  {all-owners,my-groups,group-owners}
                        Choose an operation to run
    all-owners          Show all groups and their owners in both applications.              
    my-groups           Show all groups a user is an owner of.
    group-owners        Show owners of a given (app, group) pair.
```

#### Sub-commands

| Command | Description |
| ------- | ----------- |
| `all-owners` | Return all delegated groups and their owners in both Jira and Confluence |
| `my-groups` | Returns groups the supplied username owns in Jira and Confluence |
| `group-owners` | Returns owners for a specific application/group name |


#### `my-groups` options

```text
usage: test_queries.py my-groups -u USERNAME

options:
  -u USERNAME, --username USERNAME
                        The user’s Jira/Confluence username (case‑insensitive).
```


#### `group-owners` options

```text

usage: test_queries.py group-owners -a APP -g GROUP_NAME

options:
  -a APP, --app APP     Application name (e.g. confluence).
  -g GROUP_NAME, --group-name GROUP_NAME
                        Group name within the application.
```

## Getting Started

### 1. Prerequisites

- **Python 3.9+**. Create a virtual environment before installing dependencies
- **Install Dependencies** Install the provided requirements.txt file

```bash
pyenvinstall
source activate <your-pyenv>
pip install -r delegated-groups/requirements.txt  # run from root (ops-utilities)
```

### 2. Set Up Database
- Ensure PostgreSQL is running and accessible
- Update the database connection parameters in `psql_models.py` if needed (dev vs. prod)

### 3. Import Data
- Place CSV files (`effective_owners_jira.csv` and `effective_owners_conf.csv`) in the appropriate location
- Run the import script:
  ```bash
  # run from root (ops-utilities)
  python -m delegated-groups.import.import_delegated_data 
  ```
- This will import the data and create/update database tables

### 4. Run Test Queries
Execute test queries to verify functionality:
<details>
<summary><strong>all-owners</strong></summary>

  ```bash
  # run from root (ops-utilities)
  python -m delegated-groups.tests.test_queries all-owners
  ```
</details>

<details>
<summary><strong>my-groups</strong></summary>

  ```bash
  # run from root (ops-utilities)
  python -m delegated-groups.tests.test_queries my-groups -u USERNAME 
  ```
</details>

<details>
<summary><strong>group-owners</strong></summary>

  ```bash
  # run from root (ops-utilities)
  python -m delegated-groups.tests.test_queries group-owners -a APP -g GROUP_NAME 
  ```
</details>

