import argparse
import hashlib
import io
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

if "SUMO_HOME" in os.environ:
    tools_path = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools_path not in sys.path:
        sys.path.append(tools_path)
else:
    for candidate in (
        r"C:\Program Files (x86)\Eclipse\Sumo\tools",
        r"C:\Program Files (x86)\SUMO\tools",
        r"C:\Program Files\Eclipse\Sumo\tools",
    ):
        if os.path.isdir(candidate) and candidate not in sys.path:
            sys.path.append(candidate)
            break

import sumolib
import traci

try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def get_edge_ids_and_lengths(net_path: str) -> dict[str, float]:
    abs_net = os.path.abspath(net_path)
    raw_bytes = Path(abs_net).read_bytes()
    if not raw_bytes.strip():
        raise ValueError(f"File mang luoi rong: {abs_net}")

    try:
        net = sumolib.net.readNet(io.BytesIO(raw_bytes), withInternal=False)
        edges = {e.getID(): float(e.getLength()) for e in net.getEdges(withInternal=False)}
        if edges:
            return edges
    except Exception:
        pass

    root = ET.fromstring(raw_bytes)
    edges = {}
    for edge_elem in root.findall("edge"):
        eid = edge_elem.attrib.get("id", "")
        if not eid or eid.startswith(":"):
            continue
        lanes = edge_elem.findall("lane")
        length = float(lanes[0].attrib.get("length", "10.0")) if lanes else 10.0
        edges[eid] = length
    return edges


def deterministic_ratio_score(vid: str) -> float:
    digest = hashlib.md5(vid.encode("utf-8")).hexdigest()
    return (int(digest[:8], 16) % 1000) / 1000.0


def try_lane_weave_if_blocked(
    vid: str,
    curr_edge: str,
    step: int,
    last_lane_change_step: dict[str, int],
    cooldown: int = 4,
    blocked_speed_mps: float = 5.5,
) -> bool:
    """
    Kiem tra lan hien tai co xe/bi can tro khong; neu co thi tim lan ben canh
    it xe/trong hon de chen/chuyen lan.
    """
    if not curr_edge or curr_edge.startswith(":"):
        return False

    prev = last_lane_change_step.get(vid, -cooldown)
    if (step - prev) < cooldown:
        return False

    try:
        curr_lane = traci.vehicle.getLaneIndex(vid)
        if curr_lane < 0:
            return False

        lane_count = traci.edge.getLaneNumber(curr_edge)
        if lane_count <= 1:
            return False

        curr_lane_id = f"{curr_edge}_{curr_lane}"
        curr_veh_cnt = traci.lane.getLastStepVehicleNumber(curr_lane_id)
        curr_occ = traci.lane.getLastStepOccupancy(curr_lane_id)
        spd = traci.vehicle.getSpeed(vid)

        leader_info = traci.vehicle.getLeader(vid, dist=18.0)
        has_close_leader = leader_info is not None and leader_info[1] < 12.0

        # Chi kich hoat chen lan khi lan hien tai co xe/dong xe cham hoac co xe can truoc mat
        if not (has_close_leader or (curr_veh_cnt >= 2 and spd < blocked_speed_mps) or curr_occ > 0.25):
            return False

        best_target_lane = None
        best_score = (curr_veh_cnt, curr_occ)

        for cand_lane in (curr_lane - 1, curr_lane + 1):
            if cand_lane < 0 or cand_lane >= lane_count:
                continue
            cand_lane_id = f"{curr_edge}_{cand_lane}"
            cand_veh_cnt = traci.lane.getLastStepVehicleNumber(cand_lane_id)
            cand_occ = traci.lane.getLastStepOccupancy(cand_lane_id)

            # Uu tien lan trong xe hoac it xe/occupancy thap hon ro ret
            if cand_veh_cnt + 1 < curr_veh_cnt or (cand_veh_cnt == 0 and curr_veh_cnt >= 1):
                cand_score = (cand_veh_cnt, cand_occ)
                if cand_score < best_score:
                    best_score = cand_score
                    best_target_lane = cand_lane

        if best_target_lane is not None:
            traci.vehicle.changeLane(vid, best_target_lane, duration=3.0)
            last_lane_change_step[vid] = step
            return True
    except traci.TraCIException:
        return False

    return False


