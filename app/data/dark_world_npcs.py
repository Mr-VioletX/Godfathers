# -*- coding: utf-8 -*-
"""Stage 87.4 — strategic NPC crew rules (pure and testable)."""
from __future__ import annotations
from app.data import dark_world as D

TEAM_SIZE=3
MAX_LEVEL=10
FATIGUE_MAX=100
LOYALTY_MAX=100
TRAINING_HOURS=6
REST_HOURS=4
INJURY_HOURS=8
WAGE_DAYS=7

NPC_ORDER=("informant","fixer","driver","accountant","hacker","medic","enforcer","ghost")
NPCS={
 "informant":{"class":"scout","class_name":"دیده‌بان","skills":("stealth","social"),"salary":18_000_000,"train_cost":85_000_000,"risk":.08,"description":"سرنخ و نفوذ؛ مناسب پرونده‌های آرام."},
 "fixer":{"class":"social","class_name":"مذاکره‌گر","skills":("social",),"salary":35_000_000,"train_cost":140_000_000,"risk":.06,"description":"رشوه، معامله و کنترل Heat."},
 "driver":{"class":"logistics","class_name":"راننده فرار","skills":("force","stealth"),"salary":52_000_000,"train_cost":190_000_000,"risk":.10,"description":"زمان کمتر و خروج از مسیرهای خطرناک."},
 "accountant":{"class":"tech","class_name":"حسابدار سایه","skills":("tech","social"),"salary":75_000_000,"train_cost":260_000_000,"risk":.05,"description":"سود، فناوری و رد مالی."},
 "hacker":{"class":"tech","class_name":"هکر سیاه","skills":("tech",),"salary":95_000_000,"train_cost":340_000_000,"risk":.12,"description":"برتری فناوری و دورزدن شبکه‌های امنیتی."},
 "medic":{"class":"support","class_name":"پزشک زیرزمینی","skills":("support",),"salary":80_000_000,"train_cost":300_000_000,"risk":.04,"description":"کاهش خستگی و احتمال جراحت کل تیم."},
 "enforcer":{"class":"force","class_name":"محافظ سنگین","skills":("force",),"salary":110_000_000,"train_cost":390_000_000,"risk":.14,"description":"قدرت بالا؛ مناسب عملیات تهاجمی و دفاع مخفیگاه."},
 "ghost":{"class":"stealth","class_name":"شبح نفوذی","skills":("stealth",),"salary":125_000_000,"train_cost":450_000_000,"risk":.11,"description":"نفوذ تخصصی با Heat کمتر، اما حقوق بالا."},
}
TACTIC_ORDER=("silent","balanced","aggressive")
TACTICS={
 "silent":{"name":"سایه خاموش","icon":"🥷","chance":3,"cash_mult":.90,"heat_mult":.78,"fatigue_mult":.90,"skill":"stealth","description":"رد کمتر و نفوذ بهتر؛ غنیمت پایین‌تر."},
 "balanced":{"name":"تیم حساب‌شده","icon":"♟️","chance":0,"cash_mult":1.0,"heat_mult":1.0,"fatigue_mult":1.0,"skill":None,"description":"بدون نقطه ضعف آشکار؛ پاداش و خطر متعادل."},
 "aggressive":{"name":"پنجه آهنی","icon":"💥","chance":-2,"cash_mult":1.16,"heat_mult":1.28,"fatigue_mult":1.25,"skill":"force","description":"غنیمت بیشتر؛ Heat، خستگی و جراحت بالاتر."},
}

def npc(key):return NPCS.get(str(key or ""))
def tactic(key):return TACTICS.get(str(key or ""),TACTICS["balanced"])
def salary(key,level=1):
 n=npc(key);return round(int(n["salary"])*(1+max(0,int(level)-1)*.18)) if n else 0
def training_cost(key,level=1):
 n=npc(key);return round(int(n["train_cost"])*(1+max(0,int(level)-1)*.30)) if n else 0

def member_score(level:int,loyalty:int,fatigue:int,available:bool=True):
 if not available:return 0.0
 level_factor=.75+min(MAX_LEVEL,max(1,int(level)))*.05
 loyalty_factor=.45+max(0,min(LOYALTY_MAX,int(loyalty)))*.0055
 fatigue_factor=1-max(0,min(FATIGUE_MAX,int(fatigue)))*.006
 return round(max(.15,min(1.35,level_factor*loyalty_factor*fatigue_factor)),3)

def team_analysis(members:list[dict],tactic_key="balanced"):
 active=[m for m in members if m.get("available",True) and not m.get("deserted",False)]
 scores=[member_score(m.get("level",1),m.get("loyalty",100),m.get("fatigue",0),True) for m in active]
 base=sum(scores)/len(scores) if scores else 0.0
 classes={npc(m.get("key"))["class"] for m in active if npc(m.get("key"))}
 diversity=min(3,len(classes))*0.04
 medic=any(m.get("key")=="medic" for m in active)
 effectiveness=round(min(1.35,base+diversity),3)
 t=tactic(tactic_key)
 return {"effectiveness":effectiveness,"active_count":len(active),"diversity_bonus":round(diversity,2),"medic":medic,"tactic":t,
         "chance_bonus":round(float(t["chance"])*effectiveness,2),"cash_mult":round(1+(float(t["cash_mult"])-1)*effectiveness,3),
         "heat_mult":round(1+(float(t["heat_mult"])-1)*effectiveness,3),"fatigue_mult":float(t["fatigue_mult"])*(.75 if medic else 1.0)}

def skill_bonus(members:list[dict],skill:str,tactic_key="balanced"):
 analysis=team_analysis(members,tactic_key);total=0.0
 for m in members:
  n=npc(m.get("key"))
  if n and skill in n["skills"] and m.get("available",True) and not m.get("deserted",False):
   total+=5*member_score(m.get("level",1),m.get("loyalty",100),m.get("fatigue",0),True)
 t=tactic(tactic_key)
 if t.get("skill")==skill:total+=4*analysis["effectiveness"]
 return round(min(18,total),2)

def betrayal_chance(loyalty:int,unpaid_cycles:int,risk:float):
 return round(max(0,min(45,(35-int(loyalty))*1.1+int(unpaid_cycles)*8+float(risk)*20)),2)

# Extend the original hiring shop without breaking old keys/effects.
_EXTRA={
 "hacker":{"name":"هکر سیاه","icon":"💻","cost":2_100_000_000,"required_influence":900,"description":"+فناوری در تیم فعال"},
 "medic":{"name":"پزشک زیرزمینی","icon":"🩺","cost":1_850_000_000,"required_influence":700,"description":"کاهش خستگی و جراحت تیم فعال"},
 "enforcer":{"name":"محافظ سنگین","icon":"🛡️","cost":2_450_000_000,"required_influence":1100,"description":"+جسارت در تیم فعال"},
 "ghost":{"name":"شبح نفوذی","icon":"👤","cost":3_200_000_000,"required_influence":1600,"description":"+نفوذ و Heat کمتر در تیم فعال","heat_mult":.88},
}
D.RECRUITS.update(_EXTRA)
D.RECRUIT_ORDER=NPC_ORDER
