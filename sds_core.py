#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chèn thông tin bổ sung vào Mục 16 của SDS (BASF) dạng PDF – chạy hàng loạt.

Thông tin chèn (ngay dưới tiêu đề Mục 16, nội dung cũ được đẩy xuống, không xoá gì):
    EN                                  VN
    Date of issued: dd.mm.2020          Ngày ban hành: dd.mm.2020   (ngày ngẫu nhiên năm 2020,
                                                                     cố định theo mã sản phẩm ->
                                                                     bản EN và VN trùng ngày)
    Version: <header>                   Phiên bản: <header>
    Revised date: <header>              Ngày sửa đổi: <header>
    Other information: ...              Thông tin khác: ...

Cách dùng:
    pip install pymupdf
    python sds_core.py <thư_mục_vào> <thư_mục_ra>     (chạy không cần giao diện)
    Giao diện: app.py / SDS_Tool.exe

File gốc không bị sửa. Kết quả + file log (sds_log.csv) nằm trong thư mục ra.
"""
import csv
import hashlib
import os
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pymupdf as fitz

# ---------------------------------------------------------------- cấu hình
TEXTS = {
    "EN": {
        "issued": "Date of issued: {}",
        "version": "Version: {}",
        "revised": "Revised date: {}",
        "other": "Other information: Instruction on safe usage and handling are "
                 "printed in attached document.",
    },
    "VI": {
        "issued": "Ngày ban hành: {}",
        "version": "Phiên bản: {}",
        "revised": "Ngày sửa đổi: {}",
        "other": "Thông tin khác: Hướng dẫn sử dụng và thao tác an toàn được in "
                 "trong tài liệu đính kèm.",
    },
}
ISSUE_YEAR = 2020

# Font giống Arial (Arial trên Windows, Liberation Sans trên Linux có cùng kích thước chữ)
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    str(Path(__file__).resolve().parent / "fonts" / "LiberationSans-Regular.ttf"),  # font kèm theo app web
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

RE_CODE = re.compile(r"\((\d{6,})/SDS_[^/)]+/(\w+)\)")
RE_VERSION = re.compile(r"(?:Phiên bản|Version)\s*:\s*([\d.]+)")
RE_REVISED = re.compile(r"(?:Đã được hiệu chỉnh|Date\s*/\s*Revised)\s*:\s*(\d{2}\.\d{2}\.\d{4})")
RE_PAGENO = re.compile(r"^\s*(Trang|Page)\s*:\s*(\d+)\s*/\s*(\d+)\s*$")
MARKERS = ("Date of issued:", "Ngày ban hành:")


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    raise SystemExit("Không tìm thấy font Arial/Liberation Sans/DejaVu Sans.")


FONT_FILE = find_font()
FONT = fitz.Font(fontfile=FONT_FILE)
FONT_NAME = "SDSadd"


# ---------------------------------------------------------------- tiện ích
def lines_of(page):
    """Trả về list dòng: (bbox, text, spans)."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            text = "".join(s["text"] for s in l["spans"])
            out.append((fitz.Rect(l["bbox"]), text, l["spans"]))
    out.sort(key=lambda x: (x[0].y0, x[0].x0))
    return out


def random_issue_date(product_code: str) -> str:
    """Ngày ngẫu nhiên trong năm 2020, cố định theo mã sản phẩm."""
    seed = int(hashlib.md5(product_code.encode()).hexdigest(), 16)
    rnd = random.Random(seed)
    start = date(ISSUE_YEAR, 1, 1)
    days = (date(ISSUE_YEAR + 1, 1, 1) - start).days
    return (start + timedelta(days=rnd.randrange(days))).strftime("%d.%m.%Y")


def header_info(doc):
    txt = doc[0].get_text()
    m = RE_CODE.search(txt)
    if not m:
        raise ValueError("không đọc được mã SDS trong header")
    code, lang = m.group(1), m.group(2).upper()
    lang = "VI" if lang in ("VI", "VN") else "EN"
    v = RE_VERSION.search(txt)
    r = RE_REVISED.search(txt)
    if not v or not r:
        raise ValueError("không đọc được Version / Revised date trong header")
    return code, lang, v.group(1), r.group(1)


def header_bottom(page):
    """Đáy vùng header (dòng 'Ngày in' / 'Date of print')."""
    for rect, text, _ in lines_of(page):
        if text.strip().startswith(("Ngày in", "Date of print")):
            return rect.y1 + 4
    return 140


