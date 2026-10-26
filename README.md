# SDS Tool – Web app chèn thông tin Mục 16

Web app chèn 4 dòng (Ngày ban hành / Phiên bản / Ngày sửa đổi / Thông tin khác) vào ngay dưới
tiêu đề Mục 16 của SDS dạng PDF (mẫu BASF, bản EN hoặc VI), chạy hàng loạt.

## Cách dùng (cho người dùng)
1. Mở đường link của app.
2. **Bước 1:** kéo thả các file PDF vào ô (nhiều file thì nén thành 1 file .zip).
3. **Bước 2:** bấm **Xử lý**.
4. **Bước 3:** bấm **Tải về SDS_da_sua.zip**. File zip gồm các PDF đã sửa và `sds_log.csv`.
5. Muốn làm đợt khác: bấm **Xử lý đợt mới**.

Bảng kết quả trên trang cho biết từng file: OK / BỎ QUA (đã có thông tin) / LỖI (kèm lý do).

## Các file trong repo
| File | Vai trò |
|---|---|
| `streamlit_app.py` | Giao diện web |
| `sds_core.py` | Phần xử lý PDF (giống bản desktop) |
| `fonts/LiberationSans-Regular.ttf` | Font cùng kích thước với Arial (giấy phép SIL OFL) |
| `requirements.txt` | Thư viện cần cài |

## Chạy thử trên máy (không bắt buộc)
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```
