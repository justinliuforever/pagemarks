import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, replace
from fractions import Fraction

from common import MUSICXML_SUFFIXES, musicxml_text

SEMITONES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


@dataclass(frozen=True)
class Note:
    staff: int
    onset: Fraction
    pitch: int
    duration: Fraction
    grace: bool
    step: str
    alter: int
    ties: frozenset
    fingering: tuple = ()


@dataclass(frozen=True)
class Rest:
    staff: int
    onset: Fraction
    duration: Fraction


@dataclass
class Measure:
    number: str
    notes: list = field(default_factory=list)
    rests: list = field(default_factory=list)
    signatures: list = field(default_factory=list)
    marks: list = field(default_factory=list)


def is_printed(note):
    return note.get("print-object") != "no" and (note.findtext("notehead") or "").strip() != "none"


def tie_kinds(note):
    kinds = {tie.get("type") for tie in note.findall("tie")}
    kinds |= {tied.get("type") for tied in note.iter("tied")}
    return frozenset(kind for kind in kinds if kind in ("start", "stop"))


def signatures(attributes):
    found = []
    for key in attributes.findall("key"):
        found.append(("key", key.findtext("fifths") or "0"))
    for time in attributes.findall("time"):
        found.append(("time", f"{time.findtext('beats')}/{time.findtext('beat-type')}"))
    return found


def fingering_of(note):
    return tuple(ch for mark in note.iter("fingering") for ch in (mark.text or "") if ch in "12345")


def words_fingering(direction):
    return tuple(text for text in (w.text.strip() for w in direction.iter("words") if w.text) if text in "12345" and len(text) == 1)


def marks(direction, onset=Fraction(0)):
    found = []
    for kind in direction.findall("direction-type"):
        for dynamic in kind.findall("dynamics"):
            found += [("dynamic", child.text.strip() if child.tag == "other-dynamics" and child.text else child.tag, onset)
                      for child in dynamic]
        for wedge in kind.findall("wedge"):
            if wedge.get("type") in ("crescendo", "diminuendo"):
                found.append(("wedge", wedge.get("type"), onset))
        for pedal in kind.findall("pedal"):
            if pedal.get("type") in ("start", "stop", "change"):
                found.append(("pedal", pedal.get("type"), onset))
    return found


def read_part(part, staff_offset=0):
    measures = []
    divisions = 1
    for node in part.findall("measure"):
        measure = Measure(node.get("number", ""))
        position = Fraction(0)
        chord_onset = Fraction(0)
        pending = []
        for child in node:
            if child.tag == "attributes":
                if int(child.findtext("divisions") or 0) > 0:
                    divisions = int(child.findtext("divisions"))
                measure.signatures += signatures(child)
            elif child.tag == "direction":
                measure.marks += marks(child, position + Fraction(int(child.findtext("offset") or 0), divisions))
                for digit in words_fingering(child):
                    pending.append((int(child.findtext("staff") or 1) + staff_offset,
                                    position + Fraction(int(child.findtext("offset") or 0), divisions), digit))
            elif child.tag == "backup":
                position -= Fraction(int(child.findtext("duration") or 0), divisions)
            elif child.tag == "forward":
                position += Fraction(int(child.findtext("duration") or 0), divisions)
            elif child.tag == "note":
                grace = child.find("grace") is not None
                length = Fraction(0) if grace else Fraction(int(child.findtext("duration") or 0), divisions)
                onset = chord_onset if child.find("chord") is not None else position
                if child.find("chord") is None:
                    chord_onset = position
                    position += length
                staff = int(child.findtext("staff") or 1) + staff_offset
                if not is_printed(child):
                    continue
                pitch = child.find("pitch")
                if pitch is not None:
                    step = pitch.findtext("step")
                    alter = int(float(pitch.findtext("alter") or 0))
                    midi = 12 * (int(pitch.findtext("octave")) + 1) + SEMITONES[step] + alter
                    measure.notes.append(Note(staff, onset, midi, length, grace, step, alter, tie_kinds(child),
                                              fingering_of(child)))
                elif child.find("rest") is not None:
                    measure.rests.append(Rest(staff, onset, length))
        for staff, onset, digit in pending:
            for index, note in enumerate(measure.notes):
                if note.staff == staff and note.onset == onset:
                    measure.notes[index] = replace(note, fingering=note.fingering + (digit,))
                    break
        measures.append(measure)
    return measures


def merged(parts):
    longest = max(parts, key=len)
    merged_measures = [Measure(measure.number) for measure in longest]
    for part in parts:
        for target, measure in zip(merged_measures, part):
            target.notes += measure.notes
            target.rests += measure.rests
            target.marks += measure.marks
            target.signatures += [sign for sign in measure.signatures if sign not in target.signatures]
    return merged_measures


KERN_SUFFIXES = (".krn", ".kern", ".ekern", ".bekern")
SCORE_SUFFIXES = MUSICXML_SUFFIXES + KERN_SUFFIXES


def read_score(path):
    if str(path).lower().endswith(KERN_SUFFIXES):
        from kern import read_kern
        return read_kern(path)
    try:
        text, _, _ = musicxml_text(path)
        root = ET.fromstring(text.encode("utf-8"))
        parts, staves_so_far = [], 0
        for part in root.findall("part"):
            parts.append(read_part(part, staves_so_far))
            staves_so_far += max([int(node.text) for node in part.iter("staves") if (node.text or "").isdigit()] or [1])
    except (ET.ParseError, OSError, UnicodeError, KeyError, ValueError, TypeError, AttributeError):
        return []
    return merged(parts) if parts else []


def read_pages(paths):
    measures = []
    for path in paths:
        measures += read_score(path)
    return measures
