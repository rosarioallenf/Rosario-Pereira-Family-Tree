"""
Data access layer for the family tree app.

Everything that touches Supabase lives here. The pages import from this
module and never build queries themselves, so if the schema changes there
is one file to fix.

All reads and writes go through the logged-in user's own client, which
means Postgres row level security applies as that person. There is no
service key anywhere in this app.
"""

import streamlit as st
from supabase import create_client, Client

SCHEMA = "tree"


# ---------------------------------------------------------------- client

def _anon_client() -> Client:
    """A fresh client with no user session attached."""
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
    except (KeyError, FileNotFoundError):
        st.error(
            "Supabase credentials are missing. Add SUPABASE_URL and "
            "SUPABASE_ANON_KEY in Streamlit settings under Secrets."
        )
        st.stop()
    return create_client(url, key)


def client() -> Client:
    """The client for the current session, carrying the user's login."""
    if "sb" not in st.session_state:
        st.session_state.sb = _anon_client()
    return st.session_state.sb


def tbl(name: str):
    """Query builder for a table in the tree schema."""
    return client().schema(SCHEMA).table(name)


def rpc(fn: str, params: dict | None = None):
    return client().schema(SCHEMA).rpc(fn, params or {})


# ------------------------------------------------------------------ auth

def sign_in(email: str, password: str):
    return client().auth.sign_in_with_password(
        {"email": email, "password": password}
    )


def sign_up(email: str, password: str):
    return client().auth.sign_up({"email": email, "password": password})


def send_reset(email: str):
    return client().auth.reset_password_email(email)


def sign_out():
    try:
        client().auth.sign_out()
    except Exception:
        pass
    for k in list(st.session_state.keys()):
        del st.session_state[k]


def current_user():
    try:
        return client().auth.get_user().user
    except Exception:
        return None


def me() -> dict | None:
    """The contributor row for the logged-in user, or None if not enrolled."""
    user = current_user()
    if not user:
        return None
    if st.session_state.get("_me_id") == user.id and "_me" in st.session_state:
        return st.session_state["_me"]
    try:
        r = tbl("contributor").select("*").eq("contributor_id", user.id).execute()
        row = r.data[0] if r.data else None
    except Exception:
        row = None
    st.session_state["_me_id"] = user.id
    st.session_state["_me"] = row
    return row


# -------------------------------------------------- joining the tree

def my_join_status() -> str:
    """'approved', 'pending', 'declined', or 'none'."""
    try:
        return rpc("my_join_status").execute().data or "none"
    except Exception:
        return "none"


def request_to_join(display_name: str, relationship: str, message: str = ""):
    user = current_user()
    return tbl("join_request").insert({
        "user_id": user.id,
        "email": user.email,
        "display_name": display_name.strip(),
        "relationship": relationship.strip() or None,
        "message": message.strip() or None,
    }).execute()


def pending_requests() -> list[dict]:
    try:
        r = (tbl("join_request").select("*")
             .eq("status", "pending").order("requested_at").execute())
        return r.data or []
    except Exception:
        return []


def approve_request(request_id: int) -> str:
    return rpc("approve_join_request", {"p_request_id": request_id}).execute().data


def decline_request(request_id: int) -> str:
    return rpc("decline_join_request", {"p_request_id": request_id}).execute().data


def set_admin(contributor_id: str, make_admin: bool) -> str:
    return rpc("set_contributor_admin", {
        "p_contributor_id": contributor_id,
        "p_is_admin": make_admin,
    }).execute().data


def admins() -> list[dict]:
    try:
        return tbl("v_admins").select("*").execute().data or []
    except Exception:
        return []


# --------------------------------------------------------------- lookups

@st.cache_data(ttl=600, show_spinner=False)
def lookup(table: str, code_col: str) -> list[str]:
    try:
        r = tbl(table).select("*").order("sort_order").execute()
        return [row[code_col] for row in r.data]
    except Exception:
        return []


def sexes():        return lookup("lkp_sex", "sex_code")
def generations():  return lookup("lkp_generation", "generation_code")
def union_status(): return lookup("lkp_union_status", "union_status_code")
def how_ended():    return lookup("lkp_how_ended", "how_ended_code")
def child_rels():   return lookup("lkp_child_relationship", "relationship_code")
def event_types():  return lookup("lkp_event_type", "event_type_code")
def source_types(): return lookup("lkp_source_type", "source_type_code")
def qualities():    return lookup("lkp_evidence_quality", "evidence_quality_code")


GENERATION_HELP = {
    "G0": "Earlier than great-grandparents",
    "G1": "Great-grandparents",
    "G2": "Grandparents",
    "G3": "Parents",
    "G4": "Your generation",
    "G5": "Children",
    "G6": "Grandchildren",
    "G7": "Great-grandchildren",
}


