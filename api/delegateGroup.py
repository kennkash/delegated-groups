@router.post("/groups/bulk")
async def add_managed_groups(
    req: AddGroupsRequest,
    db: Session = Depends(get_db),
):
    """
    add_managed_groups inserts one or more delegated groups into dg_managed_group
    without requiring any owners.

    Returns per-group status so the UI can show toasts like:
    "{group} is already a delegated group".
    """
    app = req.app.lower().strip()
    if app not in {"jira", "confluence"}:
        raise HTTPException(status_code=400, detail="app must be 'jira' or 'confluence'")

    results = []

    # Normalize group names
    cleaned = [g.strip() for g in req.groups if g and g.strip()]
    if not cleaned:
        raise HTTPException(status_code=400, detail="No valid group names provided")

    lower_names = [g.lower() for g in cleaned]

    existing = (
        db.query(DgManagedGroup.lower_group_name)
        .filter(DgManagedGroup.app == app)
        .filter(DgManagedGroup.lower_group_name.in_(lower_names))
        .all()
    )
    existing_set = {row[0] for row in existing}

    for group in cleaned:
        lower_group = group.lower()

        if lower_group in existing_set:
            results.append(
                {
                    "group": group,
                    "status": "exists",
                    "message": f"{group} is already a delegated group",
                }
            )
            continue

        db.add(
            DgManagedGroup(
                app=app,
                group_name=group,
                lower_group_name=lower_group,
            )
        )

        existing_set.add(lower_group)
        results.append(
            {
                "group": group,
                "status": "created",
                "message": f"{group} added as a delegated group",
            }
        )

    db.commit()

    return {
        "app": app,
        "results": results,
    }