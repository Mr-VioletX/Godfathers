# -*- coding: utf-8 -*-
"""Stage 87.7 — abstract black finance, laundering and trace rules."""
from __future__ import annotations
from datetime import date
DIRTY_MAX=10**15
TRACE_MAX=100
TRACE_DECAY_SECONDS=3600
LAUNDER_MIN=10_000_000
CLIMATES=(
 {"key":"lenient","name":"پنجره آرام","chance":8,"trace_mult":.75,"clue":"بازرسی‌ها روی پرونده‌های قدیمی متمرکز شده‌اند."},
 {"key":"normal","name":"شب معمولی","chance":0,"trace_mult":1.0,"clue":"هیچ الگوی غیرعادی در رفت‌وآمد مأموران دیده نمی‌شود."},
 {"key":"crackdown","name":"موج بازرسی","chance":-12,"trace_mult":1.35,"clue":"چند صرافی بی‌نام هم‌زمان چراغ‌هایشان را خاموش کرده‌اند."},
)
METHOD_ORDER=("front","broker","shell")
METHODS={
 "front":{"name":"کسب‌وکار پوششی","icon":"🏪","fee_pct":22,"chance":90,"duration":2700,"trace":3,"min_influence":0,"description":"آهسته و کم‌ریسک؛ کارمزد بالا."},
 "broker":{"name":"واسطه چندلایه","icon":"🤝","fee_pct":12,"chance":76,"duration":1800,"trace":9,"min_influence":200,"description":"تعادل سرعت، هزینه و ریسک."},
 "shell":{"name":"شبکه صوری","icon":"🕸️","fee_pct":6,"chance":60,"duration":900,"trace":20,"min_influence":500,"description":"سریع و ارزان، اما ردگیری و مصادره شدید."},
}
RARE_ORDER=("cipher_key","ghost_pass","obsidian_art","zero_ledger")
RARE={
 "cipher_key":{"name":"کلید رمز یک‌بارمصرف","icon":"🗝️","price":180_000_000,"effect":"launder_bonus","value":8},
 "ghost_pass":{"name":"مجوز عبور شبح","icon":"🎫","price":260_000_000,"effect":"trace_cut","value":12},
 "obsidian_art":{"name":"اثر ابسیدین","icon":"🖼️","price":420_000_000,"effect":"collectible","value":1},
 "zero_ledger":{"name":"دفتر صفر","icon":"📓","price":650_000_000,"effect":"fee_cut","value":3},
}
def climate(day=None):return CLIMATES[(day or date.today()).toordinal()%len(CLIMATES)]
def method(k):return METHODS.get(str(k or ""))
def plan(amount,method_key,trace,influence=0,has_key=False,has_pass=False,has_ledger=False,day=None):
 m=method(method_key);a=max(0,int(amount));c=climate(day)
 if not m or a<LAUNDER_MIN:return {}
 fee=max(2,int(m["fee_pct"])-(3 if has_ledger else 0));amount_risk=min(18,max(0,(a-100_000_000)/100_000_000)*1.2);chance=max(10,min(96,m["chance"]+c["chance"]+(8 if has_key else 0)-max(0,int(trace)-25)*.22-amount_risk))
 trace_gain=max(1,round(m["trace"]*c["trace_mult"])-(12 if has_pass else 0));clean=round(a*(100-fee)/100)
 confiscation_pct=min(100,35+round(a/100_000_000)*2+(15 if method_key=="shell" else 0))
 return {"amount":a,"method_key":method_key,"fee_pct":fee,"clean":clean,"chance":round(chance,2),"trace_gain":trace_gain,"duration":m["duration"],"confiscation_pct":confiscation_pct,"climate":c}
def resolve(plan,roll):
 success=float(roll)<float(plan["chance"])
 return {"success":success,"clean":plan["clean"] if success else 0,"confiscated":0 if success else round(plan["amount"]*plan["confiscation_pct"]/100),"dirty_refund":0 if success else max(0,plan["amount"]-round(plan["amount"]*plan["confiscation_pct"]/100)),"trace":plan["trace_gain"] if success else plan["trace_gain"]+12}
def rare_today(day=None):
 d=(day or date.today()).toordinal();return (RARE_ORDER[d%len(RARE_ORDER)],RARE_ORDER[(d+1)%len(RARE_ORDER)])
