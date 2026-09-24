"""A stratified subset of SMB pages, as pairs every engine reads and `table.py` scores with the note comparator.
    HF_TOKEN=… .engines/page-omr/venv/bin/python scripts/smb_subset.py [--take Pianoform=50 …]
Writes each page's image to data/raster/smb/<pair>/p001.png, its page kern (both reference corrections applied, as the
MCR evaluation reads it) to data/smb-subset/<pair>.krn, and manifest/pairs_smb_subset.jsonl. Within a texture, pages
are taken in sha1 order of their SMB id; a texture with fewer pages than its quota gives all of them."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".engines/page-omr/code/src"))
from omr.data.smb_dataset import SMBDataset

QUOTAS = {"Pianoform": 50, "Monophonic": 20, "Quartet": 20, "PianoAndVoice": 6, "Other": 5}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--take", action="append", help="TEXTURE=N; default " + " ".join(f"{k}={v}" for k, v in QUOTAS.items()))
    args = parser.parse_args()
    quotas = dict(QUOTAS)
    for item in args.take or []:
        texture, _, count = item.partition("=")
        quotas[texture] = int(count)

    smb = SMBDataset(level="page")
    by = {}
    for position, (index, _) in enumerate(smb.items):
        name = smb.rows.get(index, "id") or f"row{index}"
        by.setdefault(smb.rows.get(index, "page_texture"), []).append((hashlib.sha1(name.encode()).hexdigest(), position, index, name))
    pairs = []
    for texture, quota in quotas.items():
        for _, position, index, name in sorted(by.get(texture, []))[:quota]:
            sample = smb[position]
            pair = "smb-" + Path(name).stem
            image = ROOT / "data/raster/smb" / pair / "p001.png"
            truth = ROOT / "data/smb-subset" / f"{pair}.krn"
            image.parent.mkdir(parents=True, exist_ok=True)
            truth.parent.mkdir(parents=True, exist_ok=True)
            sample.image.convert("RGB").save(image)
            truth.write_text(sample.kern if sample.kern.endswith("\n") else sample.kern + "\n", encoding="utf-8")
            pairs.append({"id": pair, "image": str(image.relative_to(ROOT)), "symbolic": [str(truth.relative_to(ROOT))],
                          "texture": texture, "smb_id": name, "smb_row": index, "score": sample.score_id})
    with (ROOT / "manifest/pairs_smb_subset.jsonl").open("w", encoding="utf-8") as out:
        for pair in pairs:
            out.write(json.dumps(pair, ensure_ascii=False) + "\n")
    counts = {texture: sum(p["texture"] == texture for p in pairs) for texture in quotas}
    print(f"{len(pairs)} pages: {counts}; SMB holds {({t: len(v) for t, v in by.items()})}")


if __name__ == "__main__":
    main()
