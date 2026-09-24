# PageMarks: a public test set for printed piano fingering

Companion to the ISMIR 2026 late-breaking abstract *PageMarks: Reading Printed Fingering, Pedal and Dynamics from Full
Piano Score Pages*. It holds the one test set of that paper anyone can rerun, and the scorer every system was measured
with.

## The public fingering set

`public-set/`: every PDMX score that is one piano part on two staves, prints ten or more `<fingering>` marks of which 95%
are digits 1–5, and never reached our training data — excluded by PDMX id, by PDMX's duplicate groups and by song name.
Long pieces are cut at the bar that keeps a MuseScore 4.7.5 rendering within five pages; the cut MusicXML is the truth.

- 12 pieces, 48 pages of music, 893 printed digits (`public_fingering_set.json` lists each piece's PDMX path, bars and digits)
- `musicxml/` the truths, `pdf/` the renderings, `pairs.jsonl` which is which
- `build/public_set.py` is the script that froze the set, kept for its rule (it runs inside the training repository)

## Scoring a system

Rasterise each PDF page (we used 300 dpi), have the system write one MusicXML (or `**kern`) per page, then:

```
python3 scorer/score.py READINGS
```

`READINGS/<piece id>/p001.musicxml, p002.musicxml, …` — one file per page of the piece's PDF; a missing page is read as
empty. Bars are aligned by their notes, a note matches on onset and pitch, and a printed digit counts when the same digit
sits on the aligned chord (staff and onset). The output gives notes F1 and fingering recall and precision per piece, and
the pooled figures with a 95% bootstrap over pieces. The scorer needs only Python 3.

## Results (fingering recall / precision)

| System | Public set |
|---|---|
| PageMarks (three seeds) | 0.925 / 0.948 |
| Audiveris 5.11, fingering recognition on | 0.642 / 0.915 |
| GPT-6 Astra, high effort | 0.981 / 0.988 |
| Claude Opus 5.5, high effort | 0.96 / 0.96 |
| GPT-6 Sol, high effort | 0.901 / 0.948 |
| Grok 4.6, high effort | 0.52 / 0.58 |

Frontier models were asked for MusicXML with one prompt, an unreadable or empty answer asked again up to three times.

## The SMB subset

`smb-subset/pages.jsonl` lists the 101 pages of the Sheet Music Benchmark (PRAIG/SMB) used for the frontier models'
notes, stratified by texture (Pianoform 50, Monophonic 20, Quartet 20, PianoAndVoice 6, Other 5) in sha1 order of the SMB
id; `smb_subset.py` draws it from the dataset.
