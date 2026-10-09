# Solar Bill Check: web app

React front end for Solar Bill Check. A user photographs an electricity bill, checks the numbers two AI models read from it, and gets a rooftop solar plan: system size, PM Surya Ghar subsidy, cost, payback, loan EMI, a readiness checklist and the steps to apply. English and Hindi.

## Stack

Vite 8, React 19, TypeScript 6, Tailwind CSS 4, React Router 8 (lazy routes), TanStack Query 5, i18next (locales loaded on demand), Phosphor icons, `motion` for two small entrance animations (off when the user prefers reduced motion). The usage chart is plain SVG, no chart library.

## Run it

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # type-check + production build into dist/
npm run preview    # serve dist/ on http://localhost:4173
npm run lint       # oxlint
npm run typecheck
```

## Settings

| Variable | Default | What it is |
| --- | --- | --- |
| `VITE_API_URL` | the deployed Lambda function URL in `src/config.ts` | Backend base URL (`/upload-url`, `/extract`, `/plan`, `/plan/{id}`, `/speak`) |
| `VITE_CHAT_URL` | same as `VITE_API_URL` | Base URL for `POST /chat`. If it returns 404 the chat drawer says the assistant is coming soon. |

Put them in `.env.local` to override.

## Screens

| Route | What it does |
| --- | --- |
| `/` | Camera capture or PDF upload, manual entry link, an example result |
| `/reading` | Uploads to S3 with a presigned POST, then calls `/extract`, with honest progress steps |
| `/check` | Shows each field with how sure the readers are, big buttons where they disagree, the past months, and the four questions (PIN code, roof, name on bank account, earlier subsidy) |
| `/manual` | State, monthly units, sanctioned load and PIN code when there is no bill photo |
| `/plan/:id` | The plan, loaded with `GET /plan/{id}` so the link can be shared. Listen (Amazon Polly), share, chat drawer |

Flow state between screens is kept in `sessionStorage` (`sbc.flow.v1`); the bill file itself only stays in memory. The full consumer number is shown on the plan page only in the session that made the plan, since stored plans keep it masked.

## Deploy

`npm run build` and upload `dist/` to any static host (S3 + CloudFront, Amplify Hosting). It is a single-page app, so unknown paths must serve `index.html`:

- Amplify / Netlify: `public/_redirects` is already included.
- CloudFront: add custom error responses for 403 and 404 that return `/index.html` with status 200.

The backend has to allow the site's origin in CORS.
