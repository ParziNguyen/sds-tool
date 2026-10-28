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
    str(Path(__file__).resolve().parent / "LiberationSans-Regular.ttf"),            # (hoặc để ngoài cùng repo)
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
    """(số trang, đáy tiêu đề, x thụt dòng nội dung, khoảng cách dòng, cỡ chữ, đỉnh tiêu đề)."""
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
                found = (pno, bottom, indent, pitch, size, rect.y0)
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


# ---------------------------------------------------------------- dời nội dung sang trang sau
def move_block(doc, pno, top, bottom, limit):
    """Dời dải nội dung [top, bottom] của trang pno sang trang sau.

    - Nếu trang sau (có sẵn) còn đủ chỗ: đặt dải này lên đầu trang sau,
      nội dung cũ của trang sau được đẩy xuống tương ứng. Không thêm trang.
    - Nếu không (hết trang, hoặc trang sau đã đầy): chèn 1 trang mới có header
      đầy đủ ngay sau trang pno, rồi đánh lại số trang.
    Trả về ghi chú cho file log.
    """
    page = doc[pno]
    W, H = page.rect.width, page.rect.height
    h = bottom - top
    seg = page_copy_keep(doc, pno, top, bottom)
    seg_items = content_items(seg[0], top)
    seg_first = min((r.y0 for r in seg_items), default=top)

    # 1) thử đưa lên đầu trang sau có sẵn
    if pno + 1 < doc.page_count:
        nxt = doc[pno + 1]
        hn = header_bottom(nxt)
        n_items = content_items(nxt, hn + 2)
        n_bottom = max((r.y1 for r in n_items), default=hn + 2) + 1
        if n_bottom + h <= limit:
            n_first = min((r.y0 for r in n_items), default=hn + 7)
            page.add_redact_annot(fitz.Rect(0, top, W, H))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                                  graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
            if n_items:                       # đẩy nội dung cũ của trang sau xuống h
                rest = page_copy_keep(doc, pno + 1, hn + 2, n_bottom)
                nxt.add_redact_annot(fitz.Rect(0, hn + 2, W, H))
                nxt.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                                     graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
                nxt.show_pdf_page(fitz.Rect(0, hn + 2 + h, W, n_bottom + h), rest, 0,
                                  clip=fitz.Rect(0, hn + 2, W, n_bottom))
            off = n_first - seg_first         # dòng đầu của dải nằm đúng chỗ dòng đầu cũ
            nxt.show_pdf_page(fitz.Rect(0, top + off, W, bottom + off), seg, 0,
                              clip=fitz.Rect(0, top, W, bottom))
            return "tràn trang -> dời phần cuối lên đầu trang sau (không thêm trang)"

    # 2) dự phòng: thêm trang mới
    hdr_y = header_bottom(page)
    hdr = page_copy_keep(doc, pno, 0, hdr_y)
    page.add_redact_annot(fitz.Rect(0, top, W, H))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                          graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
    newp = doc.new_page(pno + 1, width=W, height=H)
    newp.show_pdf_page(newp.rect, hdr, 0)
    start = hdr_y + 7
    newp.show_pdf_page(fitz.Rect(0, start, W, start + h), seg, 0,
                       clip=fitz.Rect(0, top, W, bottom))
    renumber_pages(doc)
    return f"tràn trang -> thêm trang, tổng {doc.page_count} trang"


def insert_lines(doc, new_lines, limit, _depth=0):
    """Chèn các dòng mới ngay dưới tiêu đề Mục 16. Trả về ghi chú cho file log."""
    pno, head_bot, indent, pitch, fsize, title_top = find_section16(doc)
    page = doc[pno]
    W, H = page.rect.width, page.rect.height
    hdr_y = header_bottom(page)

    items = content_items(page, head_bot + 1)
    first_top = min((r.y0 for r in items), default=head_bot + 12)
    split = head_bot + 2                         # cắt ngay dưới tiêu đề
    bottom = max((r.y1 for r in items), default=split) + 1
    delta = pitch * len(new_lines)               # chiều cao các dòng mới
    note = ""

    if bottom + delta > limit:                   # không đủ chỗ trên trang này
        # tìm khe giữa 2 dòng để ngắt, ưu tiên ranh giới đoạn (ngay sau một dòng trống)
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
        if cut is None and first_top + delta <= limit:
            cut = split                           # chỉ vừa các dòng mới: dời toàn bộ phần dưới đi

        if cut is None:
            # Mục 16 sát đáy trang: dời cả tiêu đề (kèm đường kẻ phía trên) sang trang sau,
            # rồi chèn lại ở vị trí mới
            if _depth > 0:
                raise ValueError("không đủ chỗ để chèn, cần kiểm tra thủ công")
            block_top = title_top
            for d in page.get_drawings():
                r = d["rect"]
                if r.height < 3 and title_top - 12 < r.y0 < title_top:
                    block_top = min(block_top, r.y0)
            above = [r.y1 for r in content_items(page, hdr_y) if r.y1 <= block_top]
            if not above:
                raise ValueError("không đủ chỗ để chèn, cần kiểm tra thủ công")
            note = move_block(doc, pno, (max(above) + block_top) / 2, bottom, limit)
            return note + "; " + insert_lines(doc, new_lines, limit, _depth + 1)

        if cut < bottom:
            note = move_block(doc, pno, cut, bottom, limit)
            page = doc[pno]                       # lấy lại trang (có thể vừa chèn trang mới)

    # đẩy phần nội dung còn lại dưới tiêu đề xuống để lấy chỗ
    keep_to = cut if bottom + delta > limit else bottom
    if keep_to > split:
        seg1 = page_copy_keep(doc, pno, split, keep_to)
        page.add_redact_annot(fitz.Rect(0, split, W, H))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_PIXELS,
                              graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED)
        page.show_pdf_page(fitz.Rect(0, split + delta, W, keep_to + delta), seg1, 0,
                           clip=fitz.Rect(0, split, W, keep_to))

    # ghi các dòng mới, căn theo dòng nội dung đầu tiên của Mục 16
    page.insert_font(fontname=FONT_NAME, fontfile=FONT_FILE)
    baseline0 = first_top + fsize * 0.905 + 0.2
    for i, t in enumerate(new_lines):
        page.insert_text((indent, baseline0 + i * pitch), t,
                         fontname=FONT_NAME, fontsize=fsize)
    return note


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

    sec_page = doc[find_section16(doc)[0]]
    limit = body_limit(doc, header_bottom(sec_page))   # đáy vùng nội dung chuẩn của file
    note = insert_lines(doc, new_lines, limit)

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
