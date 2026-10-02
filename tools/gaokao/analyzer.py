#!/usr/bin/env python3
"""
河北高考志愿填报分析引擎 v2.1
位次法 + 等效分法（张雪峰七步法）双模式 + 2026省控线更新
"""
import json, os, sys
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~/knowflow/data/gaokao/hebei"))

# 等效分冲稳保区间参数（张雪峰七步法标准）
EQUIV_CWB_PARAMS = {
    "冲": {"score_add_min": 5, "score_add_max": 15, "desc": "等效分 +5 到 +15，冲刺学科强校"},
    "稳": {"score_add_min": -5, "score_add_max": 5, "desc": "等效分 ±5，主力匹配"},
    "保": {"score_add_min": -20, "score_add_max": -10, "desc": "等效分 -10 到 -20，确保不滑档"}
}

# 等效分法志愿分配（96志愿标准）
CWB_COUNTS = {"冲": 20, "稳": 50, "保": 26, "total": 96}

# 三种志愿分配预设方案（96志愿标准）
CWB_PRESETS = {
    "均衡稳妥型": {"冲": 19, "稳": 48, "保": 29, "比例": "2:5:3",
        "desc": "80%普通考生首选，中分段公办本科优先，专业不想大幅妥协"},
    "进取冲刺型": {"冲": 34, "稳": 29, "保": 33, "比例": "3:4:3",
        "desc": "高分段冲击双一流/热门专业，能接受冷门专业搏断档"},
    "压线保底型": {"冲": 29, "稳": 29, "保": 38, "比例": "3:3:4",
        "desc": "刚过本科线/民办为主，必须保住本科，大量兜底"}
}

# 物理/历史组梯度间隔参数（河北专属）
GRADIENT_PARAMS = {
    "物理组": {
        "冲稳间隔_desc": "每档间隔1000-3000位次",
        "稳保间隔_desc": "每档间隔2000-5000位次",
        "保底多预留": 0,
        "说明": "物理组考生基数大，位次稀疏，间隔可拉大"
    },
    "历史组": {
        "冲稳间隔_desc": "每档间隔300-800位次",
        "稳保间隔_desc": "每档间隔800-2000位次",
        "保底多预留": "20%",
        "说明": "历史组同分扎堆严重，保底区间多预留20%志愿"
    }
}

def load_json(filename):
    with open(DATA_DIR / filename, "r", encoding="utf-8") as f:
        return json.load(f)


