# BÁO CÁO KHẢO SÁT MÔ PHỎNG ITS — NGÃ TƯ HÀNG XANH (SUMO + TRACI)

- **Mạng lưới:** `hangxanh.net.xml` | **Luồng xe:** `hangxanh.rou.xml`
- **Edge khảo sát trục chính:** `E31` | **Bước tối đa:** `300`

## 1. Kết quả khảo sát từng kịch bản (ghi trực tiếp khi hoàn tất)

### Kịch bản: `baseline` — Kịch bản 1: Không phân luồng (0%)

- **Số bước chạy:** 300 | **Thời gian thực thi:** 33.44s | **Xe đổi lộ trình:** 0
- **Xe hoàn tất:** 842 | **TG đi TB:** 74.12s | **TG chờ TB:** 19.08s
- **Hàng đợi TB:** 8.3 xe | **Hàng đợi max:** 82 xe | **Vận tốc TB:** 14.1 km/h
- **Top edge hàng đợi lớn nhất:** `E11` (82 xe), `E14` (53 xe), `E43` (48 xe), `E31` (36 xe), `E32` (35 xe)

### Kịch bản: `reroute_30pct` — Kịch bản: Phân luồng bản đồ số (30%)

- **Số bước chạy:** 300 | **Thời gian thực thi:** 49.97s | **Xe đổi lộ trình:** 301
- **Xe hoàn tất:** 802 | **TG đi TB:** 72.95s | **TG chờ TB:** 17.63s
- **Hàng đợi TB:** 10.8 xe | **Hàng đợi max:** 88 xe | **Vận tốc TB:** 13.1 km/h
- **Top edge hàng đợi lớn nhất:** `E11` (88 xe), `E32` (54 xe), `E14` (50 xe), `E43` (45 xe), `E35` (36 xe)

### Kịch bản: `reroute_50pct` — Kịch bản: Phân luồng bản đồ số (50%)

- **Số bước chạy:** 300 | **Thời gian thực thi:** 34.98s | **Xe đổi lộ trình:** 504
- **Xe hoàn tất:** 803 | **TG đi TB:** 71.38s | **TG chờ TB:** 16.27s
- **Hàng đợi TB:** 9.3 xe | **Hàng đợi max:** 77 xe | **Vận tốc TB:** 13.4 km/h
- **Top edge hàng đợi lớn nhất:** `E11` (77 xe), `E32` (45 xe), `E14` (43 xe), `E43` (37 xe), `E35` (34 xe)

## 2. Bảng so sánh tổng hợp giữa các kịch bản

| Kịch bản | Bước | Chạy (s) | Xe hoàn tất | Đổi route | TG chờ TB (s) | Hàng đợi TB (xe) | Hàng đợi max (xe) | Vận tốc TB (km/h) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline` | 300 | 33.44 | 842 | 0 | 19.08 | 8.3 | 82 | 14.1 |
| `reroute_30pct` | 300 | 49.97 | 802 | 301 | 17.63 | 10.8 | 88 | 13.1 |
| `reroute_50pct` | 300 | 34.98 | 803 | 504 | 16.27 | 9.3 | 77 | 13.4 |

## 3. Chạy demo SUMO và đóng xuất kết quả

- **Trạng thái:** Đã mở SUMO-GUI chạy 100 bước với tỷ lệ 50% và tự đóng để xuất kết quả
- **Số bước demo:** 100 | **Thời lượng demo:** 13.05s
- **Xe hoàn tất trong demo:** 218 | **Xe đổi lộ trình:** 161 | **Hàng đợi max:** 37 xe

## 4. Hai sơ đồ khảo sát kết quả

![Ket_Qua_Mo_Phong_Hang_Xanh_so_do_1_bien_thien.png](Ket_Qua_Mo_Phong_Hang_Xanh_so_do_1_bien_thien.png)
![Ket_Qua_Mo_Phong_Hang_Xanh_so_do_2_so_sanh.png](Ket_Qua_Mo_Phong_Hang_Xanh_so_do_2_so_sanh.png)
