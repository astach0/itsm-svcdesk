# Agent Policy

This policy limits potentially destructive or submission-affecting actions by repository agents.

- git commit: Agents must not create commits automatically because the repository owner should review the complete working tree before recording a Lab 1 attempt.
- git push: Agents must not push changes because pushing modifies the shared remote repository and should be explicitly controlled by the repository owner.
- git tag: Agents must not create or move tags because laboratory attempt tags are immutable submission artifacts and must be created deliberately by the repository owner.
