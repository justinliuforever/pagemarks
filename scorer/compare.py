import argparse
import json
from collections import Counter

from notes import read_pages, read_score

GAP = -0.15
MARK_KINDS = ("fingering", "dynamic", "wedge", "pedal")


def keys(measure):
    return Counter((note.onset, note.pitch, note.grace) for note in measure.notes)


def likeness(truth, guess):
    a, b = keys(truth), keys(guess)
    if not a and not b:
        return 1.0
    return 2 * sum((a & b).values()) / (sum(a.values()) + sum(b.values()))


def align(truth, guess):
    rows, cols = len(truth), len(guess)
    score = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(1, rows + 1):
        score[i][0] = i * GAP
    for j in range(1, cols + 1):
        score[0][j] = j * GAP
    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            score[i][j] = max(score[i - 1][j - 1] + likeness(truth[i - 1], guess[j - 1]),
                              score[i - 1][j] + GAP, score[i][j - 1] + GAP)
    pairs = []
    i, j = rows, cols
    while i or j:
        # Picking the best of the three candidates, rather than testing equality against the stored score,
        # is what keeps a long run of gaps from walking off the edge when the sum rounds differently.
        paired = score[i - 1][j - 1] + likeness(truth[i - 1], guess[j - 1]) if i and j else None
        dropped = score[i - 1][j] + GAP if i else None
        added = score[i][j - 1] + GAP if j else None
        best = max(value for value in (paired, dropped, added) if value is not None)
        if paired == best:
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif dropped == best:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    return pairs[::-1]


def pitch_error(truth, guess):
    if (truth.pitch - guess.pitch) % 12 == 0:
        return "octave"
    if truth.step == guess.step and truth.pitch // 12 == guess.pitch // 12:
        return "accidental"
    return "other pitch"


def take_pairs(left, right, same):
    pairs = []
    for a in list(left):
        for b in right:
            if same(a, b):
                pairs.append((a, b))
                left.remove(a)
                right.remove(b)
                break
    return pairs


def compare_fingering(paired, missing_notes, extra_notes, number, found):
    chords = {}
    for a, b in paired:
        wanted, given = chords.setdefault((a.staff, a.onset, a.grace), (Counter(), Counter()))
        wanted.update(a.fingering)
        given.update(b.fingering)
    for (staff, onset, _), (wanted, given) in sorted(chords.items()):
        lost, added = list((wanted - given).elements()), list((given - wanted).elements())
        found["fingerings matched"] += sum((wanted & given).values())
        where = f"staff {staff} at {onset}"
        for digit, other in zip(lost, added):
            found.error("fingering", number, f"{where}: {digit} read as {other}")
        for digit in lost[len(added):]:
            found.error("missing fingering", number, f"{where}: {digit}")
        for digit in added[len(lost):]:
            found.error("extra fingering", number, f"{where}: {digit}")
    for note in missing_notes:
        for digit in note.fingering:
            found.error("missing fingering", number, f"staff {note.staff} at {note.onset}: {digit}")
    for note in extra_notes:
        for digit in note.fingering:
            found.error("extra fingering", number, f"staff {note.staff} at {note.onset}: {digit}")


def changes(measure, in_effect):
    fresh = [sign for sign in measure.signatures if in_effect.get(sign[0]) != sign[1]]
    in_effect.update(dict(fresh))
    return fresh


def compare_measure(truth, guess, number, found, in_effect=None):
    wanted, given = list(truth.notes), list(guess.notes)
    exact = take_pairs(wanted, given, lambda a, b: a == b)
    exact += take_pairs(wanted, given, lambda a, b: (a.onset, a.pitch, a.grace, a.staff) == (b.onset, b.pitch, b.grace, b.staff))
    exact += take_pairs(wanted, given, lambda a, b: (a.onset, a.pitch, a.grace) == (b.onset, b.pitch, b.grace))
    found["notes matched"] += len(exact)
    for a, b in exact:
        if not a.grace and a.duration != b.duration:
            found.error("duration", number, f"{a.step}{a.pitch} lasts {a.duration}, read as {b.duration}")
        if a.staff != b.staff:
            found.error("staff", number, f"{a.step}{a.pitch} is on staff {a.staff}, read on {b.staff}")
        if (a.step, a.alter) != (b.step, b.alter):
            found.error("spelling", number, f"{a.step}{a.alter:+d} read as {b.step}{b.alter:+d}")
        if a.ties != b.ties:
            found.error("tie", number, f"{a.step}{a.pitch} ties {sorted(a.ties)}, read as {sorted(b.ties)}")
    paired = list(exact)
    # The same-pitch pass runs first: a bar read a beat late puts unrelated notes on the same onset, and
    # pairing by onset would book every one of them as a wrong pitch.
    for a, b in take_pairs(wanted, given, lambda a, b: (a.staff, a.pitch) == (b.staff, b.pitch)):
        found.error("onset", number, f"{a.step}{a.pitch} at {a.onset}, read at {b.onset}")
        paired.append((a, b))
    for a, b in take_pairs(wanted, given, lambda a, b: (a.staff, a.onset, a.grace) == (b.staff, b.onset, b.grace)):
        found.error(pitch_error(a, b), number, f"{a.step}{a.alter:+d} ({a.pitch}) read as {b.step}{b.alter:+d} ({b.pitch})")
        paired.append((a, b))
    if "fingering" in found.emitted:
        compare_fingering(paired, wanted, given, number, found)
    for a in wanted:
        found.error("missing grace note" if a.grace else "missing note", number, f"{a.step}{a.pitch} at {a.onset}")
    for b in given:
        found.error("extra note", number, f"{b.step}{b.pitch} at {b.onset}")

    rests_wanted, rests_given = list(truth.rests), list(guess.rests)
    found["rests matched"] += len(take_pairs(rests_wanted, rests_given, lambda a, b: a == b))
    for rest in rests_wanted:
        found.error("missing rest", number, f"staff {rest.staff} at {rest.onset} for {rest.duration}")
    for rest in rests_given:
        found.error("extra rest", number, f"staff {rest.staff} at {rest.onset} for {rest.duration}")

    # Scored per bar by kind and value: a comment-form label carries no onset to hold an engine to.
    marks_wanted = Counter(mark[:2] for mark in truth.marks if mark[0] in found.emitted)
    marks_given = Counter(mark[:2] for mark in guess.marks if mark[0] in found.emitted)
    for kind, _ in (marks_wanted & marks_given).elements():
        found[f"{kind}s matched"] += 1
    for kind, value in (marks_wanted - marks_given).elements():
        found.error(f"missing {kind}", number, value)
    for kind, value in (marks_given - marks_wanted).elements():
        found.error(f"extra {kind}", number, value)

    wanted_state, given_state = in_effect if in_effect else ({}, {})
    signs_wanted = Counter(changes(truth, wanted_state))
    signs_given = Counter(changes(guess, given_state))
    for sign in (signs_wanted - signs_given).elements():
        found.error("missing signature", number, f"{sign[0]} {sign[1]}")
    for sign in (signs_given - signs_wanted).elements():
        found.error("extra signature", number, f"{sign[0]} {sign[1]}")


