-- =====================================================================
-- FAMILY TREE - SUPABASE / POSTGRES SCHEMA
-- =====================================================================
-- Collaborative, no curator. Every contributor writes directly.
-- Nothing is ever overwritten or destroyed: every change is versioned,
-- deletes are soft, and conflicting claims coexist until evidence
-- settles them.
--
-- HOW TO RUN
--   1. Supabase dashboard > SQL Editor > New query
--   2. Paste this entire file
--   3. Run
--   Takes a few seconds. Safe to re-run: it drops and rebuilds.
--
-- AFTER RUNNING
--   Run seed_data.sql to load the lookup values.
-- =====================================================================


-- =====================================================================
-- SECTION 0 - RESET
-- =====================================================================

drop schema if exists tree cascade;
create schema tree;

set search_path to tree, public;


-- =====================================================================
-- SECTION 1 - CONTRIBUTORS
-- ---------------------------------------------------------------------
-- Maps a Supabase auth user to a display name. Every edit records who
-- made it, which is what makes peer correction visible rather than
-- anonymous.
-- =====================================================================

create table contributor (
    contributor_id  uuid primary key references auth.users (id) on delete restrict,
    display_name    text not null,
    relationship    text,                    -- free text: "Allen's cousin, Ruth's daughter"
    email           text,
    is_admin        boolean not null default false,
    joined_at       timestamptz not null default now(),
    last_seen_at    timestamptz
);

comment on table contributor is
    'One row per person allowed to edit the tree. is_admin only gates '
    'destructive maintenance, not ordinary editing.';


-- =====================================================================
-- SECTION 2 - LOOKUP TABLES
-- ---------------------------------------------------------------------
-- Same eight as the Access design. Postgres enforces these as real FK
-- constraints, so a typo cannot enter the database at all.
-- =====================================================================

create table lkp_sex (
    sex_code    text primary key,
    sex_label   text not null,
    sort_order  smallint not null default 0
);

create table lkp_generation (
    generation_code   text primary key,
    generation_label  text not null,
    sort_order        smallint not null default 0
);

create table lkp_union_status (
    union_status_code text primary key,
    sort_order        smallint not null default 0
);

create table lkp_how_ended (
    how_ended_code text primary key,
    sort_order     smallint not null default 0
);

create table lkp_child_relationship (
    relationship_code text primary key,
    sort_order        smallint not null default 0
);

create table lkp_event_type (
    event_type_code text primary key,
    sort_order      smallint not null default 0
);

create table lkp_source_type (
    source_type_code text primary key,
    sort_order       smallint not null default 0
);

create table lkp_evidence_quality (
    evidence_quality_code text primary key,
    quality_description   text not null,
    sort_order            smallint not null default 0
);


-- =====================================================================
-- SECTION 3 - HUMAN-READABLE ID GENERATOR
-- ---------------------------------------------------------------------
-- Keeps the I0001 / F0001 / E0001 / S0001 format. Readable IDs matter
-- more in a shared system than a private one: relatives can say
-- "I fixed I0042" in the group chat and everyone knows what that means.
--
-- A sequence per prefix avoids the race condition you would get from
-- MAX(id)+1 when two cousins add a person at the same moment.
-- =====================================================================

create sequence seq_individual start 1;
create sequence seq_family     start 1;
create sequence seq_event      start 1;
create sequence seq_source     start 1;

create or replace function next_individual_id() returns text
language sql volatile as $$
    select 'I' || lpad(nextval('tree.seq_individual')::text, 4, '0');
$$;

create or replace function next_family_id() returns text
language sql volatile as $$
    select 'F' || lpad(nextval('tree.seq_family')::text, 4, '0');
$$;

create or replace function next_event_id() returns text
language sql volatile as $$
    select 'E' || lpad(nextval('tree.seq_event')::text, 4, '0');
$$;

create or replace function next_source_id() returns text
language sql volatile as $$
    select 'S' || lpad(nextval('tree.seq_source')::text, 4, '0');
$$;


-- =====================================================================
-- SECTION 4 - SOURCES
-- =====================================================================

