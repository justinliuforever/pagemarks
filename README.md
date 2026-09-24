# PageMarks public fingering set

Test set and scorer for *PageMarks: Reading Printed Fingering, Pedal and Dynamics from Full Piano Score Pages*
(ISMIR 2026 Late-Breaking Demo).

## Contents

- `public-set/` — 12 PDMX piano pieces with printed fingering that no PageMarks training data used: 48 pages,
  893 digits. `musicxml/` holds the truths, `pdf/` the MuseScore 4.7.5 renderings, `public_fingering_set.json`
  the selection rule and each piece's PDMX path.
- `scorer/` — the note and fingering scorer used for every system in the paper. Python 3, no dependencies.
- `smb-subset/pages.jsonl` — the 101 pages of the Sheet Music Benchmark used to compare notes.

## Scoring

```
python3 scorer/score.py READINGS
```

`READINGS/<piece id>/p001.musicxml`, `p002.musicxml`, … — one MusicXML or `**kern` file per PDF page; a missing
page counts as empty. A note matches on onset and pitch within aligned bars; a digit matches when the same digit
sits on the aligned chord. The output is notes F1 and fingering recall and precision per piece, then pooled with
a 95% bootstrap over pieces.

## Results

Fingering recall / precision on the public set:

| System | Recall | Precision |
|---|---|---|
| PageMarks (mean of three seeds) | 0.925 | 0.948 |
| Audiveris 5.11, fingering recognition on | 0.642 | 0.915 |
| GPT-6 Astra, high effort | 0.981 | 0.988 |
| GPT-6 Sol, high effort | 0.901 | 0.948 |
| Grok 4.6, high effort | 0.52 | 0.58 |
