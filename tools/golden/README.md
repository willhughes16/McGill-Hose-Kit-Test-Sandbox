# Golden regression suite — NOT parity

`tools/parity/` proves the kit reproduces the **source engine's** output. Its
expected files were captured from the source, which is what makes the claim
non-circular, and round 25 set that standard.

This suite is a different thing and must not be confused with it. `_report/reply.md`
has **no source counterpart** — the source engine never produced it — so there is
nothing to be at parity with. What a committed expected file CAN do is detect an
**unintended change** to the rendering: it is a change-detector, not a correctness
proof. The expected files here are the kit's own output, committed deliberately.

Round 34 adjudicated the distinction: a parity fixture for the reply is correctly
absent; a golden regression check is needed, and three reply mutations survived the
behavioural suite for want of one.

## What a failure here means

Something about the reply's rendering changed. That is not automatically wrong —
if the change is intended, re-capture:

    python3 tools/golden/capture.py

and read the diff before committing it. What you must NOT do is re-capture to make
a red suite green without looking, which converts the change-detector into a
rubber stamp.

## Run

    python3 tools/parity_check.py --manifest tools/golden/golden.json

The comparator is the same generic one the parity suite uses (JSON, declared
normalizations only). Reply text is wrapped via `tools/parity/wrap_text.py` so the
JSON comparator can see it.