create table source (
    source_id             text primary key default next_source_id(),
    source_type_code      text references lkp_source_type (source_type_code)
                               on update cascade on delete restrict,
    source_title          text not null,
    author_agency         text,
    repository            text,
    citation_detail       text,
    source_url            text,
    file_path             text,              -- Supabase Storage object path
    date_accessed         date,
    evidence_quality_code text references lkp_evidence_quality (evidence_quality_code)
                               on update cascade on delete restrict,
    notes                 text,

    created_by            uuid references contributor (contributor_id),
    created_at            timestamptz not null default now(),
    updated_by            uuid references contributor (contributor_id),
    updated_at            timestamptz not null default now(),
    deleted_at            timestamptz,
    deleted_by            uuid references contributor (contributor_id),

    constraint source_id_format   check (source_id ~ '^S[0-9]{4,}$'),
    constraint source_date_sane   check (date_accessed is null or date_accessed <= current_date)
);


-- =====================================================================
-- SECTION 5 - INDIVIDUALS
-- =====================================================================

create table individual (
    individual_id     text primary key default next_individual_id(),
    given_names       text not null,
    surname_at_birth  text,
    also_known_as     text,
    suffix            text,
    sex_code          text references lkp_sex (sex_code)
                           on update cascade on delete restrict,
    generation_code   text references lkp_generation (generation_code)
                           on update cascade on delete restrict,
    is_living         boolean not null default true,

    birth_date_text   text,                  -- "14 MAR 1948", "ABT 1892", "BEF 1912"
    birth_year        smallint,
    birth_place       text,
    death_date_text   text,
    death_year        smallint,
    death_place       text,
    burial_place      text,
    occupation        text,
    photo_path        text,                  -- Supabase Storage object path
    notes             text,

    created_by        uuid references contributor (contributor_id),
    created_at        timestamptz not null default now(),
    updated_by        uuid references contributor (contributor_id),
    updated_at        timestamptz not null default now(),
    deleted_at        timestamptz,
    deleted_by        uuid references contributor (contributor_id),

    constraint individual_id_format check (individual_id ~ '^I[0-9]{4,}$'),
    constraint birth_year_sane      check (birth_year is null
                                           or (birth_year > 1000
                                               and birth_year <= extract(year from current_date))),
    constraint death_year_sane      check (death_year is null
                                           or (death_year > 1000
                                               and death_year <= extract(year from current_date))),
    constraint death_after_birth    check (death_year is null
                                           or birth_year is null
                                           or death_year >= birth_year)
);

create index idx_individual_surname  on individual (lower(surname_at_birth))
    where deleted_at is null;
create index idx_individual_birthyr  on individual (birth_year)
    where deleted_at is null;
create index idx_individual_living   on individual (is_living)
    where deleted_at is null;

-- Full text search across names, for the app's search box.
create index idx_individual_search on individual
    using gin (to_tsvector('simple',
        coalesce(given_names, '') || ' ' ||
        coalesce(surname_at_birth, '') || ' ' ||
        coalesce(also_known_as, '')));


-- =====================================================================
-- SECTION 6 - FAMILIES
-- =====================================================================

create table family (
    family_id          text primary key default next_family_id(),
    partner1_id        text references individual (individual_id)
                            on update cascade on delete restrict,
    partner2_id        text references individual (individual_id)
                            on update cascade on delete restrict,
    union_status_code  text references lkp_union_status (union_status_code)
                            on update cascade on delete restrict,
    marriage_date_text text,
    marriage_year      smallint,
    marriage_place     text,
    union_end_date_text text,
    how_ended_code     text references lkp_how_ended (how_ended_code)
                            on update cascade on delete restrict,
    notes              text,

    created_by         uuid references contributor (contributor_id),
    created_at         timestamptz not null default now(),
    updated_by         uuid references contributor (contributor_id),
    updated_at         timestamptz not null default now(),
    deleted_at         timestamptz,
    deleted_by         uuid references contributor (contributor_id),

    constraint family_id_format  check (family_id ~ '^F[0-9]{4,}$'),
    constraint marriage_year_sane check (marriage_year is null
                                         or (marriage_year > 1000
                                             and marriage_year <= extract(year from current_date))),
    constraint not_self_married  check (partner1_id is null
                                        or partner2_id is null
                                        or partner1_id <> partner2_id)
);

create index idx_family_partner1 on family (partner1_id) where deleted_at is null;
create index idx_family_partner2 on family (partner2_id) where deleted_at is null;


-- =====================================================================
-- SECTION 7 - CHILD LINKS
-- ---------------------------------------------------------------------
-- The table that actually builds the tree. A child links to a FAMILY,
-- not to a person, which is what makes remarriage and half-siblings
-- resolve without special cases.
-- =====================================================================

