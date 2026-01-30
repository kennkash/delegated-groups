@router.delete("/groups")
async def delete_delegated_group(
    req: DeleteGroupRequest,
    db: Session = Depends(get_db),
):
    """
    delete_delegated_group removes a delegated group from the owners database.

    <details><summary><span>Parameters</span></summary>
    | Name | Type | Description |
    |------|------|-------------|
    | `app` | `str` | `jira` or `confluence` |
    | `group_name` | `str` | Delegated group name (supports special characters like `/`) |
    </details>

    <details><summary><span>Returns</span></summary>
    * `app`
    * `group_name`
    * `managed_group_id`
    * `deleted_owner_rows`
    * `deleted_group_owner_rules`
    </details>
    """
    app = req.app.lower()
    if app not in {"jira", "confluence"}:
        raise HTTPException(status_code=400, detail="Invalid app")

    managed_group = (
        db.query(DgManagedGroup)
        .filter(DgManagedGroup.app == app)
        .filter(DgManagedGroup.lower_group_name == req.group_name.lower())
        .one_or_none()
    )
    if not managed_group:
        raise HTTPException(status_code=404, detail="Delegated group not found")

    managed_group_id = managed_group.id

    deleted_owner_rows = (
        db.query(DgGroupOwner)
        .filter(DgGroupOwner.managed_group_id == managed_group_id)
        .delete(synchronize_session=False)
    )

    deleted_group_owner_rules = (
        db.query(DgGroupOwnerGroup)
        .filter(DgGroupOwnerGroup.managed_group_id == managed_group_id)
        .delete(synchronize_session=False)
    )

    db.delete(managed_group)
    db.commit()

    return {
        "app": app,
        "group_name": managed_group.group_name,
        "managed_group_id": managed_group_id,
        "deleted_owner_rows": deleted_owner_rows,
        "deleted_group_owner_rules": deleted_group_owner_rules,
    }
    
from pydantic import BaseModel

class DeleteGroupRequest(BaseModel):
    app: str
    group_name: str