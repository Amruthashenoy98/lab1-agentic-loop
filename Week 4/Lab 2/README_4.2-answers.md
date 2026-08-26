# Lab 4.2 - Enforcing Structure

Built a candidate-screening evaluator that always returns a valid {name, recommendation, score, reason} object, using tool schemas, validation, and retry.

## Exercise 1 - Tool Schema
Defined the input_schema for all four fields (name, recommendation enum, score integer 0-10, reason) and marked them all required, with tool_choice forced.

All three test candidates came back as clean structured objects on the first call, matching what you'd expect from their profiles (strong candidate -> strong_hire, weak candidate -> no_hire, mixed -> hire).

## Exercise 2 - Semantic Validation
Implemented validate(payload) to check types/enum/range plus cross-field rules (strong_hire needs score >= 8, no_hire needs score <= 4). Also handled the bool-is-a-subclass-of-int trap in Python.

Offline check passed on all test cases (good, bad, cross-field).
Live run: both candidates returned valid payloads.

## Exercise 3 - Retry Loop
Implemented assess_with_retry() to call the tool, validate the result, and on failure feed the specific errors back via tool_result(is_error=True) so the model can self-correct, capped at max_attempts.

Demo (simulated): attempt 1 failed cross-field check, attempt 2 passed after feedback.
Live run: candidate was strong enough to pass validation on attempt 1, no retry needed.