create table child_link (
    child_link_id     bigserial primary key,
    family_id         text not null references family (family_id)
                           on update cascade on delete restrict,
    child_id          text not null references individual (individual_id)
                           on update cascade on delete restrict,
    birth_order       smallint,
    relationship_code text references lkp_child_relationship (relationship_code)
                           on update cascade on delete restrict,
    notes             text,

    created_by        uuid references contributor (contributor_id),
    created_at        timestamptz not null default now(),
    updated_by        uuid references contributor (contributor_id),
    updated_at        timestamptz not null default now(),
    deleted_at        timestamptz,
    deleted_by        uuid references contributor (contributor_id),

    constraint birth_order_positive check (birth_order is null or birth_order > 0)
    -- "a person cannot be their own parent" spans two tables, so it cannot
    -- be a CHECK constraint. Enforced by trigger in Section 12.
);

-- A child can only be linked to the same family once (live rows only).
create unique index idx_child_link_unique
    on child_link (family_id, child_id)
    where deleted_at is null;

create index idx_child_link_child  on child_link (child_id)  where deleted_at is null;
create index idx_child_link_family on child_link (family_id) where deleted_at is null;


-- =====================================================================
-- SECTION 8 - EVENTS
-- =====================================================================

create table event (
    event_id        text primary key default next_event_id(),
    individual_id   text references individual (individual_id)
                         on update cascade on delete restrict,
    family_id       text references family (family_id)
                         on update cascade on delete restrict,
    event_type_code text references lkp_event_type (event_type_code)
                         on update cascade on delete restrict,
    event_date_text text,
    event_year      smallint,
    event_place     text,
    description     text,
    source_id       text references source (source_id)
                         on update cascade on delete restrict,

    created_by      uuid references contributor (contributor_id),
    created_at      timestamptz not null default now(),
    updated_by      uuid references contributor (contributor_id),
    updated_at      timestamptz not null default now(),
    deleted_at      timestamptz,
    deleted_by      uuid references contributor (contributor_id),

    constraint event_id_format check (event_id ~ '^E[0-9]{4,}$'),
    constraint event_year_sane check (event_year is null
                                      or (event_year > 1000
                                          and event_year <= extract(year from current_date))),
    -- Exactly one subject: a person OR a family, never both, never neither.
    constraint event_one_subject check (
        (individual_id is null) <> (family_id is null)
    )
);

create index idx_event_individual on event (individual_id) where deleted_at is null;
create index idx_event_family     on event (family_id)     where deleted_at is null;


-- =====================================================================
-- SECTION 9 - CITATION JUNCTIONS
-- ---------------------------------------------------------------------
-- applies_to_fact is what turns a source list into an audit trail:
-- "what proves his middle name?" rather than "what mentions him?"
-- =====================================================================

create table individual_source (
    ind_source_id   bigserial primary key,
    individual_id   text not null references individual (individual_id)
                         on update cascade on delete restrict,
    source_id       text not null references source (source_id)
                         on update cascade on delete restrict,
    applies_to_fact text,
    notes           text,

    created_by      uuid references contributor (contributor_id),
    created_at      timestamptz not null default now(),
    deleted_at      timestamptz,
    deleted_by      uuid references contributor (contributor_id)
);

create unique index idx_ind_source_unique
    on individual_source (individual_id, source_id, coalesce(applies_to_fact, ''))
    where deleted_at is null;

create table family_source (
    fam_source_id   bigserial primary key,
    family_id       text not null references family (family_id)
                         on update cascade on delete restrict,
    source_id       text not null references source (source_id)
                         on update cascade on delete restrict,
    applies_to_fact text,
    notes           text,

    created_by      uuid references contributor (contributor_id),
    created_at      timestamptz not null default now(),
    deleted_at      timestamptz,
    deleted_by      uuid references contributor (contributor_id)
);

create unique index idx_fam_source_unique
    on family_source (family_id, source_id, coalesce(applies_to_fact, ''))
    where deleted_at is null;


-- =====================================================================
-- SECTION 10 - COMPETING CLAIMS
-- ---------------------------------------------------------------------
-- The heart of the no-curator design. When two relatives believe
-- different things about the same fact, BOTH are recorded. Neither
-- person's information is erased by the other's edit.
--
-- The main tables hold the current working value. This table holds
-- every claim ever made about a field, including the current one.
-- =====================================================================

