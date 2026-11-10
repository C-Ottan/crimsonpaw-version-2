#!/usr/bin/env python3
"""
pdf_recovery.py - PDF recovery tool for Windows (NTFS)

Finds PDF files deleted between two dates (default: 2026-08-01 -> now) using
every source that does not require the volume to be taken offline:

  1. Recycle Bin ($I / $R record pairs)  - full original path + deletion time
  2. Windows.old (previous installation) - full path + timestamps
  3. Live user folders                   - files still present, date filtered
  4. Raw free-space carving of %PDF- ... %%EOF  (needs Administrator)

Every candidate is validated as a real PDF, hashed, and copied to an output
folder with its original name. A CSV + HTML report is written alongside.

Nothing is written to the source volume except the output folder, so run this
from a different drive if you can.

Usage:
    python pdf_recovery.py                      # scan C:, Aug 1 2026 -> now
    python pdf_recovery.py --since 2026-08-01 --until 2026-11-06
    python pdf_recovery.py --drive D: --name "invoice"
    python pdf_recovery.py --carve --drive C:   # run elevated for this
    python pdf_recovery.py --list-only          # report, copy nothing
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import ctypes.wintypes as wt
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import struct
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

DEFAULT_SINCE = "2026-08-01"
OUT_ROOT = Path(__file__).resolve().parent / "recovered_pdfs"

PDF_MAGIC = b"%PDF-"
PDF_EOF = b"%%EOF"
CHUNK = 4 * 1024 * 1024

# Directories that are pure noise for this job.
SKIP_DIR_NAMES = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "site-packages",
    "WinSxS", "assembly", "Installer", "$SysReset", "SoftwareDistribution",
    "DriverStore", "Prefetch", "Temp", "Cache", "Code Cache", "GPUCache",
}

MAX_PDF_BYTES = 512 * 1024 * 1024      # ignore absurd carved blobs
MIN_PDF_BYTES = 64                     # smaller than this is not a PDF


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"[{dt.datetime.now():%H:%M:%S}] ! {msg}", flush=True)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# ----------------------------------------------------------------------------
# Findings model
# ----------------------------------------------------------------------------

@dataclass
class Finding:
    source: str                 # recycle | windows.old | live | carved
    original_path: str
    size: int
    deleted_at: dt.datetime | None
    modified_at: dt.datetime | None
    data_path: str | None       # file on disk holding the bytes (None = carved)
    offset: int | None = None   # byte offset on the raw volume, for carved
    volume: str = "C:"
    sha256: str = ""
    valid: bool = False
    note: str = ""
    recovered_to: str = ""

    @property
    def filename(self) -> str:
        base = os.path.basename(self.original_path.replace("\\", "/").rstrip("/"))
        base = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", base).strip(" .")
        return base or "unnamed.pdf"

    @property
    def score(self) -> int:
        """Ranking: how likely this is the file the user actually wants."""
        s = 0
        if self.source == "recycle":
            s += 100
        elif self.source == "windows.old":
            s += 60
        elif self.source == "live":
            s += 30
        if self.valid:
            s += 40
        if self.deleted_at and self.deleted_at >= dt.datetime(2026, 8, 1):
            s += 25
        if self.size > 10_000:
            s += 5
        return s


def filetime_to_dt(ft: int) -> dt.datetime | None:
    """Windows FILETIME (100ns since 1601) -> local datetime."""
    if not ft:
        return None
    try:
        return dt.datetime(1601, 1, 1) + dt.timedelta(microseconds=ft / 10)
    except (OverflowError, ValueError):
        return None


def in_window(when: dt.datetime | None, since: dt.datetime, until: dt.datetime) -> bool:
    if when is None:
        return True          # unknown date: keep it, let the user judge
    return since <= when <= until


# ----------------------------------------------------------------------------
# PDF validation
# ----------------------------------------------------------------------------

def validate_pdf(path: str | None = None, blob: bytes | None = None) -> tuple[bool, str]:
    """A PDF must start with %PDF- and contain a trailer marker."""
    try:
        if blob is None:
            with open(path, "rb") as fh:
                head = fh.read(1024)
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                tail = b""
                if size > 2048:
                    fh.seek(-2048, os.SEEK_END)
                    tail = fh.read()
                else:
                    fh.seek(0)
                    tail = fh.read()
        else:
            head, tail = blob[:1024], blob[-2048:]
    except OSError as exc:
        return False, f"unreadable: {exc}"

    if not head.startswith(PDF_MAGIC):
        return False, "no %PDF- header"
    if PDF_EOF not in tail and b"trailer" not in tail and b"startxref" not in tail:
        return False, "truncated: no trailer/startxref"
    return True, ""


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


# ----------------------------------------------------------------------------
# Source 1: Recycle Bin
# ----------------------------------------------------------------------------

def parse_recycle_info(info_path: str) -> tuple[str, int, dt.datetime | None] | None:
    """Parse a $I metadata record -> (original_path, size, deleted_at)."""
    try:
        raw = Path(info_path).read_bytes()
    except OSError:
        return None
    if len(raw) < 28:
        return None
    version = struct.unpack_from("<Q", raw, 0)[0]
    if version not in (1, 2):
        return None
    size = struct.unpack_from("<Q", raw, 8)[0]
    deleted = filetime_to_dt(struct.unpack_from("<Q", raw, 16)[0])
    if version == 2:
        nchars = struct.unpack_from("<I", raw, 24)[0]
        body = raw[28:28 + nchars * 2]
    else:
        body = raw[24:]
    path = body.decode("utf-16-le", "replace").split("\x00", 1)[0]
    if not path:
        return None
    return path, size, deleted


def scan_recycle_bin(since: dt.datetime, until: dt.datetime) -> list[Finding]:
    """Recover PDFs sitting in the Recycle Bin, using $I records for metadata."""
    found: list[Finding] = []
    for bin_dir in Path("C:/$Recycle.Bin").glob("S-1-5-*"):
        if not bin_dir.is_dir():
            continue
        try:
            entries = list(bin_dir.iterdir())
        except OSError:
            continue
        for info in entries:
            if not info.name.startswith("$I"):
                continue
            data = bin_dir / ("$R" + info.name[2:])
            if not data.exists():
                continue
            meta = parse_recycle_info(str(info))
            if not meta:
                continue
            original, size, deleted = meta
            if not original.lower().endswith(".pdf"):
                continue
            if not in_window(deleted, since, until):
                continue
            ok, note = validate_pdf(path=str(data))
            found.append(Finding(
                source="recycle",
                original_path=original,
                size=size or data.stat().st_size,
                deleted_at=deleted,
                modified_at=None,
                data_path=str(data),
                valid=ok,
                note=note,
            ))
    return found


# ----------------------------------------------------------------------------
# Source 2: Windows.old
# ----------------------------------------------------------------------------

def scan_windows_old(since: dt.datetime, until: dt.datetime) -> list[Finding]:
    root = Path("C:/Windows.old")
    found: list[Finding] = []
    if not root.is_dir():
        return found
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            if not name.lower().endswith(".pdf"):
                continue
            full = os.path.join(dirpath, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            when = dt.datetime.fromtimestamp(st.st_mtime)
            if not in_window(when, since, until):
                continue
            ok, note = validate_pdf(path=full)
            found.append(Finding(
                source="windows.old",
                original_path=full,
                size=st.st_size,
                deleted_at=None,
                modified_at=when,
                data_path=full,
                valid=ok,
                note=note,
            ))
    return found


# ----------------------------------------------------------------------------
# Source 3: Live user folders
# ----------------------------------------------------------------------------

def scan_live(since: dt.datetime, until: dt.datetime, roots: list[str]) -> list[Finding]:
    found: list[Finding] = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
            for name in filenames:
                if not name.lower().endswith(".pdf"):
                    continue
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                when = dt.datetime.fromtimestamp(st.st_mtime)
                if not in_window(when, since, until):
                    continue
                ok, note = validate_pdf(path=full)
                found.append(Finding(
                    source="live",
                    original_path=full,
                    size=st.st_size,
                    deleted_at=None,
                    modified_at=when,
                    data_path=full,
                    valid=ok,
                    note=note,
                ))
    return found


# ----------------------------------------------------------------------------
# Raw volume access (requires Administrator)
# ----------------------------------------------------------------------------

GENERIC_READ = 0x80000000
FILE_SHARE_ALL = 0x00000007
OPEN_EXISTING = 3
INVALID_HANDLE = ctypes.c_void_p(-1).value

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateFileW.restype = wt.HANDLE
_k32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, wt.LPVOID,
                             wt.DWORD, wt.DWORD, wt.HANDLE]
_k32.ReadFile.argtypes = [wt.HANDLE, wt.LPVOID, wt.DWORD, wt.LPDWORD, wt.LPVOID]
_k32.SetFilePointerEx.argtypes = [wt.HANDLE, ctypes.c_longlong, wt.LPVOID, wt.DWORD]
_k32.CloseHandle.argtypes = [wt.HANDLE]


class RawVolume:
    """Sector-aligned reader for a raw NTFS volume."""

    def __init__(self, letter: str):
        self.letter = letter.rstrip(":\\/").upper()
        self.path = f"\\\\.\\{self.letter}:"
        self.handle = _k32.CreateFileW(
            self.path, GENERIC_READ, FILE_SHARE_ALL, None, OPEN_EXISTING, 0, None
        )
        if self.handle == INVALID_HANDLE:
            raise OSError(ctypes.get_last_error(),
                          f"cannot open {self.path} (run as Administrator)")
        self.boot = self.read(0, 512)
        if self.boot[3:11] != b"NTFS    ":
            raise OSError(f"{self.letter}: is not NTFS")
        self.bytes_per_sector = struct.unpack_from("<H", self.boot, 0x0B)[0]
        self.sectors_per_cluster = self.boot[0x0D]
        self.cluster_size = self.bytes_per_sector * self.sectors_per_cluster
        self.total_sectors = struct.unpack_from("<Q", self.boot, 0x28)[0]
        self.mft_lcn = struct.unpack_from("<Q", self.boot, 0x30)[0]
        rec_clusters = struct.unpack_from("<b", self.boot, 0x40)[0]
        self.record_size = (rec_clusters * self.cluster_size
                            if rec_clusters > 0 else 1 << (-rec_clusters))
        self.volume_bytes = self.total_sectors * self.bytes_per_sector

    def read(self, offset: int, length: int) -> bytes:
        sector = getattr(self, "bytes_per_sector", 512) or 512
        length = max(sector, (length + sector - 1) // sector * sector)
        if _k32.SetFilePointerEx(self.handle, offset, None, 0) == 0:
            raise OSError(ctypes.get_last_error(), "seek failed")
        buf = ctypes.create_string_buffer(length)
        got = wt.DWORD(0)
        if _k32.ReadFile(self.handle, buf, length, ctypes.byref(got), None) == 0:
            err = ctypes.get_last_error()
            if err:
                raise OSError(err, f"read failed at {offset}")
        return buf.raw[:got.value]

    def close(self) -> None:
        if self.handle and self.handle != INVALID_HANDLE:
            _k32.CloseHandle(self.handle)
            self.handle = None


def apply_fixups(rec: bytearray, bytes_per_sector: int) -> bool:
    """Undo NTFS update-sequence fixups so the record parses cleanly."""
    if len(rec) < 48:
        return False
    usa_off = struct.unpack_from("<H", rec, 4)[0]
    usa_cnt = struct.unpack_from("<H", rec, 6)[0]
    if usa_cnt == 0 or usa_off + usa_cnt * 2 > len(rec):
        return False
    usn = rec[usa_off:usa_off + 2]
    for i in range(1, usa_cnt):
        pos = i * bytes_per_sector - 2
        if pos + 2 > len(rec):
            break
        rec[pos:pos + 2] = usn
    return True


def decode_runlist(data: bytes) -> list[tuple[int, int]]:
    """NTFS runlist -> [(lcn, cluster_count)]; lcn -1 means sparse."""
    runs, pos, lcn = [], 0, 0
    while pos < len(data):
        header = data[pos]
        if header == 0:
            break
        len_size, off_size = header & 0x0F, header >> 4
        pos += 1
        if pos + len_size + off_size > len(data):
            break
        count = int.from_bytes(data[pos:pos + len_size], "little")
        pos += len_size
        if off_size:
            delta = int.from_bytes(data[pos:pos + off_size], "little", signed=True)
            lcn += delta
        pos += off_size
        if count:
            runs.append((lcn, count))
    return runs


def parse_record(rec: bytes) -> dict | None:
    """Extract flags, names and data runs from one MFT record."""
    if rec[:4] != b"FILE":
        return None
    buf = bytearray(rec)
    if not apply_fixups(buf, 512):
        return None
    flags = struct.unpack_from("<H", buf, 0x16)[0]
    attr_off = struct.unpack_from("<H", buf, 0x14)[0]
    out = {"flags": flags, "names": [], "runs": [], "resident": None,
           "real_size": 0, "times": {}}
    pos = attr_off
    while pos + 8 <= len(buf):
        atype = struct.unpack_from("<I", buf, pos)[0]
        if atype == 0xFFFFFFFF:
            break
        alen = struct.unpack_from("<I", buf, pos + 4)[0]
        if alen < 24 or pos + alen > len(buf):
            break
        nonres = buf[pos + 8]
        if atype == 0x30 and not nonres:                     # FILE_NAME
            v_off = struct.unpack_from("<H", buf, pos + 20)[0]
            val = pos + v_off
            if val + 66 <= pos + alen:
                nlen = buf[val + 64]
                name = buf[val + 66:val + 66 + nlen * 2].decode("utf-16-le", "replace")
                parent = struct.unpack_from("<Q", buf, val)[0] & 0xFFFFFFFFFFFF
                out["names"].append((parent, name))
                out["times"] = {
                    "created": filetime_to_dt(struct.unpack_from("<Q", buf, val + 8)[0]),
                    "modified": filetime_to_dt(struct.unpack_from("<Q", buf, val + 16)[0]),
                }
                if not out["real_size"]:
                    out["real_size"] = struct.unpack_from("<Q", buf, val + 48)[0]
        elif atype == 0x80:                                  # DATA
            if nonres:
                run_off = struct.unpack_from("<H", buf, pos + 32)[0]
                out["real_size"] = struct.unpack_from("<Q", buf, pos + 48)[0]
                out["runs"].extend(decode_runlist(bytes(buf[pos + run_off:pos + alen])))
            else:
                vlen = struct.unpack_from("<I", buf, pos + 16)[0]
                v_off = struct.unpack_from("<H", buf, pos + 20)[0]
                out["resident"] = bytes(buf[pos + v_off:pos + v_off + vlen])
                out["real_size"] = vlen
        pos += alen
    return out


def scan_mft(vol: RawVolume, since: dt.datetime, until: dt.datetime) -> list[Finding]:
    """
    Walk the $MFT and return deleted PDF entries.

    Deleted records keep their FILE_NAME attribute and timestamps until the
    slot is reused, which is exactly what makes them recoverable.
    """
    found: list[Finding] = []
    size = vol.record_size
    # $MFT is fragmented: follow its own data runs instead of reading linearly.
    mft = read_mft_record(vol, 0)
    if not mft or not mft["runs"]:
        warn("cannot read $MFT runlist")
        return found
    total_records = sum(c for _, c in mft["runs"]) * vol.cluster_size // size
    log(f"  $MFT: {total_records:,} records across {len(mft['runs'])} extents")
    index: dict[int, tuple[int, str]] = {}
    pending: list[tuple[int, dict]] = []
    rec_no = 0
    last_report = time.time()

    for lcn, count in mft["runs"]:
        if lcn < 0:
            rec_no += count * vol.cluster_size // size
            continue
        offset = lcn * vol.cluster_size
        end = offset + count * vol.cluster_size
        while offset < end:
            try:
                block = vol.read(offset, min(size * 256, end - offset))
            except OSError:
                break
            if not block:
                break
            for i in range(0, len(block) - size + 1, size):
                raw = block[i:i + size]
                if raw[:4] != b"FILE":
                    rec_no += 1
                    continue
                info = parse_record(raw)
                rec_no += 1
                if not info or not info["names"]:
                    continue
                parent, name = info["names"][0]
                index[rec_no - 1] = (parent, name)
                if info["flags"] & 0x01:          # in use
                    continue
                if not name.lower().endswith(".pdf"):
                    continue
                when = info["times"].get("modified") or info["times"].get("created")
                if not in_window(when, since, until):
                    continue
                pending.append((rec_no - 1, info))
            offset += len(block)
            if time.time() - last_report > 5:
                log(f"  MFT: {rec_no:,} records, {len(pending)} deleted PDF candidates")
                last_report = time.time()

    log(f"  MFT done: {rec_no:,} records scanned")
    for number, info in pending:
        path = build_path(number, index)
        runs = info["runs"]
        found.append(Finding(
            source="mft",
            original_path=path,
            size=info["real_size"],
            deleted_at=info["times"].get("modified"),
            modified_at=info["times"].get("modified"),
            data_path=None,
            volume=vol.letter,
            note="deleted MFT record" + ("" if runs or info["resident"] else "; no data runs"),
            valid=False,
        ))
    return found


def build_path(rec_no: int, index: dict[int, tuple[int, str]], depth: int = 0) -> str:
    """Reconstruct a path by walking parent record numbers (5 = root)."""
    parts: list[str] = []
    cur = rec_no
    seen = set()
    while cur in index and cur not in seen and depth < 64:
        seen.add(cur)
        parent, name = index[cur]
        parts.append(name)
        if parent == 5 or parent == cur:
            break
        cur = parent
        depth += 1
    return "\\".join(reversed(parts))


def extract_from_runs(vol: RawVolume, runs: list[tuple[int, int]],
                      want: int) -> bytes:
    """Read a file's bytes by following its data runs."""
    out = bytearray()
    for lcn, count in runs:
        if len(out) >= want:
            break
        if lcn < 0:
            continue
        need = min(count * vol.cluster_size, want - len(out))
        out += vol.read(lcn * vol.cluster_size, need)
    return bytes(out[:want])


