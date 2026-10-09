# Stack and versions

Checked on 2026-10-09 with `npm view`, PyPI, GitHub releases and the AWS docs.

## Frontend

| Package | Version | Notes |
|---|---|---|
| vite | 8.3.4 | Rolldown is the bundler. Config uses `build.rolldownOptions` |
| @vitejs/plugin-react | 6.1.2 | Oxc, no Babel |
| react, react-dom | 19.3.0 | |
| typescript | ~6.0.3 | Matches the Vite template (TS 7 is optional) |
| tailwindcss, @tailwindcss/vite | 4.3.3 | `@import "tailwindcss";` + `@theme {}`; no config file |
| react-router | 8.4.0 | `createBrowserRouter` + route `lazy`. v7 and `react-router-dom` are gone |
| @tanstack/react-query | 5.104.1 | |
| zod | 4.6.5 | Use `zod/mini` (4.9 KB gz) |
| @phosphor-icons/react | 2.1.10 | Named imports only |
| i18next, react-i18next | 26.4.2, 17.0.16 | Plain JSON catalogs, easy to translate by script |
| i18next-resources-to-backend | 1.2.3 | One lazy chunk per locale |
| @fontsource-variable/noto-sans (+ script packages) | 5.3.0 | Load the active script's CSS with `import()`; `unicode-range` keeps downloads small |
| oxlint | ^1.87 | From the template |

**No chart library.** Recharts adds about 108 KB gz for one small bar chart, so we'll hand-write the chart in SVG.

## Backend

| Item | Choice |
|---|---|
| Lambda runtime | `python3.14`, **arm64** (about 20% cheaper) |
| AWS SAM CLI | 1.167.0, official zip installer |
| Dependencies | `uv` for local work; `uv export --no-hashes > requirements.txt` for SAM builds (the uv build method is still beta) |
| aws-lambda-powertools | 3.35.0. `LambdaFunctionUrlResolver` for routing |
| pydantic | 2.14.0 |
| boto3 | 1.43.110 |
| strands-agents | 1.59.0. **Not** strands-agents-tools: it doubles the package to 164 MB. We write our own `@tool` functions |
| CORS | Set only in SAM `FunctionUrlConfig.Cors` |
| SnapStart | Only on the chat function, through `AutoPublishAlias`; delete old versions |
| Chat responses | Returned in one piece. Python Lambdas can't stream without Lambda Web Adapter |

Package size with strands-agents + powertools + pydantic is 79 MB unzipped, so a zip deploy works and no container is needed.

## Hosting

- Amplify Hosting connected to the GitHub repo, with `amplify.yml` (`baseDirectory: dist`) and Node 22.
- SPA rewrite rule: send any path that isn't a static file to `/index.html` (200).
- `customHttp.yml`:
  - `/assets/**` gets `public, max-age=31536000, immutable`.
  - `/index.html` gets `no-cache`.
- Amplify adds Brotli on its own, so no compression plugin is needed.

## Indian language support in AWS services

| | hi | en-IN | bn | ta | te | mr | gu | kn | ml | pa | or |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Polly (speech) | Kajal neural | Kajal neural | – | – | – | – | – | – | – | – | – |
| Transcribe | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Translate | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |

The "Listen" button uses Polly for Hindi and English only. UI translations come from Bedrock, which covers every language above.