create table fact_claim (
    claim_id       bigserial primary key,
    subject_type   text not null check (subject_type in ('individual', 'family')),
    subject_id     text not null,
    field_name     text not null,            -- 'birth_year', 'birth_place', ...
    claimed_value  text,
    claimed_by     uuid references contributor (contributor_id),
    claimed_at     timestamptz not null default now(),
    source_id      text references source (source_id)
                        on update cascade on delete set null,
    reasoning      text,                     -- "Grandma's bible says 1892"
    status         text not null default 'open'
                        check (status in ('open', 'accepted', 'superseded', 'withdrawn')),
    resolved_by    uuid references contributor (contributor_id),
    resolved_at    timestamptz,
    resolution_note text
);

create index idx_fact_claim_subject on fact_claim (subject_type, subject_id, field_name);
create index idx_fact_claim_open    on fact_claim (status) where status = 'open';

comment on table fact_claim is
    'Competing assertions about a single field. More than one open claim '
    'for the same subject and field means the fact is disputed - the app '
    'shows both rather than silently picking a winner.';

-- Which facts currently have more than one open claim.
create view v_disputed_facts as
select subject_type,
       subject_id,
       field_name,
       count(*)                              as claim_count,
       array_agg(distinct claimed_value)     as competing_values,
       min(claimed_at)                       as first_claimed,
       max(claimed_at)                       as last_claimed
from fact_claim
where status = 'open'
group by subject_type, subject_id, field_name
having count(distinct claimed_value) > 1;


-- =====================================================================
-- SECTION 11 - AUDIT LOG
-- ---------------------------------------------------------------------
-- Every insert, update and soft delete on every core table, with the
-- before and after values and who did it. This is what makes a bad edit
-- a one-click revert instead of an argument in the group chat.
-- =====================================================================

create table audit_log (
    audit_id       bigserial primary key,
    table_name     text        not null,
    record_id      text        not null,
    action         text        not null check (action in ('INSERT', 'UPDATE', 'DELETE', 'RESTORE')),
    changed_by     uuid,
    changed_at     timestamptz not null default now(),
    changed_fields text[],
    old_data       jsonb,
    new_data       jsonb
);

create index idx_audit_record on audit_log (table_name, record_id, changed_at desc);
create index idx_audit_recent on audit_log (changed_at desc);
create index idx_audit_who    on audit_log (changed_by, changed_at desc);


-- Name of the primary key column for a given table.
-- Junction rows carry several *_id columns, so this must be table-aware:
-- guessing by column name would log a foreign key and break revert.
create or replace function _pk_column(t text) returns text
language sql immutable as $$
    select case t
        when 'individual'        then 'individual_id'
        when 'family'            then 'family_id'
        when 'event'             then 'event_id'
        when 'source'            then 'source_id'
        when 'child_link'        then 'child_link_id'
        when 'individual_source' then 'ind_source_id'
        when 'family_source'     then 'fam_source_id'
        else 'id'
    end;
$$;

-- Returns the primary key value of the row, whichever table it is from.
create or replace function _record_id(t text, row_data jsonb) returns text
language sql immutable as $$
    select coalesce(row_data ->> _pk_column(t), '?');
$$;


create or replace function fn_audit() returns trigger
language plpgsql security definer as $$
declare
    v_old     jsonb;
    v_new     jsonb;
    v_action  text;
    v_fields  text[];
    v_actor   uuid;
    k         text;
begin
    v_actor := auth.uid();

    if tg_op = 'INSERT' then
        v_new    := to_jsonb(new);
        v_action := 'INSERT';

    elsif tg_op = 'UPDATE' then
        v_old := to_jsonb(old);
        v_new := to_jsonb(new);

        -- Soft delete and restore are distinct actions in the feed.
        if old.deleted_at is null and new.deleted_at is not null then
            v_action := 'DELETE';
        elsif old.deleted_at is not null and new.deleted_at is null then
            v_action := 'RESTORE';
        else
            v_action := 'UPDATE';
        end if;

        -- Record only the fields that actually changed.
        v_fields := array[]::text[];
        for k in select jsonb_object_keys(v_new) loop
            if k not in ('updated_at', 'updated_by')
               and (v_old -> k) is distinct from (v_new -> k) then
                v_fields := v_fields || k;
            end if;
        end loop;

        -- Nothing of substance changed: do not clutter the feed.
        if array_length(v_fields, 1) is null then
            return new;
        end if;

    elsif tg_op = 'DELETE' then
        -- Hard deletes are blocked elsewhere; logged here as a backstop.
        v_old    := to_jsonb(old);
        v_action := 'DELETE';
    end if;

    insert into audit_log (table_name, record_id, action, changed_by,
                           changed_fields, old_data, new_data)
    values (tg_table_name,
            _record_id(tg_table_name, coalesce(v_new, v_old)),
            v_action,
            v_actor,
            v_fields,
            v_old,
            v_new);

    if tg_op = 'DELETE' then
        return old;
    end if;
    return new;
