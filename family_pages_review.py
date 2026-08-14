"""Change feed, disagreements, and reports."""

import streamlit as st
import pandas as pd

import family_db as db


VERB = {
    "INSERT": "added",
    "UPDATE": "edited",
    "DELETE": "removed",
    "RESTORE": "brought back",
}


# ===================================================================
# CHANGE FEED
# ===================================================================

def changes_page():
    st.title("What's changed")
    st.caption(
        "Every edit anyone makes, with their name on it. This page is why we "
        "don't need anyone approving changes — if something is wrong, whoever "
        "spots it fixes it, and any change can be undone."
    )

    c = st.columns([2, 2, 1])
    who = c[0].selectbox(
        "Who",
        ["Everyone"] + [x["display_name"] for x in db.contributors()],
    )
    what = c[1].selectbox("What", ["Everything", "Added", "Edited", "Removed"])
    n = c[2].number_input("How many", 10, 300, 50, step=10)

    rows = db.recent_changes(int(n))

    if who != "Everyone":
        rows = [r for r in rows if r["changed_by_name"] == who]
    if what != "Everything":
        want = {"Added": "INSERT", "Edited": "UPDATE", "Removed": "DELETE"}[what]
        rows = [r for r in rows if r["action"] == want]

    if not rows:
        st.info("Nothing matches that filter.")
        return

    for r in rows:
        when = str(r["changed_at"])[:16].replace("T", " ")
        subject = r.get("subject_label") or r["record_id"]
        fields = r.get("changed_fields") or []

        with st.container(border=True):
            cols = st.columns([5, 1])
            cols[0].markdown(
                f"**{r['changed_by_name']}** {VERB.get(r['action'], r['action'].lower())} "
                f"**{subject}**  \n"
                f"<span style='color:#888;font-size:0.85em'>{when} · {r['table_name']} "
                f"{r['record_id']}</span>",
                unsafe_allow_html=True,
            )

            if fields and r.get("old_data") and r.get("new_data"):
                changes = []
                for f in fields:
                    old = r["old_data"].get(f)
                    new = r["new_data"].get(f)
                    changes.append(f"- **{f}**: {_fmt(old)} → {_fmt(new)}")
                cols[0].markdown("\n".join(changes))

            if cols[1].button("Undo", key=f"undo_{r['audit_id']}",
                              help="Put this back the way it was"):
                try:
                    msg = db.revert(r["audit_id"])
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not undo that: {e}")


def _fmt(v):
    if v is None or v == "":
        return "_blank_"
    return f"`{v}`"


# ===================================================================
# DISAGREEMENTS
# ===================================================================

def disputes_page():
    st.title("Disagreements")
    st.caption(
        "Where two people recorded different answers for the same fact. "
        "Nobody's version is deleted — whoever turns up a document settles it."
    )

    disputes = db.disputed_facts()
    claims = db.open_claims()

    if not disputes and not claims:
        st.success("Nothing disputed. Everyone agrees, or nobody has flagged anything yet.")
        st.caption(
            "If you think something in the tree is wrong but are not certain, "
            "open that person and use \"Something here look wrong?\" — it lands here."
        )
        return

    if disputes:
        st.subheader("Facts with competing answers")
        for d in disputes:
            label = db.name_of(d["subject_id"]) if d["subject_type"] == "individual" else d["subject_id"]
            with st.container(border=True):
                st.markdown(f"**{label}** — {d['field_name']}")
                st.write("Competing answers: " + ", ".join(f"`{v}`" for v in d["competing_values"]))
                if st.button("Open this person", key=f"od_{d['subject_id']}_{d['field_name']}"):
                    st.session_state["open_person"] = d["subject_id"]
                    st.rerun()

    if claims:
        st.subheader("Everything flagged")
        contribs = {c["contributor_id"]: c["display_name"] for c in db.contributors()}
        for c in claims:
            label = db.name_of(c["subject_id"]) if c["subject_type"] == "individual" else c["subject_id"]
            who = contribs.get(c.get("claimed_by"), "Automatic check")
            with st.container(border=True):
                st.markdown(f"**{label}** — {c['field_name']} should be `{c['claimed_value']}`")
                st.caption(f"{who} · {str(c['claimed_at'])[:10]}")
                if c.get("reasoning"):
                    st.write(c["reasoning"])

                cols = st.columns(3)
                if cols[0].button("This is right", key=f"acc_{c['claim_id']}"):
                    db.resolve_claim(c["claim_id"], "accepted")
                    st.success("Marked as settled. Remember to edit the person too.")
                    st.rerun()
                if cols[1].button("Not right", key=f"rej_{c['claim_id']}"):
                    db.resolve_claim(c["claim_id"], "superseded")
                    st.rerun()
                if cols[2].button("Withdraw", key=f"wd_{c['claim_id']}"):
                    db.resolve_claim(c["claim_id"], "withdrawn")
                    st.rerun()


