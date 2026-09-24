"""Score a system's readings of the PageMarks public fingering set.
    python scorer/score.py READINGS [--pairs public-set/pairs.jsonl]
READINGS holds one folder per piece id with the system's pages inside as p001.musicxml (or .krn), p002, …, one file per
page of the piece's PDF; a page with no file is read as empty. Bars are aligned by their notes; a note matches on onset
and pitch; a digit counts when the same digit sits on the aligned chord (staff and onset)."""
import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare import compare, summary
from notes import read_score

SUFFIXES = (".musicxml", ".xml", ".mxl", ".krn")


def pooled(rows):
    matched = sum(r["fingering_matched"] for r in rows)
    truth = sum(r["fingering_in_truth"] for r in rows)
    read = sum(r["fingering_read"] for r in rows)
    return matched / truth if truth else None, matched / read if read else None


def bootstrap(rows, draws=10000, seed=0):
    rng = random.Random(seed)
    recalls, precisions = [], []
    for _ in range(draws):
        recall, precision = pooled([rng.choice(rows) for _ in rows])
        if recall is not None:
            recalls.append(recall)
        if precision is not None:
            precisions.append(precision)
    band = lambda xs: (sorted(xs)[int(0.025 * len(xs))], sorted(xs)[int(0.975 * len(xs)) - 1]) if xs else (None, None)
    return band(recalls), band(precisions)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("readings", type=Path)
    parser.add_argument("--pairs", type=Path, default=Path(__file__).resolve().parent.parent / "public-set" / "pairs.jsonl")
    args = parser.parse_args()
    root = args.pairs.parent
    rows = []
    for pair in map(json.loads, args.pairs.read_text(encoding="utf-8").splitlines()):
        truth = read_score(root / pair["musicxml"])
        pages = sorted(p for p in (args.readings / pair["id"]).glob("p[0-9]*") if p.suffix in SUFFIXES)
        guess = [measure for page in pages for measure in read_score(page)]
        found = compare(truth, guess)
        rows.append({"id": pair["id"], "pages_read": len(pages), "notes_f1": summary(found)["f1"],
                     "fingering_matched": found["fingerings matched"], "fingering_in_truth": found["fingerings in truth"],
                     "fingering_read": found["fingerings read"]})
        r = rows[-1]
        print(f"{r['id']:22} pages {r['pages_read']:2}  notes F1 {r['notes_f1']:.3f}  "
              f"fingering {r['fingering_matched']:4} of {r['fingering_in_truth']:4}, {r['fingering_read']:4} read")
    recall, precision = pooled(rows)
    (r_low, r_high), (p_low, p_high) = bootstrap(rows)
    show = lambda x: "-" if x is None else f"{x:.3f}"
    print(f"\n{len(rows)} pieces  notes F1 mean {sum(r['notes_f1'] for r in rows) / len(rows):.3f}  "
          f"fingering recall {show(recall)} [{show(r_low)}, {show(r_high)}]  precision {show(precision)} "
          f"[{show(p_low)}, {show(p_high)}]  (95% bootstrap over pieces)")


if __name__ == "__main__":
    main()