def read_mft_record(vol: RawVolume, rec_no: int) -> dict | None:
    off = vol.mft_lcn * vol.cluster_size + rec_no * vol.record_size
    try:
        raw = vol.read(off, vol.record_size)
    except OSError:
        return None
    return parse_record(raw)


def free_cluster_map(vol: RawVolume) -> bytearray:
    """Read $Bitmap (MFT record 6). Bit set = cluster in use."""
    rec = read_mft_record(vol, 6)
    if not rec or not rec["runs"]:
        raise OSError("cannot read $Bitmap - free-space carving unavailable")
    total_clusters = vol.volume_bytes // vol.cluster_size
    need = (total_clusters + 7) // 8
    bitmap = bytearray(need)
    pos = 0
    for lcn, count in rec["runs"]:
        if pos >= need:
            break
        n = min(count * vol.cluster_size, need - pos)
        if lcn < 0:
            pos += n
            continue
        bitmap[pos:pos + n] = vol.read(lcn * vol.cluster_size, n)[:n]
        pos += n
    return bitmap


def is_free(bitmap: bytearray, cluster: int) -> bool:
    byte = cluster >> 3
    if byte >= len(bitmap):
        return False
    return not (bitmap[byte] >> (cluster & 7)) & 1


def carve_free_space(vol: RawVolume, since: dt.datetime, until: dt.datetime,
                     max_hits: int = 4000) -> list[Finding]:
    """
    Scan unallocated clusters for %PDF- ... %%EOF signatures.

    Carved files have no name or timestamp; the volume's own timestamps are
    gone, so they are always reported and the user filters by content.
    """
    bitmap = free_cluster_map(vol)
    total_clusters = len(bitmap) * 8
    log(f"  carving: {sum(bin(b).count('1') for b in bitmap):,} free clusters of "
        f"{total_clusters:,}")

    hits: list[Finding] = []
    cs = vol.cluster_size
    run_start: int | None = None
    run_len = 0
    last = time.time()
    cluster = 0
    while cluster < total_clusters and len(hits) < max_hits:
        if not is_free(bitmap, cluster):
            if run_start is not None:
                run_start = None
            cluster += 1
            continue
        if run_start is None:
            run_start, run_len = cluster, 0
        run_len += 1
        nxt = cluster + 1
        contiguous = nxt < total_clusters and is_free(bitmap, nxt)
        if contiguous and run_len < 4096:
            cluster = nxt
            continue

        # Carve this contiguous free run.
        base = run_start * cs
        length = run_len * cs
        try:
            data = vol.read(base, length)
        except OSError:
            data = b""
        idx = 0
        while True:
            idx = data.find(PDF_MAGIC, idx)
            if idx < 0:
                break
            end = data.find(PDF_EOF, idx)
            if end < 0:
                end = min(len(data), idx + MAX_PDF_BYTES)
            else:
                end += len(PDF_EOF)
            blob = data[idx:end]
            if MIN_PDF_BYTES <= len(blob) <= MAX_PDF_BYTES:
                ok, note = validate_pdf(blob=blob)
                if ok:
                    hits.append(Finding(
                        source="carved",
                        original_path=f"carved_{base + idx:012X}.pdf",
                        size=len(blob),
                        deleted_at=None,
                        modified_at=None,
                        data_path=None,
                        offset=base + idx,
                        volume=vol.letter,
                        valid=True,
                        note=note,
                    ))
            idx = end
        run_start = None
        cluster = nxt
        if time.time() - last > 5:
            log(f"  carve: cluster {cluster:,}/{total_clusters:,}, {len(hits)} PDFs")
            last = time.time()
    log(f"  carve done: {len(hits)} PDF signatures")
    return hits


