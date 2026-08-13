"""People pages: search, profile, add, edit."""

import streamlit as st
import pandas as pd

import family_db as db


# ===================================================================
# BROWSE / SEARCH
# ===================================================================

def browse():
    st.title("Find a person")

    if st.session_state.get("open_person"):
        _profile(st.session_state["open_person"])
        return

    search = st.text_input(
        "Search by name",
        placeholder="Harper, or Mary, or I0001",
        help="Maiden names are recorded under the surname a woman was born with.",
    )

    rows = db.people(search)
    if not rows:
        st.info("Nobody found." if search else "The tree is empty. Add someone to start.")
        return

    st.caption(f"{len(rows)} people")

    df = pd.DataFrame(rows)
    show = df[[
        "individual_id", "full_name", "birth_year", "birth_place",
        "death_year", "generation_code", "is_living",
    ]].rename(columns={
        "individual_id": "ID",
        "full_name": "Name",
        "birth_year": "Born",
        "birth_place": "Birthplace",
        "death_year": "Died",
        "generation_code": "Gen",
        "is_living": "Living",
    })

    st.dataframe(show, use_container_width=True, hide_index=True, height=340)

    options = {f"{r['individual_id']} - {r['full_name']}": r["individual_id"] for r in rows}
    pick = st.selectbox("Open someone", ["-"] + list(options.keys()))
    if pick != "-":
        st.session_state["open_person"] = options[pick]
        st.rerun()


# ===================================================================
# PROFILE
# ===================================================================

def _profile(individual_id: str):
    p = db.person(individual_id)
    if not p:
        st.error("That person is not in the tree (they may have been removed).")
        if st.button("Back"):
            del st.session_state["open_person"]
            st.rerun()
        return

    top = st.columns([5, 1])
    top[0].title(p["full_name"] or individual_id)
    if top[1].button("← Back", use_container_width=True):
        del st.session_state["open_person"]
        st.rerun()

    bits = [individual_id]
    if p.get("birth_year"):
        bits.append(f"born {p['birth_year']}")
    if p.get("death_year"):
        bits.append(f"died {p['death_year']}")
    if p.get("age_at_death"):
        bits.append(f"aged {p['age_at_death']}")
    if p.get("is_living"):
        bits.append("living")
    st.caption(" · ".join(bits))

    tabs = st.tabs(["Details", "Family", "Life events", "Sources", "Edit", "History"])

    with tabs[0]:
        _details(p)
    with tabs[1]:
        _family_section(p)
    with tabs[2]:
        _events(p)
    with tabs[3]:
        _sources(p)
    with tabs[4]:
        _edit_form(p)
    with tabs[5]:
        _history(individual_id)


def _details(p):
    c = st.columns(2)
    with c[0]:
        st.markdown("**Born**")
        st.write(p.get("birth_date_text") or "—")
        st.write(p.get("birth_place") or "")
        st.markdown("**Died**")
        st.write(p.get("death_date_text") or "—")
        st.write(p.get("death_place") or "")
        if p.get("burial_place"):
            st.markdown("**Buried**")
            st.write(p["burial_place"])
    with c[1]:
        st.markdown("**Also known as**")
        st.write(p.get("also_known_as") or "—")
        st.markdown("**Occupation**")
        st.write(p.get("occupation") or "—")
        st.markdown("**Generation**")
        g = p.get("generation_code")
        st.write(f"{g} — {db.GENERATION_HELP.get(g, '')}" if g else "—")

    if p.get("notes"):
        st.markdown("**Notes**")
        st.write(p["notes"])

    st.divider()
    with st.expander("Something here look wrong?"):
        st.caption(
            "If you are sure, edit it on the Edit tab. If you are not sure, "
            "record it here instead — both versions are kept and whoever finds "
            "a document settles it."
        )
        with st.form(f"claim_{p['individual_id']}"):
            field = st.selectbox("Which fact", [
                "birth_date_text", "birth_year", "birth_place",
                "death_date_text", "death_year", "death_place",
                "given_names", "surname_at_birth", "occupation",
            ])
            value = st.text_input("What you believe it should be")
            why = st.text_area("How do you know?", placeholder="Grandma's bible has 1892")
            if st.form_submit_button("Record this"):
                if not value:
                    st.error("Please enter what you think it should be.")
                else:
                    db.add_claim("individual", p["individual_id"], field, value, why)
                    st.success("Recorded. It now shows on the Disagreements page.")


