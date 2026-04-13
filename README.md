CRO tool for landing pages
The tool takes in an ad creative + a landing page URL and produces an enhanced version of the page, aligned with the ad's messaging and following CRO principles.

**Live Demo:** https://cro-tool-3kj8.onrender.com/

### High Level Flow

The system is a 4-stage pipeline: **extract, analyze, strategize, apply.**

**Stage 1: Extract**
- **Input:** Ad creative image (uploaded by user)
- **Output:** Structured analysis of the ad — the offer, messaging, tone, CTA, target audience, etc.
- A vision-capable LLM looks at the ad image and extracts every marketing-relevant signal.

**Stage 2: Analyse**
- **Input:** Landing page URL
- **Output:** Cleaned HTML of the page + structured analysis — current headline, CTAs, value propositions, social proof, layout, friction points
- A headless browser (Playwright/Chromium) fetches the fully rendered page, strips non-content elements, and an LLM produces a structured breakdown.

> **Note:** Stage 1 and 2 happen in parallel. The output of both stages is fed to Stage 3.

**Stage 3: Strategize**
- **Input:** Ad analysis from Stage 1 + Page analysis from Stage 2
- **Output:** A JSON modification plan — exact changes to make, with CRO justifications for each
- This is the brain of the system. An LLM with CRO expertise encoded in its prompt decides what to change, constrained by a blocklist (what not to touch), a JSON schema (what types of changes are allowed), and grounding rules (to limit hallucination).

**Stage 4: Apply**
- **Input:** Original HTML + JSON modification plan
- **Output:** Enhanced HTML with all changes applied
- All Python logic, no LLM involved.

The final output is a side-by-side comparison of the original page (left) and enhanced page (right), with an enhancement report showing what was changed and why.

---

### Run locally

```bash
git clone https://github.com/magic-bubblez/cro-tool.git
cd cro-tool
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Create a `.env` file:
```
GEMINI_API_KEY=your_google_ai_studio_key
OPENROUTER_API_KEY=your_openrouter_key
```

Get a free Gemini key at https://aistudio.google.com/apikey and a free OpenRouter key at https://openrouter.ai/keys

```bash
source .venv/bin/activate
export $(cat .env | xargs)
uvicorn app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

---

### Models

We started with Gemini 2.5 Flash on Google AI Studio's free tier — it's fast, vision-capable, and handles structured JSON output well. But free tiers have limits, and during testing we hit 503 errors when Google's servers were under load. So we built a fallback chain through OpenRouter's free models: Nemotron 120B from NVIDIA, Qwen3-Coder, Llama 3.3 70B, and Hermes 405B. Each one runs on a different upstream provider, so if one goes down the others usually stay up. The system tries Gemini first, and if it fails, cycles through the chain until something responds. In practice Gemini handles most requests fine — the fallbacks are insurance for when it doesn't.

---

## What this tool doesn't do yet (but should)

While thinking about how the system should be designed, how an ideal CRO tool *should* behave — defining the criteria, asking questions and giving explanations around them — many ideas and questions came to mind which have not been thought through and hence not implemented in this version.

Why? Because I have been trying to strictly follow this philosophy: *"The discipline of system design is staying at one level of abstraction at a time."* Trying to maintain this discipline in order to avoid going down the rabbit holes. (i absolutely love to do that, but sometimes some things must be deferred.)

### Continuous Optimization Loop

Landing pages need to be continuously optimized in accordance with constantly rolling-out advertisements, A/B tests, and multivariate experiments.

In CRO practice we don't just optimize once:
- Run ad A and B simultaneously to different users
- Each ad gets its own landing page variant
- Measure which variant converts better
- Keep iterating
- Design for continuous CRO optimization

### Output Formats Beyond Preview

The demo shows a side-by-side preview. How can people integrate the enhanced pages into their code? Options:
- Provide HTML/CSS code
- A live hosted URL (shareable link)
- A JavaScript snippet that applies modifications at runtime (how tools like Optimizely and VWO work)
- A/B test deployment into existing testing tools

### Visual Validation Agent

A screenshot agent that renders the enhanced page, compares it against the original, and flags visual regressions — text overflow, broken layouts, misaligned elements. This was proposed during design but deferred.

### Human-in-the-Loop Review

Before modifications go live, a reviewer sees the change plan with CRO justifications and approves or rejects each modification individually.

### Multi-Ad Variant Management

Dashboard to manage which ads map to which page variants, track performance per variant, and orchestrate the continuous optimization cycle.
