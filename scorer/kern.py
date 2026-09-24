import re
from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path

from notes import SEMITONES, Measure, Note, Rest

SEPARATORS = str.maketrans("", "", "·@")
INLINE = re.compile(r"/([1-5]+)$")
DURATION = re.compile(r"(\d+)(?:%(\d+))?(\.*)")
PITCH = re.compile(r"([a-gA-G])\1*")
KEY_ACCIDENTAL = re.compile(r"[a-g]([#-])")


@dataclass
class Spine:
    kern: bool
    staff: int
    position: Fraction = Fraction(0)
    key: tuple = ()
    fing: bool = False


def fingered(notes, field):
    parts = field.split()
    for index, note in enumerate(notes):
        part = parts[index] if index < len(parts) else "x"
        digits = tuple(ch for ch in part if ch in "12345")
        if digits:
            notes[index] = replace(note, fingering=digits)
    return notes


def comment_mark(line):
    kind, _, value = line[2:].partition(":")
    return (kind, value, Fraction(0)) if kind in ("dynamic", "wedge") and value else None


def quarters(token):
    found = DURATION.search(token)
    if not found:
        return Fraction(0)
    number, divisor, dots = int(found.group(1)), found.group(2), len(found.group(3))
    whole = Fraction(8) if number == 0 else Fraction(4 * int(divisor or 1), number)
    return whole * (2 - Fraction(1, 2 ** dots))


def pitch_of(token, key=()):
    found = PITCH.search(token)
    if not found:
        return None
    letters = found.group(0)
    octave = 3 + len(letters) if letters[0].islower() else 4 - len(letters)
    step = letters[0].upper()
    written = token.count("#") - token.count("-")
    alter = written if written or "n" in token else dict(key).get(step, 0)
    return step, alter, 12 * (octave + 1) + SEMITONES[step] + alter


def ties_of(token):
    kinds = set()
    if "[" in token or "_" in token:
        kinds.add("start")
    if "]" in token or "_" in token:
        kinds.add("stop")
    return frozenset(kinds)


def read_token(token, spine, measure):
    parts = token.translate(SEPARATORS).split()
    if not parts:
        return
    grace = any("q" in part for part in parts)
    length = Fraction(0) if grace else quarters(parts[0])
    for part in parts:
        if "yy" in part:
            continue
        if "r" in part:
            measure.rests.append(Rest(spine.staff, spine.position, length))
            continue
        digits = INLINE.search(part)
        if digits:
            part = part[:digits.start()]
        pitch = pitch_of(part, spine.key)
        if pitch:
            step, alter, midi = pitch
            measure.notes.append(Note(spine.staff, spine.position, midi, length, grace, step, alter, ties_of(part),
                                      tuple(digits.group(1)) if digits else ()))
    spine.position += length


def key_alters(token):
    return tuple((letter.upper(), 1 if mark == "#" else -1)
                 for letter, mark in re.findall(r"([a-g])([#-])", token))


def signature(token):
    if token.startswith("*k["):
        marks = KEY_ACCIDENTAL.findall(token)
        return "key", str(sum(1 if mark == "#" else -1 for mark in marks))
    if re.fullmatch(r"\*M\d+/\d+", token):
        return "time", token[2:]
    return None


def reshaped(spines, tokens):
    after = []
    joining = False
    for spine, token in zip(spines, tokens):
        if token == "*-":
            joining = False
            continue
        if token == "*v":
            if joining:
                after[-1].position = max(after[-1].position, spine.position)
            else:
                after.append(spine)
            joining = True
            continue
        joining = False
        after.append(spine)
        if token == "*^":
            after.append(Spine(spine.kern, spine.staff, spine.position, spine.key))
    return after


def number_staves(spines):
    kern = [spine for spine in spines if spine.kern]
    for index, spine in enumerate(kern):
        spine.staff = len(kern) - index


def walk_kern(text):
    spines = []
    for line in text.splitlines():
        if line.startswith("!!"):
            yield "comment", line, comment_mark(line)
            continue
        if not line.strip() or line.startswith("!"):
            yield "skip", line, None
            continue
        tokens = line.split("\t")
        if spines and spines[-1].fing and len(tokens) == len(spines) - 1:
            tokens.append(tokens[0] if line.startswith("=") else "*" if line.startswith("*") else ".")
        if tokens[0].startswith("**"):
            spines = [Spine(token.startswith(("**kern", "**ekern", "**bekern")), 1, fing=token.startswith("**fing"))
                      for token in tokens]
            number_staves(spines)
            yield "header", line, spines
            continue
        if len(tokens) != len(spines):
            yield "skip", line, None
            continue
        if all(token.startswith("*") for token in tokens):
            detail = {"signatures": [], "pedal": []}
            for spine, token in zip(spines, tokens):
                staff = re.fullmatch(r"\*staff(\d+)", token)
                if staff and spine.kern:
                    spine.staff = int(staff.group(1))
                if spine.kern and token.startswith("*k["):
                    spine.key = key_alters(token)
                if spine.kern and token in ("*ped", "*Xped"):
                    detail["pedal"].append(("pedal", "start" if token == "*ped" else "stop", spine.position))
                sign = signature(token) if spine.kern else None
                if sign:
                    detail["signatures"].append(sign)
            yield "interp", line, detail
            if any(token in ("*^", "*v", "*-") for token in tokens):
                spines = reshaped(spines, tokens)
            continue
        if tokens[0].startswith("="):
            number = re.search(r"\d+", tokens[0])
            for spine in spines:
                spine.position = Fraction(0)
            yield "bar", line, number.group(0) if number else None
            continue
        scratch = Measure("")
        notes, rests = [], []
        for spine, token in zip(spines, tokens):
            if spine.kern and token != ".":
                before_notes, before_rests = len(scratch.notes), len(scratch.rests)
                read_token(token, spine, scratch)
                notes += scratch.notes[before_notes:]
                rests += scratch.rests[before_rests:]
        fields = [token for spine, token in zip(spines, tokens) if spine.fing]
        yield "data", line, {"notes": notes, "rests": rests, "fing": fields}
        if any(token in ("*^", "*v", "*-") for token in tokens):
            spines = reshaped(spines, tokens)


