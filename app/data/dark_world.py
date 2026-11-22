# -*- coding: utf-8 -*-
"""Stage 87.1: dependency-free rules for the Dark World endgame."""
from __future__ import annotations
import math
from datetime import datetime, timedelta

ACCESS_LEVEL=35
ENDGAME_LEVEL_CAP=60
ENERGY_MAX=100
ENERGY_REGEN_SECONDS=360
HEAT_MAX=100
HEAT_DECAY_SECONDS=1800
RANKING_LIMIT=10
RANK_TIERS=(
 {"key":"unmarked","name":"بی‌نشان","icon":"◼️","threshold":0},
 {"key":"courier","name":"پیک سایه","icon":"📨","threshold":75},
 {"key":"broker","name":"واسطه شب","icon":"🕴️","threshold":200},
 {"key":"operative","name":"عامل سیاه","icon":"🥷","threshold":500},
 {"key":"capo","name":"کاپوی سایه","icon":"🎩","threshold":1100},
 {"key":"baron","name":"بارون زیرزمین","icon":"🗝️","threshold":2300},
 {"key":"don","name":"دون تاریکی","icon":"♠️","threshold":4500},
 {"key":"nameless","name":"افسانه بی‌نام","icon":"👑","threshold":8000},
)
APPROACH_ORDER=("stealth","calculated","force")
APPROACHES={
 "stealth":{"name":"نفوذ خاموش","icon":"🥷","description":"شانس بیشتر، زمان بیشتر و رد کمتر.","chance_bonus":8.0,"cash_mult":.85,"xp_mult":1.0,"heat_mult":.6,"duration_mult":1.25},
 "calculated":{"name":"نقشه حساب‌شده","icon":"♟️","description":"تعادل زمان، خطر و پاداش.","chance_bonus":0.0,"cash_mult":1.0,"xp_mult":1.0,"heat_mult":1.0,"duration_mult":1.0},
 "force":{"name":"یورش بی‌پروا","icon":"💥","description":"سریع و پردرآمد، اما پرخطر.","chance_bonus":-12.0,"cash_mult":1.45,"xp_mult":1.35,"heat_mult":1.5,"duration_mult":.75},
}
CONTRACT_ORDER=("dead_drop","night_route","silent_auction","ghost_heist")
CONTRACTS={
 "dead_drop":{"name":"تحویل نقطه کور","icon":"📦","difficulty":1,"difficulty_name":"کم‌خطر","required_influence":0,"energy":12,"intel_cost":0,"entry_cost":2_000_000,"duration":600,"success_pct":82.0,"cash":25_000_000,"xp":1200,"dark_xp":18,"influence":14,"influence_loss":4,"heat":3,"intel_reward":2,"description":"بسته‌ای بی‌نام را پیش از روشن‌شدن شهر تحویل بده."},
 "night_route":{"name":"مسیر شبانه","icon":"🚚","difficulty":2,"difficulty_name":"حرفه‌ای","required_influence":75,"energy":20,"intel_cost":1,"entry_cost":15_000_000,"duration":1800,"success_pct":68.0,"cash":90_000_000,"xp":3500,"dark_xp":48,"influence":38,"influence_loss":12,"heat":7,"intel_reward":2,"description":"یک محموله حساس را از سه ایست بازرسی عبور بده."},
 "silent_auction":{"name":"مزایده خاموش","icon":"🎭","difficulty":3,"difficulty_name":"مرگبار","required_influence":200,"energy":30,"intel_cost":3,"entry_cost":60_000_000,"duration":4500,"success_pct":54.0,"cash":280_000_000,"xp":9000,"dark_xp":115,"influence":95,"influence_loss":32,"heat":14,"intel_reward":3,"description":"در مزایده‌ای با مهمان‌های بی‌نام، معامله را بدزد."},
 "ghost_heist":{"name":"سرقت شبح","icon":"👻","difficulty":4,"difficulty_name":"کابوس","required_influence":500,"energy":45,"intel_cost":8,"entry_cost":250_000_000,"duration":10800,"success_pct":38.0,"cash":900_000_000,"xp":22000,"dark_xp":280,"influence":250,"influence_loss":90,"heat":25,"intel_reward":5,"description":"وارد خزانه‌ای شو که روی هیچ نقشه‌ای وجود ندارد."},
}
RECRUIT_ORDER=("informant","fixer","driver","accountant")
RECRUITS={
 "informant":{"name":"خبرچین خیابانی","icon":"👁️","cost":150_000_000,"required_influence":0,"description":"+۵٪ شانس موفقیت تمام عملیات‌ها","success_bonus":5.0},
 "fixer":{"name":"کارچاق‌کن","icon":"🤝","cost":400_000_000,"required_influence":75,"description":"۲۵٪ گرمای کمتر پس از عملیات","heat_mult":.75},
 "driver":{"name":"راننده فرار","icon":"🏎️","cost":750_000_000,"required_influence":200,"description":"۲۰٪ زمان کمتر برای تمام عملیات‌ها","duration_mult":.8},
 "accountant":{"name":"حسابدار سایه","icon":"🧮","cost":1_500_000_000,"required_influence":500,"description":"۱۵٪ پول بیشتر از عملیات موفق","cash_mult":1.15},
}