# ----------------------------------------------------------------------------
# Recovery
# ----------------------------------------------------------------------------

def unique_path(folder: Path, name: str) -> Path:
    target = folder / name
    if not target.exists():
        return target
    stem, ext = os.path.splitext(name)
    for n in range(2, 10000):
        cand = folder / f"{stem} ({n}){ext}"
        if not cand.exists():
            return cand
    return folder / f"{stem} ({int(time.time())}){ext}"


def recover(f: Finding, out_dir: Path, vol: RawVolume | None,
            list_only: bool) -> None:
    """Copy one finding into out_dir and record its hash."""
    if list_only:
        if f.data_path:
            try:
                f.sha256 = sha256_of(f.data_path)
            except OSError:
                pass
        return

    folder = out_dir / f.source
    folder.mkdir(parents=True, exist_ok=True)
    target = unique_path(folder, f.filename)

    try:
        if f.source == "carved":
            if vol is None:
                return
            with open(target, "wb") as fh:
                remaining = f.size
                pos = f.offset
                while remaining > 0:
                    block = vol.read(pos, min(CHUNK, remaining))
                    if not block:
                        break
                    fh.write(block)
                    pos += len(block)
                    remaining -= len(block)
        else:
            shutil.copy2(f.data_path, target)
    except (OSError, shutil.Error) as exc:
        f.note = f"{f.note}; copy failed: {exc}".strip("; ")
        return

    f.recovered_to = str(target)
    try:
        f.sha256 = sha256_of(str(target))
        ok, note = validate_pdf(path=str(target))
        f.valid = ok
        if note:
            f.note = f"{f.note}; {note}".strip("; ")
    except OSError:
        pass