def _family_section(p):
    pid = p["individual_id"]

    st.markdown("### Parents")
    if p.get("father_id") or p.get("mother_id"):
        for label, key, nkey in [("Father", "father_id", "father_name"),
                                 ("Mother", "mother_id", "mother_name")]:
            if p.get(key):
                if st.button(f"{label}: {p.get(nkey) or p[key]}", key=f"go_{key}_{pid}"):
                    st.session_state["open_person"] = p[key]
                    st.rerun()
    else:
        st.caption("Not recorded. Add them on the Marriages & children page.")

    sibs = db.siblings_of(pid)
    if sibs:
        st.markdown("### Brothers and sisters")
        for s in sibs:
            yr = f" ({s['birth_year']})" if s.get("birth_year") else ""
            if st.button(f"{s['full_name']}{yr}", key=f"sib_{s['individual_id']}_{pid}"):
                st.session_state["open_person"] = s["individual_id"]
                st.rerun()

    fams = db.families_of(pid)
    if fams:
        st.markdown("### Marriages and children")
    for f in fams:
        other = f["partner2_id"] if f["partner1_id"] == pid else f["partner1_id"]
        header = db.name_of(other) or "partner not recorded"
        yr = f" — married {f['marriage_year']}" if f.get("marriage_year") else ""
        st.markdown(f"**{header}**{yr}  \n<span style='color:#888'>{f['family_id']}</span>",
                    unsafe_allow_html=True)
        kids = db.children_of_family(f["family_id"])
        if not kids:
            st.caption("No children recorded.")
        for k in kids:
            kid = db.person(k["child_id"])
            if not kid:
                continue
            byr = f" ({kid['birth_year']})" if kid.get("birth_year") else ""
            rel = f" · {k['relationship_code']}" if k.get("relationship_code") not in (None, "Natural") else ""
            if st.button(f"↳ {kid['full_name']}{byr}{rel}",
                         key=f"kid_{k['child_link_id']}"):
                st.session_state["open_person"] = k["child_id"]
                st.rerun()


def _events(p):
    evs = db.events_of(p["individual_id"])
    if evs:
        for e in evs:
            st.markdown(
                f"**{e.get('event_type_code') or 'Event'}** — "
                f"{e.get('event_date_text') or e.get('event_year') or ''}"
            )
            if e.get("event_place"):
                st.caption(e["event_place"])
            if e.get("description"):
                st.write(e["description"])
            st.divider()
    else:
        st.caption("Nothing recorded yet.")

    with st.expander("Add a life event"):
        with st.form(f"ev_{p['individual_id']}"):
            etype = st.selectbox("Type", db.event_types())
            date_text = st.text_input("Date", placeholder="14 MAR 1948, or ABT 1948")
            year = st.number_input("Year", 1000, 2100, step=1, value=None)
            place = st.text_input("Place", placeholder="Town, County, State, Country")
            desc = st.text_area("What happened")
            if st.form_submit_button("Save"):
                db.add_event({
                    "individual_id": p["individual_id"],
                    "event_type_code": etype,
                    "event_date_text": date_text,
                    "event_year": int(year) if year else None,
                    "event_place": place,
                    "description": desc,
                })
                st.success("Added.")
                st.rerun()


