#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
河北高考96志愿批量填报引擎
===========================
功能：读取学生信息CSV，自动计算冲稳保方案，填满96个志愿，输出每个学生的完整填报方案

用法：
    python3 batch_analyzer.py --input students.csv --output ~/knowflow/output/gaokao_batch/ --year 2025

数据文件位置（相对于 ~/knowflow/data/gaokao/hebei/）：
    - national_universities.json  院校数据
    - university_academic.json    学科评估
    - major_trends.json           专业趋势
    - control_lines.json          省控线+一分一段表
    - ../shuangyiliu_disciplines.json  双一流学科
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

# ============================================================
# 常量
# ============================================================
BASE_DIR = os.path.expanduser("~/knowflow/data/gaokao/hebei")
SHUANGYILIU_PATH = os.path.expanduser("~/knowflow/data/gaokao/shuangyiliu_disciplines.json")

TOTAL_VOLUNTEERS = 96
CHONG_COUNT = 20
WEN_COUNT = 50
BAO_COUNT = 26


# ============================================================
# 数据加载
# ============================================================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_data():
    """加载所有数据文件"""
    universities = load_json(os.path.join(BASE_DIR, "national_universities.json"))
    academic = load_json(os.path.join(BASE_DIR, "university_academic.json"))
    major_trends = load_json(os.path.join(BASE_DIR, "major_trends.json"))
    control_lines = load_json(os.path.join(BASE_DIR, "control_lines.json"))
    shuangyiliu = load_json(SHUANGYILIU_PATH)

    # 提取 metadata
    metadata = universities.pop("metadata", {})
    # 构建双一流查找表: 高校名 -> 双一流学科列表
    syl_map = {}
    for entry in shuangyiliu.get("学科列表", []):
        uni_name = entry.get("高校", "")
        syl_map[uni_name] = entry.get("双一流学科", [])

    return universities, academic, major_trends, control_lines, syl_map, metadata


# ============================================================
# 一分一段表工具
# ============================================================
def build_rank_to_score_table(score_table):
    """
    从一分一段表构建 位次->分数 的查找字典。
    score_table: [{"score": 750, "count": 11, "cumulative": 11}, ...]
    返回: {位次: 分数} 的映射
    """
    rank_map = {}
    for entry in score_table:
        score = entry["score"]
        cumulative = entry["cumulative"]
        count = entry["count"]
        # 该分段内的考生位次范围为 (cumulative - count, cumulative]
        for offset in range(count):
            rank = cumulative - offset
            rank_map[rank] = score
    return rank_map


def get_score_for_rank(rank_map, rank):
    """根据位次获取对应分数，若位次超出范围则返回边界值"""
    if rank in rank_map:
        return rank_map[rank]
    if not rank_map:
        return None
    all_ranks = sorted(rank_map.keys())
    if rank < all_ranks[0]:
        return rank_map[all_ranks[0]]
    if rank > all_ranks[-1]:
        return rank_map[all_ranks[-1]]
    # 插值：找到最近的位次
    for r in all_ranks:
        if r >= rank:
            return rank_map[r]
    return rank_map[all_ranks[-1]]


# ============================================================
# 学生解析
# ============================================================
def parse_students(csv_path):
    """解析学生信息CSV"""
    students = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("姓名", "").strip()
            score_str = row.get("分数", "").strip()
            rank_str = row.get("位次", "").strip()
            category = row.get("科类", "").strip()
            subjects = row.get("选科", "").strip()
            intent_major = row.get("意向专业", "").strip()
            intent_city = row.get("意向城市", "").strip()

            if not name:
                continue
            try:
                score = int(float(score_str)) if score_str else None
                rank = int(float(rank_str)) if rank_str else None
            except ValueError:
                print(f"  [警告] 学生 '{name}' 分数/位次解析失败: score={score_str}, rank={rank_str}")
                continue

            intent_majors = [m.strip() for m in intent_major.split("、") if m.strip()] if intent_major else []
            intent_cities = [c.strip() for c in intent_city.split("、") if c.strip()] if intent_city else []

            students.append({
                "name": name,
                "score": score,
                "rank": rank,
                "category": category,
                "subjects": subjects,
                "intent_majors": intent_majors,
                "intent_cities": intent_cities,
            })
    return students


