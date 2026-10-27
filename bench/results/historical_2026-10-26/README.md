# Hồ sơ benchmark lịch sử (26/10/2026)

Ba hiện vật bên cạnh được sao chép nguyên byte từ `origin/chuan-dau-ra` tại commit `456ffcc76731aeba757715932792e43dbf2060b7`:

- `benchmark.raw.csv` — số đo thô.
- `benchmark.medians.csv` — bảng tổng hợp do runner cũ tạo.
- `benchmark.html` — báo cáo và biểu đồ lịch sử.

SHA-256:

| File | SHA-256 |
|---|---|
| `benchmark.raw.csv` | `68f070f987f70bd16c30431263c9e6d79d0300367554f5a8e5a05af64449782b` |
| `benchmark.medians.csv` | `75dba94b93357b3bf5dae8a01c9535e2951a81d9d74f95d927a8792570fdbaf1` |
| `benchmark.html` | `257daf0e553981bc2427f0a0d76342748b59d6b5f77c365e6bdf06371d7d6c70` |

## Kiểm tra lại dữ liệu

- CSV thô có 220 dòng đo: 44 tổ hợp × 5 lượt. CSV trung vị có 44 dòng. Bốn tổ hợp BigQuery × 5× × wide không có trong bộ lịch sử.
- Tính lại median, min và max từ từng nhóm năm lượt trong CSV thô khớp toàn bộ 44 dòng trung vị với sai số tối đa `1e-12` giây.
- IQR của từng nhóm cũng được tính lại từ năm lượt thô; CSV trung vị cũ không có cột IQR để đối chiếu. Runner task 3.9 lưu IQR theo từng tổ hợp.
- Khoảng `(max - min) / median` không quá 10% ở 18/44 tổ hợp; trung vị của tỷ lệ này là 21,6%, lớn nhất là 268,1%. Các chênh lệch nhỏ hơn độ dao động cần được diễn giải thận trọng.
- Dữ liệu lịch sử ghi BigQuery 5× star chậm hơn 3NF khoảng 2,48× ở BR2/Q9 và 4,52× ở BR4/Q14. Vì vậy, nhận định “star không bao giờ chậm hơn nhiều” không được dữ liệu hỗ trợ.

## Giới hạn bằng chứng

CSV thô chỉ lưu engine, scale, layout, query, lượt, thời gian và bytes processed. Nó không lưu kết quả truy vấn, row count hay hash theo từng lượt. Cột `same_as_star` trong CSV trung vị được tính từ DataFrame của lượt cuối cho mỗi tổ hợp; nó không chứng minh parity của năm lượt hoặc parity chéo engine. Các median/min/max lịch sử có thể dùng để phân tích lại hiệu năng, nhưng không thay thế cổng correctness mới.

Trang HTML gốc nêu một số giải thích về phân vùng song song, cache và cách dựng bảng. Khi không có job metadata, execution plan hoặc phép đo kiểm soát tương ứng đi kèm, các giải thích đó chỉ là giả thuyết, không phải kết luận được chứng minh bởi CSV.

BR1/Q7 và BR4/Q14 trong bộ lịch sử là workload benchmark. Chúng không tự động trở thành SQL sản xuất đã được TV2 nghiệm thu. BR4 dùng `PERCENTILE_CONT` chính xác; SQL TV2 dùng `APPROX_QUANTILES` chưa được chứng minh tương đương. Q7/Q14 cần được đánh giá theo hợp đồng nghiệp vụ trước khi dùng benchmark để khẳng định parity sản phẩm.