# --------------------------------------------------------------- people

def people(search: str = "", limit: int = 500) -> list[dict]:
    q = tbl("v_individual").select("*")
    if search:
        s = search.replace(",", " ").strip()
        q = q.or_(
            f"given_names.ilike.%{s}%,"
            f"surname_at_birth.ilike.%{s}%,"
            f"also_known_as.ilike.%{s}%,"
            f"individual_id.ilike.%{s}%"
        )
    r = q.order("surname_at_birth").order("birth_year").limit(limit).execute()
    return r.data or []


def person(individual_id: str) -> dict | None:
    r = tbl("v_individual").select("*").eq("individual_id", individual_id).execute()
    return r.data[0] if r.data else None


def add_person(data: dict) -> str:
    clean = {k: v for k, v in data.items() if v not in ("", None)}
    r = tbl("individual").insert(clean).execute()
    return r.data[0]["individual_id"]


def possible_duplicates(given: str, surname: str, birth_year=None) -> list[dict]:
    """
    People already in the tree who look like the same person.

    Deliberately loose: a near-match is worth a second look even when it turns
    out to be a genuine different person. Families reuse names heavily, so this
    warns rather than blocks.
    """
    given = (given or "").strip().lower()
    surname = (surname or "").strip().lower()
    if not given:
        return []

    first = given.split()[0]
    hits = []
    for p in people(limit=2000):
        pg = (p.get("given_names") or "").strip().lower()
        ps = (p.get("surname_at_birth") or "").strip().lower()
        if not pg:
            continue

        same_first = pg.split()[0] == first
        same_full = pg == given
        surname_ok = (ps == surname) or not ps or not surname

        if not ((same_full and surname_ok) or (same_first and ps == surname and surname)):
            continue

        if birth_year and p.get("birth_year"):
            if abs(int(birth_year) - int(p["birth_year"])) > 3:
                continue

        hits.append(p)
    return hits


def update_person(individual_id: str, data: dict):
    clean = {k: (v if v != "" else None) for k, v in data.items()}
    return tbl("individual").update(clean).eq("individual_id", individual_id).execute()


def soft_delete_person(individual_id: str):
    from datetime import datetime, timezone
    return (
        tbl("individual")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("individual_id", individual_id)
        .execute()
    )


def name_of(individual_id: str | None) -> str:
    if not individual_id:
        return ""
    p = person(individual_id)
    return p["full_name"] if p else individual_id


def people_options() -> dict[str, str]:
    """{'I0001 - John HARPER (1888)': 'I0001'} for select boxes."""
    out = {}
    for p in people(limit=2000):
        yr = f" ({p['birth_year']})" if p.get("birth_year") else ""
        out[f"{p['individual_id']} - {p['full_name']}{yr}"] = p["individual_id"]
    return out


# -------------------------------------------------------------- families

def families_of(individual_id: str) -> list[dict]:
    """Unions this person is a partner in."""
    r = (
        tbl("family")
        .select("*")
        .or_(f"partner1_id.eq.{individual_id},partner2_id.eq.{individual_id}")
        .is_("deleted_at", "null")
        .execute()
    )
    return r.data or []


def family(family_id: str) -> dict | None:
    r = tbl("family").select("*").eq("family_id", family_id).execute()
    return r.data[0] if r.data else None


def all_families() -> list[dict]:
    r = tbl("family").select("*").is_("deleted_at", "null").order("family_id").execute()
    return r.data or []


def add_family(data: dict) -> str:
    clean = {k: v for k, v in data.items() if v not in ("", None)}
    r = tbl("family").insert(clean).execute()
    return r.data[0]["family_id"]


def update_family(family_id: str, data: dict):
    clean = {k: (v if v != "" else None) for k, v in data.items()}
    return tbl("family").update(clean).eq("family_id", family_id).execute()


