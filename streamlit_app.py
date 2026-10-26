# -*- coding: utf-8 -*-
"""
SDS Tool – web app: chèn thông tin vào Mục 16 của SDS (PDF).

Người dùng: tải PDF (hoặc .zip chứa PDF) lên -> bấm Xử lý -> tải file .zip kết quả về.
Phần xử lý PDF nằm trong sds_core.py (giữ nguyên logic bản desktop).
File chỉ được lưu tạm trong lúc xử lý và bị xoá ngay sau đó.
"""
import io
import shutil
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

import sds_core

st.set_page_config(page_title="SDS Tool – Mục 16", page_icon="📄", layout="centered")


def is_junk(name: str) -> bool:
    """File rác do máy Mac tạo khi nén (__MACOSX/, ._abc.pdf)."""
    parts = Path(name).parts
    return "__MACOSX" in parts or Path(name).name.startswith("._")


def save_uploads(uploads, in_dir: Path):
    """Lưu file tải lên vào in_dir; giải nén .zip. Trả về danh sách file .zip hỏng."""
    bad_zips = []
    for up in uploads:
        name = Path(up.name).name
        data = up.getvalue()
        if name.lower().endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    for info in z.infolist():
                        if info.is_dir() or is_junk(info.filename):
                            continue
                        if not info.filename.lower().endswith(".pdf"):
                            continue
                        z.extract(info, in_dir)
            except zipfile.BadZipFile:
                bad_zips.append(name)
        elif name.lower().endswith(".pdf") and not is_junk(name):
            (in_dir / name).write_bytes(data)
    return bad_zips


def zip_folder(folder: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(folder))
    return buf.getvalue()


# ------------------------------------------------------------------ giao diện
st.title("📄 SDS Tool")
st.markdown("#### Chèn thông tin vào Mục 16 của SDS (PDF)")

with st.expander("ℹ️ Chương trình làm gì? (bấm để xem)"):
    st.markdown(
        """
Chương trình chèn 4 dòng vào ngay dưới tiêu đề **Mục 16** của mỗi SDS:

| Bản tiếng Anh | Bản tiếng Việt |
|---|---|
| Date of issued: *ngày ngẫu nhiên năm 2020* | Ngày ban hành: *ngày ngẫu nhiên năm 2020* |
| Version: *lấy từ header* | Phiên bản: *lấy từ header* |
| Revised date: *lấy từ header* | Ngày sửa đổi: *lấy từ header* |
| Other information: Instruction on safe usage and handling are printed in attached document. | Thông tin khác: Hướng dẫn sử dụng và thao tác an toàn được in trong tài liệu đính kèm. |

- Ngôn ngữ được nhận tự động. Bản EN và VN của cùng sản phẩm luôn trùng ngày ban hành.
- Nội dung cũ của Mục 16 được giữ nguyên. Nếu tràn trang, chương trình tự thêm trang và đánh lại số trang.
- File lỗi được báo và bỏ qua. File đã xử lý rồi sẽ không bị chèn lần 2.
- File chỉ được lưu tạm trong lúc xử lý và bị xoá ngay sau đó.
"""
    )

st.markdown("### Bước 1 – Chọn file SDS")
uploads = st.file_uploader(
    "Kéo thả file PDF vào đây, hoặc bấm **Browse files**. "
    "Nhiều file thì nên nén thành 1 file .zip.",
    type=["pdf", "zip"],
    accept_multiple_files=True,
    key=f"uploader_{st.session_state.get('uploader_round', 0)}",
)

st.markdown("### Bước 2 – Bấm Xử lý")
run = st.button("▶️ Xử lý", type="primary", disabled=not uploads, use_container_width=True)
if not uploads:
    st.caption("Hãy chọn file ở Bước 1 trước.")

if run and uploads:
    st.session_state.pop("result", None)
    with tempfile.TemporaryDirectory() as tmp:
        in_dir, out_dir = Path(tmp, "goc"), Path(tmp, "da_sua")
        in_dir.mkdir()
        bad_zips = save_uploads(uploads, in_dir)
        total = len(sds_core.list_pdfs(in_dir))

        if total == 0:
            st.error("Không tìm thấy file PDF nào trong các file đã chọn.")
        else:
            bar = st.progress(0.0, text=f"Đang xử lý 0/{total} file…")

            def on_file(i, n, info):
                bar.progress(i / n, text=f"Đang xử lý {i}/{n}: {info['file']}")

            ok, total, log_path = sds_core.run_batch(in_dir, out_dir, on_file)
            bar.progress(1.0, text=f"Đã xử lý xong {total} file.")
            st.session_state["result"] = dict(
                ok=ok, total=total, bad_zips=bad_zips,
                log=pd.read_csv(log_path, dtype=str).fillna(""),
                zip=zip_folder(out_dir),
            )
        shutil.rmtree(tmp, ignore_errors=True)

res = st.session_state.get("result")
if res:
    st.markdown("### Bước 3 – Tải kết quả về")
    log = res["log"]
    n_skip = int(log["status"].str.startswith("BỎ QUA").sum())
    n_err = res["total"] - res["ok"] - n_skip

    c1, c2, c3 = st.columns(3)
    c1.metric("✅ Thành công", res["ok"])
    c2.metric("⏭️ Bỏ qua", n_skip)
    c3.metric("❌ Lỗi", n_err)

    for z in res["bad_zips"]:
        st.warning(f"File {z} bị hỏng, không giải nén được.")
    if n_err:
        st.error(f"Có {n_err} file bị lỗi và đã được bỏ qua. Xem lý do trong bảng bên dưới.")

    st.download_button(
        "⬇️ Tải về SDS_da_sua.zip",
        data=res["zip"],
        file_name="SDS_da_sua.zip",
        mime="application/zip",
        type="primary",
        use_container_width=True,
    )
    st.caption("File .zip gồm các PDF đã sửa và file sds_log.csv (mở bằng Excel).")

    view = log.rename(columns={
        "file": "File", "status": "Kết quả", "lang": "Ngôn ngữ", "code": "Mã SP",
        "version": "Phiên bản", "revised": "Ngày sửa đổi",
        "issued": "Ngày ban hành", "note": "Ghi chú"})
    st.dataframe(view, hide_index=True, use_container_width=True)

    if st.button("🔄 Xử lý đợt mới"):
        st.session_state.pop("result", None)
        st.session_state["uploader_round"] = st.session_state.get("uploader_round", 0) + 1
        st.rerun()