# ===================================================================
# REPORTS
# ===================================================================

def reports_page():
    st.title("Reports")

    tabs = st.tabs(["Everyone", "Needs a source", "Who's contributed", "Download"])

    with tabs[0]:
        rows = db.people(limit=2000)
        if not rows:
            st.caption("Nothing yet.")
        else:
            df = pd.DataFrame(rows)
            gen = st.multiselect("Generation", sorted(
                [g for g in df["generation_code"].dropna().unique()]))
            if gen:
                df = df[df["generation_code"].isin(gen)]
            st.caption(f"{len(df)} people")
            st.dataframe(
                df[["individual_id", "full_name", "birth_year", "birth_place",
                    "death_year", "father_name", "mother_name", "generation_code"]],
                use_container_width=True, hide_index=True, height=460,
            )

    with tabs[1]:
        st.caption(
            "A name with no source behind it is a hypothesis. These are the "
            "people most worth spending research time on."
        )
        rows = db.unsourced()
        if not rows:
            st.success("Everyone has at least one source. That is unusual and good.")
        else:
            st.warning(f"{len(rows)} people have no source.")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tabs[2]:
        rows = db.contributor_activity()
        if rows:
            df = pd.DataFrame(rows)[
                ["display_name", "relationship", "records_added", "records_edited",
                 "total_edits", "last_edit"]
            ].rename(columns={
                "display_name": "Name",
                "relationship": "Who they are",
                "records_added": "Added",
                "records_edited": "Edited",
                "total_edits": "Total",
                "last_edit": "Last active",
            })
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.caption(
            "Take a copy for yourself. **Living people are left out** of the "
            "shared download — a birth date plus a mother's maiden name is most "
            "of what someone needs to impersonate you."
        )
        rows = db.people(limit=5000)
        if not rows:
            st.caption("Nothing to download yet.")
            return

        include_living = st.checkbox(
            "Include living people (keep this file private)", value=False
        )
        df = pd.DataFrame(rows)
        if not include_living:
            df = df[~df["is_living"].fillna(False)]

        st.download_button(
            "Download as CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name="family_tree.csv",
            mime="text/csv",
        )
        st.caption(f"{len(df)} people in this file.")


def approvals_page():
    st.title("Approvals")
    st.caption(
        "Relatives who have signed up and are waiting to be let in. "
        "Approving takes one click — no SQL, no copying IDs around."
    )

    pending = db.pending_requests()

    if not pending:
        st.success("Nobody waiting.")
    else:
        for r in pending:
            with st.container(border=True):
                st.markdown(f"### {r['display_name']}")
                bits = [x for x in [r.get("relationship"), r.get("email")] if x]
                if bits:
                    st.caption(" · ".join(bits))
                if r.get("message"):
                    st.write(f"_{r['message']}_")
                st.caption(f"Asked {str(r['requested_at'])[:16].replace('T', ' ')}")

                c = st.columns([1, 1, 3])
                if c[0].button("Approve", key=f"ap_{r['request_id']}",
                               type="primary", use_container_width=True):
                    try:
                        st.success(db.approve_request(r["request_id"]))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not approve: {e}")
                if c[1].button("Decline", key=f"dc_{r['request_id']}",
                               use_container_width=True):
                    try:
                        db.decline_request(r["request_id"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not decline: {e}")

    st.divider()
    st.subheader("Who can edit the tree")

    rows = db.contributors()
    if not