def soft_delete_family(family_id: str):
    """
    Remove a marriage. Any child links hanging off it go too, otherwise
    they would point at a marriage that no longer shows anywhere.
    The PEOPLE are untouched - only the marriage record and its links.
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    for link in children_of_family(family_id):
        tbl("child_link").update({"deleted_at": now}) \
            .eq("child_link_id", link["child_link_id"]).execute()

    return tbl("family").update({"deleted_at": now}) \
        .eq("family_id", family_id).execute()


# ----------------------------------------------------------------- links

def children_of_family(family_id: str) -> list[dict]:
    r = (
        tbl("child_link")
        .select("*")
        .eq("family_id", family_id)
        .is_("deleted_at", "null")
        .order("birth_order")
        .execute()
    )
    return r.data or []


def birth_family_of(individual_id: str) -> dict | None:
    r = (
        tbl("child_link")
        .select("*")
        .eq("child_id", individual_id)
        .is_("deleted_at", "null")
        .execute()
    )
    return r.data[0] if r.data else None


def link_child(family_id: str, child_id: str, birth_order=None, relationship=None):
    row = {"family_id": family_id, "child_id": child_id}
    if birth_order:
        row["birth_order"] = int(birth_order)
    if relationship:
        row["relationship_code"] = relationship
    return tbl("child_link").insert(row).execute()


def unlink_child(child_link_id: int):
    from datetime import datetime, timezone
    return (
        tbl("child_link")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("child_link_id", child_link_id)
        .execute()
    )


def siblings_of(individual_id: str) -> list[dict]:
    bf = birth_family_of(individual_id)
    if not bf:
        return []
    out = []
    for link in children_of_family(bf["family_id"]):
        if link["child_id"] != individual_id:
            p = person(link["child_id"])
            if p:
                out.append(p)
    return out


# ---------------------------------------------------------------- events

def events_of(individual_id: str) -> list[dict]:
    r = (
        tbl("event")
        .select("*")
        .eq("individual_id", individual_id)
        .is_("deleted_at", "null")
        .order("event_year")
        .execute()
    )
    return r.data or []


def add_event(data: dict):
    clean = {k: v for k, v in data.items() if v not in ("", None)}
    return tbl("event").insert(clean).execute()


# --------------------------------------------------------------- sources

def sources() -> list[dict]:
    r = tbl("source").select("*").is_("deleted_at", "null").order("source_id").execute()
    return r.data or []


def add_source(data: dict) -> str:
    clean = {k: v for k, v in data.items() if v not in ("", None)}
    r = tbl("source").insert(clean).execute()
    return r.data[0]["source_id"]


def sources_for_person(individual_id: str) -> list[dict]:
    r = (
        tbl("individual_source")
        .select("*, source(*)")
        .eq("individual_id", individual_id)
        .is_("deleted_at", "null")
        .execute()
    )
    return r.data or []


def cite_person(individual_id: str, source_id: str, applies_to: str = ""):
    return tbl("individual_source").insert({
        "individual_id": individual_id,
        "source_id": source_id,
        "applies_to_fact": applies_to or None,
    }).execute()


# ---------------------------------------------------------------- claims

def claims_for(subject_type: str, subject_id: str) -> list[dict]:
    r = (
        tbl("fact_claim")
        .select("*")
        .eq("subject_type", subject_type)
        .eq("subject_id", subject_id)
        .order("claimed_at", desc=True)
        .execute()
    )
    return r.data or []


def add_claim(subject_type, subject_id, field_name, value, reasoning, source_id=None):
    return tbl("fact_claim").insert({
        "subject_type": subject_type,
        "subject_id": subject_id,
        "field_name": field_name,
        "claimed_value": str(value) if value is not None else None,
        "reasoning": reasoning or None,
        "source_id": source_id or None,
        "claimed_by": (current_user().id if current_user() else None),
    }).execute()


def resolve_claim(claim_id: int, status: str, note: str = ""):
    from datetime import datetime, timezone
    return tbl("fact_claim").update({
        "status": status,
        "resolved_by": (current_user().id if current_user() else None),
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "resolution_note": note or None,
    }).eq("claim_id", claim_id).execute()


def disputed_facts() -> list[dict]:
    r = tbl("v_disputed_facts").select("*").execute()
    return r.data or []


def open_claims() -> list[dict]:
    r = (
        tbl("fact_claim")
        .select("*")
        .eq("status", "open")
        .order("claimed_at", desc=True)
        .limit(200)
        .execute()
    )
    return r.data or []


# ----------------------------------------------------------- change feed

def recent_changes(limit: int = 100) -> list[dict]:
    r = tbl("v_recent_changes").select("*").limit(limit).execute()
    return r.data or []


def changes_for_record(table_name: str, record_id: str) -> list[dict]:
    r = (
        tbl("v_recent_changes")
        .select("*")
        .eq("table_name", table_name)
        .eq("record_id", record_id)
        .execute()
    )
    return r.data or []


def revert(audit_id: int) -> str:
    r = rpc("revert_change", {"p_audit_id": audit_id}).execute()
    return r.data


# --------------------------------------------------------------- reports

def unsourced() -> list[dict]:
    r = tbl("v_unsourced_individuals").select("*").execute()
    return r.data or []


def contributor_activity() -> list[dict]:
    r = tbl("v_contributor_activity").select("*").order("total_edits", desc=True).execute()
    return r.data or []


def contributors() -> list[dict]:
    r = tbl("contributor").select("*").order("display_name").execute()
    return r.data or []


def stats() -> dict:
    def n(table, live_only=True):
        try:
            q = tbl(table).select("*", count="exact").limit(1)
            if live_only:
                q = q.is_("deleted_at", "null")
            return q.execute().count or 0
        except Exception:
            return 0

    return {
        "people": n("individual"),
        "families": n("family"),
        "links": n("child_link"),
        "events": n("event"),
        "sources": n("source"),
        "unsourced": len(unsourced()),
        "disputes": len(disputed_facts()),
    }


# ==================================================================
# ADDING A RELATIVE IN ONE STEP
# ------------------------------------------------------------------
# The database stores people, marriages and child links as three
# separate things. Relatives do not think that way - they think
# "add my father". These functions do all three behind one action.
# ==================================================================

_GEN_ORDER = ["G0", "G1", "G2", "G3", "G4", "G5", "G6", "G7"]


def suggest_generation(anchor_gen, relation: str):
    """Father of a G4 is probably G3; their child probably G5."""
    if not anchor_gen or anchor_gen not in _GEN_ORDER:
        return None
    i = _GEN_ORDER.index(anchor_gen)
    shift = {"father": -1, "mother": -1, "child": 1, "spouse": 0, "sibling": 0}
    j = i + shift.get(relation, 0)
    if 0 <= j < len(_GEN_ORDER):
        return _GEN_ORDER[j]
    return None


def _ensure_birth_family(anchor_id: str) -> str:
    """The family the anchor was born into, creating an empty one if needed."""
    bf = birth_family_of(anchor_id)
    if bf:
        return bf["family_id"]
    fam_id = add_family({})
    link_child(fam_id, anchor_id)
    return fam_id


def add_relative(anchor_id: str, relation: str, person_data: dict,
                 family_id=None, marriage=None):
    """
    Create a person and connect them to anchor_id in one go.

    relation: 'father' | 'mother' | 'spouse' | 'child' | 'sibling'
    Returns (new_individual_id, plain-English description).
    Raises ValueError with a readable message when the link is not possible.
    """
    anchor = person(anchor_id)
    if not anchor:
        raise ValueError("That person is no longer in the tree.")
    anchor_name = anchor["full_name"]

    if relation in ("father", "mother"):
        slot = "partner1_id" if relation == "father" else "partner2_id"
        bf = birth_family_of(anchor_id)

        if bf:
            fam_id = bf["family_id"]
            fam = family(fam_id)
            if fam and fam.get(slot):
                who = name_of(fam[slot])
                raise ValueError(
                    f"{anchor_name} already has a {relation} recorded: {who}. "
                    f"Open {who} to correct that record instead."
                )
            new_id = add_person(person_data)
            update_family(fam_id, {slot: new_id})
        else:
            new_id = add_person(person_data)
            fam_id = add_family({slot: new_id})
            link_child(fam_id, anchor_id)

        return new_id, f"Added as {anchor_name}'s {relation}."

    if relation == "spouse":
        new_id = add_person(person_data)
        row = {"partner1_id": anchor_id, "partner2_id": new_id}
        if marriage:
            row.update({k: v for k, v in marriage.items() if v not in ("", None)})
        add_family(row)
        return new_id, f"Added as {anchor_name}'s spouse or partner."

    if relation == "child":
        fams = families_of(anchor_id)
        if family_id:
            fam_id = family_id
        elif len(fams) == 1:
            fam_id = fams[0]["family_id"]
        elif not fams:
            fam_id = add_family({"partner1_id": anchor_id})
        else:
            raise ValueError(
                f"{anchor_name} has more than one marriage recorded. "
                "Choose which one this child belongs to."
            )
        new_id = add_person(person_data)
        link_child(fam_id, new_id)
        return new_id, f"Added as a child of {anchor_name}."

    if relation == "sibling":
        fam_id = _ensure_birth_family(anchor_id)
        new_id = add_person(person_data)
        link_child(fam_id, new_id)
        return new_id, f"Added as {anchor_name}'s brother or sister."

    raise ValueError(f"Unknown relationship: {relation}")


def marriages_of_labelled(individual_id: str) -> dict:
    """{'with Mary COLE (1912)': 'F0001'} - for choosing between marriages."""
    out = {}
    for f in families_of(individual_id):
        other = f["partner2_id"] if f["partner1_id"] == individual_id else f["partner1_id"]
        label = f"with {name_of(other) or 'partner not recorded'}"
        if f.get("marriage_year"):
            label += f" ({f['marriage_year']})"
        out[label] = f["family_id"]
    return out