def body_limit(doc, hdr_y):
    """Đáy vùng nội dung lớn nhất trên các trang (để biết khi nào tràn trang)."""
    mx = 0
    for p in doc:
        for rect, text, _ in lines_of(p):
            if text.strip() and rect.y0 > hdr_y:
                mx = max(mx, rect.y1)
    return mx + 1


def find_section16(doc):
    """(số trang, đáy tiêu đề, x thụt dòng nội dung, khoảng cách dòng, cỡ chữ)."""
    found = None
    for pno in range(doc.page_count):
        L = lines_of(doc[pno])
        for i, (rect, text, spans) in enumerate(L):
            s0 = spans[0]
            if text.strip().startswith("16.") and "Bold" in s0["font"] and s0["size"] > 11:
                # tiêu đề có thể xuống 2 dòng
                j, bottom = i, rect.y1
                while j + 1 < len(L):
                    nr, nt, ns = L[j + 1]
                    if ns[0]["size"] > 11 and "Bold" in ns[0]["font"] and nr.y0 - bottom < 3:
                        j, bottom = j + 1, nr.y1
                    else:
                        break
                body = [x for x in L[j + 1:] if x[0].x0 > 80]
                indent = body[0][0].x0 if body else 92.2
                size = body[0][2][0]["size"] if body else 9.96
                pitch = (body[1][0].y0 - body[0][0].y0) if len(body) > 1 else 11.5
                found = (pno, bottom, indent, pitch, size)
    if not found:
        raise ValueError("không tìm thấy tiêu đề Mục 16")
    return found


def content_items(page, y_from):
    """Bbox của mọi dòng chữ + nét vẽ nằm dưới y_from."""
    items = [r for r, t, _ in lines_of(page) if r.y0 >= y_from and (t.strip() or r.y1 < 790)]
    items += [d["rect"] for d in page.get_drawings() if d["rect"].y0 >= y_from]
    return items


def page_copy_keep(doc, pno, keep_from, keep_to):
    """Bản sao 1 trang, xoá thật (redact) mọi thứ ngoài dải [keep_from, keep_to]."""
    tmp = fitz.open()
    tmp.insert_pdf(doc, from_page=pno, to_page=pno)
    p = tmp[0]
    W, H = p.rect.width, p.rect.height
    if keep_from > 0:
        p.add_redact_annot(fitz.Rect(0, 0, W, keep_from))
    if keep_to < H:
        p.add_redact_annot(fitz.Rect(0, keep_to, W, H))
    p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                       graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
    return tmp


def renumber_pages(doc):
    """Cập nhật 'Trang: x/y' khi số trang thay đổi."""
    total = doc.page_count
    for pno, page in enumerate(doc):
        for rect, text, spans in lines_of(page):
            for s in spans:
                m = RE_PAGENO.match(s["text"])
                if not m:
                    continue
                new = f"{m.group(1)}: {pno + 1}/{total}"
                r = fitz.Rect(s["bbox"])
                page.add_redact_annot(r)
                page.apply_redactions(graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                                      images=fitz.PDF_REDACT_IMAGE_NONE)
                page.insert_font(fontname=FONT_NAME, fontfile=FONT_FILE)
                x1 = r.x0 + fitz.get_text_length(s["text"].rstrip(), fontname="helv",
                                                 fontsize=s["size"])
                w = FONT.text_length(new, s["size"])
                page.insert_text((x1 - w, s["origin"][1]), new,
                                 fontname=FONT_NAME, fontsize=s["size"])


