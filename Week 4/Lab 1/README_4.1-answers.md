# Lab 4.1 - Precision Prompting

Built a moderation classifier (REMOVE / REVIEW / ALLOW) using three prompting techniques.

## Exercise 1 - Explicit Criteria
Replaced the vague prompt with clear definitions for each action and a tie-break rule (if unsure, choose review).

Vague prompt: 5/8 accuracy, 1 wrongful remove
Explicit prompt: 8/8 accuracy, 0 wrongful removes

## Exercise 2 - Few-Shot Examples
Added three labeled examples (one REMOVE, one ALLOW, one REVIEW) to lock the output format.

Zero-shot: 4/4 format matches
Few-shot: 4/4 format matches

Both were fully compliant on format, but the few-shot examples also changed a couple of the actual judgments (e.g. blunt criticism moved from REVIEW to ALLOW), not just the formatting.

## Exercise 3 - Generalization
Wrote a short principles block covering intent behind each action, so edge cases the examples never showed still route correctly (public vs private info, stated "joke" intent not excusing doxxing, ambiguous threats going to REVIEW).

First run: 3/4 edge cases correct
After tightening the REVIEW principle to cover threat-like language even in a playful context: 4/4 edge cases correct
