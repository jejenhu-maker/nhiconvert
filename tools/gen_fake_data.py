# -*- coding: utf-8 -*-
"""
產生「上課練習用」的假健保門診申報檔（TOTFA-yyymm.zip）。

做法：
- 從真實申報檔只取「非個人」的臨床樣板（診斷碼組合、醫令組合、點數結構、案件分類等）
  當作詞彙與分布來源；病人、姓名、身分證、出生日期、就醫日期、醫師、機構代號、
  就醫識別碼全部是隨機捏造的。
- 身分證字號刻意做成「檢查碼錯誤」，保證不會對應到任何真實的人。
- 醫令組合會隨機刪減、次診斷順序會打亂，因此沒有任何一筆與真實就醫紀錄相同。

用法：
  python tools/gen_fake_data.py <真實申報檔資料夾> <輸出資料夾> [--seed 42] [--ratio 0.6]
"""
import argparse
import collections
import io
import os
import random
import re
import sys
import zipfile
from datetime import date, timedelta

# ---------- 讀取真實檔案，抽出臨床樣板（不含任何個人欄位） ----------

ADMIN = ["d1", "d4", "d5", "d6", "d7", "d8", "d13", "d14", "d15", "d17", "d18", "d28",
         "d35", "d36", "d37", "d38", "d43", "d44", "d57", "d58"]
CLINICAL = ["d19", "d20", "d21", "d22", "d23", "d24", "d25", "d26", "d27",
            "d32", "d33", "d34", "d39", "d40", "d41"]
ORDER_DROP = {"p13", "p26"}                         # 重新產生或不輸出（p14/p15/p16 依樣板有無再重填）
INSTITUTION_FIELDS = ("d55", "p24")                 # 機構代號 → 對應到假代號


def read_real(folder):
    templates, birth_years, months = [], [], []
    real_names = set()                                    # 只用來排除，確保假姓名不與真實姓名相同
    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".zip"):
            continue
        with zipfile.ZipFile(os.path.join(folder, name)) as z:
            xml_names = [n for n in z.namelist() if n.lower().endswith(".xml")]
            if not xml_names:
                continue
            text = z.read(xml_names[0]).decode("cp950", "replace")
        m = re.search(r"<t3>(\d{5})</t3>", text)
        months.append((m.group(1) if m else name, name))
        for block in re.findall(r"<ddata>(.*?)</ddata>", text, re.S):
            body = re.sub(r"<pdata>.*?</pdata>", "", block, flags=re.S)
            f = dict(re.findall(r"<(d\d+)>(.*?)</\1>", body))
            real_names.add(f.get("d49", "").strip())
            if "d45" in f or "d51" in f or "d61" in f or "d62" in f:
                continue                                  # 新生兒依附、跨機構特殊案件不納入
            orders = []
            for ob in re.findall(r"<pdata>(.*?)</pdata>", block, re.S):
                o = dict(re.findall(r"<(p\d+)>(.*?)</\1>", ob))
                orders.append({k: v for k, v in o.items() if k not in ORDER_DROP})
            t = {k: f[k] for k in ADMIN + CLINICAL if k in f}
            t["_d10"] = "d10" in f
            t["_ic"] = f.get("d29", "").startswith("IC")
            t["_d31"] = "d31" in f
            t["_d55"] = f.get("d55", "")
            t["orders"] = orders
            templates.append(t)
            if re.fullmatch(r"\d{7}", f.get("d11", "")):
                birth_years.append(int(f["d11"][:3]))
    return templates, birth_years, months, real_names


# ---------- 假人物 ----------

SURNAMES = ("陳王李張林黃吳劉蔡楊許鄭謝郭洪邱曾廖賴徐周葉蘇莊呂江何蕭羅高潘簡朱鍾游彭詹胡施沈余趙盧梁顏柯翁魏孫戴范方宋鄧杜傅侯曹薛丁溫馬藍馮姚石卓紀"
            "康程連唐姜古白黎嚴龔涂尤巫韓阮陸熊倪童金俞秦")
SURNAME_WEIGHTS = [10, 9, 8, 6, 6, 5, 5, 4, 4, 3, 3, 3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1]
GIVEN_M = "志明俊宏建志文雄家豪冠宇承翰宗翰哲瑋柏翰彥廷子軒宇軒冠廷俊傑國華明德永昌建宏文彬進財金龍春生木火水土清標榮輝"
GIVEN_F = "淑芬美玲雅婷怡君淑惠佩珊怡如雅雯欣怡宜蓁詩涵思妤佳穎品妍秀英麗華月娥阿嬌春花秀琴美惠淑貞玉蘭桂英碧玉素珍"
ID_LETTERS = "ABCDEFGHJKLMNPQRSTUVXYWZIO"
ID_LETTER_VALUES = {c: i for i, c in enumerate(["A", "B", "C", "D", "E", "F", "G", "H", "J", "K", "L", "M", "N", "P", "Q", "R", "S", "T", "U", "V", "X", "Y", "W", "Z", "I", "O"], start=10)}
ID_REGION_WEIGHTS = [10, 6, 2, 3, 5, 6, 2, 3, 3, 3, 2, 2, 5, 4, 3, 2, 2, 3, 2, 2, 1, 1, 1, 1, 1, 1]