def is_note(part):
    part = part.translate(SEPARATORS)
    return "yy" not in part and "r" not in part and pitch_of(INLINE.sub("", part), ()) is not None


def inline_of(text):
    lines = text.splitlines()
    if not lines or "**fing" not in lines[0].split("\t"):
        return text
    out = []
    for line in lines:
        cells = line.split("\t")
        if line.startswith("**"):
            out.append("\t".join(c for c in cells if c != "**fing"))
        elif line.startswith("!!") or len(cells) < 2:
            out.append(line)
        elif line[0] in "*=!":
            out.append("\t".join(cells[:-1]))
        else:
            digits = cells[-1].split(" ") if cells[-1] not in (".", "") else []
            kern, taken = cells[:-1], 0
            for i, cell in enumerate(kern):
                if cell == ".":
                    continue
                parts = []
                for part in cell.split(" "):
                    if is_note(part):
                        digit = "".join(ch for ch in (digits[taken] if taken < len(digits) else "x") if ch in "12345")
                        taken += 1
                        part = part + "/" + digit if digit else part
                    parts.append(part)
                kern[i] = " ".join(parts)
            out.append("\t".join(kern))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def well_formed(text):
    out, width = [], None
    for line in text.splitlines():
        cells = line.split("\t")
        if cells[0].startswith("**"):
            width = len(cells)
        elif width is not None and line.strip() and not line.startswith("!!"):
            fill = "*-" if line.startswith("*-") else "*" if line.startswith("*") else "!" if line.startswith("!") else cells[0] if line.startswith("=") else "."
            cells = cells + [fill] * (width - len(cells))
            line = "\t".join(cells)
            if line.startswith("*") and not line.startswith("*-"):
                runs = [len(run) for run in re.findall(r"v+", "".join("v" if c == "*v" else "." for c in cells))]
                width += cells.count("*^") - sum(run - 1 for run in runs)
        out.append(line)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def without_layers(text):
    lines = text.split("\n")
    header = lines[0].split("\t") if lines else []
    spined = "**fing" in header
    spines = header.count("**kern")
    kept = []
    for line in lines:
        if line.startswith("!!dynamic:") or line.startswith("!!wedge:"):
            continue
        fields = line.split("\t")[:spines] if spined else line.split("\t")
        if fields and all(f in ("*", "*ped", "*Xped") for f in fields) and any(f in ("*ped", "*Xped") for f in fields):
            continue
        if line and line[0] not in "*!=":
            fields = [" ".join(INLINE.sub("", part) for part in field.split(" ")) for field in fields]
        kept.append("\t".join(fields))
        if spined and line.startswith("*"):
            runs = [len(run) for run in re.findall(r"v+", "".join("v" if f == "*v" else "." for f in fields))]
            spines += fields.count("*^") - sum(run - 1 for run in runs)
    return "\n".join(kept)


def read_kern(path):
    measures = []
    current = Measure("1")
    pending, moment, end = [], Fraction(0), Fraction(0)

    def stamp(at):
        current.marks += [(kind, value, at) for kind, value, _ in pending]
        pending.clear()

    for kind, line, detail in walk_kern(Path(path).read_text(encoding="utf-8", errors="replace")):
        if kind == "comment" and detail:
            pending.append(detail)
        elif kind == "interp":
            pending.extend(detail["pedal"])
            for sign in detail["signatures"]:
                if sign not in current.signatures:
                    current.signatures.append(sign)
        elif kind == "bar":
            stamp(end)
            if current.notes or current.rests:
                measures.append(current)
                current = Measure(detail or str(len(measures) + 1))
            elif detail:
                current.number = detail
            moment = end = Fraction(0)
        elif kind == "data":
            events = detail["notes"] + detail["rests"]
            if events:
                moment = min(event.onset for event in events)
                end = max([end] + [event.onset + event.duration for event in events])
                stamp(moment)
            notes = detail["notes"]
            for field in detail["fing"]:
                if field != ".":
                    notes = fingered(notes, field)
            current.notes += notes
            current.rests += detail["rests"]
    stamp(end)
    if current.notes or current.rests:
        measures.append(current)
    return measures