def init_live_markdown(md_path: Path, net_file: str, rou_file: str, focus_edge: str, max_steps: int) -> None:
    header = [
        "# BÁO CÁO KHẢO SÁT MÔ PHỎNG ITS — NGÃ TƯ HÀNG XANH (SUMO + TRACI)",
        "",
        f"- **Mạng lưới:** `{net_file}` | **Luồng xe:** `{rou_file}`",
        f"- **Edge khảo sát trục chính:** `{focus_edge}` | **Bước tối đa:** `{max_steps}`",
        "",
        "## 1. Kết quả khảo sát từng kịch bản (ghi trực tiếp khi hoàn tất)",
        "",
    ]
    md_path.write_text("\n".join(header) + "\n", encoding="utf-8")


def append_scenario_to_markdown(md_path: Path, r: dict) -> None:
    top_str = ", ".join(
        f"`{item['edge']}` ({item['max_xe']} xe)"
        for item in r.get("top_edge_hang_doi", [])
    ) or "Không ghi nhận"

    block = [
        f"### Kịch bản: `{r['kich_ban']}` — {r.get('ten_hien_thi', r['kich_ban'])}",
        "",
        f"- **Số bước chạy:** {r['so_buoc']} | **Thời gian thực thi:** {r['thoi_gian_chay_s']}s | **Xe đổi lộ trình:** {r['xe_doi_lo_trinh']} | **Lượt chen/đổi làn:** {r.get('so_lan_chen_lan', 0)}",
        f"- **Xe hoàn tất:** {r['xe_hoan_tat']} | **TG đi TB:** {r['thoi_gian_di_tb_s']}s | **TG chờ TB:** {r['thoi_gian_cho_tb_s']}s",
        f"- **Hàng đợi TB:** {r['hang_doi_tb_xe']} xe | **Hàng đợi max:** {r['hang_doi_max_xe']} xe | **Vận tốc TB:** {r['toc_do_tb_kmh']} km/h",
        f"- **Top edge hàng đợi lớn nhất:** {top_str}",
        "",
    ]
    with md_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(block) + "\n")


