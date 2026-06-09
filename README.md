# TGFC TGFC Market Dashboard — LIVE (self-refreshing)

Unlike the static Netlify version, this app **fetches the USDA reports itself every time
it loads** and renders fresh numbers. Deploy it once and the link stays current with no
manual updates.

## What it does
- On load (cached 6 hours), pulls live from:
  - Beef boxed-beef cutout (AMS LM_XB403)
  - Pork FOB plant cutout (AMS LM_PK602)
  - Daily livestock & poultry slaughter (AMS)
  - Daily direct hog prices (AMS LM_HG201)
  - Weekly national chicken report (AMS)
  - FAS weekly export sales (beef & pork)
- Re-renders the same dashboard (branded + plain) with the new figures.
- **Safety net:** every report is parsed in a try/except. If one is unreachable or USDA
  changes a layout, those fields fall back to the bundled snapshot (`baseline_data.json`)
  so the page never breaks. The sidebar shows per-source status (ok / fallback).

## Files
- `streamlit_app.py` ..... the app (version toggle + force-refresh button in the sidebar)
- `usda_fetch.py` ........ fetches & parses the USDA reports -> data dict
- `baseline_data.json` ... snapshot used as the fallback / starting point
- `template_branded.html` / `template_plain.html` ... the dashboard shells (data injected at runtime)
- `requirements.txt` ..... streamlit, requests, pdfplumber

## Deploy on Streamlit Community Cloud (free, gives a public link)
1. Put this `live-app` folder in a GitHub repo (browser upload is fine — github.com ->
   New repository -> Add file -> Upload files -> drag everything in -> Commit).
2. Go to https://share.streamlit.io -> sign in with GitHub -> **New app**.
3. Pick the repo, branch `main`, **Main file path: `streamlit_app.py`**. Deploy.
4. You get a public URL like `https://<app-name>.streamlit.app` — that's your live, always-current link.

## Notes
- First load takes a few seconds while it fetches; afterwards it's cached for 6 hours.
- Visitors can flip Branded / Plain in the sidebar; the **↻ Force refresh now** button
  pulls immediately.
- To move the fallback snapshot forward, replace `baseline_data.json` (export the latest
  DATA from Cowork) and push — but normally you won't need to, since it fetches live.
- Poultry average weights and a few weekly-derived figures intentionally use the snapshot
  (they change monthly / aren't in the daily feeds); everything daily is fetched live.
