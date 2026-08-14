"""
Family Tree - collaborative family history for the whole family.

Entry point. Handles sign in, then routes to the pages.

Anyone in the family can add and edit. Nothing is ever lost: every change
is recorded with who made it, deletions are recoverable, and where two
people disagree both versions are kept.
"""

import streamlit as st

import family_db as db

st.set_page_config(
    page_title="Family Tree",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ===================================================================
# SIGN IN
# ===================================================================

def login_screen():
    st.title("🌳 Our Family Tree")
    st.caption("A shared record of where we come from.")

    tab_in, tab_new, tab_forgot = st.tabs(["Sign in", "Create account", "Forgot password"])

    with tab_in:
        with st.form("signin"):
            email = st.text_input("Email")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                try:
                    db.sign_in(email.strip(), pw)
                    st.session_state.pop("_me", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not sign in: {e}")

    with tab_new:
        st.info(
            "Anyone in the family is welcome. After you create an account, "
            "tell us who you are and an admin will let you in."
        )
        with st.form("signup"):
            email = st.text_input("Email", key="su_email")
            pw = st.text_input("Choose a password", type="password", key="su_pw")
            pw2 = st.text_input("Type it again", type="password", key="su_pw2")
            if st.form_submit_button("Create account", use_container_width=True):
                if pw != pw2:
                    st.error("The two passwords do not match.")
                elif len(pw) < 8:
                    st.error("Please use at least 8 characters.")
                else:
                    try:
                        db.sign_up(email.strip(), pw)
                        st.success("Account created. Now sign in on the first tab.")
                    except Exception as e:
                        st.error(f"Could not create the account: {e}")

    with tab_forgot:
        with st.form("forgot"):
            email = st.text_input("Your email", key="fp_email")
            if st.form_submit_button("Email me a reset link", use_container_width=True):
                try:
                    db.send_reset(email.strip())
                    st.success("Check your email.")
                except Exception as e:
                    st.error(f"Could not send it: {e}")


def join_request_screen(user):
    """Shown to someone who has signed in but is not yet a contributor."""
    st.title("🌳 Our Family Tree")

    status = db.my_join_status()

    if status == "pending":
        st.info("**Your request is in.** An admin will let you in shortly.")
        st.caption(
            "You will not need to do anything else — next time you sign in, "
            "you will be straight into the tree."
        )
        st.caption(f"Signed in as {user.email}")
        if st.button("Sign out"):
            db.sign_out()
            st.rerun()
        return

    if status == "declined":
        st.warning("That request was not approved. Have a word with Allen.")
        if st.button("Sign out"):
            db.sign_out()
            st.rerun()
        return

    st.write(
        "Welcome. Tell us who you are and you will be let in — usually the "
        "same day."
    )

    with st.form("joinreq"):
        name = st.text_input(
            "Your name *",
            placeholder="Alden DoRosario",
            help="How the family knows you. This appears next to anything you add.",
        )
        rel = st.text_input(
            "How are you related?",
            placeholder="Allen's cousin, Ruth's son",
        )
        msg = st.text_area(
            "Anything you want to add",
            placeholder="I have Grandma's photo albums and her old bible.",
            height=80,
        )
        if st.form_submit_button("Ask to join", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Please tell us your name.")
            else:
                try:
                    db.request_to_join(name, rel, msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not send that: {e}")

    st.caption(f"Signed in as {user.email}")
    if st.button("Sign out"):
        db.sign_out()
        st.rerun()


# ===================================================================
# ROUTING
# ===================================================================

def main():
    user = db.current_user()
    if not user:
        login_screen()
        return

    contributor = db.me()
    if not contributor:
        join_request_screen(user)
        return

    import family_pages_people as pp
    import family_pages_family as pf
    import family_pages_review as pr

    with st.sidebar:
        st.markdown("### 🌳 Family Tree")
        st.caption(f"Signed in as **{contributor['display_name']}**")

        pages = [
            "Home",
            "Find a person",
            "Add a person",
            "Marriages & children",
            "Ancestors & descendants",
            "What's changed",
            "Disagreements",
            "Reports",
        ]
        waiting = 0
        if contributor.get("is_admin"):
            waiting = len(db.pending_requests())
            pages.append(f"Approvals ({waiting})" if waiting else "Approvals")

        page = st.radio("Go to", pages, label_visibility="collapsed")

        if waiting:
            st.warning(f"{waiting} waiting to join")

        st.divider()
        if st.button("Sign out", use_container_width=True):
            db.sign_out()
            st.rerun()

        st.caption(
            "Everything you add is credited to you. "
            "Nothing here can be permanently deleted."
        )

    if page == "Home":
        home(contributor)
    elif page == "Find a person":
        pp.browse()
    elif page == "Add a person":
        pp.add_person_form()
    elif page == "Marriages & children":
        pf.families_page()
    elif page == "Ancestors & descendants":
        pf.tree_page()
    elif page == "What's changed":
        pr.changes_page()
    elif page == "Disagreements":
        pr.disputes_page()
    elif page == "Reports":
        pr.reports_page()
    elif page.startswith("Approvals"):
        pr.approvals_page()


# ===================================================================
# HOME
# ===================================================================

def home(contributor):
    st.title("🌳 Our Family Tree")
    st.write(f"Welcome back, {contributor['display_name'].split()[0]}.")

    s = db.stats()
    c = st.columns(4)
    c[0].metric("People", s["people"])
    c[1].metric("Marriages", s["families"])
    c[2].metric("Events recorded", s["events"])
    c[3].metric("Sources", s["sources"])

    if s["people"] == 0:
        st.info(
            "The tree is empty. Start with yourself on the **Add a person** page, "
            "then work backwards one generation at a time."
        )
        return

    c2 = st.columns(2)
    with c2[0]:
        if s["unsourced"]:
            st.warning(
                f"**{s['unsourced']} people have no source yet.** "
                "A name without a source is a hypothesis. See Reports."
            )
    with c2[1]:
        if s["disputes"]:
            st.info(
                f"**{s['disputes']} facts are disputed.** "
                "Two people recorded different answers. See Disagreements."
            )

    st.divider()
    st.subheader("Recently changed")
    st.caption("This is how we catch mistakes. If something looks wrong, open it and fix it.")

    changes = db.recent_changes(15)
    if not changes:
        st.caption("Nothing yet.")
        return

    verb = {
        "INSERT": "added",
        "UPDATE": "edited",
        "DELETE": "removed",
        "RESTORE": "restored",
    }
    for ch in changes:
        when = str(ch["changed_at"])[:16].replace("T", " ")
        fields = ch.get("changed_fields") or []
        detail = f" ({', '.join(fields)})" if fields else ""
        st.write(
            f"**{ch['changed_by_name']}** {verb.get(ch['action'], ch['action'].lower())} "
            f"{ch.get('subject_label') or ch['record_id']}{detail}  \n"
            f"<span style='color:#888;font-size:0.85em'>{when}</span>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