def append_summary_and_charts_to_markdown(
    md_path: Path,
    results: list[dict],
    chart_files: list[str],
    demo_info: dict | None = None,
) -> None:
    lines = [
        "## 2. Bảng so sánh tổng hợp giữa các kịch bản",
        "",
        "| Kịch bản | Bước | Chạy (s) | Xe hoàn tất | Đổi route | Chen làn | TG chờ TB (s) | Hàng đợi TB (xe) | Hàng đợi max (xe) | Vận tốc TB (km/h) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| `{r['kich_ban']}` | {r['so_buoc']} | {r['thoi_gian_chay_s']} | {r['xe_hoan_tat']} | "
            f"{r['xe_doi_lo_trinh']} | {r.get('so_lan_chen_lan', 0)} | {r['thoi_gian_cho_tb_s']} | {r['hang_doi_tb_xe']} | "
            f"{r['hang_doi_max_xe']} | {r['toc_do_tb_kmh']} |"
        )

    if demo_info:
        lines.extend([
            "",
            "## 3. Chạy demo SUMO và đóng xuất kết quả",
            "",
            f"- **Trạng thái:** {demo_info['trang_thai']}",
            f"- **Số bước demo:** {demo_info['so_buoc']} | **Thời lượng demo:** {demo_info['thoi_gian_chay_s']}s",
            f"- **Xe hoàn tất trong demo:** {demo_info['xe_hoan_tat']} | **Xe đổi lộ trình:** {demo_info['xe_doi_lo_trinh']} | **Hàng đợi max:** {demo_info['hang_doi_max_xe']} xe",
        ])

    if chart_files:
        lines.extend(["", "## 4. Hai sơ đồ khảo sát kết quả", ""])
        for img in chart_files:
            lines.append(f"![{img}]({img})")

    with md_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def simulate_case(
    cfg_file: str | None,
    net_file: str,
    rou_file: str,
    mode: str,
    reroute_ratio: float = 0.5,
    max_steps: int = 300,
    speed_threshold: float = 4.0,
    reroute_interval: int = 15,
    reroute_cooldown: int = 45,
    use_gui: bool = False,
    sample_interval: int = 2,
    focus_edge: str = "E31",
    auto_close_gui: bool = False,
    gui_close_delay_s: float = 0.5,
    gui_step_delay_ms: int = 15,
    fast_traci: bool = True,
) -> dict:
    t_start = time.perf_counter()
    binary = sumolib.checkBinary("sumo-gui" if use_gui else "sumo")
    abs_net = os.path.abspath(net_file)
    abs_rou = os.path.abspath(rou_file)

    cmd = [
        binary,
        "-n", abs_net,
        "-r", abs_rou,
        "--no-warnings", "true",
        "--ignore-route-errors", "true",
        "--duration-log.disable", "true",
        "--tripinfo-output.write-unfinished", "false",
    ]
    if cfg_file and os.path.exists(os.path.abspath(cfg_file)):
        cmd = [
            binary,
            "-c", os.path.abspath(cfg_file),
            "-n", abs_net,
            "-r", abs_rou,
            "--no-warnings", "true",
            "--ignore-route-errors", "true",
            "--duration-log.disable", "true",
        ]
    if use_gui:
        cmd.extend(["--start", "true", "--delay", str(max(0, gui_step_delay_ms))])
        if auto_close_gui:
            cmd.extend(["--quit-on-end", "true"])

    if use_gui:
        print(f"[DEMO SUMO] Đang mở {binary} (tối đa {max_steps} bước, chế độ={mode}, tỷ lệ={int(reroute_ratio*100)}%)...")

    edge_lengths = get_edge_ids_and_lengths(abs_net)
    monitored_edges = list(edge_lengths.keys())
    has_focus = focus_edge in edge_lengths

    traci.start(cmd)

    depart_time: dict[str, float] = {}
    wait_time: dict[str, float] = defaultdict(float)
    speed_sum: dict[str, float] = defaultdict(float)
    speed_cnt: dict[str, int] = defaultdict(int)
    rerouted_ids: set[str] = set()
    last_reroute_step: dict[str, int] = {}
    last_lane_change_step: dict[str, int] = {}
    lane_weave_count = 0

    done_travel: list[float] = []
    done_wait: list[float] = []
    done_speed: list[float] = []
    max_queue_by_edge: dict[str, int] = defaultdict(int)

    queue_sum = 0.0
    queue_samples_cnt = 0
    speed_kmh_sum = 0.0
    speed_kmh_cnt = 0
    congestion_events = 0
    timeline: list[dict] = []

    step = 0
    try:
        while step < max_steps:
            if traci.simulation.getMinExpectedNumber() <= 0 and step > 30:
                break

            traci.simulationStep()
            now = traci.simulation.getTime()
            step += 1

            for vid in traci.simulation.getDepartedIDList():
                depart_time[vid] = now

            active = traci.vehicle.getIDList()
            need_reroute_tick = (mode == "reroute") and (step % reroute_interval == 0)
            need_sample_tick = (step % sample_interval == 0) or (step == max_steps)

            if (not fast_traci) or need_sample_tick or need_reroute_tick:
                for vid in active:
                    spd = traci.vehicle.getSpeed(vid)
                    speed_sum[vid] += spd
                    speed_cnt[vid] += 1
                    speed_kmh_sum += spd * 3.6
                    speed_kmh_cnt += 1
                    w = traci.vehicle.getWaitingTime(vid)
                    if w > wait_time[vid]:
                        wait_time[vid] = w

            # Chuc nang: duong lan co xe thi kiem tra chen qua lan trong xe
            # Khi phan luong (mode == "reroute"), xe co ty le chu dong lach/chen lan cao hon
            weave_prob = 0.25 if mode == "baseline" else min(0.95, 0.35 + reroute_ratio)
            if step % 2 == 0:
                for vid in active:
                    if deterministic_ratio_score(f"{vid}_{step // 4}") <= weave_prob:
                        curr_edge = traci.vehicle.getRoadID(vid)
                        if try_lane_weave_if_blocked(vid, curr_edge, step, last_lane_change_step):
                            lane_weave_count += 1

            congested = []
            step_queue = 0
            focus_queue = 0

            for eid in monitored_edges:
                veh_cnt = traci.edge.getLastStepVehicleNumber(eid)
                if veh_cnt == 0:
                    continue

                mean_spd = traci.edge.getLastStepMeanSpeed(eid)
                halting = traci.edge.getLastStepHaltingNumber(eid)

                q_len = halting if halting > 0 else (
                    veh_cnt if (veh_cnt >= 5 and mean_spd < speed_threshold) else 0
                )
                if eid == focus_edge:
                    focus_queue = q_len

                if q_len > step_queue:
                    step_queue = q_len
                if q_len > max_queue_by_edge[eid]:
                    max_queue_by_edge[eid] = q_len

                if veh_cnt >= 4 and mean_spd < speed_threshold:
                    congested.append(eid)

                if need_reroute_tick:
                    edge_len = edge_lengths.get(eid, 10.0)
                    # Tang trong so thoi gian di tren doan un tac theo muc reroute_ratio de phan luong ro ret
                    penalty = 1.0 + (reroute_ratio * 2.5 if mean_spd < speed_threshold else reroute_ratio * 0.5)
                    traci.edge.adaptTraveltime(eid, (edge_len / max(mean_spd, 0.5)) * penalty)

            q_curr = focus_queue if has_focus else step_queue
            queue_sum += q_curr
            queue_samples_cnt += 1

            if congested:
                congestion_events += 1

            if need_reroute_tick and congested:
                congested_set = set(congested)
                for vid in active:
                    prev_step = last_reroute_step.get(vid, -reroute_cooldown)
                    if (step - prev_step) < reroute_cooldown:
                        continue
                    route = traci.vehicle.getRoute(vid)
                    if route and any(edge in congested_set for edge in route):
                        if deterministic_ratio_score(vid) < reroute_ratio:
                            curr_edge = traci.vehicle.getRoadID(vid)
                            if curr_edge and not curr_edge.startswith(":") and curr_edge != route[-1]:
                                traci.vehicle.rerouteTraveltime(vid)
                                rerouted_ids.add(vid)
                                last_reroute_step[vid] = step

            for vid in traci.simulation.getArrivedIDList():
                if vid in depart_time:
                    done_travel.append(now - depart_time[vid])
                    done_wait.append(wait_time[vid])
                    cnt = speed_cnt.get(vid, 0)
                    done_speed.append((speed_sum.get(vid, 0.0) / cnt) if cnt else 0.0)
                    depart_time.pop(vid, None)
                    wait_time.pop(vid, None)
                    speed_sum.pop(vid, None)
                    speed_cnt.pop(vid, None)
                    last_reroute_step.pop(vid, None)
                    last_lane_change_step.pop(vid, None)

            if need_sample_tick:
                timeline.append({
                    "giay": int(now),
                    "hang_doi_focus": q_curr,
                    "xe_dang_chay": len(active),
                    "xe_hoan_tat": len(done_travel),
                    "xe_doi_lo_trinh": len(rerouted_ids),
                    "so_lan_chen_lan": lane_weave_count,
                    "hang_doi_nhip": step_queue,
                    "so_edge_un_tac": len(congested),
                })

        if use_gui and auto_close_gui:
            if gui_close_delay_s > 0:
                time.sleep(gui_close_delay_s)
            print("[DEMO SUMO] Hoàn tất demo, đang tự động đóng SUMO-GUI...")
    finally:
        try:
            traci.close()
        except Exception:
            pass

    top_edges = sorted(max_queue_by_edge.items(), key=lambda x: x[1], reverse=True)[:5]
    avg_queue = round(queue_sum / queue_samples_cnt, 1) if queue_samples_cnt else 0.0
    avg_speed_kmh = round(speed_kmh_sum / speed_kmh_cnt, 1) if speed_kmh_cnt else 0.0
    elapsed_s = round(time.perf_counter() - t_start, 2)

    pct = int(reroute_ratio * 100)
    return {
        "kich_ban": "baseline" if mode == "baseline" else f"reroute_{pct}pct",
        "ten_hien_thi": (
            "Kịch bản 1: Không phân luồng (0%)"
            if mode == "baseline"
            else f"Kịch bản: Phân luồng bản đồ số ({pct}%)"
        ),
        "nhan_cot": "KB1: 0%\n(Không bản đồ)" if mode == "baseline" else f"KB ({pct}%)\n(Phân luồng {pct}%)",
        "so_buoc": step,
        "thoi_gian_chay_s": elapsed_s,
        "xe_hoan_tat": len(done_travel),
        "xe_doi_lo_trinh": len(rerouted_ids),
        "so_lan_chen_lan": lane_weave_count,
        "thoi_gian_di_tb_s": round(sum(done_travel) / len(done_travel), 2) if done_travel else 0.0,
        "thoi_gian_cho_tb_s": round(sum(done_wait) / len(done_wait), 2) if done_wait else 0.0,
        "toc_do_tb_kmh": avg_speed_kmh,
        "hang_doi_tb_xe": avg_queue,
        "hang_doi_max_xe": max(max_queue_by_edge.values()) if max_queue_by_edge else 0,
        "so_nhip_un_tac": congestion_events,
        "top_edge_hang_doi": [{"edge": eid, "max_xe": q} for eid, q in top_edges],
        "dien_bien_theo_thoi_gian": timeline,
    }