end;
$$;


-- Stamps updated_at / updated_by and the create/delete actor columns.
create or replace function fn_stamp() returns trigger
language plpgsql as $$
begin
    if tg_op = 'INSERT' then
        new.created_by := coalesce(new.created_by, auth.uid());
        new.created_at := coalesce(new.created_at, now());
        if to_jsonb(new) ? 'updated_by' then
            new.updated_by := coalesce(new.updated_by, auth.uid());
            new.updated_at := now();
        end if;

    elsif tg_op = 'UPDATE' then
        if to_jsonb(new) ? 'updated_by' then
            new.updated_by := auth.uid();
            new.updated_at := now();
        end if;
        if old.deleted_at is null and new.deleted_at is not null then
            new.deleted_by := coalesce(new.deleted_by, auth.uid());
        end if;
        if new.deleted_at is null then
            new.deleted_by := null;
        end if;
    end if;
    return new;
end;
$$;


-- Blocks hard deletes. Nothing leaves this database.
create or replace function fn_block_hard_delete() returns trigger
language plpgsql as $$
begin
    raise exception
        'Hard delete is not allowed on %. Set deleted_at instead - the row '
        'disappears from the app but stays recoverable.', tg_table_name;
end;
$$;


-- Attach all three to every core table.
do $$
declare
    t text;