def fake_id(rng):
    """產生格式正確但『檢查碼刻意錯誤』的身分證字號，確保不會是任何真人的號碼。"""
    letter = rng.choices(ID_LETTERS, ID_REGION_WEIGHTS)[0]
    digits = [int(rng.choice("12"))] + [rng.randrange(10) for _ in range(7)]
    v = ID_LETTER_VALUES[letter]
    total = (v // 10) + (v % 10) * 9 + sum(d * w for d, w in zip(digits, [8, 7, 6, 5, 4, 3, 2, 1]))
    correct = (10 - total % 10) % 10
    wrong = rng.choice([d for d in range(10) if d != correct])
    return letter + "".join(map(str, digits)) + str(wrong)


def fake_name(rng, female):
    sur = rng.choices(SURNAMES, (SURNAME_WEIGHTS + [1] * len(SURNAMES))[:len(SURNAMES)])[0]
    pool = GIVEN_F if female else GIVEN_M
    n = 2 if rng.random() < 0.9 else 1
    return sur + "".join(rng.choice(pool) for _ in range(n))


def roc(d):
    return "%03d%02d%02d" % (d.year - 1911, d.month, d.day)


def make_patients(rng, n, birth_years, avoid_names=frozenset()):
    pats = []
    for _ in range(n):
        pid = fake_id(rng)
        female = pid[1] == "2"
        name = fake_name(rng, female)
        while name in avoid_names:
            name = fake_name(rng, female)
        y = rng.choice(birth_years) + 1911
        try:
            b = date(y, rng.randrange(1, 13), rng.randrange(1, 29))
        except ValueError:
            b = date(y, 1, 1)
        pats.append({"id": pid, "name": name, "birth": roc(b), "seq": 0})
    return pats


# ---------- 產生一個月份 ----------

def month_dates(ym):
    y, m = int(ym[:3]) + 1911, int(ym[3:])
    d = date(y, m, 1)
    out = []
    while d.month == m:
        if d.weekday() < 6:                       # 週日休診
            out.append(d)
        d += timedelta(days=1)
    return out


def rand_code(rng, n=20):
    return "".join(rng.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(n))


def gen_month(rng, ym, n_cases, templates, patients, doctors, inst_map, pharmacist):
    dates = month_dates(ym)
    weights = [1.6 if d.weekday() in (0, 1) else 1.0 for d in dates]
    # 病人抽樣：少數人常回診（權重偏斜）
    pw = [1.0 / (i + 30) for i in range(len(patients))]
    cases = []
    for _ in range(n_cases):
        t = rng.choice(templates)
        p = rng.choices(patients, pw)[0]
        visit = rng.choices(dates, weights)[0]
        f = {k: v for k, v in t.items() if not k.startswith("_") and k != "orders"}
        f["d3"] = p["id"]
        f["d49"] = p["name"]
        f["d11"] = p["birth"]
        f["d9"] = roc(visit)
        if t["_d10"]:
            f["d10"] = f["d9"]
        if t["_ic"]:
            f["d29"] = "IC%02d" % rng.randrange(1, 40)
        else:
            p["seq"] += 1
            f["d29"] = "%04d" % min(p["seq"], 60)
        doc = rng.choices(doctors, [4, 3, 3, 3])[0]
        f["d30"] = doc
        if t["_d31"]:
            f["d31"] = pharmacist
        if t["_d55"]:
            f["d55"] = inst_map.setdefault(t["_d55"], "35%08d" % rng.randrange(10 ** 8))
        f["d60"] = rand_code(rng)
        # 次診斷順序打亂
        secs = [f.pop(k) for k in ("d20", "d21", "d22", "d23") if k in f]
        rng.shuffle(secs)
        for k, v in zip(("d20", "d21", "d22", "d23"), secs):
            f[k] = v
        # 醫令：零點數藥品隨機刪一項，使組合與原始紀錄不同
        orders = [dict(o) for o in t["orders"]]
        zero_drugs = [i for i, o in enumerate(orders) if o.get("p3") == "4" and o.get("p12", "0") in ("0", "0.0")]
        if len(zero_drugs) >= 3 and rng.random() < 0.5:
            del orders[rng.choice(zero_drugs)]
        stamp = f["d9"] + "0000"
        for i, o in enumerate(orders, 1):
            o["p13"] = str(i)
            if "p14" in o:
                o["p14"] = stamp
            if "p15" in o:
                o["p15"] = stamp
            if "p24" in o:
                o["p24"] = inst_map.setdefault(o["p24"], "JY%08d" % rng.randrange(10 ** 8))
            if "p16" in o:
                o["p16"] = doc
        cases.append((f, orders))
    # 依案件分類分組，流水編號各自從 1 開始
    order_of = collections.OrderedDict()
    for f, o in sorted(cases, key=lambda c: (c[0]["d1"], c[0]["d9"])):
        order_of.setdefault(f["d1"], []).append((f, o))
    out = []
    for d1, group in order_of.items():
        for i, (f, o) in enumerate(group, 1):
            f["d2"] = str(i)
            out.append((f, o))
    return out


def num(k):
    return int(re.sub(r"\D", "", k))


def build_xml(ym, cases, org_code):
    lines = ['<?xml version="1.0" encoding="Big5"?>', "<outpatient>", "<tdata>"]
    y, m = int(ym[:3]), int(ym[3:])
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    counts = collections.Counter()
    points = collections.Counter()
    copay_n, copay_pts = 0, 0
    for f, _ in cases:
        d1 = f["d1"]
        key = "t7" if d1 == "01" else "t31" if d1 in ("A3", "D2", "DF") else "t11" if d1 == "05" else "t15" if d1 in ("06", "C4") else "t9"
        counts[key] += 1
        points[key] += int(f.get("d41", "0") or 0)
        c = int(f.get("d40", "0") or 0)
        if c > 0:
            copay_n += 1
            copay_pts += c
    t = {"t1": "10", "t2": org_code, "t3": ym, "t4": "2", "t5": "1", "t6": "%03d%02d11" % (ny, nm)}
    pairs = {"t7": "t8", "t9": "t10", "t11": "t12", "t15": "t16", "t31": "t32"}
    west_n = west_p = 0
    for cn, pn in pairs.items():
        if counts[cn]:
            t[cn], t[pn] = str(counts[cn]), str(points[cn])
            if cn != "t31":
                west_n += counts[cn]
                west_p += points[cn]
    if west_n:
        t["t17"], t["t18"] = str(west_n), str(west_p)
    t["t37"] = str(len(cases))
    t["t38"] = str(sum(points.values()))
    t["t39"], t["t40"] = str(copay_n), str(copay_pts)
    for k in sorted(t, key=num):
        lines.append("<%s>%s</%s>" % (k, t[k], k))
    lines.append("</tdata>")
    for f, orders in cases:
        lines += ["<ddata>", "<dhead>", "<d1>%s</d1>" % f["d1"], "<d2>%s</d2>" % f["d2"], "</dhead>", "<dbody>"]
        for k in sorted((k for k in f if k not in ("d1", "d2")), key=num):
            lines.append("<%s>%s</%s>" % (k, f[k], k))
        for o in orders:
            lines.append("<pdata>")
            for k in sorted(o, key=num):
                lines.append("<%s>%s</%s>" % (k, o[k], k))
            lines.append("</pdata>")
        lines += ["</dbody>", "</ddata>"]
    lines.append("</outpatient>")
    return ("\r\n".join(lines) + "\r\n").encode("cp950")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--ratio", type=float, default=0.6, help="每月筆數 = 真實筆數 × ratio")
    ap.add_argument("--patients", type=int, default=9000)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    templates, birth_years, months, real_names = read_real(a.real_dir)
    print("templates:", len(templates), "months:", [m for m, _ in months])
    patients = make_patients(rng, a.patients, birth_years, real_names)
    doctors = [fake_id(rng) for _ in range(4)]
    pharmacist = fake_id(rng)
    inst_map = {}
    org_code = "3501234567"
    os.makedirs(a.out_dir, exist_ok=True)
    # 每月真實筆數（供 ratio 用）
    real_counts = {}
    for ym, name in months:
        with zipfile.ZipFile(os.path.join(a.real_dir, name)) as z:
            xml = [n for n in z.namelist() if n.lower().endswith(".xml")][0]
            real_counts[ym] = z.read(xml).count(b"<ddata>")
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as bz:
        for ym, _ in months:
            n = max(200, int(real_counts[ym] * a.ratio))
            cases = gen_month(rng, ym, n, templates, patients, doctors, inst_map, pharmacist)
            xml = build_xml(ym, cases, org_code)
            zname = "TOTFA-%s.zip" % ym
            path = os.path.join(a.out_dir, zname)
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("TOTFA.xml", xml)
            bz.write(path, zname)
            print(zname, "cases", len(cases), "orders", sum(len(o) for _, o in cases), "bytes", os.path.getsize(path))
        readme = (
            "健保門診申報「假資料」－ 僅供上課練習使用\r\n\r\n"
            "本資料包內的 TOTFA-yyymm.zip 全部是程式合成的假資料：病人姓名、身分證字號（檢查碼刻意錯誤）、\r\n"
            "出生日期、就醫日期、醫師代號、機構代號、就醫識別碼皆為隨機產生，不對應任何真實的人或診所。\r\n"
            "診斷碼、藥品代號與點數結構參考真實申報格式，方便練習「健保申報資料去識別化轉 CSV 工具」。\r\n\r\n"
            "請勿將本資料視為真實資料使用。\r\n"
            "工具與說明：https://jejenhu-maker.github.io/nhiconvert/\r\n"
        )
        bz.writestr("說明_這是假資料.txt", readme.encode("utf-8-sig"))
    bundle_path = os.path.join(a.out_dir, "健保申報假資料_上課用.zip")
    with open(bundle_path, "wb") as fh:
        fh.write(bundle.getvalue())
    print("bundle", bundle_path, os.path.getsize(bundle_path))


if __name__ == "__main__":
    main()
