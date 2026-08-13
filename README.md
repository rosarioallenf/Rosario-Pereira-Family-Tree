# Our Family Tree

A shared family history anyone in the family can add to, from a phone or a
laptop. No software to install, no curator approving changes.

Built on the same stack as the Cartel golf app: Streamlit Cloud for the app,
Supabase Postgres for the data, GitHub in between.

---

## Files

Flat layout on purpose — GitHub's browser upload page silently flattens
folders, so there are none to flatten.

| File | What it does |
|---|---|
| `streamlit_app.py` | Entry point: sign in, navigation, home page |
| `family_db.py` | Every call to Supabase. Nothing else touches the database |
| `family_pages_people.py` | Search, profile, add, edit |
| `family_pages_family.py` | Marriages, linking children, the visual tree |
| `family_pages_review.py` | Change feed with undo, disagreements, reports |
| `requirements.txt` | Three packages |

---

## Setup

### 1. Database

In the Supabase SQL Editor, run `supabase_schema.sql`, then
`supabase_seed.sql`. Both are safe to re-run.

### 2. Expose the `tree` schema — do not skip this

The tables live in a schema called `tree`, not `public`. Supabase only serves
`public` through its API by default, so **until you do this, every page will
show "relation does not exist"** even though the tables are plainly there.

> **Settings → API → Exposed schemas → add `tree` → Save**

This is the single most likely thing to go wrong.

### 3. Add yourself as a contributor

Nobody can read or write anything until they exist in the `contributor`
table. That table *is* the access control.

1. **Authentication → Users → Add user** (or sign up through the app)
2. Copy the user's UUID
3. In the SQL Editor:

```sql
insert into tree.contributor (contributor_id, display_name, relationship, is_admin)
values ('paste-uuid-here', 'Allen', 'started the tree', true);
```

### 4. Deploy

Push these files to a GitHub repo, then at **share.streamlit.io** point a new
app at `streamlit_app.py`.

In the app's **Settings → Secrets**, paste:

```toml
SUPABASE_URL = "https://yourproject.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

Both come from **Settings → API** in Supabase. Use the **anon** key, never the
service role key — the anon key is safe in a browser because row level
security does the real work.

> **After uploading to GitHub, check the file sizes on the repo page.** Browser
> uploads have silently failed to commit before. A 0-byte file is the tell.

---

## Adding relatives

1. They open the app and create an account
2. They send you the UUID the app shows them
3. You run the `insert into tree.contributor` line above with their name

Set `is_admin` to `false` for everyone but you. Admin only controls the
dropdown lists — ordinary editing needs no special rights.

---

## How the no-curator design holds up

Everyone edits directly. What keeps that safe is that **nothing is ever lost**:

- **Every change is recorded** — who, when, old value, new value
- **Undo is one click** on the What's changed page
- **Nothing hard-deletes.** A database trigger blocks it for everyone,
  including you. Removed people are hidden, not destroyed
- **Disagreements are kept, not resolved by force.** Two relatives with
  different birth years for the same person both get recorded. The later edit
  does not erase the earlier belief
- **Implausible gaps flag themselves.** A parent-child birth gap under 12 or
  over 65 years files a note automatically — the check nobody's memory
  provides for people born in the 1800s

---

## Privacy

Living people are marked as such and are **left out of CSV downloads by
default**. A birth date plus a mother's maiden name is most of a security
questionnaire.

Anonymous visitors get nothing at all: no contributor row, no data.

---

## If something breaks

| Symptom | Cause |
|---|---|
| "relation tree.x does not exist" | Step 2 — schema not exposed |
| Signed in but "not on the contributor list" | Step 3 — no contributor row |
| "Supabase credentials are missing" | Secrets not set in Streamlit settings |
| Everything empty, no error | Contributor row exists but RLS blocked it; check the UUID matches exactly |
| Blank page after upload | Check file sizes on GitHub for a failed commit |
