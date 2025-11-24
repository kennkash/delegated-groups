from sqlalchemy import text
from .database import psql_models as models  # adjust import if needed

SQL = """
GRANT USAGE ON SCHEMA "atlassian-admin.dev" TO "atlassian_admin.dev";

GRANT ALL PRIVILEGES
ON TABLE
    "atlassian-admin.dev".dg_user,
    "atlassian-admin.dev".dg_managed_group,
    "atlassian-admin.dev".dg_group_owner
TO "atlassian_admin.dev";

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA "atlassian-admin.dev"
TO "atlassian_admin.dev";

GRANT SELECT
ON "atlassian-admin.dev".vw_delegated_group_owners
TO "atlassian_admin.dev";


ALTER DEFAULT PRIVILEGES IN SCHEMA "atlassian-admin.dev"
GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLES TO "atlassian_admin.dev";

ALTER DEFAULT PRIVILEGES IN SCHEMA "atlassian-admin.dev"
GRANT USAGE, SELECT
ON SEQUENCES TO "atlassian_admin.dev";
"""

with models.engine.begin() as conn:
    conn.execute(text(SQL))