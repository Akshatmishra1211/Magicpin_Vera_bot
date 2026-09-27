# magicpin AI Challenge — Vera Merchant AI Assistant ("Vera Apex")

## 1. Overview & Architecture

This submission implements an advanced merchant engagement engine and stateful HTTP server modeled after magicpin's Vera marketing assistant. It addresses production Vera's critical shortcomings (canned auto-reply pollution, intent-handoff failures, generic discounting copy, and low interaction frequency) using a unified **4-Context Composition Architecture**:

$$\text{Next Action} = \text{compose}(\text{CategoryContext}, \text{MerchantContext}, \text{TriggerContext}, \text{CustomerContext}^?)$$

### Core Components
- **`bot.py`**:
  - The standalone `compose(...)` contract returning `{body, cta, send_as, suppression_key, rationale}`.
  - A FastAPI server exposing the 5 standard endpoints (`GET /v1/healthz`, `GET /v1/metadata`, `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply`).
  - Thread-safe, version-aware in-memory context store with strict idempotency (HTTP 200 on higher versions, HTTP 409 on stale/equal versions).
- **`conversation_handlers.py`**:
  - Multi-turn state machine managing intent transitions, auto-reply backoff, and courteous exits.
- **`submission.jsonl`**:
  - 30 canonical evaluation compositions covering diverse trigger archetypes across 5 verticals.

---

## 2. Compulsion Levers & Rubric Alignment

Every message is engineered to maximize the 5 judging dimensions (Target: 50/50):

| Rubric Dimension | Implementation Technique |
|---|---|
| **Specificity** | Zero generic percentages. Cites verifiable figures, dates, peer ratings, and source citations (e.g. *JIDA Oct 2026 p.14*, *DCI circular 2026-11-04*, *CDSCO alert Apr 2026*). |
| **Category Fit** | Strict vertical alignment: clinical-peer for dentists (zero medical claim overreaches), fellow-operator for restaurants (covers, AOV, delivery shifts), approachable-expert for salons, coach for gyms, trustworthy-precise for pharmacies. |
| **Merchant Fit** | Personalizes using owner first name (`Dr. Meera`, `Suresh`, `Padma`), locality (`Lajpat Nagar`, `Indiranagar`), actual performance deltas, active catalog offers (`Haircut @ ₹99`, `Dental Cleaning @ ₹299`), and language mix. |
| **Trigger Relevance** | Explicitly answers "why now" using exact trigger payloads (match venue/teams, competitor distance and offer, recall window opening). |
| **Engagement Compulsion** | Employs loss aversion (unverified GBP view penalties, competitor openings), social proof, effort externalization ("live in 2 min", "already drafted"), and a single primary binary CTA. |

---

## 3. Multi-Turn Dialogue State Machine

1. **Auto-Reply Loop Suppression**:
   - Turn 1: Flags the automated nature gently with a low-friction hook for the human owner.
   - Turn 2: Initiates a 24h wait backoff (`action: "wait"`).
   - Turn 3+: Cleanly terminates the loop (`action: "end"`).
2. **Intent Transition (Immediate Action Mode)**:
   - When merchants commit (e.g. *"Ok lets do it. Whats next?"*, *"I want to join"*), the bot immediately switches to execution mode (`action: "send"` with action verbs like *Done*, *Drafted*, *Sending*) and requests a single binary confirmation (`cta: "binary_confirm_cancel"`). It never regresses into qualification questions.
3. **Hostility & Opt-Out Grace**:
   - Outright opt-outs (*"Stop messaging me"*, *"useless spam"*) trigger immediate conversation termination (`action: "end"`), honoring merchant autonomy without defensive counter-arguments.
4. **Off-Topic Redirection**:
   - Inquiries outside local growth (e.g., GST filings) are politely deferred and refocused onto active growth levers.

---

## 4. Key Engineering Tradeoffs

- **Deterministic Rule-Guided Engine vs. Unconstrained LLM Generation**: We built a deterministic expert composer with exact schema validation. This guarantees zero hallucination (no fake paper citations or non-existent competitor names), deterministic reproducibility (temperature=0 equivalent), and sub-50ms execution speed (well under the 30-second budget).
- **Single Primary CTA vs. Multi-Option Menus**: We strictly enforce a single binary CTA placed in the terminal sentence, except for customer slot booking flows where a 2-slot choice is required to minimize scheduling round-trips.
- **In-Memory Volatility vs. External Dependencies**: To ensure zero setup friction and total self-containment during judging, context and dialogue states are stored in high-efficiency Python structures.

---

## 5. What Additional Context Would Have Helped Most

1. **Direct Clinic / Salon POS & Calendar Integration**: Live visibility into available chair/doctor slots would enable real-time booking rather than offering pre-estimated appointment options.
2. **Merchant Unit Economics & Margins**: Knowing the gross margin on specific services (e.g., aligners vs. scaling) would enable the bot to optimize recommendations for merchant profit rather than purely top-line volume.
3. **Customer Roster Consent & Opt-In Provenance**: Granular opt-in timestamps and channel preferences would allow more personalized follow-ups without compliance ambiguity.

---

## 6. How to Run Locally

### Start the Bot Server
```bash
python bot.py
# Server starts at http://0.0.0.0:8080
```

### Run the Judge Simulator
```bash
python judge_simulator.py
```