def generate_two_clear_survey_charts(
    results: list[dict],
    out_prefix: str,
    focus_edge: str = "E31",
    activation_threshold: float = 12.0,
) -> list[str]:
    if not HAS_MATPLOTLIB or not results:
        return []

    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.unicode_minus"] = False

    chart1_path = f"{out_prefix}_so_do_1_bien_thien.png"
    fig1, ax1 = plt.subplots(figsize=(9.5, 5.4))
    palette = ["#C0262D", "#EA7A15", "#1F8A3B", "#1D6FD6"]
    linestyles = ["-", "--", "-.", ":"]
    linewidths = [2.4, 2.0, 1.7, 1.7]
    alphas = [0.95, 0.90, 0.85, 0.85]

    max_y1 = activation_threshold
    for idx, r in enumerate(results):
        tl = r.get("dien_bien_theo_thoi_gian", [])
        if not tl:
            continue
        xs = np.array([pt["giay"] for pt in tl], dtype=float)
        ys = np.array([pt.get("hang_doi_focus", pt.get("hang_doi_nhip", 0)) for pt in tl], dtype=float)
        if len(ys) > 0:
            max_y1 = max(max_y1, float(np.max(ys)))

        col = palette[idx % len(palette)]
        ls = linestyles[idx % len(linestyles)]
        lw = linewidths[idx % len(linewidths)]
        al = alphas[idx % len(alphas)]

        ax1.plot(
            xs,
            ys,
            color=col,
            linestyle=ls,
            linewidth=lw,
            alpha=al,
            zorder=10 - idx,
            label=r.get("ten_hien_thi", r["kich_ban"]),
        )
        if idx == 0:
            ax1.fill_between(xs, ys, color=col, alpha=0.06)

    ax1.axhline(
        activation_threshold,
        color="#4B5563",
        linestyle="--",
        linewidth=1.3,
        zorder=2,
        label=f"Ngưỡng kích hoạt bản đồ số ({activation_threshold:g} xe)",
    )
    ax1.set_ylim(0, max(15.0, max_y1 * 1.15))
    ax1.set_title(f"Sơ đồ khảo sát 1: Biến thiên hàng đợi trên trục chính ({focus_edge})", fontsize=12, fontweight="bold", pad=12)
    ax1.set_xlabel("Thời gian mô phỏng (giây)", fontsize=10.5)
    ax1.set_ylabel("Số phương tiện dừng chờ (xe)", fontsize=10.5)
    ax1.grid(True, linestyle="--", linewidth=0.6, alpha=0.35)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper left", fontsize=9, frameon=True, facecolor="white", framealpha=0.95)
    fig1.tight_layout()
    fig1.savefig(chart1_path, dpi=200)
    plt.close(fig1)

    chart2_path = f"{out_prefix}_so_do_2_so_sanh.png"
    fig2, ax2 = plt.subplots(figsize=(8.8, 5.2))

    x_labels = [r.get("nhan_cot", r["kich_ban"]) for r in results]
    avg_queues = [r.get("hang_doi_tb_xe", 0.0) for r in results]
    avg_speeds = [r.get("toc_do_tb_kmh", 0.0) for r in results]

    x_pos = np.arange(len(results))
    width = 0.34

    bars_q = ax2.bar(
        x_pos - width / 2,
        avg_queues,
        width,
        color="#2563EB",
        edgecolor="#1E40AF",
        linewidth=0.8,
        label="Hàng đợi TB (xe)",
    )
    bars_v = ax2.bar(
        x_pos + width / 2,
        avg_speeds,
        width,
        color="#16A34A",
        edgecolor="#166534",
        linewidth=0.8,
        label="Vận tốc TB (km/h)",
    )

    ax2.set_title("Sơ đồ khảo sát 2: So sánh hiệu quả giữa các kịch bản", fontsize=12, fontweight="bold", pad=12)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(x_labels, fontsize=9.5)
    ax2.set_ylabel("Giá trị trung bình", fontsize=10.5)
    ax2.grid(axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper right", fontsize=9, frameon=True, facecolor="white", framealpha=0.92)

    max_val = max(avg_queues + avg_speeds + [1.0])
    ax2.set_ylim(0, max_val * 1.2)

    for bar, val in zip(bars_q, avg_queues):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_val * 0.018,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color="#1E3A8A",
        )

    for bar, val in zip(bars_v, avg_speeds):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max_val * 0.018,
            f"{val:.1f}",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color="#14532D",
        )

    fig2.tight_layout()
    fig2.savefig(chart2_path, dpi=200)
    plt.close(fig2)

    return [chart1_path, chart2_path]


