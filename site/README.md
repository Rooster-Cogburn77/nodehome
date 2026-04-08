# Nodehome Site

Static publication site for `nodehome.ai`.

## Build

```powershell
python site\build_site.py
```

Output goes to:

- `site/public/`

## Local Preview

```powershell
cd site\public
python -m http.server 8080
```

Then open:

- `http://localhost:8080`

## Content

The homepage and article pages are generated from:

- `site/content_manifest.json`
- markdown files under `docs/`
