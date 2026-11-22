# -*- coding: utf-8 -*-
"""Stage 87.10 — competitive scoring, divisions, boss and bounded rewards."""
from __future__ import annotations
BOSS_ENERGY_COST=15
BOSS_HIT_COOLDOWN_SECONDS=7200
MIN_RANK_ACTIVITY=3
DIVISIONS=((5000,"تاج‌دارِ خلأ","🜲"),(2500,"فرمانده‌ی خسوف","🌑"),(1200,"پنجه‌ی شب","🐈‍⬛"),(500,"پچ‌پچِ مه","🌫️"),(0,"جرقه‌ی کوچه","🕯️"))
def score(*,influence,contribution,shipments,launders,raid_wins,employment,boss_damage):
 activity=int(shipments)+int(launders)+int(raid_wins)+int(employment)
 total=min(250,max(0,int(influence))//10)+min(300,max(0,int(contribution))//2)+int(shipments)*35+int(launders)*30+int(raid_wins)*80+int(employment)*25+min(800,max(0,int(boss_damage))//10)
 return {"score":max(0,total),"activity":activity}
def division(score_value):
 for threshold,name,icon in DIVISIONS:
  if int(score_value)>=threshold:return {"key":name,"name":name,"icon":icon,"threshold":threshold}
def reward(rank,total,economy_factor=1.0):
 r=max(1,int(rank));n=max(1,int(total));pct=r/n;factor=max(.75,min(1.15,float(economy_factor)))
 if r==1:base,intel,prestige,title=1_000_000_000,60,120,"فرمانروای شب"
 elif r<=3:base,intel,prestige,title=600_000_000,40,80,"وارث سایه"
 elif pct<=.10:base,intel,prestige,title=300_000_000,25,50,"نخبه فصل"
 else:base,intel,prestige,title=80_000_000,8,20,"بازمانده فصل"
 return {"dirty":round(base*factor),"intel":intel,"prestige":prestige,"title":title}
def economy_factor(created,cleaned,confiscated,market_volume):
 source=max(1,int(created));sink=max(0,int(cleaned)+int(confiscated));pressure=(sink+int(market_volume)*.02)/source
 return round(max(.75,min(1.15,1.05-(pressure-.45)*.30)),3)
def boss_max_hp(member_count):return max(2_000,int(member_count)*700)
def boss_damage(level,team_effectiveness,roll_pct):return max(25,round(40+int(level)*3+float(team_effectiveness)*30+float(roll_pct)*.8))