class GaokaoAnalyzer:
    def __init__(self):
        self.control = load_json("control_lines.json")
        self.universities = load_json("national_universities.json")
        self.vocational = load_json("hebei_vocational_colleges.json")
        self.academic = load_json("university_academic.json")
        self.trends = load_json("major_trends.json")
        
        # gk100 高校索引 + 录取缓存（混合模式）
        self.gk100_index = self._load_gk100_index()
        self.gk100_cache = self._load_gk100_cache()
    
    def _load_gk100_index(self):
        """加载gk100河北高校索引"""
        f = DATA_DIR / "gk100_school_index.json"
        if not f.exists():
            return {"schools": []}
        return json.load(open(f, "r", encoding="utf-8"))
    
    def _load_gk100_cache(self):
        """加载gk100录取数据缓存"""
        f = DATA_DIR / "gk100_admission_cache.json"
        if not f.exists():
            return {}
        return json.load(open(f, "r", encoding="utf-8"))

    # ──────────────────────────────────────────
    # ① 等效分换算引擎（张雪峰七步法 第二步）
    # ──────────────────────────────────────────
    def _rank_to_equivalent_scores(self, rank, group, years=None):
        """
        将当年位次换算成近3年等效分，取均值。
        
        张雪峰七步法第二步：拿着位次 → 对照近3年一分一段表 → 找到对应分数 → 取均值
        """
        if years is None:
            # 2026年一分一段表尚未发布时，使用2023-2025三年数据做等效分换算
            years = ["2023", "2024", "2025"]
        
        years_data = self.control.get("各年份详细数据", {})
        equiv_scores = {}
        
        for y in years:
            ydata = years_data.get(y)
            if not ydata:
                continue
            gdata = ydata.get(group)
            if not gdata:
                continue
            segments = gdata.get("一分一段表", [])
            if not segments:
                continue
            
            # 一分一段表按分数降序排列，cumulative 是累计人数（从高分往低分累计）
            # 查找该位次对应的分数：找到 cumulative >= rank 的第一个 segment
            found_score = None
            for seg in segments:
                if seg.get("cumulative", 0) >= rank:
                    found_score = seg.get("score")
                    break
            
            if found_score is not None:
                equiv_scores[y] = found_score
        
        # 计算均值
        if equiv_scores:
            avg = round(sum(equiv_scores.values()) / len(equiv_scores))
        else:
            avg = None
        
        return {
            "input_rank": rank,
            "equiv_scores": equiv_scores,
            "years_available": list(equiv_scores.keys()),
            "average_equiv_score": avg,
            "note": f"位次{rank} → 近{len(equiv_scores)}年等效分均值 {avg}分（张雪峰七步法）"
        }

    # ──────────────────────────────────────────
    # ② 等效分冲稳保区间（张雪峰七步法 第三步）
    # ──────────────────────────────────────────
    def _equivalent_cwb(self, avg_equiv_score):
        """基于等效分划定冲稳保区间（张雪峰七步法标准区间）"""
        if avg_equiv_score is None:
            return {"error": "等效分缺失，无法划定区间"}
        
        result = {}
        for tier, params in EQUIV_CWB_PARAMS.items():
            lower = avg_equiv_score + params["score_add_min"]
            upper = avg_equiv_score + params["score_add_max"]
            result[tier] = {
                "等效分范围": f"{lower}-{upper}分",
                "等效分低位": lower,
                "等效分高位": upper,
                "建议数量": CWB_COUNTS[tier],
                "策略": params["desc"]
            }
        result["志愿总数"] = CWB_COUNTS["total"]
        result["基于等效分"] = avg_equiv_score
        return result

    # ──────────────────────────────────────────
    # ③ 三年位次稳定性分析（张雪峰七步法 第四步）
    # ──────────────────────────────────────────
    def _stability_analysis(self, matched_universities, group):
        """
        对匹配院校做三年位次稳定性分析。
        当前高校数据为单年参考位次，框架已就绪：
        - 待补充三年录取数据后，自动计算波动系数
        - 标记"位次稳定"/"大小年波动"/"优先考虑（扩招）"
        """
        names = set()
        for key in ["冲", "稳", "保"]:
            for u in matched_universities.get(key, []):
                names.add(u["name"])
        
        stability = {}
        for name in names:
            info = self.universities.get(name, {})
            rank_p = info.get("rank_p")
            rank_h = info.get("rank_h")
            
            entry = {
                "当前参考位次（物理组）": rank_p,
                "当前参考位次（历史组）": rank_h,
                "三年数据状态": "待补充",
                "稳定性等级": "待评估",
                "备注": "仅含单年参考位次，需补充三年录取数据后才能做大小年分析"
            }
            stability[name] = entry
        
        return stability

    # ──────────────────────────────────────────
    # ④ 扩招标注
    # ──────────────────────────────────────────
    def _expand_enrollment_marking(self, matched_universities):
        """
        标注扩招院校（数据待补充）。
        张雪峰：今年扩招→录取位次可能降→优先考虑
        """
        # 当前高校数据无扩招信息，预留接口
        return {
            "status": "待补充",
            "note": "扩招数据待补充。补充后可自动标注'今年扩招→优先考虑'"
        }

    # ──────────────────────────────────────────
    # ⑥ gk100 混合模式匹配（真实录取数据）
    # ──────────────────────────────────────────
    def _match_gk100_schools(self, group, rank, score):
        """
        使用gk100真实录取数据匹配院校（混合模式）。
        优先使用缓存数据，无缓存则提供爬取入口。
        """
        schools = self.gk100_index.get("schools", [])
        cache = self.gk100_cache
        rank_key = "rank_p" if group == "物理组" else "rank_h"
        
        # 筛选河北省的学校，走读匹配
        matched = {"冲": [], "稳": [], "保": [], "未缓存": []}
        
        for s in schools:
            if s["province"] != "河北":
                continue
            name = s["name"]
            cached = cache.get(name)
            
            if not cached:
                # 未缓存，记录但不匹配
                matched["未缓存"].append({
                    "name": name, "gk100_id": s["gk100_id"],
                    "level": s["level"], "category": s.get("category", ""),
                    "location": s["location"]
                })
                continue
            
            # 使用缓存中的2025年录取位次
            adm = cached.get("admission_2025", {})
            r = adm.get("rank")
            if r is None:
                matched["未缓存"].append({"name": name, "gk100_id": s["gk100_id"], "reason": "无2025位次数据"})
                continue
            
            # 冲稳保匹配（使用真实位次）
            threshold = 0.7 if s["level"] == "本科" else 0.65
            if r < rank * threshold:
                continue
            elif r < rank:
                matched["冲"].append(self._gk100_entry(s, cached, "冲"))
            elif r <= rank * 1.5:
                matched["稳"].append(self._gk100_entry(s, cached, "稳"))
            else:
                matched["保"].append(self._gk100_entry(s, cached, "保"))
        
        for key in ["冲", "稳", "保"]:
            matched[key].sort(key=lambda x: x.get("rank_2025", 999999))
        
        return {
            "冲": matched["冲"][:12],
            "稳": matched["稳"][:12],
            "保": matched["保"][:12],
            "未缓存_可爬取": matched["未缓存"][:20],
            "total_冲": len(matched["冲"]),
            "total_稳": len(matched["稳"]),
            "total_保": len(matched["保"]),
            "total_未缓存": len(matched["未缓存"])
        }
    
    def _gk100_entry(self, school, cached, tier):
        """构建gk100匹配条目"""
        ad25 = cached.get("admission_2025", {})
        ad24 = cached.get("admission_2024", {})
        ad23 = cached.get("admission_2023", {})
        return {
            "name": school["name"],
            "gk100_id": school["gk100_id"],
            "level": school["level"],
            "location": school["location"],
            "category": school.get("category", ""),
            "tags": school.get("tags", []),
            "tier": tier,
            "rank_2025": ad25.get("rank"),
            "score_2025": ad25.get("score"),
            "rank_2024": ad24.get("rank"),
            "rank_2023": ad23.get("rank"),
            "data_source": "gk100.com (真实)"
        }

    # ──────────────────────────────────────────
    # ⑤ 专科院校匹配
    # ──────────────────────────────────────────
    def _match_vocational_colleges(self, group, rank):
        """匹配专科（高职）院校"""
        rank_key = "rank_p" if group == "物理组" else "rank_h"
        matched = {"冲": [], "稳": [], "保": []}
        
        for name, info in self.vocational.items():
            if name == "metadata" or name == "school_types":
                continue
            r = info.get(rank_key)
            if r is None:
                continue
            
            # 专科匹配使用更宽松的比例
            if r < rank * 0.7:
                continue
            elif r < rank:
                matched["冲"].append({
                    "name": name, "rank": r, "tier": "专科",
                    "level": info.get("level", ""), "location": info.get("location", ""),
                    "tags": info.get("tags", []),
                    "admission_score": info.get("admission_score_2025"),
                    "recommended_majors": info.get("recommended_majors", [])[:3],
                    "employment_note": info.get("employment_note", "")
                })
            elif r <= rank * 1.5:
                matched["稳"].append({
                    "name": name, "rank": r, "tier": "专科",
                    "level": info.get("level", ""), "location": info.get("location", ""),
                    "tags": info.get("tags", []),
                    "admission_score": info.get("admission_score_2025"),
                    "recommended_majors": info.get("recommended_majors", [])[:3],
                    "employment_note": info.get("employment_note", "")
                })
            else:
                if r <= rank * 2.0:
                    matched["保"].append({
                        "name": name, "rank": r, "tier": "专科",
                        "level": info.get("level", ""), "location": info.get("location", ""),
                        "tags": info.get("tags", []),
                        "admission_score": info.get("admission_score_2025"),
                        "recommended_majors": info.get("recommended_majors", [])[:3],
                        "employment_note": info.get("employment_note", "")
                    })
        
        for key in matched:
            matched[key].sort(key=lambda x: x["rank"])
        
        return {
            "冲": matched["冲"][:12],
            "稳": matched["稳"][:12],
            "保": matched["保"][:12],
            "total_冲": len(matched["冲"]),
            "total_稳": len(matched["稳"]),
            "total_保": len(matched["保"])
        }
    
    # ──────────────────────────────────────────
    # 新增：自动推荐预设方案 + 梯度信息
    # ──────────────────────────────────────────
    def _recommend_scheme_and_gradient(self, group, score, special_line, benke_line):
        """根据分数段自动推荐志愿分配方案，并返回物理/历史梯度信息"""
        # 1. 推荐方案
        over_special = score - special_line if special_line else 0
        over_benke = score - benke_line if benke_line else 0
        
        if over_special >= 30:
            scheme_name = "进取冲刺型"
        elif over_benke <= 20 and over_benke >= 0:
            scheme_name = "压线保底型"
        else:
            scheme_name = "均衡稳妥型"
        
        scheme = CWB_PRESETS[scheme_name]
        
        # 2. 梯度信息
        gradient = GRADIENT_PARAMS.get(group, {})
        
        return {
            "推荐方案": {
                "名称": scheme_name,
                "比例": scheme["比例"],
                "分配": f"冲{scheme['冲']}个 / 稳{scheme['稳']}个 / 保{scheme['保']}个",
                "说明": scheme["desc"]
            },
            "所有方案": CWB_PRESETS,
            "梯度说明": {
                "冲稳间隔": gradient.get("冲稳间隔_desc", ""),
                "稳保间隔": gradient.get("稳保间隔_desc", ""),
                "保底提醒": gradient.get("说明", ""),
                "历史组保底多预留": gradient.get("保底多预留", 0)
            }
        }

    # ──────────────────────────────────────────
    # 原有方法：位次定位
    # ──────────────────────────────────────────
    def _positioning(self, group, score, rank, year):
        """位次定位分析"""
        years_data = self.control.get("各年份详细数据", {})
        year_key = year
        # 2026实际数据已更新，直接用year_key即可
        if year_key not in years_data:
            if "2026" in years_data:
                year_key = "2026"
            elif "2025" in years_data:
                year_key = "2025"
        
        ydata = years_data.get(year_key)
        if not ydata:
            ydata = years_data.get("2025", years_data.get(list(years_data.keys())[0]))
        
        gdata = ydata.get(group) if ydata else None
        if not gdata:
            for yk, yv in years_data.items():
                if group in yv:
                    gdata = yv[group]
                    break
        
        if not gdata:
            return {"error": f"未找到{group}组{year}年数据"}
        
        control_line = gdata.get("省控线", gdata)
        special_line = control_line.get("特殊类型招生控制线", 0)
        benke_line = control_line.get("本科批分数线", 0)
        
        over_special = score - special_line if special_line else 0
        over_benke = score - benke_line if benke_line else 0
        
        if score >= special_line:
            level = "特招线上（高分段）"
        elif score >= benke_line:
            level = "本科线上（中分段）"
        else:
            level = "本科线下"
        
        segments = gdata.get("一分一段表", [])
        approx_rank = None
        for seg in segments:
            if seg.get("score") == score:
                approx_rank = seg.get("cumulative")
                break
        
        # 位次定位描述
        if rank <= 1000:
            rank_desc = "全省顶尖，清北复交段"
        elif rank <= 5000:
            rank_desc = "顶级985段"
        elif rank <= 12000:
            rank_desc = "中上游985/顶级211段"
        elif rank <= 25000:
            rank_desc = "下游985/强势211段"
        elif rank <= 50000:
            rank_desc = "中游211/省重点段"
        elif rank <= 100000:
            rank_desc = "普通一本/公办二本段"
        elif rank <= 150000:
            rank_desc = "本科中游段"
        else:
            rank_desc = "本科边缘/专科段"
        
        # 推荐方案 + 梯度信息
        scheme_gradient = self._recommend_scheme_and_gradient(group, score, special_line, benke_line)
        
        return {
            "score": score,
            "rank": rank,
            "group": group,
            "special_type_line": special_line,
            "benke_line": benke_line,
            "over_special_line": over_special,
            "over_benke_line": over_benke,
            "level": level,
            "rank_level": rank_desc,
            "approx_rank_from_segments": approx_rank,
            "year": year,
            "total_candidates": self.control.get("考生人数参考", {}).get(year, "未知"),
            "volunteer_plan": scheme_gradient["推荐方案"],
            "scheme_options": scheme_gradient["所有方案"],
            "gradient_note": scheme_gradient["梯度说明"]
        }

    # ──────────────────────────────────────────
    # 原有方法：位次法冲稳保
    # ──────────────────────────────────────────
    def _chong_wen_bao(self, group, rank, year, scheme=None):
        """位次法冲稳保计算（保留原有方法，与等效分法并存）
           scheme: 推荐方案字典，含冲/稳/保数量"""
        chong_upper = int(rank * 0.6)
        chong_lower = int(rank * 0.85)
        wen_upper = int(rank * 0.85)
        wen_lower = int(rank * 1.15)
        bao_upper = int(rank * 1.15)
        bao_lower = int(rank * 1.5)
        
        # 使用推荐方案中的志愿数量，否则用默认值
        if scheme:
            chong_n = scheme.get("冲", 20)
            wen_n = scheme.get("稳", 50)
            bao_n = scheme.get("保", 26)
        else:
            chong_n, wen_n, bao_n = 20, 50, 26
        
        return {
            "冲一冲": {
                "位次范围": f"{chong_upper}-{chong_lower}",
                "建议数量": chong_n,
                "策略": "用名校冷门专业或偏远地区985冲击"
            },
            "稳一稳": {
                "位次范围": f"{wen_upper}-{wen_lower}",
                "建议数量": wen_n,
                "策略": "主力志愿，匹配度最高"
            },
            "保一保": {
                "位次范围": f"{bao_upper}-{bao_lower}",
                "建议数量": bao_n,
                "策略": "确保不滑档"
            },
            "志愿总数": chong_n + wen_n + bao_n
        }

    # ──────────────────────────────────────────
    # 原有方法：位次法院校匹配
    # ──────────────────────────────────────────
    def _match_universities(self, group, rank):
        """按位次匹配院校（保留原逻辑）"""
        rank_key = "rank_p" if group == "物理组" else "rank_h"
        matched = {"冲": [], "稳": [], "保": []}
        
        for name, info in self.universities.items():
            if name == "metadata":
                continue
            r = info.get(rank_key)
            if r is None:
                continue
            
            if r < rank * 0.7:
                continue
            elif r < rank:
                matched["冲"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
            elif r <= rank * 1.3:
                matched["稳"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
            else:
                matched["保"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
        
        for key in matched:
            matched[key].sort(key=lambda x: x["rank"])
        
        return {
            "冲": matched["冲"][:15],
            "稳": matched["稳"][:15],
            "保": matched["保"][:15],
            "total_冲": len(matched["冲"]),
            "total_稳": len(matched["稳"]),
            "total_保": len(matched["保"])
        }

    # ──────────────────────────────────────────
    # ⑤ 等效分法院校匹配 + 稳定性标注
    # ──────────────────────────────────────────
    def _match_universities_by_equiv(self, group, avg_equiv_score):
        """
        基于等效分匹配院校。
        策略：将 等效分 → 找2025年一分一段表对应位次 → 再用该位次匹配
        """
        rank_key = "rank_p" if group == "物理组" else "rank_h"
        
        # 将等效分转为2025年位次（最接近的参考年份）
        years_data = self.control.get("各年份详细数据", {})
        ydata = years_data.get("2025", years_data.get("2024"))
        gdata = ydata.get(group) if ydata else None
        equiv_rank = None
        if gdata:
            segments = gdata.get("一分一段表", [])
            for seg in segments:
                if seg.get("score", 0) <= avg_equiv_score:
                    equiv_rank = seg.get("cumulative")
                    break
        
        if equiv_rank is None:
            return {"error": "无法将等效分转为参考位次"}
        
        matched = {"冲": [], "稳": [], "保": []}
        
        for name, info in self.universities.items():
            if name == "metadata":
                continue
            r = info.get(rank_key)
            if r is None:
                continue
            
            # 等效分法对应的位次匹配（稍宽松，因为等效分法更保守）
            if r < equiv_rank * 0.7:
                continue
            elif r < equiv_rank:
                matched["冲"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
            elif r <= equiv_rank * 1.35:
                matched["稳"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
            else:
                matched["保"].append({"name": name, "rank": r, "tier": info.get("tier",""), "location": info.get("location",""), "tags": info.get("tags",[]), "level": info.get("level","")})
        
        for key in matched:
            matched[key].sort(key=lambda x: x["rank"])
        
        return {
            "等效分参考位次": equiv_rank,
            "冲": matched["冲"][:15],
            "稳": matched["稳"][:15],
            "保": matched["保"][:15],
            "total_冲": len(matched["冲"]),
            "total_稳": len(matched["稳"]),
            "total_保": len(matched["保"])
        }

    # ──────────────────────────────────────────
    # 选科筛选
    # ──────────────────────────────────────────
    def _filter_majors(self, subjects):
        """根据选科筛选可报专业"""
        physics = "物" in subjects
        chemistry = "化" in subjects
        biology = "生" in subjects
        politics = "政" in subjects
        history = "史" in subjects
        geography = "地" in subjects
        
        available = []
        for name, info in self.trends.items():
            req = info.get("subject_requirements", {})
            physics_req = req.get("physics", False)
            chemistry_req = req.get("chemistry", False)
            
            can_apply = True
            if physics_req and not physics:
                can_apply = False
            if chemistry_req and chemistry_req != "recommended" and not chemistry:
                can_apply = False
                
            if can_apply:
                available.append({
                    "name": name,
                    "category": info.get("category",""),
                    "红利评分": info.get("红利评分", 0),
                    "推荐指数": info.get("推荐指数", ""),
                    "未来10年": info.get("未来10年", ""),
                    "风险": info.get("风险", ""),
                    "硕博必要性": info.get("硕博必要性", ""),
                    "核心城市": info.get("核心城市", []),
                    "建议院校层次": info.get("建议院校层次", "")
                })
        
        available.sort(key=lambda x: x["红利评分"], reverse=True)
        return available

    # ──────────────────────────────────────────
    # 策略生成
    # ──────────────────────────────────────────
    def _generate_strategies(self, matched, majors, group, subjects):
        """生成推荐策略"""
        return {
            "school_first": "优先保学校层次，适合有名校情结的学生",
            "major_first": "优先保专业前景，适合对职业有清晰规划的学生",
            "city_first": "优先保城市区位，适合想在特定城市发展的学生",
            "recommended_majors": [m["name"] for m in majors[:10]]
        }

    # ──────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────
    def analyze(self, group, score, rank, subjects, province="河北省", year="2026"):
        """主分析入口——双模式输出：位次法 + 等效分法"""
        # 1. 位次定位
        positioning = self._positioning(group, score, rank, year)
        
        # 2. 等效分换算（张雪峰七步法 第二步）
        equiv_result = self._rank_to_equivalent_scores(rank, group)
        
        # 3. 冲稳保计算（双模式）
        recommended_scheme = positioning.get("volunteer_plan", {})
        scheme_counts = {"冲": 20, "稳": 50, "保": 26}
        # 从分配字符串中解析数量，如"冲19个 / 稳48个 / 保29个"
        alloc = recommended_scheme.get("分配", "")
        if alloc:
            import re as _re
            parts = _re.findall(r'冲(\d+)个|稳(\d+)个|保(\d+)个', alloc)
            if parts:
                for p in parts:
                    if p[0]: scheme_counts["冲"] = int(p[0])
                    if p[1]: scheme_counts["稳"] = int(p[1])
                    if p[2]: scheme_counts["保"] = int(p[2])
        cwb_rank = self._chong_wen_bao(group, rank, year, scheme=scheme_counts)  # 位次法
        cwb_equiv = self._equivalent_cwb(equiv_result.get("average_equiv_score"))  # 等效分法
        
        # 4. 院校匹配（双模式）
        matched_rank = self._match_universities(group, rank)               # 位次法（本科）
        matched_equiv = self._match_universities_by_equiv(
            group, equiv_result.get("average_equiv_score")
        )  # 等效分法（本科）

        # 4b. 专科院校匹配（位次法）
        matched_vocational = self._match_vocational_colleges(group, rank)

        # 4c. gk100 真实数据补充（混合模式）
        gk100_matched = self._match_gk100_schools(group, rank, score)

        # 5. 三年位次稳定性分析
        stability = self._stability_analysis(matched_rank, group)
        
        # 6. 扩招标注
        enrollment_marking = self._expand_enrollment_marking(matched_rank)
        
        # 7. 选科可报专业
        available_majors = self._filter_majors(subjects)
        
        # 8. 推荐策略
        strategies = self._generate_strategies(matched_rank, available_majors, group, subjects)
        
        return {
            "positioning": positioning,
            "equiv_score_analysis": equiv_result,          # 新增
            "chong_wen_bao_rank_method": cwb_rank,         # 位次法（原有）
            "chong_wen_bao_equiv_method": cwb_equiv,       # 新增：等效分法
            "matched_universities_rank_method": matched_rank,     # 位次法（原有）
            "matched_universities_equiv_method": matched_equiv,   # 新增：等效分法
            "matched_vocational_colleges": matched_vocational,     # 新增：专科院校匹配
            "matched_gk100_schools": gk100_matched,               # 新增：gk100真实数据混合模式
            "stability_analysis": stability,               # 新增
            "enrollment_marking": enrollment_marking,       # 新增
            "available_majors": available_majors,
            "strategies": strategies,
            "academic_data": self.academic,
            "trends": self.trends,
            "analysis_info": {
                "版本": "v3.0",
                "新增功能": [
                    "等效分换算引擎（张雪峰七步法第二步）",
                    "等效分冲稳保区间（张雪峰七步法第三步）",
                    "三年位次稳定性分析框架（张雪峰七步法第四步）",
                    "扩招标注框架",
                    "双模式输出：位次法 vs 等效分法",
                    "专科院校匹配（28所专科/高职院校数据）",
                    "gk100 混合模式（133所河北高校索引 + 真实录取数据缓存）"
                ],
                "待补充数据": [
                    "各高校近3年录取位次（稳定性分析）",
                    "各高校扩招/缩招信息",
                    "体检限制/单科分数要求（退档红线）",
                    "各高校各专业录取位次（96志愿精细化）",
                    "更多专科院校专业组数据"
                ]
            }
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="河北高考志愿分析 v2.0 — 位次法+等效分法双模式")
    parser.add_argument("--group", required=True, choices=["物理组","历史组"])
    parser.add_argument("--score", type=int, required=True)
    parser.add_argument("--rank", type=int, required=True)
    parser.add_argument("--subjects", required=True, help="如 物化生")
    parser.add_argument("--year", default="2026")
    parser.add_argument("--no-equiv", action="store_true", help="仅输出位次法，跳过等效分分析")
    args = parser.parse_args()
    
    analyzer = GaokaoAnalyzer()
    result = analyzer.analyze(args.group, args.score, args.rank, args.subjects, year=args.year)
    print(json.dumps(result, ensure_ascii=False, indent=2))