def dedupe(findings: list[Finding]) -> list[Finding]:
    """Drop duplicates by (size, sha256) keeping the best-scored copy."""
    seen: dict[tuple[int, str], Finding] = {}
    for f in sorted(findings, key=lambda x: -x.score):
        key = (f.size, f.sha256) if f.sha256 else (f.size, f.original_path.lower())
        if key in seen:
            continue
        seen[key] = f
    return list(seen.values())


# ----------------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------------

def write_reports(findings: list[Finding], out_dir: Path, args) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = out_dir / f"report_{stamp}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["score", "source", "valid", "size", "deleted_at",
                    "modified_at", "original_path", "recovered_to", "sha256", "note"])
        for f in findings:
            w.writerow([f.score, f.source, f.valid, f.size,
                        f.deleted_at, f.modified_at, f.original_path,
                        f.recovered_to, f.sha256, f.note])

    json_path = out_dir / f"report_{stamp}.json"
    json_path.write_text(json.dumps({
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "since": args.since, "until": args.until, "drive": args.drive,
        "count": len(findings),
        "findings": [{**asdict(f),
                      "deleted_at": f.deleted_at.isoformat() if f.deleted_at else None,
                      "modified_at": f.modified_at.isoformat() if f.modified_at else None}
                     for f in findings],
    }, indent=2), encoding="utf-8")

    rows = []
    for f in findings:
        rows.append(
            "<tr class='{c}'><td>{s}</td><td>{src}</td><td>{sz}</td>"
            "<td>{d}</td><td class='p'>{p}</td><td>{n}</td></tr>".format(
                c="ok" if f.valid else "bad", s=f.score, src=f.source,
                sz=f"{f.size:,}", d=f.deleted_at or f.modified_at or "?",
                p=html.escape(f.recovered_to or f.original_path),
                n=html.escape(f.note)))
    doc = f"""<!doctype html><meta charset="utf-8">
<title>PDF recovery report</title>
<style>
body{{font:13px/1.5 Segoe UI,sans-serif;background:#14161a;color:#dde;margin:24px}}
h1{{font-size:18px}} .meta{{color:#889;margin-bottom:16px}}
table{{border-collapse:collapse;width:100%}} th,td{{padding:5px 8px;
border-bottom:1px solid #262a33;text-align:left;vertical-align:top}}
th{{background:#1d2027;position:sticky;top:0}} tr.bad td{{color:#8a8f9c}}
tr.ok td:first-child{{color:#5ddc7a;font-weight:700}} .p{{word-break:break-all}}
</style>
<h1>{len(findings)} PDF candidates</h1>
<div class="meta">Window {args.since} &rarr; {args.until} on {args.drive}
&middot; generated {dt.datetime.now():%Y-%m-%d %H:%M:%S}</div>
<table><tr><th>score</th><th>source</th><th>bytes</th><th>date</th>
<th>path</th><th>note</th></tr>{''.join(rows)}</table>"""
    (out_dir / f"report_{stamp}.html").write_text(doc, encoding="utf-8")
    log(f"reports: {csv_path.name}, {json_path.name}, report_{stamp}.html")


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------

