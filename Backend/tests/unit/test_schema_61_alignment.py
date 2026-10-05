"""Compare the checked-in PostgreSQL 6.1 schema with ORM metadata."""

import re
from pathlib import Path

from sqlalchemy import CheckConstraint, Computed, UniqueConstraint
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateIndex

from app.models.orm_models import Base


SCHEMA = Path(__file__).resolve().parents[2] / 'migrations' / '006_1_create_initial_test_schema.sql'


def normalize(value):
    value = str(value).lower().replace('if not exists', '')
    return re.sub(r'[\s()"]+', '', value).rstrip(';')


def test_schema_columns_types_nullability_defaults_and_enums_match_orm():
    sql = SCHEMA.read_text()
    tables = dict(re.findall(r'create table if not exists (\w+)\s*\((.*?)\n\);', sql, re.S))
    assert set(tables) == set(Base.metadata.tables)
    for name, body in tables.items():
        # Column declarations in the maintained schema occupy one line each.
        columns = {}
        for line in body.splitlines():
            match = re.match(r'\s*(\w+)\s+(double precision|\w+(?:\(\d+\))?)(.*)', line)
            if match and match[1] not in ('constraint', 'references', 'primary'):
                columns[match[1]] = (match[2], match[3])
        table = Base.metadata.tables[name]
        expected_names = set(columns)
        if name == 'groups':
            expected_names.add('active_owner_role')  # added by ALTER after memberships exists
        assert expected_names == set(table.c.keys()), name
        for column_name, (sql_type, tail) in columns.items():
            column = table.c[column_name]
            orm_type = str(column.type.compile(dialect=dialect())).lower()
            aliases = {'integer': 'int', 'timestamp with time zone': 'timestamptz', 'float': 'double precision'}
            assert aliases.get(orm_type, orm_type) == sql_type, (name, column_name)
            sql_not_null = 'not null' in tail or 'primary key' in tail
            assert column.nullable == (not sql_not_null), (name, column_name)
            default = re.search(r"\bdefault\s+('[^']*'|\w+)", tail)
            assert ('generated always as identity' in tail) == (column.identity is not None), (name, column_name)
            if column.identity is not None:
                assert column.identity.always
            orm_default = None if column.server_default is None or column.identity is not None else str(column.server_default.arg)
            assert (default[1] if default else None) == orm_default, (name, column_name)

    enums = dict(re.findall(r'create type (\w+) as enum\s*\(([^)]+)\)', sql))
    for table in Base.metadata.tables.values():
        for column in table.c:
            if hasattr(column.type, 'enums'):
                assert re.findall(r"'([^']+)'", enums[column.type.name]) == column.type.enums
    generated = Base.metadata.tables['groups'].c.active_owner_role.server_default
    assert isinstance(generated, Computed) and generated.persisted
    assert not Base.metadata.tables['groups'].c.active_owner_role.nullable
    assert str(generated.sqltext) == "'owner'::member_roles"
    assert re.search(r"generated always as\s*\('owner'::member_roles\) stored not null", sql)
    assert normalize(generated.sqltext) in normalize(sql)


def test_schema_named_foreign_keys_and_indexes_match_orm():
    sql = SCHEMA.read_text()
    sql_fks = {
        name: (normalize(columns), target, normalize(target_columns))
        for name, columns, target, target_columns in re.findall(
            r'constraint (\w+)\s+foreign key\s*\(([^)]+)\)\s*references (\w+)\s*\(([^)]+)\)', sql)
    }
    orm_fks = {}
    for table in Base.metadata.tables.values():
        for fk in table.foreign_key_constraints:
            if fk.name:
                orm_fks[fk.name] = (','.join(fk.column_keys), fk.referred_table.name,
                                   ','.join(e.column.name for e in fk.elements))
    assert sql_fks == orm_fks
    owner_fk = next(fk for fk in Base.metadata.tables['groups'].foreign_key_constraints
                    if fk.name == 'fk_groups_active_owner')
    assert owner_fk.deferrable and owner_fk.initially == 'DEFERRED'
    assert re.search(r'constraint fk_groups_active_owner\b[^;]*deferrable initially deferred', sql)
    # The two unnamed mention FKs deliberately cascade instead of retaining history.
    for fk in Base.metadata.tables['message_mentions'].foreign_key_constraints:
        assert fk.ondelete == 'CASCADE'
        column = next(iter(fk.columns))
        assert re.search(rf'{column.name} \w+ not null references \w+\(\w+\) on delete cascade', sql)

    sql_indexes = {normalize(statement) for statement in re.findall(
        r'create (?:unique )?index [^;]+;', sql)}
    orm_indexes = {normalize(CreateIndex(index).compile(dialect=dialect()))
                   for table in Base.metadata.tables.values() for index in table.indexes}
    assert sql_indexes == orm_indexes


def test_test_schema_mirror_matches_current_schema():
    assert SCHEMA.read_text() == (SCHEMA.parent / 'test_schema' / SCHEMA.name).read_text()


def test_primary_unique_and_check_constraints_match_orm():
    sql = SCHEMA.read_text()
    tables = dict(re.findall(r'create table if not exists (\w+)\s*\((.*?)\n\);', sql, re.S))
    for name, body in tables.items():
        table = Base.metadata.tables[name]
        composite_pk = re.search(r'primary key\s*\(([^)]+)\)', body)
        if composite_pk:
            primary_keys = [item.strip() for item in composite_pk[1].split(',')]
        else:
            primary_keys = re.findall(r'^\s*(\w+) [^\n]*primary key', body, re.M)
        assert primary_keys == list(table.primary_key.columns.keys()), name
        sql_unique = {normalize(columns) for columns in re.findall(r'\bunique\s*\(([^)]+)\)', body)}
        sql_unique.update(re.findall(r'^\s*(\w+) [^\n]*\bunique\s*,?$', body, re.M))
        orm_unique = {','.join(c.columns.keys()) for c in table.constraints if isinstance(c, UniqueConstraint)}
        assert sql_unique == orm_unique, name
        sql_checks = {constraint: normalize(expression) for constraint, expression in re.findall(
            r'constraint (\w+) check\s*\(([^)]+)\)', body)}
        orm_checks = {c.name: normalize(c.sqltext) for c in table.constraints if isinstance(c, CheckConstraint)}
        assert sql_checks == orm_checks, name