def _sources(p):
    st.caption(
        "A source is how we know something is true. A certificate beats a "
        "recollection, but a recollection beats nothing at all."
    )
    cites = db.sources_for_person(p["individual_id"])
    if cites:
        for c in cites:
            s = c.get("source") or {}
            st.markdown(f"**{s.get('source_title', c['source_id'])}**")
            meta = " · ".join(x for x in [
                s.get("source_type_code"),
                s.get("evidence_quality_code"),
                c.get("applies_to_fact"),
            ] if x)
            if meta:
                st.caption(meta)
    else:
        st.caption("No sources yet for this person.")

    with st.expander("Cite a source"):
        existing = db.sources()
        opts = {f"{s['source_id']} - {s['source_title']}": s["source_id"] for s in existing}
        mode = st.radio("Source", ["Use an existing one", "Add a new one"],
                        horizontal=True, key=f"srcmode_{p['individual_id']}")

        if mode == "Use an existing one" and opts:
            with st.form(f"cite_{p['individual_id']}"):
                pick = st.selectbox("Which source", list(opts.keys()))
                fact = st.text_input("What does it prove?", placeholder="Birth date")
                if st.form_submit_button("Cite it"):
                    db.cite_person(p["individual_id"], opts[pick], fact)
                    st.success("Cited.")
                    st.rerun()
        else:
            with st.form(f"newsrc_{p['individual_id']}"):
                title = st.text_input("Title", placeholder="1930 US Federal Census")
                stype = st.selectbox("Type", db.source_types())
                qual = st.selectbox("Quality", db.qualities(),
                                    help="Original = made at the time. Authored = someone's conclusion.")
                repo = st.text_input("Where is it held?")
                detail = st.text_input("Reference", placeholder="Sheet 4B, line 21")
                fact = st.text_input("What does it prove?", placeholder="Birth date")
                if st.form_submit_button("Add and cite"):
                    if not title:
                        st.error("A title is needed.")
                    else:
                        sid = db.add_source({
                            "source_title": title,
                            "source_type_code": stype,
                            "evidence_quality_code": qual,
                            "repository": repo,
                            "citation_detail": detail,
                        })
                        db.cite_person(p["individual_id"], sid, fact)
                        st.success(f"Added {sid}.")
                        st.rerun()


def _edit_form(p):
    st.caption("Everyone can edit. Your name goes on the change, and it can always be undone.")
    with st.form(f"edit_{p['individual_id']}"):
        c = st.columns(2)
        with c[0]:
            given = st.text_input("Given names", p.get("given_names") or "")
            surname = st.text_input("Surname at birth", p.get("surname_at_birth") or "",
                                    help="For a married woman, her maiden name.")
            aka = st.text_input("Also known as", p.get("also_known_as") or "")
            suffix = st.text_input("Suffix", p.get("suffix") or "")
            sex = _sel("Sex", db.sexes(), p.get("sex_code"))
            gen = _sel("Generation", db.generations(), p.get("generation_code"))
            living = st.checkbox("Still living", value=bool(p.get("is_living")))
        with c[1]:
            bdate = st.text_input("Birth date", p.get("birth_date_text") or "",
                                  help="14 MAR 1948, or ABT 1948, or BEF 1950")
            byear = st.number_input("Birth year", 1000, 2100, step=1,
                                    value=p.get("birth_year") or None)
            bplace = st.text_input("Birth place", p.get("birth_place") or "")
            ddate = st.text_input("Death date", p.get("death_date_text") or "")
            dyear = st.number_input("Death year", 1000, 2100, step=1,
                                    value=p.get("death_year") or None)
            dplace = st.text_input("Death place", p.get("death_place") or "")
            burial = st.text_input("Buried at", p.get("burial_place") or "")

        occ = st.text_input("Occupation", p.get("occupation") or "")
        notes = st.text_area("Notes", p.get("notes") or "", height=100)

        if st.form_submit_button("Save changes", type="primary"):
            try:
                db.update_person(p["individual_id"], {
                    "given_names": given,
                    "surname_at_birth": surname,
                    "also_known_as": aka,
                    "suffix": suffix,
                    "sex_code": sex,
                    "generation_code": gen,
                    "is_living": living,
                    "birth_date_text": bdate,
                    "birth_year": int(byear) if byear else None,
                    "birth_place": bplace,
                    "death_date_text": ddate,
                    "death_year": int(dyear) if dyear else None,
                    "death_place": dplace,
                    "burial_place": burial,
                    "occupation": occ,
                    "notes": notes,
                })
                st.success("Saved.")
                st.rerun()
            except Exception as e:
                st.error(_friendly(e))

    with st.expander("Remove this person"):
        st.caption(
            "They disappear from the tree but are never destroyed — anything "
            "removed can be brought back from the What's changed page."
        )
        if st.button("Remove", key=f"del_{p['individual_id']}"):
            try:
                db.soft_delete_person(p["individual_id"])
                st.session_state.pop("open_person", None)
                st.rerun()
            except Exception as e:
                st.error(_friendly(e))


