/*
Version: 8

Purpose:
    Add a persistent privacy preference controlling whether an authenticated
    user may appear in online-member lists.

Notes:
    Actual online presence remains temporary Redis state. PostgreSQL stores
    only the user's privacy preference.
*/

alter table users
add column if not exists show_online_status boolean
default true
not null;