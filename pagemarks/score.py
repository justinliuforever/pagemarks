import argparse
import json
import random
import sys
from pathlib import Path

from .compare import compare, summary
from .notes import read_score

SUFFIXES = (".musicxml", ".xml", ".mxl", ".krn")
PAIRS = Path(__file__).resolve().parent.parent / "public-set" / "pairs.jsonl"


def warn(message):
    print(message, file=sys.stderr)


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


def pages_of(folder):
    pages = {}
    for path in sorted(folder.iterdir()):
        if path.name.startswith("."):
            continue
        if path.suffix not in SUFFIXES or not (path.stem[:1] == "p" and path.stem[1:].isdigit()):
            warn(f"skipped: {path} is not pNNN.musicxml, .xml, .mxl or .krn")
            continue
        number = int(path.stem[1:])
        if number in pages:
            raise ValueError(f"two files for page {number} of {folder.name}: {pages[number].name}, {path.name}")
        pages[number] = path
    return [pages[number] for number in sorted(pages)]


def score(readings, pairs=PAIRS):
    readings, pairs = Path(readings), Path(pairs)
    if not readings.is_dir():
        raise NotADirectoryError(f"READINGS is not a directory: {readings}")
    pieces = [json.loads(line) for line in pairs.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = {piece["id"] for piece in pieces}
    for folder in sorted(readings.iterdir()):
        if folder.name not in ids and not folder.name.startswith("."):
            warn(f"ignored: {folder.name} is not a piece id")
    if not any((readings / piece_id).is_dir() for piece_id in ids):
        raise FileNotFoundError(f"no piece folders in {readings}; folder names are the ids in {pairs}")
    rows = []
    for piece in pieces:
        folder = readings / piece["id"]
        if not folder.is_dir():
            warn(f"no folder for {piece['id']}, scored as empty")
        pages, guess = pages_of(folder) if folder.is_dir() else [], []
        if folder.is_dir() and not pages:
            warn(f"no pages in {folder}, scored as empty")
        for page in pages:
            measures = read_score(page)
            if not measures:
                warn(f"{page}: no bars read, scored as empty")
            guess += measures
        truth = read_score(pairs.parent / piece["musicxml"])
        if not truth:
            raise ValueError(f"truth for {piece['id']} has no bars: {pairs.parent / piece['musicxml']}")
        found = compare(truth, guess)
        rows.append({"id": piece["id"], "pages_read": len(pages),
                     "notes_f1": summary(found)["f1"], "fingering_matched": found["fingerings matched"],
                     "fingering_in_truth": found["fingerings in truth"], "fingering_read": found["fingerings read"]})
    if not any(r["pages_read"] for r in rows):
        raise FileNotFoundError(f"no pages in any piece folder of {readings}")
    recall, precision = pooled(rows)
    recall_95, precision_95 = bootstrap(rows)
    return {"pieces": rows, "notes_f1": sum(r["notes_f1"] for r in rows) / len(rows), "recall": recall,
            "precision": precision, "recall_95": recall_95, "precision_95": precision_95}


def main():
    parser = argparse.ArgumentParser(prog="pagemarks-score", description="Score readings of the PageMarks public fingering set.")
    parser.add_argument("readings", type=Path, metavar="READINGS", help="a folder per piece id holding p001.musicxml, p002.musicxml, ...")
    parser.add_argument("--pairs", type=Path, default=PAIRS, help="the pairs file (default: public-set/pairs.jsonl of the clone)")
    args = parser.parse_args()
    if args.pairs == PAIRS and not PAIRS.exists():
        parser.exit(1, "error: public-set/pairs.jsonl not found; install with pip install -e . from a clone, or pass --pairs\n")
    try:
        result = score(args.readings, args.pairs)
    except (OSError, ValueError) as error:
        parser.exit(1, f"error: {error}\n")
    for r in result["pieces"]:
        print(f"{r['id']:22} pages {r['pages_read']:2}  notes F1 {r['notes_f1']:.3f}  "
              f"fingering {r['fingering_matched']:4} of {r['fingering_in_truth']:4}, {r['fingering_read']:4} read")
    show = lambda x: "-" if x is None else f"{x:.3f}"
    (r_low, r_high), (p_low, p_high) = result["recall_95"], result["precision_95"]
    print(f"\n{len(result['pieces'])} pieces  notes F1 mean {result['notes_f1']:.3f}  "
          f"fingering recall {show(result['recall'])} [{show(r_low)}, {show(r_high)}]  "
          f"precision {show(result['precision'])} [{show(p_low)}, {show(p_high)}]  (95% bootstrap over pieces)")


if __name__ == "__main__":
    main()
