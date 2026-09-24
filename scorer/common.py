import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

MUSICXML_SUFFIXES = (".musicxml", ".mxl")


def declared_encoding(raw):
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return "utf-16"
    if raw[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    declared = re.match(rb"<\?xml[^>]*?encoding=[\"']([A-Za-z0-9._-]+)[\"']", raw[:200])
    return declared.group(1).decode("ascii").lower() if declared else "utf-8"


def musicxml_text(path):
    raw = Path(path).read_bytes()
    compressed = raw[:2] == b"PK"
    if compressed:
        archive = zipfile.ZipFile(io.BytesIO(raw))
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        raw = archive.read(container.find(".//{*}rootfile").get("full-path"))
    encoding = declared_encoding(raw)
    text = raw.decode(encoding)
    text = re.sub(r"^(<\?xml[^>]*?encoding=)([\"'])[^\"']+\2", r"\1\2UTF-8\2", text, count=1)
    return text, encoding, compressed