# ============================================================
# 院校评分与匹配
# ============================================================
def calc_comprehensive_score(uni_name, uni_info, academic_data, syl_map, student):
    """
    计算院校对学生的综合推荐评分（分数越高越推荐）
    评分维度：院校层级、双一流、专业匹配、城市匹配、保研率
    """
    score = 0
    details = []

    # 1. 院校层级评分 (0-30分)
    tier = uni_info.get("tier", "")
    level = uni_info.get("level", "")
    tier_scores = {
        "985": 30, "211": 20, "双一流": 15,
    }
    level_scores = {
        "顶尖": 30, "顶级985": 28, "985": 25,
        "211": 20, "双一流": 15,
    }
    tier_score = tier_scores.get(tier, 0) or level_scores.get(level, 0)
    score += tier_score
    details.append(f"院校层级+{tier_score}")

    # 2. 双一流评分 (0-15分)
    uni_syl = syl_map.get(uni_name, [])
    syl_score = min(len(uni_syl), 15)
    if syl_score > 0:
        score += syl_score
        details.append(f"双一流+{syl_score}")

    # 3. 意向专业匹配评分 (0-30分)
    uni_academic = academic_data.get(uni_name, {})
    a_plus_disciplines = uni_academic.get("academic_ranking", {}).get("A+学科", [])
    a_disciplines = uni_academic.get("academic_ranking", {}).get("A学科", [])
    all_top_disciplines = a_plus_disciplines + a_disciplines

    matched_majors = []
    for major in student["intent_majors"]:
        for subject in all_top_disciplines:
            if major in subject or subject in major:
                if subject not in matched_majors:
                    matched_majors.append(subject)

    major_match_score = min(len(matched_majors) * 10, 30)
    if major_match_score > 0:
        score += major_match_score
        details.append(f"专业匹配+{major_match_score}")

    # 4. 意向城市匹配评分 (0-20分)
    location = uni_info.get("location", "")
    city_match = 0
    for city in student["intent_cities"]:
        if city and (city in location or location in city):
            city_match = 20
            break
    if city_match > 0:
        score += city_match
        details.append(f"城市匹配+{city_match}")

    # 5. 保研率加分 (0-5分)
    baoyan_rate_str = uni_academic.get("保研率", "0%")
    try:
        baoyan_rate = float(baoyan_rate_str.replace("约", "").replace("%", ""))
        baoyan_bonus = min(baoyan_rate / 10, 5)
        if baoyan_bonus > 0:
            score += baoyan_bonus
            details.append(f"保研率+{baoyan_bonus:.1f}")
    except ValueError:
        pass

    return round(score, 1), details, matched_majors


# ============================================================
# 冲稳保分类
# ============================================================
def classify_school(uni_rank_p, student_rank):
    """
    根据学生位次和学校录取最低位次判断冲稳保
    rank_p 是录取最低位次（数字越小学校越好）
    冲：学校位次 < 学生位次（学校更好），但差距30%以内（学校位次 >= 学生位次*0.7）
    稳：学生位次 <= 学校位次 <= 学生位次*1.3
    保：学校位次 > 学生位次*1.3，但不超过学生位次*2
    超出2倍的不推荐
    """
    if uni_rank_p is None:
        return None

    lower_bound = student_rank * 0.7
    upper_bound = student_rank * 2.0

    if uni_rank_p < lower_bound:
        return None  # 超出冲的范围，太冒险
    elif uni_rank_p < student_rank:
        if uni_rank_p >= student_rank * 0.7:
            return "冲"
        else:
            return None
    elif uni_rank_p <= student_rank * 1.3:
        return "稳"
    elif uni_rank_p <= student_rank * 2.0:
        return "保"
    else:
        return None  # 超出2倍，不推荐


