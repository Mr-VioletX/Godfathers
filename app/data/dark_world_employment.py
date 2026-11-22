# -*- coding: utf-8 -*-
"""Stage 87.5 — pure rules for the player-to-player Dark World labor market."""
from __future__ import annotations
from app.data import dark_world as D

ACCOUNT_AGE_HOURS=24
CONTRACT_TTL_HOURS=24
PAIR_DAILY_LIMIT=3
DAILY_POST_LIMIT=8
DAILY_ESCROW_LIMIT=5_000_000_000
MAX_SHARE_PCT=30
MARKET_LIMIT=10

JOB_ORDER=("intel_scout","shadow_courier","signal_breach","safehouse_guard")
JOBS={
 "intel_scout":{"name":"شناسایی شبکه","icon":"🔎","base_chance":72,"budget":30_000_000,"wage":24_000_000,"bonus":18_000_000,"loot_mult":.45,"effect":"intel","effect_success":5,"effect_fail":1,"min_level":35,"description":"جمع‌آوری اطلاعات معتبر برای کارفرما."},
 "shadow_courier":{"name":"حمل سایه","icon":"🚚","base_chance":64,"budget":90_000_000,"wage":55_000_000,"bonus":45_000_000,"loot_mult":1.25,"effect":"cash","effect_success":0,"effect_fail":0,"min_level":37,"description":"عبور دادن محموله مالی از مسیر متغیر."},
 "signal_breach":{"name":"نفوذ سیگنال","icon":"📡","base_chance":58,"budget":140_000_000,"wage":80_000_000,"bonus":75_000_000,"loot_mult":1.55,"effect":"heat","effect_success":-18,"effect_fail":5,"min_level":40,"description":"پاک‌کردن بخشی از رد دیجیتال ذی‌نفع."},
 "safehouse_guard":{"name":"دفاع مخفیگاه","icon":"🛡️","base_chance":61,"budget":110_000_000,"wage":70_000_000,"bonus":60_000_000,"loot_mult":1.10,"effect":"integrity","effect_success":28,"effect_fail":-8,"min_level":38,"description":"خنثی‌سازی رخنه و ترمیم دفاع مخفیگاه."},
}
PAYMENT_ORDER=("fixed","share","hybrid")
PAYMENTS={
 "fixed":{"name":"دستمزد ثابت","fixed_mult":1.35,"bonus_mult":0,"share":0,"description":"درآمد کارگر مطمئن‌تر؛ سهمی از غنیمت ندارد."},
 "share":{"name":"سهمی","fixed_mult":.35,"bonus_mult":0,"share":25,"description":"دستمزد کم، اما ۲۵٪ غنیمت؛ مناسب پذیرش ریسک."},
 "hybrid":{"name":"ترکیبی","fixed_mult":.80,"bonus_mult":1.0,"share":12,"description":"دستمزد متوسط + پاداش موفقیت + ۱۲٪ غنیمت."},
}
CONDITION_ORDER=("quiet","corrupt","volatile")
CONDITIONS={
 "quiet":{"name":"شب آرام","counter":"stealth","clue":"رفت‌وآمد کم است، اما هر صدای اضافه مدت زیادی در حافظه می‌ماند."},
 "corrupt":{"name":"حلقه فاسد","counter":"social","clue":"یکی از نگهبان‌ها بیشتر از مسیر، به قیمت معامله نگاه می‌کند."},
 "volatile":{"name":"وضعیت شکننده","counter":"force","clue":"زمان در حال تمام‌شدن است و مسیر هر دقیقه بسته‌تر می‌شود."},
}
APPROACH_ORDER=("stealth","social","force")
APPROACHES={
 "stealth":{"name":"حرکت بی‌رد","icon":"🥷","chance":2,"loot_mult":.88,"heat":2},
 "social":{"name":"بازی واسطه‌ها","icon":"🎭","chance":0,"loot_mult":1.0,"heat":5},
 "force":{"name":"اجرای سریع","icon":"💥","chance":-5,"loot_mult":1.28,"heat":11},
}

def job(key):return JOBS.get(str(key or ""))
def payment(key):return PAYMENTS.get(str(key or ""))
def approach(key):return APPROACHES.get(str(key or ""))
def package(job_key,payment_key):
 j=job(job_key);p=payment(payment_key)
 if not j or not p:return {}
 fixed=round(j["wage"]*p["fixed_mult"]);bonus=round(j["bonus"]*p["bonus_mult"]);budget=int(j["budget"])
 return {"fixed_wage":fixed,"success_bonus":bonus,"share_pct":min(MAX_SHARE_PCT,int(p["share"])),"operation_budget":budget,"escrow_total":fixed+bonus+budget}
def execution_chance(job_key,condition_key,approach_key,*,level:int,trust:int,heat:int,team_effectiveness:float=0,team_tactic:str="balanced"):
 j=job(job_key);c=CONDITIONS.get(condition_key);a=approach(approach_key)
 if not j or not c or not a:return {}
 match=18 if c["counter"]==approach_key else (-8 if (c["counter"],approach_key) in (("stealth","force"),("force","social"),("social","stealth")) else 0)
 level_bonus=max(0,min(12,int(level)-int(j["min_level"])))
 trust_bonus=(max(0,min(100,int(trust)))-50)*.10
 team_bonus=min(8,max(0,float(team_effectiveness))*5)
 tactic_bonus=3 if (team_tactic=="silent" and approach_key=="stealth") or (team_tactic=="aggressive" and approach_key=="force") else 0
 heat_penalty=max(0,int(heat)-50)*.12
 chance=max(12,min(95,j["base_chance"]+a["chance"]+match+level_bonus+trust_bonus+team_bonus+tactic_bonus-heat_penalty))
 return {"chance":round(chance,2),"match":match,"level_bonus":level_bonus,"trust_bonus":round(trust_bonus,2),"team_bonus":round(team_bonus,2),"heat_penalty":round(heat_penalty,2)}
def resolve(job_key,condition_key,approach_key,roll:float,budget:int):
 info=execution_chance(job_key,condition_key,approach_key,level=35,trust=50,heat=0)
 if not info:return {}
 # Caller supplies its persisted, player-specific chance separately; this helper models rewards only.
 success=bool(roll<info["chance"]);j=job(job_key);a=approach(approach_key)
 loot=round(int(budget)*j["loot_mult"]*a["loot_mult"]*(1 if success else .10))
 effect=j["effect_success"] if success else j["effect_fail"]
 return {"success":success,"loot":max(0,loot),"effect":effect,"heat":a["heat"]+(0 if success else 8)}
def settlement(fixed_wage:int,success_bonus:int,share_pct:int,operation_budget:int,loot:int,success:bool):
 fixed=max(0,int(fixed_wage));bonus=max(0,int(success_bonus)) if success else 0;share=max(0,min(MAX_SHARE_PCT,int(share_pct)))
 worker=fixed+bonus+round(max(0,int(loot))*share/100);employer=max(0,int(operation_budget)-max(0,int(loot)))+max(0,int(loot))-round(max(0,int(loot))*share/100)+(0 if success else max(0,int(success_bonus)))
 return {"worker":worker,"employer":max(0,employer),"worker_share":round(max(0,int(loot))*share/100),"bonus":bonus}