# ---------------------------------------------------------------- xử lý 1 file
def process(src: Path, dst: Path):
    doc = fitz.open(src)
    alltext = "".join(p.get_text() for p in doc[-3:])
    if any(m in alltext for m in MARKERS):
        return dict(status="BỎ QUA (đã có thông tin)")

    code, lang, version, revised = header_info(doc)
    issued = random_issue_date(code)
    T = TEXTS[lang]
    new_lines = [T["issued"].format(issued), T["version"].format(version),
                 T["revised"].format(revised), T["other"]]

    pno, head_bot, indent, pitch, fsize = find_section16(doc)
    page = doc[pno]
    W, H = page.rect.width, page.rect.height
    hdr_y = header_bottom(page)
    limit = body_limit(doc, hdr_y)

    items = content_items(page, head_bot + 1)
    first_top = min((r.y0 for r in items), default=head_bot + 12)
    split = head_bot + 2                         # cắt ngay dưới tiêu đề
    bottom = max((r.y1 for r in items), default=split) + 1
    delta = pitch * len(new_lines)               # chiều cao 4 dòng mới
    note = ""

    overflow = bottom + delta > limit
    if overflow:
        # tìm khe giữa 2 dòng để ngắt; phần dưới khe sang trang mới
        # ưu tiên ngắt ở ranh giới đoạn (ngay sau một dòng trống)
        blank_bottoms = [r.y1 for r, t, _ in lines_of(page)
                         if r.y0 > split and not t.strip()]
        cut = cut_para = None
        for t in sorted({r.y0 for r in items}):
            above = [r.y1 for r in items if r.y1 <= t]
            if above and max(above) + delta <= limit:
                cut = (max(above) + t) / 2        # giữa khe, không chạm chữ
                if any(abs(b - max(above)) < 0.5 for b in blank_bottoms):
                    cut_para = cut
        cut = cut_para or cut
        if cut is None or cut <= split:
            raise ValueError("không đủ chỗ để chèn, cần kiểm tra thủ công")
        seg1 = page_copy_keep(doc, pno, split, cut)
        seg2 = page_copy_keep(doc, pno, cut, bottom)
        hdr = page_copy_keep(doc, pno, 0, hdr_y)
    else:
        seg1, cut = page_copy_keep(doc, pno, split, bottom), bottom

    page.add_redact_annot(fitz.Rect(0, split, W, H))    # xoá phần nội dung khỏi trang gốc...
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                          graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
    # ...và đặt lại thấp hơn delta
    page.show_pdf_page(fitz.Rect(0, split + delta, W, cut + delta), seg1, 0,
                       clip=fitz.Rect(0, split, W, cut))

    if overflow:
        newp = doc.new_page(pno + 1, width=W, height=H)
        newp.show_pdf_page(newp.rect, hdr, 0)
        start = hdr_y + 7
        newp.show_pdf_page(fitz.Rect(0, start, W, start + bottom - cut), seg2, 0,
                           clip=fitz.Rect(0, cut, W, bottom))
        renumber_pages(doc)
        note = f"tràn trang -> thêm trang, tổng {doc.page_count} trang"
        page = doc[pno]                          # lấy lại trang sau khi chèn trang mới

    # ghi 4 dòng mới, căn theo dòng nội dung đầu tiên của Mục 16
    page.insert_font(fontname=FONT_NAME, fontfile=FONT_FILE)
    baseline0 = first_top + fsize * 0.905 + 0.2
    for i, t in enumerate(new_lines):
        page.insert_text((indent, baseline0 + i * pitch), t,
                         fontname=FONT_NAME, fontsize=fsize)

    dst.parent.mkdir(parents=True, exist_ok=True)
    doc.save(dst, garbage=3, deflate=True)
    return dict(status="OK", lang=lang, code=code, version=version,
                revised=revised, issued=issued, note=note)


# ---------------------------------------------------------------- chạy hàng loạt
def list_pdfs(src_dir):
    return sorted(p for p in Path(src_dir).rglob("*") if p.suffix.lower() == ".pdf")


def run_batch(src_dir, out_dir, on_file=None):
    """Xử lý cả thư mục. on_file(i, total, info) được gọi sau mỗi file.
    Trả về (số file OK, tổng số file, đường dẫn log)."""
    src_dir, out_dir = Path(src_dir), Path(out_dir)
    files = list_pdfs(src_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, f in enumerate(files, 1):
        dst = out_dir / f.relative_to(src_dir)
        try:
            info = process(f, dst)
        except Exception as e:                      # noqa: BLE001
            info = dict(status=f"LỖI: {e}")
        info["file"] = f.name
        rows.append(info)
        if on_file:
            on_file(i, len(files), info)
    cols = ["file", "status", "lang", "code", "version", "revised", "issued", "note"]
    log_path = out_dir / "sds_log.csv"
    with open(log_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["status"] == "OK" for r in rows)
    return ok, len(rows), log_path


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    ok, total, log_path = run_batch(
        sys.argv[1], sys.argv[2],
        lambda i, n, info: print(f"{info['status']:<10} {info['file']} {info.get('note', '')}"))
    print(f"\nXong: {ok}/{total} file OK. Log: {log_path}")


if __name__ == "__main__":
    main()
