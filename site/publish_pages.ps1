param(
    [string]$ProjectName = "nodehome",
    [string]$Directory = "site/public"
)

$ErrorActionPreference = "Stop"

if (-not $env:CLOUDFLARE_API_TOKEN) {
    throw "CLOUDFLARE_API_TOKEN is required."
}

if (-not $env:CLOUDFLARE_ACCOUNT_ID) {
    throw "CLOUDFLARE_ACCOUNT_ID is required."
}

python site\build_site.py
cmd /c npx wrangler pages deploy $Directory --project-name=$ProjectName
