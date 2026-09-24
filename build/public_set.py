"""The public fingering set: PDMX piano scores with printed fingering that no training cut has used, rendered by MuseScore.
    .venv/bin/python scripts/public_set.py --exclude MANIFEST.jsonl [--exclude …]
Writes manifest/public_fingering_set.json once (it refuses to overwrite) and manifest/pairs_public_fingering.jsonl.

A score qualifies when PDMX keeps it in its deduplicated subset with a valid MusicXML; it is one piano part on two
staves; it carries at least MIN_DIGITS fingering marks, of which at least FINGERING_LIKE are digits 1-5 (a score that
spends the element on scale degrees or chord numbers is not fingered); and neither it, nor any score PDMX groups with
it as the same song or arrangement, nor any score of the same normalised song name, is a source named by an --exclude
manifest. Every qualifying score is taken, cut after the bar that keeps its MuseScore render within MAX_PAGES pages,
and that cut MusicXML is both what is rendered and the truth."""
import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, MANIFEST, read_jsonl, write_jsonl
from notes import read_score
from relabel import member_index, source_score

FROZEN = MANIFEST / "public_fingering_set.json"
PAIRS = MANIFEST / "pairs_public_fingering.jsonl"
OUT = DATA / "public-set"
MIN_DIGITS = 10
FINGERING_LIKE = 0.95
MAX_PAGES = 5
MUSIC = 20
PIANO = re.compile(r"piano|klavier|fl[uü]gel|pianoforte|keyboard", re.I)
DIGITS = re.compile(r"^\s*[1-5](\s*[-–,/ ]\s*[1-5])*\s*$")


def hash_of(path):
    return Path(path).stem


def song(name):
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def excluded_sources(manifests):
    return {row["source"] for path in manifests for row in read_jsonl(Path(path)) if row.get("source")}


def cut(source, target, keep):
    tree = ET.parse(source)
    for part in tree.getroot().findall("part"):
        for measure in part.findall("measure")[keep:]:
            part.remove(measure)
    tree.write(target, encoding="UTF-8", xml_declaration=True)


def rendered(score, pdf):
    pdf.unlink(missing_ok=True)
    subprocess.run(["mscore", "-o", str(pdf), str(score)], capture_output=True, timeout=600)
    if not pdf.exists():
        return 0
    with pymupdf.open(pdf) as document:
        return len(document)


def music_pages(pdf):
    with pymupdf.open(pdf) as document:
        return [index + 1 for index, page in enumerate(document) if len(page.get_drawings()) >= MUSIC]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude", action="append", required=True)
    args = parser.parse_args()
    if FROZEN.exists():
        raise SystemExit(f"{FROZEN} is frozen")

    banned = excluded_sources(args.exclude)
    csv.field_size_limit(sys.maxsize)
    with (DATA / "pdmx" / "PDMX.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_hash = {hash_of(row["path"]): row for row in rows}
    groups = {by_hash[h][key] for h in banned if h in by_hash for key in ("best_path", "best_arrangement")}
    songs = {song(by_hash[h]["song_name"]) for h in banned if h in by_hash} - {""}
    counted = {hash_of(row["mxl"]): row for row in map(json.loads, filter(str.strip, (DATA / "pdmx" / "scan.jsonl")
                                                                            .read_text(encoding="utf-8").split("\n")))}
    where = member_index()
    (OUT / "render").mkdir(parents=True, exist_ok=True)

    taken, refused = [], []
    candidates = sorted(rows, key=lambda row: hashlib.sha1(row["path"].encode()).hexdigest())
    for row in candidates:
        h, facts = hash_of(row["path"]), counted.get(hash_of(row["path"]))
        if (row["subset:deduplicated"] != "True" or row["subset:valid_mxl_pdf"] != "True" or not facts
                or facts["parts"] != 1 or facts["staves"] != 2 or facts["fingering"] < MIN_DIGITS
                or not PIANO.search((facts["part_names"] or [""])[0])):
            continue
        if h in banned or row["best_path"] in groups or row["best_arrangement"] in groups or song(row["song_name"]) in songs:
            continue
        if source_score(h, where) is None:
            refused.append({"pdmx": row["path"], "why": "not in the archive"}); continue
        whole = DATA / "relabelled" / "source" / f"{h}.musicxml"
        text = whole.read_text(encoding="utf-8", errors="replace")
        values = re.findall(r"<fingering[^>]*>([^<]*)</fingering>", text)
        if sum(bool(DIGITS.match(v)) for v in values) < FINGERING_LIKE * len(values):
            refused.append({"pdmx": row["path"], "why": "its fingering elements hold other numbers"}); continue
        score, pdf = OUT / f"{h}.musicxml", OUT / "render" / f"{h}.pdf"
        bars = len(ET.parse(whole).getroot().find("part").findall("measure"))
        keep = bars
        while True:
            cut(whole, score, keep)
            pages = rendered(score, pdf)
            if not pages or pages <= MAX_PAGES or keep <= 4:
                break
            keep = max(4, min(keep - 1, keep * MAX_PAGES // pages))
        if not pages or pages > MAX_PAGES:
            refused.append({"pdmx": row["path"], "why": "MuseScore wrote no PDF" if not pages else f"{pages} pages at 4 bars"}); continue
        digits = sum(len(note.fingering) for measure in read_score(score) for note in measure.notes)
        music = music_pages(pdf)
        taken.append({"id": f"public-{h[:12]}", "pdmx": row["path"], "song": row["song_name"], "composer": row["composer_name"],
                      "bars": keep, "of_bars": bars, "pages": pages, "music_pages": music, "marks": digits})
        print(f"  {len(taken):3d} {h[:12]} bars {keep:4d} of {bars:4d}, {pages} pages, {digits:4d} digits  {row['song_name'][:50]}", flush=True)

    version = subprocess.run(["mscore", "--version"], capture_output=True, text=True).stdout.strip()
    FROZEN.write_text(json.dumps({
        "frozen": date.today().isoformat(), "rule": __doc__.split("\n\n", 1)[1].strip(), "renderer": version,
        "min_digits": MIN_DIGITS, "fingering_like": FINGERING_LIKE, "max_pages": MAX_PAGES,
        "excluded_manifests": [Path(p).name for p in args.exclude], "excluded_sources": len(banned),
        "pieces": taken, "refused": refused,
        "totals": {"pieces": len(taken), "pages": sum(t["pages"] for t in taken),
                   "music_pages": sum(len(t["music_pages"]) for t in taken), "marks": sum(t["marks"] for t in taken)}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    write_jsonl(PAIRS, [{"id": t["id"], "image": f"data/public-set/render/{hash_of(t['pdmx'])}.pdf",
                         "symbolic": [f"data/public-set/{hash_of(t['pdmx'])}.musicxml"],
                         "collection": "pdmx", "engraving": "musescore", "marks": t["marks"]} for t in taken])
    print(f"{len(taken)} pieces, {sum(len(t['music_pages']) for t in taken)} pages of music, "
          f"{sum(t['marks'] for t in taken)} digits; {len(refused)} refused")


if __name__ == "__main__":
    main()
