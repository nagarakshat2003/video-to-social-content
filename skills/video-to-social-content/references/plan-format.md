# plan.json Format

`outputs/<video-name>/plan.json` is the only file you write by hand before rendering. `render.py`, `verify.py` and `captions.py` derive every crop, fade, file name and check from it. Validate it any time with `python3 "$S/plan.py" outputs/<video-name>/plan.json`.

## Example

```json
{
  "reels": [
    {
      "id": "01", "slug": "insight", "genre": "Insight",
      "start": "00:01:14.0", "end": "00:01:45.5",
      "ratio": "9:16", "subject_x": 960,
      "hook": "The $2M mistake"
    },
    {
      "id": "02", "slug": "walkthrough", "genre": "Action",
      "start": 212.4, "end": 241.0,
      "subject_track": [{"t": 212.4, "x": 700}, {"t": 228, "x": 1150}, {"t": 241, "x": 1200}]
    }
  ],
  "photos": [
    {"id": "01", "slug": "speaker", "time": "00:01:24.5", "subject_x": 900, "carousel": 1},
    {"id": "02", "slug": "crowd", "time": 95.2, "carousel": 1, "theme": "Audience reaction"}
  ]
}
```

## Fields

**Times** are source timestamps: seconds (`74.5`) or `HH:MM:SS.mmm` / `MM:SS`. Use the same times you see in `analysis/` and the contact sheets.

**Subject position** is in *display* pixels of the source (after rotation, as reported in `meta.json`):

| Field | Meaning |
| :--- | :--- |
| `subject_x` | Horizontal centre of the subject (face / action). Used when the source is wider than the target ratio (the usual case for landscape footage). Omit to centre. |
| `subject_y` | Vertical centre. Used only when the source is narrower than the target (e.g. 9:16 footage to 3:4). |
| `subject_track` | Reels only: at least 2 `{"t": time, "x": pixels}` points; the crop pans linearly between them. Use it when the subject moves across the frame instead of splitting the clip. `track_subject.py` can fill it in. |

**Reels**

| Field | Required | Notes |
| :--- | :--- | :--- |
| `id` | yes | Letters, digits, `-`, `_`. Becomes `reel_<id>_<slug>.mp4`. |
| `start`, `end` | yes | 3–90 s hard limit; 15–60 s recommended. Cut on sentence boundaries. |
| `slug` | no | Short name for the file. |
| `ratio` | no | `9:16` (default), `3:4` or `1:1`. |
| `genre`, `hook` | no | Copied into `captions.md`. |
| `canvas` | no | `true` also renders a 1080x1920 blurred-background version. Set it only after the user agrees. |

**Photos**

| Field | Required | Notes |
| :--- | :--- | :--- |
| `id`, `time` | yes | Becomes `photo_<id>_<slug>.jpg`. |
| `ratio` | no | `3:4` (default), `9:16` or `1:1`. |
| `carousel` | no | Group number (default 1); photos in the same group form one post, in plan order. |
| `format` | no | `jpg` (default) or `png`. |
| `slug`, `theme` | no | File name and a short label for the summary table. |

Unknown keys are ignored with a warning; `notes` is allowed anywhere for your own reasoning.
