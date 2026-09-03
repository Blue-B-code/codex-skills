---
name: upwork-job-filter
description: Evaluate Upwork (or other freelance) job postings against this user's real, verifiable profile and return an explicit APPLY / SKIP / CONDITIONAL verdict with a fit table and reasons, optionally drafting a proposal. Use when the user pastes a job posting (title, summary, requirements/"You:", client info, budget/rate) and asks whether to apply, asks "fit?", "should I apply?", "what do you think of this job?", or asks you to draft a proposal. Also use to judge whether a Connects spend is justified.
---

# Upwork Job Filter

Evaluate the pasted job against the user's real profile and give an honest, decisive verdict. Never inflate fit — the user's credibility depends on honesty. Read `references/profile.md` when mapping job requirements to evidence.

## 1. Extract the facts (ask if missing)

Pull from the posting: title, summary, requirements / "You:" section, engagement type (fixed/hourly, full-time/part-time, one-off/ongoing), budget + estimated hours, "to apply" instructions, and client info (country, reviews, payment verified, $ spent, avg hourly rate paid).

## 2. Two-minute filter — a clear NO on any of these → SKIP

1. **Fit** — can the user credibly prove at least 3 of the core techs/requirements? (evidence in `references/profile.md`)
2. **Scope** — is it a small/medium fixed task? A full product rebuild, "entire platform", or "multi-year role" → SKIP for now.
3. **Domain** — no unknown jargon (CAD/engineering, fintech, regulated health, etc.) unless the user has proof.
4. **Ratio** — Connects cost vs realistic odds: 18–26 Connects on a low-fit or niche job → SKIP.

## 3. Price / rate floor

- Effective rate = fixed budget ÷ estimated hours (when scope is given).
- Below **~$15/hr** equivalent → SKIP, and show the math (e.g. $96 ÷ 32h = $3/hr).
- Client explicitly wants **"lowest rates"** → SKIP (bad-signal client).
- Factor Upwork's ~0–15% service fee into the real take-home.
- For a **first contract**, accept a *fair* fixed price for credibility, but never exploitation (a $96/32h job is unacceptable).

## 4. Verdict output format (always explicit)

- **VERDICT: APPLY / SKIP / CONDITIONAL**
- Fit table: requirement → user evidence → ✅ / ⚠️ / ❌
- 2–3 concrete reasons.
- **APPLY / CONDITIONAL** → provide a ready-to-paste proposal (respect any required opening phrase, e.g. "SCOPE CONFIRMED.").
- **SKIP** → one-line why + what to target instead.

## 5. Proposal drafting (APPLY / CONDITIONAL)

- First 1–2 sentences personalize and prove the job was read (restate the specific need).
- Lead with a **real, linked** project proof (see `references/profile.md`).
- Confirm availability honestly (10–20 h/week; realistic start timing).
- End with 1–2 smart questions.
- Never invent skills, numbers, clients, or results.

## Reference

- `references/profile.md` — verified credentials, proof projects, keywords to seek/exclude, red flags.