# ============================================================
# 核心引擎
# ============================================================
def analyze_student(student, universities, academic_data, major_trends, syl_map, rank_map_wl, rank_map_ls):
    """
    为单个学生生成96个志愿方案
    返回: (chong_list, wen_list, bao_list) 每个列表是已排序的志愿条目
    """
    student_rank = student["rank"]
    category = student["category"]

    # 选择对应科类的位次-分数映射表
    if "物理" in category:
        rank_map = rank_map_wl
    elif "历史" in category:
        rank_map = rank_map_ls
    else:
        rank_map = rank_map_wl  # 默认物理组

    # 将学生位次转换为大致分数（用于参考展示）
    student_score_from_rank = get_score_for_rank(rank_map, student_rank)

    # 分类所有院校
    chong_list = []
    wen_list = []
    bao_list = []

    for uni_name, uni_info in universities.items():
        if not isinstance(uni_info, dict):
            continue
        rank_p = uni_info.get("rank_p")
        if rank_p is None:
            continue

        classification = classify_school(rank_p, student_rank)
        if classification is None:
            continue

        # 计算综合评分
        comp_score, details, matched_majors = calc_comprehensive_score(
            uni_name, uni_info, academic_data, syl_map, student
        )

        # 获取学校的分数区间（展示用）
        school_score_p = get_score_for_rank(rank_map, rank_p)
        rank_h = uni_info.get("rank_h")
        school_score_h = get_score_for_rank(rank_map, rank_h) if rank_h else None

        # 双一流标注
        uni_syl = syl_map.get(uni_name, [])
        is_shuangyiliu = len(uni_syl) > 0
        is_985 = uni_info.get("tier") == "985" or uni_info.get("level") in ["顶尖", "顶级985", "985"]
        is_211 = uni_info.get("tier") == "211" or uni_info.get("level") == "211"

        entry = {
            "name": uni_name,
            "rank_p": rank_p,
            "rank_h": rank_h,
            "score_p": school_score_p,
            "score_h": school_score_h,
            "location": uni_info.get("location", ""),
            "tier": uni_info.get("tier", ""),
            "level": uni_info.get("level", ""),
            "tags": uni_info.get("tags", []),
            "comp_score": comp_score,
            "score_details": details,
            "matched_majors": matched_majors,
            "is_shuangyiliu": is_shuangyiliu,
            "is_985": is_985,
            "is_211": is_211,
        }

        if classification == "冲":
            chong_list.append(entry)
        elif classification == "稳":
            wen_list.append(entry)
        elif classification == "保":
            bao_list.append(entry)

    # 按综合评分降序排列
    chong_list.sort(key=lambda x: (-x["comp_score"], x["rank_p"]))
    wen_list.sort(key=lambda x: (-x["comp_score"], x["rank_p"]))
    bao_list.sort(key=lambda x: (-x["comp_score"], x["rank_p"]))

    return chong_list, wen_list, bao_list, student_score_from_rank


def fill_volunteers(chong_list, wen_list, bao_list):
    """
    填充96个志愿：冲20个、稳50个、保26个
    如果某类不足，从其他类补充；如果总候选不足96个，灵活分配空缺占位
    """
    # 所有候选已按综合评分排序，取全部
    all_avail = {"冲": chong_list[:], "稳": wen_list[:], "保": bao_list[:]}
    used_names = set()
    volunteers = []  # 元素: (entry_or_None, category)

    def pick_one(categories):
        """从指定类别列表中取第一个未被使用的条目"""
        for cat in categories:
            items = all_avail[cat]
            for i, item in enumerate(items):
                if item["name"] not in used_names:
                    used_names.add(item["name"])
                    all_avail[cat] = items[i + 1:]
                    return item, cat
        return None, None

    # 先填冲
    for _ in range(CHONG_COUNT):
        item, cat = pick_one(["冲", "稳", "保"])
        if item:
            volunteers.append((item, "冲"))
        else:
            volunteers.append((None, "冲"))

    # 再填稳
    for _ in range(WEN_COUNT):
        item, cat = pick_one(["稳", "保", "冲"])
        if item:
            volunteers.append((item, "稳"))
        else:
            volunteers.append((None, "稳"))

    # 最后填保
    for _ in range(BAO_COUNT):
        item, cat = pick_one(["保", "稳", "冲"])
        if item:
            volunteers.append((item, "保"))
        else:
            volunteers.append((None, "保"))

    return volunteers


