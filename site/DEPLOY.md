# Deploy To Cloudflare

`nodehome.ai` can be deployed directly from `site/public/`.

## Build

```powershell
python site\build_site.py
```

## Publish

One command rebuild + deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\site\publish_pages.ps1
```

Required environment variables:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

## Cloudflare Pages

1. Create a Pages project in Cloudflare.
2. Choose `Direct Upload` or connect this repo.
3. Use this output directory:
   - `site/public`
4. If Cloudflare asks for a build command, use:
   - `python site/build_site.py`
5. Attach the custom domain:
   - `nodehome.ai`

## Notes

- This site is fully static.
- No Node toolchain is required.
- Rebuild after changes to `docs/` or `site/content_manifest.json`.
