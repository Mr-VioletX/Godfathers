# -*- coding: utf-8 -*-
"""Stage 87.8 — multiplayer raids and information warfare."""
from __future__ import annotations
FORMING_SECONDS=600
RECON_TTL_HOURS=2
PAIR_COOLDOWN_HOURS=12
DAILY_RAID_LIMIT=3
STAKE=100_000_000
SUPPORT_INTEL_COST=5
RECON_INTEL_COST=8
MAX_SUPPORTERS_PER_SIDE=2
APPROACH_ORDER=("infiltrate","cyber","assault")
APPROACHES={
 "infiltrate":{"name":"نفوذ خاموش","icon":"🥷","heat":7,"beats":"decoy","clue":"شکستن لایه‌های فریب با حرکت انسانی."},
 "cyber":{"name":"محاصره سیگنال","icon":"📡","heat":10,"beats":"fortify","clue":"خاموش‌کردن سامانه‌های دفاعی و قفل‌ها."},
 "assault":{"name":"ضربه برق‌آسا","icon":"💥","heat":17,"beats":"counter","clue":"فشار مستقیم پیش از واکنش ضدجاسوسی."},
}
DEFENSE_ORDER=("decoy","fortify","counter")
DEFENSES={
 "decoy":{"name":"انبار طعمه","icon":"🎭","beats":"cyber","integrity":0,"clue":"رفت‌وآمدهای تکراری به چند نقطه ساختگی دیده می‌شود."},
 "fortify":{"name":"قلعه شبانه","icon":"🧱","beats":"assault","integrity":8,"clue":"ورودی‌ها تقویت شده و نگهبان‌ها آشکارا جابه‌جا می‌شوند."},
 "counter":{"name":"ضدجاسوسی","icon":"🕵️","beats":"infiltrate","integrity":2,"clue":"پیام‌های جعلی برای شکار نفوذی‌ها در شبکه پخش شده است."},
}
def matchup(approach,defense):
 if APPROACHES.get(approach,{}).get("beats")==defense:return 18
 if DEFENSES.get(defense,{}).get("beats")==approach:return -18
 return 0
def chance(approach,defense,*,attacker_level,defender_level,attacker_influence,defender_influence,hideout_level,hideout_integrity,attack_team=0,defense_team=0,attack_support=0,defense_support=0,recon_truth=True):
 value=50+matchup(approach,defense)+(int(attacker_level)-int(defender_level))*.8+(int(attacker_influence)-int(defender_influence))/100
 value+=float(attack_team)*5-float(defense_team)*5+int(attack_support)*5-int(defense_support)*5+(4 if recon_truth else -4)
 value-=max(0,int(hideout_level)-1)*2+max(0,int(hideout_integrity)-50)*.10+DEFENSES[defense]["integrity"]
 return round(max(8,min(92,value)),2)
def resolve(chance_pct,roll,stake,target_dirty):
 ok=float(roll)<float(chance_pct);steal=min(250_000_000,max(0,round(int(target_dirty)*.10))) if ok else 0
 return {"success":ok,"stolen":steal,"stake_refund":int(stake) if ok else 0,"defense_pool":0 if ok else round(int(stake)*.70),"burned":0 if ok else int(stake)-round(int(stake)*.70)}
