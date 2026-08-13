-- =====================================================================
-- FAMILY TREE - LOOKUP SEED DATA
-- =====================================================================
-- Run AFTER supabase_schema.sql.
-- Supabase dashboard > SQL Editor > New query > paste > Run.
--
-- Safe to re-run: uses ON CONFLICT DO NOTHING, so it will not disturb
-- values you have added or edited yourself.
-- =====================================================================

set search_path to tree, public;

insert into lkp_sex (sex_code, sex_label, sort_order) values
    ('M', 'Male',    1),
    ('F', 'Female',  2),
    ('U', 'Unknown', 3)
on conflict do nothing;

insert into lkp_generation (generation_code, generation_label, sort_order) values
    ('G0', 'Earlier than great-grandparents', 0),
    ('G1', 'Great-grandparents',              1),
    ('G2', 'Grandparents',                    2),
    ('G3', 'Parents',                         3),
    ('G4', 'Self and siblings',               4),
    ('G5', 'Children',                        5),
    ('G6', 'Grandchildren',                   6),
    ('G7', 'Great-grandchildren',             7)
on conflict do nothing;

insert into lkp_union_status (union_status_code, sort_order) values
    ('Married',   1),
    ('Divorced',  2),
    ('Widowed',   3),
    ('Partners',  4),
    ('Unmarried', 5),
    ('Separated', 6),
    ('Annulled',  7),
    ('Unknown',   8)
on conflict do nothing;

insert into lkp_how_ended (how_ended_code, sort_order) values
    ('Still together',  1),
    ('Death of spouse', 2),
    ('Divorce',         3),
    ('Separation',      4),
    ('Annulment',       5),
    ('Unknown',         6)
on conflict do nothing;

insert into lkp_child_relationship (relationship_code, sort_order) values
    ('Natural',      1),
    ('Adopted',      2),
    ('Step',         3),
    ('Foster',       4),
    ('Guardianship', 5),
    ('Unknown',      6)
on conflict do nothing;

insert into lkp_event_type (event_type_code, sort_order) values
    ('Baptism or christening', 1),
    ('Bar or bat mitzvah',     2),
    ('Census',                 3),
    ('Confirmation',           4),
    ('Education',              5),
    ('Emigration',             6),
    ('Graduation',             7),
    ('Immigration',            8),
    ('Land or property',       9),
    ('Military service',      10),
    ('Naturalization',        11),
    ('Obituary',              12),
    ('Occupation',            13),
    ('Religious affiliation', 14),
    ('Residence',             15),
    ('Retirement',            16),
    ('Will or probate',       17),
    ('Other',                 18)
on conflict do nothing;

insert into lkp_source_type (source_type_code, sort_order) values
    ('Vital record',           1),
    ('Census',                 2),
    ('Church record',          3),
    ('Newspaper',              4),
    ('Obituary',               5),
    ('Family bible',           6),
    ('Headstone or cemetery',  7),
    ('Interview',              8),
    ('Photograph',             9),
    ('Military record',       10),
    ('Immigration record',    11),
    ('Land or property record', 12),
    ('Will or probate',       13),
    ('Online database',       14),
    ('DNA test',              15),
    ('Personal knowledge',    16),
    ('Other',                 17)
on conflict do nothing;

insert into lkp_evidence_quality (evidence_quality_code, quality_description, sort_order) values
    ('Original',   'Created at the time of the event by a witness or official', 1),
    ('Derivative', 'A copy, transcript, abstract or index of an original',      2),
    ('Authored',   'Someone''s conclusion: a published tree, a recollection',   3)
on conflict do nothing;


-- =====================================================================
-- ADD YOURSELF AS THE FIRST CONTRIBUTOR
-- ---------------------------------------------------------------------
-- Sign up through the app first (or Supabase dashboard > Authentication
-- > Users > Add user). Then uncomment the line below, paste your user's
-- UUID from that Users page, and run it.
--
-- Nobody can read or write anything until they exist in this table.
-- =====================================================================

-- insert into contributor (contributor_id, display_name, relationship, is_admin)
-- values ('PASTE-YOUR-UUID-HERE', 'Allen', 'started the tree', true);


-- =====================================================================
-- SANITY CHECK
-- =====================================================================

select 'lkp_sex'                as table, count(*) from lkp_sex
union all select 'lkp_generation',         count(*) from lkp_generation
union all select 'lkp_union_status',       count(*) from lkp_union_status
union all select 'lkp_how_ended',          count(*) from lkp_how_ended
union all select 'lkp_child_relationship', count(*) from lkp_child_relationship
union all select 'lkp_event_type',         count(*) from lkp_event_type
union all select 'lkp_source_type',        count(*) from lkp_source_type
union all select 'lkp_evidence_quality',   count(*) from lkp_evidence_quality;
