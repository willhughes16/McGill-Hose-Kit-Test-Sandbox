# VERIFICATION — mcgill-email-to-bom kit, round 38

**Artifact:** `/Users/axr/Desktop/McGill/mcgill-email-to-bom` at `7fb1663`, kit **v0.26.0**, live on the instance.
**Bar:** `ACCEPTANCE_ROUND38.md` (pre-registered, K-1..K-9).
**Source of truth:** `/Users/axr/Desktop/McGill/email-to-bom-agent` at `6b0a897` (its `main`; the bar's `270f32b` does not exist in that clone — see N-1).

---

# VERDICT: **FAIL** (fourteenth consecutive)

**The single blocker: `config/questions.json` asks the customer to confirm values that
`render_customer` structurally guarantees they will never see, and tells them two
falsehoods about assumptions the engine actually made.**

This is not one bad string. It is a *class* of translation defect that the author could
not see, exactly as the bar predicted, and it is load-bearing: **five of the twenty-six
customer-facing translations fire only when the underlying field is `reading` or
`assumed`, and `render_customer` prints only fields whose status is exactly `captured`.**
The questions and the answers are disjoint by construction. A customer who replies
"yes, that's right" is confirming a number they were never shown.

`reply.md` is the customer's email. Round 37's blocker cost a reviewer a wrong document;
this one puts a wrong statement and an unanswerable question into a customer's inbox with
one fewer human in the way. **Roll back.**

---

## Reproduction environment

All work in `/private/tmp/.../scratchpad`; the repo was never mutated. `git status --porcelain`
shows only this report.

```
cp -r <kit>/src <scratch>/run1 && cd <scratch>/run1
python3 scripts/prepare_input.py --body body.html --attachments-dir input/ \
        --subject "RFQ hydraulic hose" --state _report/state.json
python3 scripts/run_engine.py --from-state --state _report/state.json --out _report/case_state.json
python3 generate_report.py  --out _report/bom_draft.md --state _report/state.json
python3 scripts/render_reply.py --out _report/reply.md --state _report/state.json
```

Every fixture below uses RFC 2606 namespaces (`example.com` / `.org` / `.net`).

---

# Findings

## H-1 — BLOCKER. The customer is asked to confirm five classes of value that the email is *structurally incapable* of showing them

`render_customer` (`src/scripts/render_reply.py:545-563`):

```python
    for name in sorted(fields):
        f = fields[name] or {}
        if f.get("status") != CONFIRMED_STATUS:   # CONFIRMED_STATUS == "captured"
            continue
```

So **WHAT WE HAVE UNDERSTOOD SO FAR contains `captured` fields only.** Now the engine side:

| code | engine fires it when | so the field's status is |
|---|---|---|
| `LENGTH_CONFIRM` | `ex.length_value and ex.length_type` | `reading` |
| `TEMPERATURE_CONFIRM_READING` | `t["status"] == "reading"` | `reading` |
| `PRESSURE_CONFIRM_READING` | `p["status"] == "reading"` | `reading` |
| `TEMPERATURE_ASSUMPTION_CONFIRM` | `t["status"] == "assumed"` | `assumed` |
| `VACUUM_VALUE_CONFIRM` | `p["kind"]=="vacuum" and p["status"]=="reading"` | `reading` |

Each of these five translations says "confirm the X we have read from your message" — and the
value of X is excluded from the email by the same condition that raised the question.

**Reproduction** (`flange` fixture — body: *"Please quote 2 steam hose assemblies with 150# flange
ends both ends. 3 inch ID, 20 ft overall length, 150 psi, 350 F."*):

engine's asks, from `_report/case_state.json`:

```
[TEMPERATURE_CONFIRM_READING] Temperature read as 350°F from context — confirm before fabrication.
[LENGTH_CONFIRM]              Length read as 20 ft OAL — confirm value and convention before fabrication (WI-020).
```

`_report/reply.md`, verbatim:

```
WHAT WE NEED FROM YOU

  1. What material should these be made from? If a specific grade is required, please tell us which.
  2. Could you confirm the operating temperature we have read from your message?
  3. Which flange specification do you need — the standard and the pressure class?
  4. Which flange specification do you need — the standard and the pressure class?
  5. Could you confirm the length we have read from your message is right?

WHAT WE HAVE UNDERSTOOD SO FAR

  media: steam
  pressure: 150.0
  quantity: 2
  size: 3 ID
```

`350°F` and `20 ft OAL` appear nowhere. The customer is asked to confirm both.

**Why this is a wrong answer and not a coverage gap.** `LENGTH_CONFIRM` is the engine's
guard against the length rail — the field the engine reads off free text and deliberately
refuses to capture. The engine's own ask is *"confirm value **and convention**"*. The
customer's version drops the convention entirely and asks about a value it does not
disclose. A customer who answers "yes" has confirmed *`20 ft`, convention `OAL`* without
ever being told either. The reply then reads as a customer-confirmed length to the next
reader. That is the precise failure mode `reading` status exists to prevent, re-introduced
on the customer-facing side.

Reproduced on five independent fixtures: `flange`, `triclamp`, `pressure_reading`,
`punit`, `lengthconfirm`, `correction` (all show question "confirm the length we have read"
with no length in the email).

---

## H-2 — BLOCKER. `TEMPERATURE_ASSUMPTION_CONFIRM` tells the customer the exact opposite of what happened

`config/questions.json:26`:

```json
"TEMPERATURE_ASSUMPTION_CONFIRM": {"audience": "customer",
  "question": "Could you confirm the operating temperature? We have not assumed one."}
```

The code is named `..._ASSUMPTION_CONFIRM`. The engine raises it at `core.py:642` **only** in
the branch `elif t["status"] == "assumed":` — i.e. **only when it HAS assumed one.**

**Reproduction** (`run1`, body contains *"working at ambient temperature"*):

`_report/case_state.json`:

```json
"temperature": {"kind": "range", "value": [50, 90], "unit": "F", "status": "assumed",
                "max_f": 90, "evidence": "ambient",
                "note": "'ambient' read as 50-90°F — confirm"}
```

engine ask: `Temperature 'ambient' read as 50-90°F — confirm — please advise if that's not correct.`

`_report/reply.md` line 2 of WHAT WE NEED FROM YOU:

```
  2. Could you confirm the operating temperature? We have not assumed one.
```

The engine assumed **50–90 °F**, wrote it into `fields.temperature.value`, and that
assumption is live — `max_f: 90` is what arms `DERATING_REVIEW` (`core.py:684`). The
customer is told in writing that no assumption exists. If they reply "no particular
temperature, it's an outdoor line" the 50–90 °F band stands unchallenged, because they
were told there was nothing to challenge. **A false statement of fact about our own draft,
sent to the customer.**

`CLAUDE.md` forbids this in as many words: *"Never report a `reading` or `assumed` field as
confirmed."* This is worse — it reports an `assumed` field as *nonexistent*.

---

## H-3 — BLOCKER. `FLUID_ASSUMPTION_CONFIRM` makes a false claim about our process

`config/questions.json:28`:

```json
"FLUID_ASSUMPTION_CONFIRM": {"audience": "customer",
  "question": "What will be flowing through this? We would rather ask than assume."}
```

The engine (`core.py:669-673`) raises this **only after assuming**:

```
[FLUID_ASSUMPTION_CONFIRM] We've assumed standard petroleum-based hydraulic oil — confirm,
                           or tell us if this is a special fluid (e.g. Skydrol).
```

and `case_state.json` carries:

```json
"fluid_detail": {"value": "petroleum-based hydraulic oil", "status": "assumed",
                 "note": "industry default — confirm, or name the fluid"}
```

`_report/reply.md`:

```
  3. What will be flowing through this? We would rather ask than assume.
```

Two defects in one line. (a) *"We would rather ask than assume"* is false — we assumed, and
the assumption is in the draft. (b) The engine's ask is a **confirmation** ("confirm, or tell
us if this is a special fluid, e.g. Skydrol"); the translation converts it to an **open
question** and withholds what was assumed. A customer running Skydrol who answers "hydraulic
fluid" has confirmed nothing, and petroleum-based oil — incompatible with Skydrol's seal
requirements — stays in the draft. The engine's parenthetical exists precisely to surface
that trap; the translation deletes it.

Reproduced on `run1`, `pressure_reading` and `correction`.

---

## H-4 — BLOCKER. `FLANGE_SPEC_MISSING` asks a different question from the one the engine raised

engine (`core.py:711-714`):

```
End 1 (flange): confirm pressure class (150 lb / 300 lb / other) AND fixed or floating.
```

customer (`questions.json:30`):

```
Which flange specification do you need — the standard and the pressure class?
```

**`fixed or floating` is dropped, and replaced with "the standard", which the engine never
asked about.** Fixed vs floating (a floating/lapped flange rotates for bolt-hole alignment;
a fixed one does not) is a *fabrication* decision — get it wrong and the assembly cannot be
bolted up in the field. It is the half of the ask that cannot be guessed, and it is the half
that was deleted.

Reproduction: `flange` fixture. The customer had already written "150# flange ends" in the
email, so the only *new* information the engine wanted was fixed-or-floating — and that is
the one thing the customer is not asked. The reply asks them to restate the pressure class
they already gave, twice (H-7), and never mentions fixed or floating.

**A missing answer reaching a customer.** This one blocks on its own.

---

## H-5 — BLOCKER. `PRESSURE_CONFLICT` forces the customer to discard a real requirement

engine (`core.py:617-620`) — this branch fires **only** for a vacuum-vs-positive conflict:

```
Both a vacuum value and a positive pressure appear (28 inHg vacuum vs 200 psi) — confirm which applies.
```

customer (`questions.json:20`):

```
Your message gives more than one pressure — which one should we work to?
```

**Reproduction** (`pconflict`, body: *"rated 200 psi and also 28 in Hg vacuum"*). The
customer email:

```
  2. Your message gives more than one pressure — which one should we work to?

WHAT WE HAVE UNDERSTOOD SO FAR
  quantity: 1
  size: 2 ID
```

Neither candidate value is shown (H-1 again — `pressure` is `conflict`, not `captured`), and
the framing is wrong in a way that costs safety. A suction-and-discharge hose rated for
**both** 200 psi working pressure and 28 inHg vacuum is an entirely ordinary requirement;
that is what the customer wrote. The engine asks "which *applies*", which a vacuum/pressure
duo can legitimately answer with "both". The translation asks "which one should we **work
to**", which admits only one answer. A customer who picks "200 psi" has just deleted their
own collapse-resistance requirement, and the reply gives them no way to see they did.

---

## H-6 — HIGH. `COMPONENT_FIELD_MISSING` sends N identical unanswerable sentences

The engine emits one item **per missing field, naming the field**. The translation is a
single field-agnostic sentence, so N distinct questions become N copies of one vague one.

**Reproduction** (`component` fixture, body: *"Please quote camlock gaskets."*):

engine:
```
[COMPONENT_FIELD_MISSING] gasket: confirm size.
[COMPONENT_FIELD_MISSING] gasket: confirm used with.
[COMPONENT_FIELD_MISSING] gasket: confirm thickness standard or extra.
[COMPONENT_FIELD_MISSING] gasket: confirm material if chemical service.
```

customer:
```
  2. We are missing a detail on one of the parts you listed — could you confirm the full specification?
  3. We are missing a detail on one of the parts you listed — could you confirm the full specification?
  4. We are missing a detail on one of the parts you listed — could you confirm the full specification?
  5. We are missing a detail on one of the parts you listed — could you confirm the full specification?
```

Four bullet-numbered copies of one sentence. The customer is told four details are missing
and which four is withheld; the document reads as broken. The engine's `field=` and
`component=` attributes are present on every item and are simply not used.

---

## H-7 — HIGH. Per-end questions collapse End 1 and End 2 into indistinguishable duplicates

`END_GENDER_MISSING`, `FLANGE_SPEC_MISSING` and `TRI_CLAMP_SIZE_CONFIRM` are all raised
**per end**, with `End {i}` and the family in the ask. All three translations are end-blind.

Reproduced on `run1`/`lengthconfirm` (gender), `flange` (flange spec), `triclamp` (size):

```
  4. Should the end connections be male or female?
  5. Should the end connections be male or female?
```

A hose with a male JIC one end and a female swivel the other — the single most common
hydraulic assembly there is — **cannot be expressed in an answer to this email.** The
customer either answers once (and we do not know which end), or answers "one of each" (and
we do not know which is which). Both outcomes send the case back round, and a wrong guess
between them produces an assembly that will not connect.

---

## M-1 — `VACUUM_VALUE_CONFIRM` asserts a figure the engine does not have

engine: `Vacuum/suction service noted — confirm the vacuum level (in Hg / mm Hg) or 'full vacuum'.`
customer: `Could you confirm the vacuum figure, and the units it is in (in Hg or mm Hg)?`

Reproduction (`vacuum` fixture, body: *"for vacuum service"*, no figure given). There is no
vacuum figure anywhere in the case — `pressure` does not appear in WHAT WE HAVE UNDERSTOOD
at all. The customer is asked to "confirm the vacuum figure" that does not exist, and the
engine's explicitly-offered answer **`'full vacuum'`** — the normal way a customer states
this — is deleted from the options.

## M-2 — `TRI_CLAMP_SIZE_CONFIRM` substitutes a domain claim the engine never made

engine: `...confirm the clamp size — jump sizes are used, so it may not match the hose size.`
customer: `...Tri-clamp sizes are named by tube size rather than by the ferrule.`

The question is the same; the *reason* is a different, kit-invented assertion about McGill's
sizing conventions, presented to a customer as fact. The engine's actual reason — that a
jump size means the clamp may not match the hose size, which is the thing that makes the
question necessary — is gone. Reproduced on `triclamp`.

## M-3 — a captured value is shown to the customer without its unit

`run1`: `case_state.json` has `"pressure": {"value": 3000.0, "unit": "psi", "status": "captured"}`.
`reply.md` shows:

```
  pressure: 3000.0
```

The ALLOW-list at `render_reply.py:559` (`family, gender, type, kind, unit`) is only reached
in the `value in (None, "", [], {})` fallback branch, so a captured scalar **never** carries
its unit. "Please correct anything above that is not right" invites the customer to check a
bare number. `3000.0` is also a float artefact of an integer the customer wrote as `3000`.
A pressure without a unit is a value a customer needed to see and did not (K-1 "Loss").

## M-4 — `MATERIAL_UNLISTED_GRADE` drops the grade it is asking about

engine: `Material 'X' is a specific callout not in the known list...confirm the exact grade`.
customer: `We do not recognise the material grade named — could you confirm the exact grade...?`
The grade the engine could not place is not quoted back, so on a multi-material RFQ the
customer cannot tell which callout we failed on.

---

# The review-request side-by-side is a mitigation, not a fix

`render_review.py` does print the engine ask beside the customer wording, and it does render
these pairs honestly — I confirmed it shows `engine asks: Temperature 'ambient' read as
50-90°F` beside `customer sees: ...We have not assumed one.` That is the kit's stated
defence, and it works as described.

It does not close any finding above, for three reasons I verified in the same document:

1. The review request's own instruction is **"The response below is sent UNCHANGED. Edit it
   in your reply, not here."** — the default action is approve; catching a translation defect
   requires the reviewer to read 26-line side-by-sides adversarially on every case.
2. The defects in H-1 are invisible *in the side-by-side*: the reviewer sees a plausible
   "confirm the length we have read" beside a plausible engine ask. Nothing in that table
   reveals that the value is absent from the customer's email — that requires reading the
   embedded reply and cross-checking WHAT WE HAVE UNDERSTOOD against every question.
3. `questions.json`'s own `_when_unsure` rule is *"Mark it internal... mis-asking sends a
   customer a question about their own order that we got wrong."* Seven codes here are
   mis-asking. The rule was written; it was not applied.
