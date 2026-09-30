from sf_lib import metadata


def qualified_table(ctx: dict, table_name: str) -> str:
    return f'"{ctx["database"]}"."{ctx["schema"]}"."{table_name}"'


def build_dataset_catalog(session, ctx: dict, domains: list[dict]) -> str:
    """Render the caller's own populated domain tables, their live columns,
    and known cross-domain relationships as compact text the LLM can ground
    SQL generation in. `domains` is always scoped to the caller's own schema
    already, by construction (RBAC) — from metadata.list_ready_domains().
    """
    if not domains:
        return "The user has no data loaded yet."

    relationships = metadata.list_relationships(session, ctx)
    lines: list[str] = []
    for d in domains:
        table_ref = qualified_table(ctx, d["TABLE_NAME"])
        lines.append(f"\nTable {table_ref}  (agent={d['AGENT_KEY']}, rows={d['ROW_COUNT']})")

        for col in metadata.get_existing_table_columns(session, ctx, d["TABLE_NAME"]):
            lines.append(f'  - "{col["name"]}" {col["type"]}')

        for rel in relationships:
            if rel["SOURCE_AGENT_KEY"] != d["AGENT_KEY"]:
                continue
            target = next((o for o in domains if o["AGENT_KEY"] == rel["TARGET_AGENT_KEY"]), None)
            if target:
                target_ref = qualified_table(ctx, target["TABLE_NAME"])
                lines.append(
                    f'  relationship: {table_ref}."{rel["SOURCE_COLUMN"]}" -> {target_ref}."{rel["TARGET_COLUMN"]}"'
                )

    return "\n".join(lines)


def allowed_table_names(domains: list[dict]) -> set[str]:
    return {d["TABLE_NAME"].upper() for d in domains if d["TABLE_NAME"]}


def table_to_agent_key(domains: list[dict]) -> dict[str, str]:
    return {d["TABLE_NAME"].upper(): d["AGENT_KEY"] for d in domains}
