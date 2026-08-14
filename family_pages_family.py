"""Marriages, parent-child links, and the visual tree."""

import streamlit as st

import family_db as db
from family_pages_people import _friendly, _sel


# ===================================================================
# MARRIAGES AND CHILDREN
# ===================================================================

def families_page():
    st.title("Marriages & children")
    st.caption(
        "This is what actually connects the tree. A child is linked to a "
        "marriage rather than to a person, which is how second marriages and "
        "half-brothers and sisters come out right."
    )

    tab_link, tab_new, tab_list = st.tabs(
        ["Link a child to parents", "Record a marriage", "All marriages"]
    )

    with tab_new:
        _new_family()
    with tab_link:
        _link_child()
    with tab_list:
        _list_families()


def _new_family():
    opts = db.people_options()
    if len(opts) < 1:
        st.info("Add some people first.")
        return

    if st.session_state.get("_just_married"):
        m = st.session_state["_just_married"]
        st.success(f"Saved **{m['label']}** as {m['id']}.")
        st.info("Next: link their children on the first tab.")
        c = st.columns(2)
        if c[0].button("Record another marriage", type="primary",
                       use_container_width=True):
            del st.session_state["_just_married"]
            st.rerun()
        if c[1].button("Done", use_container_width=True):
            del st.session_state["_just_married"]
            st.rerun()
        return

    st.caption(
        "Record a marriage or partnership. For someone who married twice, "
        "record two separate marriages — that is what keeps the children straight."
    )

    with st.form("newfam", clear_on_submit=True):
        c = st.columns(2)
        p1 = c[0].selectbox("Partner 1", ["-"] + list(opts.keys()))
        p2 = c[1].selectbox("Partner 2", ["-"] + list(opts.keys()))

        c2 = st.columns(2)
        status = c2[0].selectbox("Status", [""] + db.union_status())
        ended = c2[1].selectbox("How it ended", [""] + db.how_ended())

        c3 = st.columns(3)
        mdate = c3[0].text_input("Marriage date", placeholder="22 DEC 1912")
        myear = c3[1].number_input("Year", 1000, 2100, step=1, value=None)
        mplace = c3[2].text_input("Place")

        notes = st.text_area("Notes")

        submitted = st.form_submit_button("Save marriage", type="primary")

    if not submitted:
        return

    if p1 == "-" and p2 == "-":
        st.error("Choose at least one partner.")
        return
    if p1 != "-" and p1 == p2:
        st.error("A person cannot marry themselves.")
        return

    id1, id2 = opts.get(p1), opts.get(p2)

    # Already recorded? Two rows for the same couple is the usual double-click.
    for f in db.all_families():
        pair_now = {id1, id2} - {None}
        pair_old = {f.get("partner1_id"), f.get("partner2_id")} - {None}
        if pair_now and pair_now == pair_old:
            st.warning(
                f"That couple is already recorded as **{f['family_id']}**. "
                "Not saving a second one — see 'All marriages' to edit it."
            )
            return

    try:
        fid = db.add_family({
            "partner1_id": id1,
            "partner2_id": id2,
            "union_status_code": status or None,
            "how_ended_code": ended or None,
            "marriage_date_text": mdate,
            "marriage_year": int(myear) if myear else None,
            "marriage_place": mplace,
            "notes": notes,
        })
        label = " & ".join(x for x in [db.name_of(id1), db.name_of(id2)] if x)
        st.session_state["_just_married"] = {"id": fid, "label": label}
        st.rerun()
    except Exception as e:
        st.error(_friendly(e))


def _link_child():
    fams = db.all_families()
    if not fams:
        st.info("Record a marriage first — children attach to a marriage.")
        return

    if st.session_state.get("_just_linked"):
        j = st.session_state["_just_linked"]
        st.success(f"Linked **{j['child']}** to {j['family']}.")
        c = st.columns(2)
        if c[0].button("Link another child", type="primary", use_container_width=True):
            del st.session_state["_just_linked"]
            st.rerun()
        if c[1].button("Done", use_container_width=True):
            del st.session_state["_just_linked"]
            st.rerun()
        return

    people_opts = db.people_options()
    fam_opts = {}
    for f in fams:
        n1 = db.name_of(f["partner1_id"]) or "?"
        n2 = db.name_of(f["partner2_id"]) or "?"
        yr = f" ({f['marriage_year']})" if f.get("marriage_year") else ""
        fam_opts[f"{f['family_id']} - {n1} & {n2}{yr}"] = f["family_id"]

    with st.form("linkchild", clear_on_submit=True):
        fam_pick = st.selectbox("Whose child?", list(fam_opts.keys()))
        child_pick = st.selectbox("Which child", ["-"] + list(people_opts.keys()))
        c = st.columns(2)
        order = c[0].number_input("Birth order", 1, 30, step=1, value=None,
                                  help="1 = eldest. Leave blank if unsure.")
        rel = c[1].selectbox("Relationship", db.child_rels())
        submitted = st.form_submit_button("Link", type="primary")

    if not submitted:
        return

    if child_pick == "-":
        st.error("Choose a child.")
        return

    fid = fam_opts[fam_pick]
    cid = people_opts[child_pick]

    if any(l["child_id"] == cid for l in db.children_of_family(fid)):
        st.warning("That child is already linked to that marriage.")
        return

    try:
        db.link_child(fid, cid, order, rel)
        st.session_state["_just_linked"] = {
            "child": db.name_of(cid),
            "family": fam_pick.split(" - ", 1)[-1],
        }
        st.rerun()
    except Exception as e:
        st.error(_friendly(e))