def mark_totals(measures):
    totals = Counter(kind for measure in measures for kind, *_ in measure.marks)
    totals["fingering"] = sum(len(note.fingering) for measure in measures for note in measure.notes)
    return totals


class Findings(Counter):
    def __init__(self):
        super().__init__()
        self.errors = []
        self.emitted = set()
        self.not_emitted = {}

    def error(self, kind, measure, detail):
        self[kind] += 1
        self.errors.append({"kind": kind, "measure": measure, "detail": detail})

    def add(self, other):
        self.update(other)
        self.errors += other.errors
        self.emitted |= other.emitted
        for kind, n in other.not_emitted.items():
            self.not_emitted[kind] = self.not_emitted.get(kind, 0) + n


def layers_emitted(measures):
    totals = mark_totals(measures)
    return {kind for kind in MARK_KINDS if totals[kind]}


def signatures_before(measures):
    state = {}
    for measure in measures:
        changes(measure, state)
    return state


def compare(truth, guess, emitted=(), in_effect_at_start=None):
    found = Findings()
    found["notes in truth"] = sum(len(measure.notes) for measure in truth)
    found["notes read"] = sum(len(measure.notes) for measure in guess)
    found["measures in truth"] = len(truth)
    found["measures read"] = len(guess)
    wanted, given = mark_totals(truth), mark_totals(guess)
    found.update({f"{kind}s in truth": wanted[kind] for kind in MARK_KINDS if wanted[kind]})
    found.update({f"{kind}s read": given[kind] for kind in MARK_KINDS if given[kind]})
    for kind in MARK_KINDS:
        if given[kind] or kind in emitted:
            found.emitted.add(kind)
        elif wanted[kind]:
            found.not_emitted[kind] = wanted[kind]
    opening = dict(in_effect_at_start or {})
    in_effect = (opening, dict(opening))
    for i, j in align(truth, guess):
        if j is None:
            found.error("missing measure", truth[i].number, f"{len(truth[i].notes)} notes")
            found["notes in missing measures"] += len(truth[i].notes)
        elif i is None:
            found.error("extra measure", guess[j].number, f"{len(guess[j].notes)} notes")
            found["notes in extra measures"] += len(guess[j].notes)
        else:
            compare_measure(truth[i], guess[j], truth[i].number, found, in_effect)
    return found


def rates(matched, in_truth, read):
    recall = matched / in_truth if in_truth else 1.0
    precision = matched / read if read else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"recall": round(recall, 4), "precision": round(precision, 4), "f1": round(f1, 4)}


def summary(found):
    scores = rates(found["notes matched"], found["notes in truth"], found["notes read"])
    for kind in MARK_KINDS:
        in_truth, read = found[f"{kind}s in truth"], found[f"{kind}s read"]
        layer = (rates(found[f"{kind}s matched"], in_truth, read) if in_truth or read
                 else {"recall": None, "precision": None, "f1": None})
        for name, value in layer.items():
            scores[f"{kind}_{name}"] = value
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("truth")
    parser.add_argument("read", nargs="+", help="one MusicXML, or one per page in page order")
    parser.add_argument("--json")
    args = parser.parse_args()

    found = compare(read_score(args.truth), read_pages(args.read))
    report = {"scores": summary(found), "counts": dict(found), "not_emitted": found.not_emitted, "errors": found.errors}
    if args.json:
        with open(args.json, "w", encoding="utf-8") as out:
            json.dump(report, out, ensure_ascii=False, indent=1)
    print("note onset+pitch:", {name: report["scores"][name] for name in ("recall", "precision", "f1")})
    for kind in MARK_KINDS:
        if report["scores"][f"{kind}_f1"] is None:
            continue
        matched = found[f"{kind}s matched"]
        print(f"{kind}: recall {report['scores'][f'{kind}_recall']:.4f} ({matched} of {found[f'{kind}s in truth']} in truth), "
              f"precision {report['scores'][f'{kind}_precision']:.4f} ({matched} of {found[f'{kind}s read']} read), "
              f"f1 {report['scores'][f'{kind}_f1']:.4f}")
    for kind, n in sorted(found.items(), key=lambda item: -item[1]):
        print(f"  {n:6d}  {kind}")
    for kind, n in found.not_emitted.items():
        print(f"  {n:6d}  {kind} in the truth, none read: not emitted")


if __name__ == "__main__":
    main()