# ============================================================
# 输出
# ============================================================
def generate_markdown(student, volunteers, student_score_from_rank, output_dir):
    """生成单个学生的志愿方案Markdown文件"""
    name = student["name"]
    student_dir = os.path.join(output_dir, name)
    os.makedirs(student_dir, exist_ok=True)

    # 过滤出有效的志愿
    valid_vols = [v for v in volunteers if v is not None]
    total_valid = len(valid_vols)
    total_slots = len(volunteers)

    lines = []
    lines.append(f"# {name} 高考志愿填报方案")
    lines.append("")
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("## 学生基本信息")
    lines.append("")
    lines.append(f"| 项目 | 内容 |")
    lines.append(f"|------|------|")
    lines.append(f"| 姓名 | {student['name']} |")
    if student['score']:
        lines.append(f"| 分数 | {student['score']} 分 |")
    if student['rank']:
        lines.append(f"| 位次 | {student['rank']} 名 |")
        if student_score_from_rank:
            lines.append(f"| 位次对应分数（参考） | {student_score_from_rank} 分 |")
    lines.append(f"| 科类 | {student['category']} |")
    if student['subjects']:
        lines.append(f"| 选科 | {student['subjects']} |")
    if student['intent_majors']:
        lines.append(f"| 意向专业 | {'、'.join(student['intent_majors'])} |")
    if student['intent_cities']:
        lines.append(f"| 意向城市 | {'、'.join(student['intent_cities'])} |")
    lines.append("")

    # 策略说明
    lines.append("## 冲稳保策略说明")
    lines.append("")
    lines.append(f"- **冲（{CHONG_COUNT}个）**：学校录取位次 < 学生位次，但差距在30%以内")
    lines.append(f"- **稳（{WEN_COUNT}个）**：学生位次 ≤ 学校录取位次 ≤ 学生位次×1.3")
    lines.append(f"- **保（{BAO_COUNT}个）**：学校录取位次 > 学生位次×1.3，不超过学生位次×2")
    lines.append(f"- 共 **{TOTAL_VOLUNTEERS}个** 志愿")
    if total_valid < total_slots:
        lines.append("")
        lines.append(f"> ⚠ **注意**：当前数据集中符合条件的高校仅有 **{total_valid}所**，不足 {total_slots} 个志愿。")
        lines.append("> 建议补充更多院校数据以获得完整方案。")
    lines.append("")

    # 统计
    chong_count = sum(1 for v in valid_vols if v.get("_type") == "冲")
    wen_count = sum(1 for v in valid_vols if v.get("_type") == "稳")
    bao_count = sum(1 for v in valid_vols if v.get("_type") == "保")

    lines.append("## 志愿方案概览")
    lines.append("")
    lines.append(f"| 类别 | 计划 | 实际 |")
    lines.append(f"|------|------|------|")
    lines.append(f"| 🔴 冲 | {CHONG_COUNT} 个 | {chong_count} 个 |")
    lines.append(f"| 🟡 稳 | {WEN_COUNT} 个 | {wen_count} 个 |")
    lines.append(f"| 🟢 保 | {BAO_COUNT} 个 | {bao_count} 个 |")
    lines.append(f"| **合计** | **{total_slots} 个** | **{total_valid} 个** |")
    lines.append("")

    # 详细志愿列表
    lines.append("## 详细志愿列表")
    lines.append("")
    lines.append("| 序号 | 类别 | 院校名称 | 所在地 | 层次 | 录取位次(最低) | 预估分数 | 综合评分 | 双一流 | 匹配专业 |")
    lines.append("|------|------|----------|--------|------|---------------|----------|----------|--------|----------|")

    seq = 0
    for i in range(len(volunteers)):
        v = volunteers[i]
        if v is None:
            seq += 1
            lines.append(
                f"| {seq} | ⚪空缺 | — | — | — | — | — | — | — | — |"
            )
        else:
            seq += 1
            _type = v.get("_type", "")
            type_icon = {"冲": "🔴", "稳": "🟡", "保": "🟢"}.get(_type, "⚪")
            syl_tag = "✓" if v["is_shuangyiliu"] else "✗"
            matched = "、".join(v["matched_majors"][:3]) if v["matched_majors"] else "-"
            score_p_str = str(v["score_p"]) if v["score_p"] else "-"

            lines.append(
                f"| {seq} | {type_icon}{_type} | **{v['name']}** | {v['location']} | "
                f"{v['tier'] or v['level']} | {v['rank_p']} | {score_p_str} 分 | "
                f"{v['comp_score']} | {syl_tag} | {matched} |"
            )

    lines.append("")

    # 分类详细（只列有效志愿）
    for _type, type_name, icon in [("冲", "冲（冲刺）", "🔴"), ("稳", "稳（稳妥）", "🟡"), ("保", "保（保底）", "🟢")]:
        type_vols = [v for v in valid_vols if v.get("_type") == _type]
        if not type_vols:
            continue
        lines.append(f"### {icon} {type_name}（{len(type_vols)}个）")
        lines.append("")
        lines.append("| 序号 | 院校名称 | 所在地 | 录取位次 | 综合评分 | 双一流 | 匹配专业 |")
        lines.append("|------|----------|--------|----------|----------|--------|----------|")
        sub_seq = 0
        for v in type_vols:
            sub_seq += 1
            syl_tag = "✓" if v["is_shuangyiliu"] else "✗"
            matched = "、".join(v["matched_majors"][:3]) if v["matched_majors"] else "-"
            lines.append(
                f"| {sub_seq} | **{v['name']}** | {v['location']} | {v['rank_p']} | "
                f"{v['comp_score']} | {syl_tag} | {matched} |"
            )
        lines.append("")

    # 推荐说明
    lines.append("---")
    lines.append("")
    lines.append("*本方案由河北高考志愿填报引擎自动生成，仅供参考。*")
    lines.append("*正式填报前请务必查阅河北省教育考试院官方公布的招生计划。*")

    content = "\n".join(lines)
    filepath = os.path.join(student_dir, "志愿方案.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath


def generate_summary_csv(all_results, output_dir):
    """生成汇总CSV"""
    csv_path = os.path.join(output_dir, "summary.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "姓名", "科类", "分数", "位次", "意向专业", "意向城市",
            "志愿总数", "实际院校数", "冲数量", "稳数量", "保数量",
            "推荐院校_top10"
        ])
        for student, volunteers, _ in all_results:
            valid_vols = [v for v in volunteers if v is not None]
            chong_n = sum(1 for v in valid_vols if v.get("_type") == "冲")
            wen_n = sum(1 for v in valid_vols if v.get("_type") == "稳")
            bao_n = sum(1 for v in valid_vols if v.get("_type") == "保")
            top10 = "、".join([v["name"] for v in valid_vols[:10]])
            writer.writerow([
                student["name"], student["category"], student["score"], student["rank"],
                "、".join(student["intent_majors"]), "、".join(student["intent_cities"]),
                len(volunteers), len(valid_vols), chong_n, wen_n, bao_n,
                top10,
            ])
    return csv_path