def _list_families():
    fams = db.all_families()
    if not fams:
        st.caption("No marriages recorded yet.")
        return

    st.caption(
        "Everything recorded so far. Open one to see its children, or to "
        "remove a duplicate."
    )

    for f in fams:
        n1 = db.name_of(f["partner1_id"]) or "—"
        n2 = db.name_of(f["partner2_id"]) or "—"
        yr = f" · married {f['marriage_year']}" if f.get("marriage_year") else ""
        with st.expander(f"{n1} & {n2}{yr}"):
            st.caption(f["family_id"])
            if f.get("marriage_place"):
                st.write(f"Married at {f['marriage_place']}")
            if f.get("union_status_code"):
                st.write(f"Status: {f['union_status_code']}")

            kids = db.children_of_family(f["family_id"])
            if kids:
                st.markdown("**Children**")
                for k in kids:
                    kid = db.person(k["child_id"])
                    if not kid:
                        continue
                    byr = f" ({kid['birth_year']})" if kid.get("birth_year") else ""
                    rel = ""
                    if k.get("relationship_code") and k["relationship_code"] != "Natural":
                        rel = f" — {k['relationship_code']}"
                    cols = st.columns([5, 1])
                    cols[0].write(f"{k.get('birth_order') or '·'}. {kid['full_name']}{byr}{rel}")
                    if cols[1].button("Unlink", key=f"ul_{k['child_link_id']}"):
                        db.unlink_child(k["child_link_id"])
                        st.rerun()
            else:
                st.caption("No children recorded.")

            st.divider()
            key = f"delfam_{f['family_id']}"
            if st.session_state.get(key):
                st.warning(
                    f"Remove this marriage? {len(kids)} child link(s) will be "
                    f"removed with it. **{n1} and {n2} themselves are not "
                    "touched.** This can be undone from What's changed."
                )
                c = st.columns(2)
                if c[0].button("Yes, remove it", key=f"yes_{f['family_id']}",
                               type="primary", use_container_width=True):
                    try:
                        db.soft_delete_family(f["family_id"])
                        del st.session_state[key]
                        st.rerun()
                    except Exception as e:
                        st.error(_friendly(e))
                if c[1].button("Cancel", key=f"no_{f['family_id']}",
                               use_container_width=True):
                    del st.session_state[key]
                    st.rerun()
            else:
                if st.button("Remove this marriage", key=f"ask_{f['family_id']}"):
                    st.session_state[key] = True
                    st.rerun()


# ===================================================================
# TREE VIEW
# ===================================================================

def tree_page():
    st.title("Ancestors & descendants")

    opts = db.people_options()
    if not opts:
        st.info("Add some people first.")
        return

    c = st.columns([3, 1, 1])
    pick = c[0].selectbox("Start from", list(opts.keys()))
    direction = c[1].radio("Show", ["Ancestors", "Descendants"])
    depth = c[2].slider("Generations", 1, 5, 3)

    root = opts[pick]

    if direction == "Ancestors":
        dot = _ancestor_dot(root, depth)
    else:
        dot = _descendant_dot(root, depth)

    st.graphviz_chart(dot, use_container_width=True)

    st.caption(
        "Boxes are people. A missing branch means the parents are not recorded "
        "yet, not that they are unknown to the family — go and add them."
    )


def _label(pid: str) -> str:
    p = db.person(pid)
    if not p:
        return pid
    name = (p["full_name"] or pid).replace('"', "'")
    years = ""
    if p.get("birth_year") or p.get("death_year"):
        years = f"\\n{p.get('birth_year') or '?'}–{p.get('death_year') or ''}"
    return f"{name}{years}"


def _ancestor_dot(root: str, max_depth: int) -> str:
    lines = ["digraph G {", "rankdir=BT;",
             'node [shape=box style="rounded,filled" fillcolor="#f5f2ea" '
             'fontname="Helvetica" fontsize=10];',
             'edge [color="#888888"];']
    seen = set()

    def walk(pid, d):
        if d > max_depth or pid in seen:
            return
        seen.add(pid)
        lines.append(f'"{pid}" [label="{_label(pid)}"];')
        p = db.person(pid)
        if not p:
            return
        for parent in (p.get("father_id"), p.get("mother_id")):
            if parent:
                walk(parent, d + 1)
                lines.append(f'"{parent}" -> "{pid}";')

    walk(root, 0)
    lines.append(f'"{root}" [fillcolor="#d4e4d4" penwidth=2];')
    lines.append("}")
    return "\n".join(lines)


def _descendant_dot(root: str, max_depth: int) -> str:
    lines = ["digraph G {", "rankdir=TB;",
             'node [shape=box style="rounded,filled" fillcolor="#f5f2ea" '
             'fontname="Helvetica" fontsize=10];',
             'edge [color="#888888"];']
    seen = set()

    def walk(pid, d):
        if d > max_depth or pid in seen:
            return
        seen.add(pid)
        lines.append(f'"{pid}" [label="{_label(pid)}"];')
        for f in db.families_of(pid):
            for link in db.children_of_family(f["family_id"]):
                child = link["child_id"]
                walk(child, d + 1)
                lines.append(f'"{pid}" -> "{child}";')

    walk(root, 0)
    lines.append(f'"{root}" [fillcolor="#d4e4d4" penwidth=2];')
    lines.append("}")
    return "\n".join(lines)
