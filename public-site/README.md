# Revenant atlas web application

This is the complete published viewer and its Vinext/Cloudflare Worker source. See [../docs/hosting.md](../docs/hosting.md) for the independent mirror, build instructions, R2 routes, secret handling, and deployment options.

`public/atlas.html`, `public/atlas.css`, and `public/atlas.js` are the actual UI. `worker/atlas.ts` streams catalog files, native PNG tile ranges, and full PNG/BigTIFF downloads from the `BUCKET` binding. The remaining files preserve the framework and Sites build integration.

The `.openai/hosting.json` in this public source snapshot contains binding declarations but no existing account's project ID. Register your own Site before deploying with Sites. You can instead use the independent Python mirror, which needs no Node dependencies or cloud credentials.
