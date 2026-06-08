Save Autonomous Courses/Oscanner Plan As Markdown
Summary
Add a documentation-only plan file in the Oscanner repository. Do not change backend, frontend, APIs, jobs, schedulers, or tests.

Key Change
Create docs/autonomous_courses_oscanner_plan.md containing the proposed “course schedule driven + Gitee Issue feedback” architecture plan from the previous message.
The file should clearly state: “Planning document only; not implemented.”
Keep the plan focused on intended behavior, ownership split between Courses and Oscanner, APIs to add later, and test strategy.
Content Structure
Title: Course-Driven Autonomous Oscanner Plan
Sections:
Summary
Key Changes
Behavior
Test Plan
Assumptions
Preserve the chosen defaults:
trigger: Course Schedule
conversation channel: Gitee Issue
posting policy: Auto-post Results
job scope: Check + Evaluate + Test + Feedback
Assumptions
Documentation belongs under docs/ in /Users/bluce/working/oscanner.
No implementation work should be done in this change.