def clamp(value,low,high): return max(low,min(high,value))
def get_contract(key): return CONTRACTS.get(str(key or ""))
def get_approach(key): return APPROACHES.get(str(key or ""))
def get_recruit(key): return RECRUITS.get(str(key or ""))
def rank_for(influence):
 points=max(0,int(influence or 0)); current=RANK_TIERS[0]
 for tier in RANK_TIERS:
  if points<int(tier["threshold"]): break
  current=tier
 return current
def next_rank(influence):
 points=max(0,int(influence or 0))
 for tier in RANK_TIERS:
  if points<int(tier["threshold"]): return tier
 return None
def progress_to_next_rank(influence):
 current=rank_for(influence); nxt=next_rank(influence)
 if nxt is None: return None
 return max(0,int(influence)-int(current["threshold"])),int(nxt["threshold"])-int(current["threshold"])
def recruit_modifiers(keys,effectiveness=1.0):
 out={"success_bonus":0.0,"heat_mult":1.0,"duration_mult":1.0,"cash_mult":1.0}
 for key in set(keys or ()):
  rec=get_recruit(key)
  if not rec: continue
  out["success_bonus"]+=float(rec.get("success_bonus",0))*float(effectiveness)
  for k in ("heat_mult","duration_mult","cash_mult"): out[k]*=1+(float(rec.get(k,1))-1)*float(effectiveness)
 return out
def contract_plan(contract_key,approach_key,heat=0,streak=0,recruit_keys=(),team_effectiveness=1.0,team_tactic="balanced"):
 c=get_contract(contract_key); a=get_approach(approach_key)
 if not c or not a: return {}
 mods=recruit_modifiers(recruit_keys,team_effectiveness); hv=int(clamp(int(heat or 0),0,HEAT_MAX))
 chance=clamp(float(c["success_pct"])+float(a["chance_bonus"])+mods["success_bonus"]-max(0,hv-20)*.22,15,95)
 streak_pct=min(30,max(0,int(streak or 0))*3)
 
 t={"silent":(3,.90,.78),"balanced":(0,1,1),"aggressive":(-2,1.16,1.28)}.get(team_tactic,(0,1,1)); chance=clamp(chance+t[0]*float(team_effectiveness),15,95)
 cash_mult=float(a["cash_mult"])*mods["cash_mult"]*(1+streak_pct/100)*t[1]
 xp_mult=float(a["xp_mult"]); duration_mult=float(a["duration_mult"])*mods["duration_mult"]; heat_mult=float(a["heat_mult"])*mods["heat_mult"]*t[2]
 sx=max(1,round(int(c["xp"])*xp_mult))
 return {"contract_key":contract_key,"approach_key":approach_key,"difficulty":int(c["difficulty"]),"chance":round(chance,2),"energy":int(c["energy"]),"intel_cost":int(c["intel_cost"]),"entry_cost":int(c["entry_cost"]),"duration":max(60,round(int(c["duration"])*duration_mult)),"cash_success":max(0,round(int(c["cash"])*cash_mult)),"xp_success":sx,"xp_failure":max(100,round(sx*.3)),"dark_xp_success":max(1,round(int(c["dark_xp"])*xp_mult)),"dark_xp_failure":max(1,round(int(c["dark_xp"])*.25)),"influence_success":int(c["influence"]),"influence_failure":-int(c["influence_loss"]),"heat_success":max(1,math.ceil(int(c["heat"])*heat_mult)),"heat_failure":max(1,math.ceil(int(c["heat"])*heat_mult*1.4)),"intel_reward":int(c["intel_reward"]),"streak_bonus_pct":streak_pct}
def resolve_plan(plan,roll,cash_factor_pct=100):
 if not plan: return {}
 ok=float(roll)<float(plan["chance"]); factor=int(clamp(int(cash_factor_pct or 100),90,110))
 if ok: return {"success":True,"cash":round(int(plan["cash_success"])*factor/100),"xp":int(plan["xp_success"]),"dark_xp":int(plan["dark_xp_success"]),"influence":int(plan["influence_success"]),"heat":int(plan["heat_success"]),"intel":int(plan["intel_reward"])}
 return {"success":False,"cash":0,"xp":int(plan["xp_failure"]),"dark_xp":int(plan["dark_xp_failure"]),"influence":int(plan["influence_failure"]),"heat":int(plan["heat_failure"]),"intel":0}
def recovery_steps(last_at,now,every_seconds):
 if last_at is None: return 0,now
 steps=int(max(0,(now-last_at).total_seconds())//max(1,int(every_seconds)))
 return steps,(last_at+timedelta(seconds=steps*max(1,int(every_seconds))) if steps else last_at)
def fmt_duration(seconds):
 seconds=max(0,int(seconds or 0)); h,rem=divmod(seconds,3600); m,s=divmod(rem,60)
 return f"{h} ساعت و {m} دقیقه" if h else (f"{m} دقیقه" if m else f"{s} ثانیه")
def heat_label(heat):
 v=int(clamp(int(heat or 0),0,HEAT_MAX))
 return "تعقیب سراسری" if v>=80 else "حکم تعقیب" if v>=60 else "بازرسی" if v>=40 else "زیر ذره‌بین" if v>=20 else "نامرئی"


def operation_locked(heat): return int(heat or 0) >= 80