def parse_date(text: str, end_of_day: bool = False) -> dt.datetime:
    d = dt.datetime.strptime(text, "%Y-%m-%d")
    return d + dt.timedelta(days=1) - dt.timedelta(seconds=1) if end_of_day else d


def run(args) -> int:
    since = parse_date(args.since)
    until = parse_date(args.until, end_of_day=True)
    if until < since:
        warn("--until is before --since")
        return 2

    drive = args.drive.rstrip(":\\/").upper() + ":"
    out_dir = Path(args.out).resolve() if args.out else OUT_ROOT
    out_dir.mkdir(parents=True, exist_ok=True)

    log(f"window {since:%Y-%m-%d} -> {until:%Y-%m-%d} | drive {drive} | out {out_dir}")
    if not args.list_only:
        log("tip: writing recovered files to a different drive avoids overwriting evidence")

    findings: list[Finding] = []

    log("scanning Recycle Bin")
    findings += scan_recycle_bin(since, until)
    log(f"  {len(findings)} from Recycle Bin")

    log("scanning Windows.old")
    before = len(findings)
    findings += scan_windows_old(since, until)
    log(f"  {len(findings) - before} from Windows.old")

    if args.live:
        log("scanning live folders")
        before = len(findings)
        findings += scan_live(since, until, args.live)
        log(f"  {len(findings) - before} from live folders")

    vol: RawVolume | None = None
    if args.carve or args.mft:
        if not is_admin():
            warn("raw volume access needs Administrator - MFT/carve skipped")
        else:
            try:
                vol = RawVolume(drive)
                log(f"raw volume open: {vol.cluster_size} B clusters, "
                    f"{vol.record_size} B records")
            except OSError as exc:
                warn(f"raw volume: {exc}")

    if vol is not None and args.mft:
        log("parsing $MFT for deleted records")
        findings += scan_mft(vol, since, until)

    if vol is not None and args.carve:
        log("carving free space")
        findings += carve_free_space(vol, since, until)

    if args.name:
        needle = args.name.lower()
        findings = [f for f in findings if needle in f.original_path.lower()]
        log(f"{len(findings)} match --name '{args.name}'")

    findings.sort(key=lambda f: (-f.score, f.original_path.lower()))
    if args.limit:
        findings = findings[:args.limit]

    log(f"recovering {len(findings)} candidates")
    for n, f in enumerate(findings, 1):
        recover(f, out_dir, vol, args.list_only)
        if n % 50 == 0:
            log(f"  {n}/{len(findings)}")

    findings = dedupe(findings)
    write_reports(findings, out_dir, args)
    if vol is not None:
        vol.close()

    good = sum(1 for f in findings if f.valid)
    print()
    log(f"DONE - {len(findings)} candidates, {good} valid PDFs")
    log(f"open {out_dir}")
    for f in findings[:15]:
        print(f"  [{f.score:3}] {f.source:11} {f.size:>10,}  "
              f"{f.deleted_at or f.modified_at or '?'}  {f.original_path}")
    if len(findings) > 15:
        print(f"  ... {len(findings) - 15} more in the CSV/HTML report")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Recover deleted PDFs from an NTFS volume by date window.")
    p.add_argument("--since", default=DEFAULT_SINCE,
                   help=f"start date YYYY-MM-DD (default {DEFAULT_SINCE})")
    p.add_argument("--until", default=dt.date.today().isoformat(),
                   help="end date YYYY-MM-DD (default today)")
    p.add_argument("--drive", default="C:", help="volume to scan (default C:)")
    p.add_argument("--name", help="only keep paths containing this text")
    p.add_argument("--out", help=f"output folder (default {OUT_ROOT})")
    p.add_argument("--limit", type=int, help="stop after N candidates")
    p.add_argument("--list-only", action="store_true",
                   help="report only, copy nothing")
    p.add_argument("--live", nargs="*", metavar="DIR",
                   help="also scan live folders (default: user profile)")
    p.add_argument("--mft", action="store_true", default=True,
                   help="parse $MFT for deleted records (default on, needs admin)")
    p.add_argument("--no-mft", dest="mft", action="store_false")
    p.add_argument("--carve", action="store_true",
                   help="carve free space for PDF signatures (needs admin, slow)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.live is not None and not args.live:
        home = os.path.expanduser("~")
        args.live = [os.path.join(home, d) for d in
                     ("Documents", "Downloads", "Desktop", "Pictures", "Videos")]
    try:
        return run(args)
    except KeyboardInterrupt:
        warn("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