# ============================================================
# 主程序
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="河北高考96志愿批量填报引擎")
    parser.add_argument("--input", "-i", required=True, help="学生信息CSV路径")
    parser.add_argument("--output", "-o", required=True, help="输出目录路径")
    parser.add_argument("--year", "-y", type=str, default="2025", help="参考年份（如 2025）")
    args = parser.parse_args()

    input_path = args.input
    output_dir = os.path.expanduser(args.output)
    year = args.year

    if not os.path.exists(input_path):
        print(f"[错误] 输入文件不存在: {input_path}")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("河北高考96志愿批量填报引擎")
    print(f"参考年份: {year}")
    print("=" * 60)

    # 1. 加载数据
    print("\n[1/5] 加载数据文件...")
    universities, academic_data, major_trends, control_lines, syl_map, metadata = load_all_data()
    print(f"  ✓ 院校数据: {len(universities)} 所")
    print(f"  ✓ 学科评估: {len(academic_data)} 所")
    print(f"  ✓ 专业趋势: {len(major_trends)} 个专业")
    print(f"  ✓ 双一流: {len(syl_map)} 所高校")

    # 2. 解析学生
    print("\n[2/5] 解析学生信息...")
    students = parse_students(input_path)
    print(f"  ✓ 读取到 {len(students)} 名学生")

    if not students:
        print("[错误] 未读取到任何学生信息，请检查CSV格式")
        sys.exit(1)

    # 3. 构建一分一段表
    print("\n[3/5] 构建一分一段表...")
    year_data = control_lines.get("各年份详细数据", {}).get(year, {})
    if not year_data:
        print(f"  [警告] 未找到 {year} 年数据，尝试使用  2023 年数据")
        year_data = control_lines.get("各年份详细数据", {}).get("2023", {})

    wl_data = year_data.get("物理组", {})
    ls_data = year_data.get("历史组", {})

    wl_score_table = wl_data.get("一分一段表", [])
    ls_score_table = ls_data.get("一分一段表", [])

    rank_map_wl = build_rank_to_score_table(wl_score_table) if wl_score_table else {}
    rank_map_ls = build_rank_to_score_table(ls_score_table) if ls_score_table else {}

    print(f"  ✓ 物理组一分一段: {len(rank_map_wl)} 个位次映射")
    print(f"  ✓ 历史组一分一段: {len(rank_map_ls)} 个位次映射")

    # 4. 逐学生分析
    print(f"\n[4/5] 逐学生志愿分析...")
    all_results = []

    for i, student in enumerate(students, 1):
        name = student["name"]
        print(f"\n  [{i}/{len(students)}] {name} ({student['category']}, 分数={student['score']}, 位次={student['rank']})")
        print(f"    意向专业: {student['intent_majors'] or '无'}")
        print(f"    意向城市: {student['intent_cities'] or '无'}")

        chong_list, wen_list, bao_list, student_score_from_rank = analyze_student(
            student, universities, academic_data, major_trends, syl_map, rank_map_wl, rank_map_ls
        )

        print(f"    → 候选: 冲{len(chong_list)}个 / 稳{len(wen_list)}个 / 保{len(bao_list)}个")

        volunteers = fill_volunteers(chong_list, wen_list, bao_list)

        # 标记真实分类并解包
        flat_volunteers = []
        for item, assigned_cat in volunteers:
            if item:
                item["_type"] = assigned_cat
                flat_volunteers.append(item)
            else:
                flat_volunteers.append(None)

        chong_n = sum(1 for v in flat_volunteers if v and v.get("_type") == "冲")
        wen_n = sum(1 for v in flat_volunteers if v and v.get("_type") == "稳")
        bao_n = sum(1 for v in flat_volunteers if v and v.get("_type") == "保")
        actual_n = sum(1 for v in flat_volunteers if v is not None)

        print(f"    → 方案: 冲{chong_n}个 / 稳{wen_n}个 / 保{bao_n}个 (共{actual_n}个志愿)")
        if actual_n < TOTAL_VOLUNTEERS:
            print(f"    ⚠ 注意: 数据集中仅{actual_n}所院校符合条件，不足96个")

        all_results.append((student, flat_volunteers, student_score_from_rank))

    # 5. 输出
    print(f"\n[5/5] 生成输出文件...")

    for student, volunteers, student_score_from_rank in all_results:
        filepath = generate_markdown(student, volunteers, student_score_from_rank, output_dir)
        print(f"  ✓ {student['name']}: {filepath}")

    csv_path = generate_summary_csv(all_results, output_dir)
    print(f"  ✓ 汇总CSV: {csv_path}")

    print("\n" + "=" * 60)
    print("批量填报完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
