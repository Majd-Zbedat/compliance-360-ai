# Compliance 360 Web UI

Enterprise dashboard for the AI-Native Regulatory Document Auditor.
Stack: **Next.js 14 (App Router) · React 18 · TypeScript · Tailwind CSS ·
hand-rolled shadcn-style components**.

## Run locally

```powershell
# from the FinalProject root
cd webui
npm install
Copy-Item .env.local.example .env.local
npm run dev
```

Open <http://localhost:3000>. The dashboard talks to the orchestrator at
`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`).

## Pages

- `/` — KPI cards + recent audits feed.
- `/audits` — full audits table.
- `/audits/new` — upload a contract PDF and start a Compliance 360 audit.
- `/audits/[id]` — risk pill, findings table, per-finding detail drawer,
  and the safe (guardrail-validated) report.
- `/regulations` — browse the seeded GDPR / ISO 27001 / Local Law corpus.

## Matching the Figma

The shell (sidebar nav, KPI cards, table-on-card pattern, right-side
assistant drawer) deliberately mirrors the enterprise SaaS dashboard
pattern from the attached Figma. Colour tokens live in
`src/app/globals.css`; tweak `--primary` / `--ring` to match Figma
branding if needed.
