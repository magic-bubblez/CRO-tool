# CRO tool for landing pages
The tool takes in an ad creative + a landing page URL and produces an enhanced version of the page, aligned with the ad's messaging and following CRO principles.

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
  - This is the brain of the system. An LLM with CRO expertise encoded in its prompt decides what to change, constrained by a blocklist (what not to touch), a JSON schema (what types of changes are
  allowed), and grounding rules (to limit hallucination).

  **Stage 4: Apply**
  - **Input:** Original HTML + JSON modification plan
  - **Output:** Enhanced HTML with all changes applied
  - All Python logic, no LLM involved.

  The final output is a side-by-side comparison of the original page (left) and enhanced page (right), with an enhancement report showing what was changed and why.

  ---

  ## Key Components and Decisions Made

  ### The Strategist (Stage 3)

  This is the brain of the system. The LLM is given a detailed system prompt encoding CRO expertise — 6 optimization principles (message match, value prop clarity, CTA optimization, urgency, social proof,
   cognitive load reduction) — along with two guardrails:

  **The Blocklist** — what the AI cannot touch. We chose blocklist over whitelist because the AI needs creative freedom for CRO, but certain elements are sacred: navigation, footer, forms, brand identity,
   third-party integrations (payment/analytics/chat), SEO elements, accessibility attributes, authentication flows. Rule of thumb: if it touches money, law, brand trust, or data routing — it's blocked.

  **The Structured Output Schema** — every modification must be expressed through a predefined JSON schema. Character limits on all text fields, exact-match grounding for replacements, CRO justification
  required for every change, only safe CSS properties allowed. If a change can't be expressed in the schema, it can't be made.

  ### Page Fetching with Headless Browser

  To fully render the pages and capture the final DOM (the code will be required in Stage 3 for the LLM to generate the enhanced page).

  ### Multi-Provider LLM Architecture

  Every free LLM provider has rate limits and outages. Instead of depending on one, the system chains multiple models across independent providers:

  - **Primary:** Gemini 2.5 Flash via Google AI Studio
  - If Gemini fails, the system tries a chain of open-source models via OpenRouter (all free):
    1. Nemotron 120B (NVIDIA infrastructure)
    2. Qwen3-Coder (Qwen/Venice infrastructure)
    3. Llama 3.3 70B (Meta/Venice infrastructure)
    4. Hermes 405B (NousResearch/Venice infrastructure)

  ---

  ## How failures are avoided

  ### Random / Unwanted Changes

  The blocklist prevents the AI from touching structural elements. The JSON schema constrains what types of changes are expressible. The AI cannot add new sections, remove elements, change images, modify
  links, inject JavaScript, or alter forms. If a change is not in the schema, it does not happen.

  ### Broken UI

  Character limits on every text field prevent overflow. CSS property restrictions only allow safe properties — no layout changes. Other related constraints are enforced by a schema validator before any
  changes are applied.

  *(Another thought occurred to include a UI validation agent, however it isn't within the scope of the demo.)*

  ### Hallucinations

  We cannot fully control it, however it has been limited by defining strict grounding rules: every piece of generated text must be traceable to the ad creative or the existing page content.

  Social proof must cite its source. If the ad has no urgency signals, urgency elements are not allowed. The AI is explicitly instructed: *"Do not invent statistics, testimonials, or claims not present in
   either input."*

  ### Inconsistent Outputs

  JSON schema validation catches structural issues before changes are applied.

  If the LLM produces invalid JSON or fails constraint checks, the system retries with error feedback: *"Your previous output had these validation errors: [list]. Fix these and respond with only valid
  JSON."*

  Maximum 2 retries. If validation still fails after retries, changes are applied with warnings attached.

  ---

  ## Another Challenge Worth Mentioning

  While testing the tool in the afternoon, the Gemini models were failing to produce any output. The many OpenRouter free models that are being used as a fallback mechanism route through a single upstream
   provider (Venice), so when Venice is overloaded, multiple models fail together.

  This problem in free-tier models, we cannot solve.

  ---

  ## Beyond Demo Scope

  While thinking about how the system should be designed, how an ideal CRO tool *should* behave — defining the criteria, asking questions and giving explanations around them — many ideas and questions
  came to mind which have not been thought through and hence not implemented in this version.

  Why? Because I have been trying to strictly follow this philosophy: *"The discipline of system design is staying at one level of abstraction at a time."* Trying to maintain this discipline in order to
  avoid going down the rabbit holes.

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

  A screenshot agent that renders the enhanced page, compares it against the original, and flags visual regressions — text overflow, broken layouts, misaligned elements. This was proposed during design
  but deferred.

  ### Human-in-the-Loop Review

  Before modifications go live, a reviewer sees the change plan with CRO justifications and approves or rejects each modification individually.

  ### Multi-Ad Variant Management

  Dashboard to manage which ads map to which page variants, track performance per variant, and orchestrate the continuous optimization cycle.
