from app.config import get_settings
from app.models import Dataset

settings = get_settings()


def qualified_table(schema_name: str, table_name: str) -> str:
    return f'"{settings.snowflake_database}"."{schema_name}"."{table_name}"'


def build_dataset_catalog(datasets: list[Dataset]) -> str:
    """Render the authenticated user's READY datasets, columns, and known
    relationships as compact text the LLM can ground SQL generation in.
    Only ever called with datasets already filtered to `user_id` by the caller.
    """
    if not datasets:
        return "The user has no datasets loaded yet."

    lines: list[str] = []
    for ds in datasets:
        table_ref = qualified_table(ds.snowflake_schema, ds.snowflake_table)
        lines.append(f"\nTable {table_ref}  (dataset_id={ds.id}, type={ds.dataset_type}, agent={ds.agent})")
        for col in ds.columns:
            if not col.include:
                continue
            flags = []
            if col.primary_key_candidate:
                flags.append("PK")
            if col.foreign_key_candidate:
                flags.append("FK")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f'  - "{col.target_column}" {col.target_type}{flag_str}  -- {col.semantic_type}')

        for rel in ds.relationships_out:
            target = next((d for d in datasets if d.id == rel.target_dataset_id), None)
            if target:
                target_ref = qualified_table(target.snowflake_schema, target.snowflake_table)
                lines.append(
                    f'  relationship: {table_ref}."{rel.source_column}" -> {target_ref}."{rel.target_column}"'
                )

    return "\n".join(lines)


def allowed_table_names(datasets: list[Dataset]) -> set[str]:
    return {d.snowflake_table.upper() for d in datasets if d.snowflake_table}
