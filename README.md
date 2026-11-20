# Mô phỏng ITS & Phân luồng Giao thông — Ngã tư Hàng Xanh (SUMO + TraCI)

**Nhóm thực hiện:** Nhóm 15 — Đồ án / Báo cáo Hệ thống Giao thông Thông minh (ITS)  
**Khu vực nghiên cứu:** Nút giao Ngã tư Hàng Xanh, Quận Bình Thạnh, TP. Hồ Chí Minh

---

## 1. Giới thiệu bài toán & Mục tiêu
Dự án xây dựng mô hình vi mô bằng **Eclipse SUMO** kết hợp điều khiển thời gian thực qua **TraCI (Python)** nhằm đánh giá hiệu quả của giải pháp **phân luồng định tuyến động dựa trên dữ liệu bản đồ số** trong việc giảm thiểu ùn tắc tại nút giao Ngã tư Hàng Xanh.

Các kịch bản khảo sát chính:
- **Kịch bản 1 (`baseline` — 0%):** Phương tiện di chuyển theo lộ trình cố định ban đầu, không có điều hướng phân luồng.
- **Kịch bản 2 (`reroute_30pct` — 30%):** 30% phương tiện đi qua các đoạn đường có dấu hiệu ùn tắc được cập nhật thời gian di chuyển và định tuyến lại lộ trình tối ưu.
- **Kịch bản 3 (`reroute_50pct` — 50%):** 50% phương tiện được điều hướng động để giảm tải cho trục chính.

---

## 2. Cấu trúc thư mục dự án

```text
sumo11/
├── hangxanh.sumocfg                                  # File cấu hình tổng của SUMO
├── hangxanh.net.xml                                  # Dữ liệu mạng lưới đường, làn xe & nút giao
├── hangxanh.rou.xml                                  # Dữ liệu luồng phương tiện (xe máy, ô tô, xe buýt)
├── simulate_hangxanh_v5.py                           # Script mô phỏng chính (TraCI + xuất báo cáo + vẽ sơ đồ + demo GUI)
├── Ket_Qua_Mo_Phong_Hang_Xanh.md                     # Báo cáo thống kê chi tiết (ghi nối tiếp từng kịch bản)
├── Ket_Qua_Mo_Phong_Hang_Xanh.json                   # Dữ liệu kết quả dạng cấu trúc JSON
├── Ket_Qua_Mo_Phong_Hang_Xanh_so_do_1_bien_thien.png # Sơ đồ 1: Biến thiên hàng đợi theo thời gian trên trục chính
├── Ket_Qua_Mo_Phong_Hang_Xanh_so_do_2_so_sanh.png    # Sơ đồ 2: So sánh hàng đợi TB & vận tốc TB giữa các kịch bản
└── README.md                                         # Tài liệu hướng dẫn sử dụng dự án
```

---

## 3. Yêu cầu môi trường & Cài đặt

1. **Phần mềm & Ngôn ngữ:**
   - **Python 3.10+**
   - **Eclipse SUMO** (đã thiết lập biến môi trường `SUMO_HOME` hoặc cài đặt tại `C:\Program Files (x86)\Eclipse\Sumo` / `C:\Program Files (x86)\SUMO`).
2. **Thư viện Python hỗ trợ xuất sơ đồ thống kê:**
   ```powershell
   pip install matplotlib numpy
   ```

---

## 4. Hướng dẫn chạy mô phỏng

Mở PowerShell tại thư mục dự án (`sumo11`) và sử dụng các lệnh sau:

### Cách 1: Chạy khảo sát đầy đủ + Xuất báo cáo & 2 sơ đồ thống kê
```powershell
python simulate_hangxanh_v5.py --cfg hangxanh.sumocfg --net hangxanh.net.xml --rou hangxanh.rou.xml --focus-edge E31 --ratios 0.3 0.5 --max-steps 300 --sample-interval 2 --format both --charts
```

### Cách 2: Chạy kèm Demo SUMO-GUI tự mở trước & tự đóng xuất kết quả
```powershell
python simulate_hangxanh_v5.py --cfg hangxanh.sumocfg --net hangxanh.net.xml --rou hangxanh.rou.xml --focus-edge E31 --ratios 0.3 0.5 --max-steps 300 --sample-interval 2 --format both --charts --demo-sumo --demo-first --demo-steps 100
```

---

## 5. Giải thích các tham số dòng lệnh

| Tham số | Mặc định | Ý nghĩa |
| :--- | :--- | :--- |
| `--cfg` | `hangxanh.sumocfg` | Đường dẫn file cấu hình SUMO. |
| `--net` | `hangxanh.net.xml` | Đường dẫn file mạng lưới giao thông. |
| `--rou` | `hangxanh.rou.xml` | Đường dẫn file định nghĩa luồng phương tiện. |
| `--focus-edge` | `E31` | ID đoạn đường (`edge`) trục chính dùng để đo biến thiên hàng đợi. |
| `--ratios` | `0.3 0.5` | Danh sách tỷ lệ phương tiện tham gia phân luồng động (`0.3` = 30%, `0.5` = 50%). |
| `--max-steps` | `300` | Số bước mô phỏng tối đa (giây) cho mỗi kịch bản. |
| `--sample-interval` | `2` | Chu kỳ lấy mẫu dữ liệu vẽ biểu đồ (giây/mẫu). |
| `--threshold` | `12.0` | Ngưỡng số xe dừng chờ kích hoạt cảnh báo bản đồ số. |
| `--charts` | `False` | Xuất 2 file ảnh sơ đồ thống kê `.png` độ phân giải cao. |
| `--demo-sumo` | `False` | Mở giao diện trực quan `sumo-gui` chạy thử nghiệm và tự động đóng. |
| `--demo-first` | `False` | Ưu tiên chạy phiên demo `sumo-gui` trước khi chạy các kịch bản nền. |
| `--demo-steps` | `100` | Số bước mô phỏng trong phiên demo trực quan. |

---

## 6. Lưu ý kỹ thuật
- **Lựa chọn trục khảo sát (`--focus-edge`):** Nên chọn các đoạn đường có lưu lượng lớn và phản ánh rõ hiện tượng tích tụ hàng đợi (như `E31`, `E14`, `E32`) thay vì các đoạn nối quá ngắn ít xe (như `E12`).
- **Tối ưu hiệu năng TraCI:** Script sử dụng cơ chế cập nhật trọng số định tuyến theo chu kỳ (`--reroute-interval 15`) kết hợp thời gian hồi (`--reroute-cooldown 45`) giúp giảm tải gọi API TraCI và mô phỏng sát thực tế phản ứng của người lái xe.