begin
    foreach t in array array[
        'individual', 'family', 'child_link', 'event', 'source',
        'individual_source', 'family_source'
    ] loop
        execute format(
            'create trigger trg_stamp_%1$s before insert or update on tree.%1$I
             for each row execute function tree.fn_stamp()', t);

        execute format(
            'create trigger trg_audit_%1$s after insert or update on tree.%1$I
             for each row execute function tree.fn_audit()', t);

        execute format(
            'create trigger trg_nodelete_%1$s before delete on tree.%1$I
             for each row execute function tree.fn_block_hard_delete()', t);
    end loop;
end $$;


-- =====================================================================
-- SECTION 12 - INTEGRITY TRIGGERS
-- ---------------------------------------------------------------------
-- Rules Postgres cannot express as CHECK constraints because they span
-- more than one table.
-- =====================================================================

create or replace function fn_child_not_own_parent() returns trigger
language plpgsql as $$
declare
    p1 text;
    p2 text;
begin
    select partner1_id, partner2_id into p1, p2
    from family where family_id = new.family_id;

    if new.child_id in (p1, p2) then
        raise exception 'A person cannot be their own parent (% in family %).',
            new.child_id, new.family_id;
    end if;
    return new;
end;
$$;

create trigger trg_child_not_own_parent
    before insert or update on child_link
    for each row execute function fn_child_not_own_parent();


-- Warns rather than blocks: implausible ages are often correctly
-- transcribed from a document that is itself wrong. Recorded as an open
-- claim for someone to look at, not rejected at the keyboard.
create or replace function fn_flag_implausible() returns trigger
language plpgsql as $$
declare
    parent_birth smallint;
    child_birth  smallint;
    gap          int;
begin
    select i.birth_year into child_birth
    from individual i where i.individual_id = new.child_id;

    if child_birth is null then return new; end if;

    for parent_birth in
        select i.birth_year
        from family f
        join individual i on i.individual_id in (f.partner1_id, f.partner2_id)
        where f.family_id = new.family_id and i.birth_year is not null
    loop
        gap := child_birth - parent_birth;
        if gap < 12 or gap > 65 then
            insert into fact_claim (subject_type, subject_id, field_name,
                                    claimed_value, reasoning, status)
            values ('individual', new.child_id, 'birth_year',
                    child_birth::text,
                    format('Automatic flag: parent born %s, child born %s - '
                           'a gap of %s years. Worth checking.',
                           parent_birth, child_birth, gap),
                    'open');
        end if;
    end loop;
    return new;
end;
$$;

create trigger trg_flag_implausible
    after insert or update on child_link
    for each row execute function fn_flag_implausible();


-- =====================================================================
-- SECTION 13 - VIEWS FOR THE APP
-- =====================================================================

-- Live rows only, with parents resolved. The app's main read surface.
create view v_individual as
select
    i.individual_id,
    trim(coalesce(i.given_names, '') || ' ' ||
         coalesce(i.surname_at_birth, '') || ' ' ||
         coalesce(i.suffix, ''))                       as full_name,
    i.given_names,
    i.surname_at_birth,
    i.also_known_as,
    i.suffix,
    i.sex_code,
    i.generation_code,
    i.is_living,
    i.birth_date_text,
    i.birth_year,
    i.birth_place,
    i.death_date_text,
    i.death_year,
    i.death_place,
    i.burial_place,
    i.occupation,
    i.photo_path,
    i.notes,
    case when i.death_year is not null and i.birth_year is not null
         then i.death_year - i.birth_year end          as age_at_death,
    cl.family_id                                       as birth_family_id,
    f.partner1_id                                      as father_id,
    fa.given_names || ' ' || coalesce(fa.surname_at_birth, '') as father_name,
    f.partner2_id                                      as mother_id,
    mo.given_names || ' ' || coalesce(mo.surname_at_birth, '') as mother_name,
    i.created_by,
    i.created_at,
    i.updated_by,
    i.updated_at
from individual i
left join child_link cl on cl.child_id = i.individual_id and cl.deleted_at is null
left join family     f  on f.family_id = cl.family_id    and f.deleted_at  is null
left join individual fa on fa.individual_id = f.partner1_id
left join individual mo on mo.individual_id = f.partner2_id
where i.deleted_at is null;


-- The change feed. This is what makes peer correction actually happen:
-- people only fix what they can see.
create view v_recent_changes as
select
    a.audit_id,
    a.changed_at,
    a.table_name,
    a.record_id,
    a.action,
    coalesce(c.display_name, 'Unknown') as changed_by_name,
    a.changed_fields,
    case a.table_name
        when 'individual' then coalesce(a.new_data ->> 'given_names', a.old_data ->> 'given_names')
                               || ' ' ||
                               coalesce(a.new_data ->> 'surname_at_birth', a.old_data ->> 'surname_at_birth', '')
        else a.record_id
    end                                 as subject_label,
    a.old_data,
    a.new_data
from audit_log a
left join contributor c on c.contributor_id = a.changed_by
order by a.changed_at desc;


-- Research quality dashboard: who has no evidence behind them.
create view v_unsourced_individuals as
select i.individual_id,
       trim(i.given_names || ' ' || coalesce(i.surname_at_birth, '')) as full_name,
       i.birth_year,
       i.generation_code
from individual i
where i.deleted_at is null
  and not exists (
      select 1 from individual_source s
      where s.individual_id = i.individual_id and s.deleted_at is null
  );


-- Everyone who contributed, and how much.
create view v_contributor_activity as
select c.contributor_id,
       c.display_name,
       c.relationship,
       count(a.audit_id)                                         as total_edits,
       count(*) filter (where a.action = 'INSERT')               as records_added,
       count(*) filter (where a.action = 'UPDATE')               as records_edited,
       max(a.changed_at)                                         as last_edit
from contributor c
left join audit_log a on a.changed_by = c.contributor_id
group by c.contributor_id, c.display_name, c.relationship;


-- =====================================================================
-- SECTION 14 - ROW LEVEL SECURITY
-- ---------------------------------------------------------------------
-- Model: any signed-in contributor may read and write everything.
-- Anonymous visitors get nothing at all. Hard deletes are blocked for
-- everyone, including admins, by the triggers above.
--
-- The living-person protection is at the EXPORT boundary, not here -
-- family members legitimately need to see each other's details.
-- =====================================================================

alter table contributor            enable row level security;
alter table individual             enable row level security;
alter table family                 enable row level security;
alter table child_link             enable row level security;
alter table event                  enable row level security;
alter table source                 enable row level security;
alter table individual_source      enable row level security;
alter table family_source          enable row level security;
alter table fact_claim             enable row level security;
alter table audit_log              enable row level security;
alter table lkp_sex                enable row level security;
alter table lkp_generation         enable row level security;
alter table lkp_union_status       enable row level security;
alter table lkp_how_ended          enable row level security;
alter table lkp_child_relationship enable row level security;
alter table lkp_event_type         enable row level security;
alter table lkp_source_type        enable row level security;
alter table lkp_evidence_quality   enable row level security;


-- Is the current user a registered contributor?
create or replace function is_contributor() returns boolean
language sql stable security definer as $$
    select exists (
        select 1 from tree.contributor
        where contributor_id = auth.uid()
    );
$$;

create or replace function is_admin() returns boolean
language sql stable security definer as $$
    select coalesce(
        (select is_admin from tree.contributor where contributor_id = auth.uid()),
        false);
$$;


-- Core tables: contributors read and write freely.
do $$
declare
    t text;
begin
    foreach t in array array[
        'individual', 'family', 'child_link', 'event', 'source',
        'individual_source', 'family_source', 'fact_claim'
    ] loop
        execute format(
            'create policy %1$s_read on tree.%1$I
             for select using (tree.is_contributor())', t);
        execute format(
            'create policy %1$s_insert on tree.%1$I
             for insert with check (tree.is_contributor())', t);
        execute format(
            'create policy %1$s_update on tree.%1$I
             for update using (tree.is_contributor())', t);
    end loop;
end $$;

-- Lookups: readable by all contributors, changeable only by admins.
do $$
declare
    t text;
begin
    foreach t in array array[
        'lkp_sex', 'lkp_generation', 'lkp_union_status', 'lkp_how_ended',
        'lkp_child_relationship', 'lkp_event_type', 'lkp_source_type',
        'lkp_evidence_quality'
    ] loop
        execute format(
            'create policy %1$s_read on tree.%1$I
             for select using (tree.is_contributor())', t);
        execute format(
            'create policy %1$s_admin on tree.%1$I
             for all using (tree.is_admin())', t);
    end loop;
end $$;

-- Audit log: everyone reads it, nobody writes it by hand.
create policy audit_read on audit_log
    for select using (is_contributor());

-- Contributors: everyone sees the roster; you edit only your own row.
create policy contributor_read on contributor
    for select using (is_contributor());
create policy contributor_self on contributor
    for update using (contributor_id = auth.uid());
create policy contributor_admin on contributor
    for all using (is_admin());


grant usage on schema tree to authenticated;
grant select, insert, update on all tables in schema tree to authenticated;
grant usage, select on all sequences in schema tree to authenticated;
grant execute on all functions in schema tree to authenticated;


-- =====================================================================
-- SECTION 15 - REVERT HELPER
-- ---------------------------------------------------------------------
-- Undo any single change from the audit log. This is the feature that
-- makes open editing safe: a wrong edit costs one click, not a debate.
-- =====================================================================

create or replace function revert_change(p_audit_id bigint)
returns text
language plpgsql security definer as $$
declare
    a          audit_log;
    v_sql      text;
    v_sets     text := '';
    v_pk_col   text;
    k          text;
begin
    select * into a from audit_log where audit_id = p_audit_id;
    if not found then
        raise exception 'No audit entry %', p_audit_id;
    end if;

    v_pk_col := _pk_column(a.table_name);

    if a.action = 'INSERT' then
        -- Undoing a creation means soft deleting it.
        execute format(
            'update tree.%I set deleted_at = now() where %I = %L',
            a.table_name, v_pk_col, a.record_id);
        return format('Soft deleted %s %s', a.table_name, a.record_id);
    end if;

    if a.old_data is null then
        raise exception 'Audit entry % has no previous state to restore.', p_audit_id;
    end if;

    foreach k in array coalesce(a.changed_fields, array[]::text[]) loop
        if k <> v_pk_col then
            v_sets := v_sets || format('%I = %L, ', k, a.old_data ->> k);
        end if;
    end loop;

    if v_sets = '' then
        return 'Nothing to revert.';
    end if;

    v_sql := format('update tree.%I set %s where %I = %L',
                    a.table_name,
                    left(v_sets, length(v_sets) - 2),
                    v_pk_col, a.record_id);
    execute v_sql;

    return format('Reverted %s on %s %s (%s fields)',
                  a.action, a.table_name, a.record_id,
                  array_length(a.changed_fields, 1));
end;
$$;


-- =====================================================================
-- DONE
-- =====================================================================
-- Next: run seed_data.sql to load the eight lookup tables.
-- =====================================================================
