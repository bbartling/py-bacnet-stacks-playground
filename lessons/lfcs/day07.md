## Day 7 – Basic Git operations

*LFCS · Essential Commands*

### Goal

Init a repo, commit, branch, and inspect history (LFCS includes Git basics).

### Concept

```bash
cd ~/lfcs-lab && mkdir git-lab && cd git-lab
git init
echo "lab" > README.md
git add README.md
git status
git commit -m "Initial commit"
git branch feature
git checkout feature
git log --oneline
```

### Why This Matters

Config-as-code and exam tasks expect basic Git fluency.

### Mini examples

- `git diff`
- `git clone` (if network)

### Micro exercises

1. Make a second commit
2. Create and switch a branch
3. Show `git log -1`

### Key takeaway

add → commit → status. Muscle memory.