def _history(individual_id):
    rows = db.changes_for_record("individual", individual_id)
    if not rows:
        st.caption("No changes recorded.")
        return
    for r in rows:
        when = str(r["changed_at"])[:16].replace("T", " ")
        fields = r.get("changed_fields") or []
        st.markdown(f"**{r['changed_by_name']}** — {r['action'].lower()} — {when}")
        if fields and r.get("old_data") and r.get("new_data"):
            for f in fields:
                old = r["old_data"].get(f)
                new = r["new_data"].get(f)
                st.caption(f"{f}: {old!r} → {new!r}")
        st.divider()


# ===================================================================
# ADD
# ===================================================================

def add_person_form():
    st.title("Add a person")
    st.caption(
        "Approximate is better than a guess. Write \"about 1948\" rather than "
        "inventing a date — a wrong date sends everyone hunting the wrong records."
    )

    with st.form("addperson"):
        c = st.columns(2)
        with c[0]:
            given = st.text_input("Given names *", placeholder="William John, not Bill")
            surname = st.text_input("Surname at birth",
                                    help="For a married woman, her maiden name.")
            aka = st.text_input("Also known as", placeholder="Bill, or married surname")
            sex = _sel("Sex", db.sexes(), None)
            gen = _sel("Generation", db.generations(), None)
            living = st.checkbox("Still living", value=True)
        with c[1]:
            bdate = st.text_input("Birth date", placeholder="14 MAR 1948, or ABT 1948")
            byear = st.number_input("Birth year", 1000, 2100, step=1, value=None,
                                    help="Used for sorting. Fill it even if the date is approximate.")
            bplace = st.text_input("Birth place", placeholder="Town, County, State, Country")
            ddate = st.text_input("Death date")
            dyear = st.number_input("Death year", 1000, 2100, step=1, value=None)
            dplace = st.text_input("Death place")

        occ = st.text_input("Occupation")
        notes = st.text_area("Anything else worth recording", height=90)

        if st.form_submit_button("Add to the tree", type="primary"):
            if not given.strip():
                st.error("At least a given name is needed.")
            else:
                try:
                    new_id = db.add_person({
                        "given_names": given.strip(),
                        "surname_at_birth": surname.strip(),
                        "also_known_as": aka.strip(),
                        "sex_code": sex,
                        "generation_code": gen,
                        "is_living": living,
                        "birth_date_text": bdate,
                        "birth_year": int(byear) if byear else None,
                        "birth_place": bplace,
                        "death_date_text": ddate,
                        "death_year": int(dyear) if dyear else None,
                        "death_place": dplace,
                        "occupation": occ,
                        "notes": notes,
                    })
                    st.success(f"Added as {new_id}.")
                    st.info(
                        "Now connect them: use **Marriages & children** to record "
                        "their parents, spouse, or children."
                    )
                except Exception as e:
                    st.error(_friendly(e))


# ===================================================================
# HELPERS
# ===================================================================

def _sel(label, options, current, **kw):
    opts = [""] + list(options)
    idx = opts.index(current) if current in opts else 0
    v = st.selectbox(label, opts, index=idx, **kw)
    return v or None


def _friendly(e) -> str:
    """Turn a Postgres constraint error into something a relative understands."""
    msg = str(e)
    table = {
        "death_after_birth": "That death year is before the birth year.",
        "birth_year_sane": "That birth year is not a plausible year.",
        "death_year_sane": "That death year is not a plausible year.",
        "marriage_year_sane": "That marriage year is not a plausible year.",
        "not_self_married": "A person cannot be married to themselves.",
        "event_one_subject": "An event belongs to one person or one marriage, not both.",
        "own parent": "A person cannot be their own parent.",
        "Hard delete is not allowed": "Records here are never destroyed — use Remove instead.",
        "idx_child_link_unique": "That child is already linked to that family.",
    }
    for key, friendly in table.items():
        if key in msg:
            return friendly
    return f"Could not save that: {msg}"