def print_console_summary(results: list[dict]) -> None:
    print("\n" + "=" * 114)
    print(f"{'KICH BAN':<18} {'CHAY (s)':>9} {'HOAN TAT':>9} {'DOI ROUTE':>9} {'CHEN LAN':>9} {'TG CHO (s)':>11} {'QUEUE TB':>10} {'VAN TOC':>10}")
    print("-" * 114)
    for r in results:
        print(
            f"{r['kich_ban']:<18} "
            f"{r['thoi_gian_chay_s']:>9} "
            f"{r['xe_hoan_tat']:>9} "
            f"{r['xe_doi_lo_trinh']:>9} "
            f"{r.get('so_lan_chen_lan', 0):>9} "
            f"{r['thoi_gian_cho_tb_s']:>11} "
            f"{r['hang_doi_tb_xe']:>10} "
            f"{r['toc_do_tb_kmh']:>10}"
        )
    print("=" * 114)


def main() -> None:
    t_total = time.perf_counter()
    parser = argparse.ArgumentParser(description="Khảo sát ITS Hàng Xanh, ghi .md nối tiếp, xuất 2 sơ đồ & demo SUMO tự đóng")
    parser.add_argument("--cfg", default="hangxanh.sumocfg")
    parser.add_argument("--net", default="hangxanh.net.xml")
    parser.add_argument("--rou", default="hangxanh.rou.xml")
    parser.add_argument("--ratios", nargs="+", type=float, default=[0.3, 0.5])
    parser.add_argument("--max-steps", type=int, default=300)
    parser.add_argument("--sample-interval", type=int, default=2)
    parser.add_argument("--focus-edge", default="E31")
    parser.add_argument("--threshold", type=float, default=12.0)
    parser.add_argument("--reroute-interval", type=int, default=15)
    parser.add_argument("--reroute-cooldown", type=int, default=45)
    parser.add_argument("--format", choices=["md", "json", "both"], default="both")
    parser.add_argument("--charts", action="store_true")
    parser.add_argument("--demo-sumo", action="store_true")
    parser.add_argument("--demo-first", action="store_true", help="Mở SUMO-GUI demo chạy trước rồi mới chạy các kịch bản nền")
    parser.add_argument("--demo-steps", type=int, default=100)
    parser.add_argument("--gui-close-delay", type=float, default=0.5)
    parser.add_argument("--gui-step-delay", type=int, default=15)
    parser.add_argument("--no-fast-traci", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--out-prefix", default="Ket_Qua_Mo_Phong_Hang_Xanh")
    args = parser.parse_args()

    fast_traci = not args.no_fast_traci
    md_path = Path(f"{args.out_prefix}.md")
    if args.format in ("md", "both"):
        init_live_markdown(md_path, args.net, args.rou, args.focus_edge, args.max_steps)

    demo_info: dict | None = None
    demo_ratio = args.ratios[-1] if args.ratios else 0.5

    def run_demo_gui() -> dict:
        demo_run = simulate_case(
            cfg_file=args.cfg,
            net_file=args.net,
            rou_file=args.rou,
            mode="reroute",
            reroute_ratio=demo_ratio,
            max_steps=args.demo_steps,
            reroute_interval=args.reroute_interval,
            reroute_cooldown=args.reroute_cooldown,
            use_gui=True,
            sample_interval=max(1, args.sample_interval),
            focus_edge=args.focus_edge,
            auto_close_gui=True,
            gui_close_delay_s=args.gui_close_delay,
            gui_step_delay_ms=args.gui_step_delay,
            fast_traci=fast_traci,
        )
        return {
            "trang_thai": f"Đã mở SUMO-GUI chạy {demo_run['so_buoc']} bước với tỷ lệ {int(demo_ratio*100)}% và tự đóng để xuất kết quả",
            "so_buoc": demo_run["so_buoc"],
            "thoi_gian_chay_s": demo_run["thoi_gian_chay_s"],
            "xe_hoan_tat": demo_run["xe_hoan_tat"],
            "xe_doi_lo_trinh": demo_run["xe_doi_lo_trinh"],
            "hang_doi_max_xe": demo_run["hang_doi_max_xe"],
        }

    if args.demo_sumo and args.demo_first:
        demo_info = run_demo_gui()

    results: list[dict] = []

    base_res = simulate_case(
        cfg_file=args.cfg,
        net_file=args.net,
        rou_file=args.rou,
        mode="baseline",
        reroute_ratio=0.0,
        max_steps=args.max_steps,
        reroute_interval=args.reroute_interval,
        reroute_cooldown=args.reroute_cooldown,
        use_gui=args.gui,
        sample_interval=args.sample_interval,
        focus_edge=args.focus_edge,
        fast_traci=fast_traci,
    )
    results.append(base_res)
    if args.format in ("md", "both"):
        append_scenario_to_markdown(md_path, base_res)

    for r in args.ratios:
        sc_res = simulate_case(
            cfg_file=args.cfg,
            net_file=args.net,
            rou_file=args.rou,
            mode="reroute",
            reroute_ratio=r,
            max_steps=args.max_steps,
            reroute_interval=args.reroute_interval,
            reroute_cooldown=args.reroute_cooldown,
            use_gui=args.gui,
            sample_interval=args.sample_interval,
            focus_edge=args.focus_edge,
            fast_traci=fast_traci,
        )
        results.append(sc_res)
        if args.format in ("md", "both"):
            append_scenario_to_markdown(md_path, sc_res)

    if args.demo_sumo and not args.demo_first:
        demo_info = run_demo_gui()

    print_console_summary(results)

    chart_files: list[str] = []
    if args.charts:
        if HAS_MATPLOTLIB:
            chart_files = generate_two_clear_survey_charts(
                results,
                args.out_prefix,
                focus_edge=args.focus_edge,
                activation_threshold=args.threshold,
            )
            for cf in chart_files:
                print(f"[IMG]  Đã xuất sơ đồ khảo sát: {os.path.abspath(cf)}")
        else:
            print("[WARN] Chưa cài matplotlib/numpy. Chạy: pip install matplotlib numpy")

    if args.format in ("md", "both"):
        append_summary_and_charts_to_markdown(md_path, results, chart_files, demo_info=demo_info)
        print(f"[MD]   Đã hoàn tất ghi báo cáo: {os.path.abspath(md_path)}")

    if args.format in ("json", "both"):
        json_path = f"{args.out_prefix}.json"
        payload = {
            "net_file": args.net,
            "rou_file": args.rou,
            "focus_edge": args.focus_edge,
            "max_steps": args.max_steps,
            "demo_sumo": demo_info,
            "charts": chart_files,
            "scenarios": results,
        }
        Path(json_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[JSON] Đã lưu dữ liệu: {os.path.abspath(json_path)}")

    print(f"Tổng thời gian chạy toàn bộ phiên: {round(time.perf_counter() - t_total, 2)}s")


if __name__ == "__main__":
    main()