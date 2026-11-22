# Plugin evals

End-to-end cases for `claude plugin eval`. Each case generates its own synthetic video in a scaffold script (no media is committed) and grades the agent on using the scripts, verifying outputs, and reporting honestly.

| Case | Checks |
| :--- | :--- |
| `local-landscape` | Skill loaded, plan → render → verify → captions, honest low-resolution report, no invented dialogue |
| `rotated-phone` | Rotation handled: 3:4 photos are 1080x1440 from the 1080x1920 display frame |
| `missing-input` | Asks for a video instead of inventing content |

Run (needs ffmpeg; runs full Claude sessions on your account, so it costs tokens):

```bash
claude plugin eval . --scaffold --allow-tools Bash Write Edit --runs 1 --no-publish
```

`--scaffold` is required to generate the test videos. Without `--runs 1` each case runs twice (`runs: 2`). Results go to `evals/results/` (git-ignored).
