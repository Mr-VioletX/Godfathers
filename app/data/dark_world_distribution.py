# -*- coding: utf-8 -*-
"""Stage 87.13 — fictional customer, district and distribution simulation."""
from __future__ import annotations
DISTRICT_ORDER=("oldtown","neon","harbor","heights","industrial","undercity")
DISTRICTS={
 "oldtown":{"name":"شهر قدیم","icon":"🏚️","signature":"dream","wealth":.92,"enforcement":8},
 "neon":{"name":"محله نئون","icon":"🌃","signature":"pulse","wealth":1.18,"enforcement":14},
 "harbor":{"name":"بندر خاموش","icon":"⚓","signature":"frost","wealth":1.05,"enforcement":11},
 "heights":{"name":"ارتفاعات شیشه‌ای","icon":"🏙️","signature":"solar","wealth":1.42,"enforcement":19},
 "industrial":{"name":"کمربند صنعتی","icon":"🏭","signature":"void","wealth":1.12,"enforcement":16},
 "undercity":{"name":"زیرشهر","icon":"🕳️","signature":"dream","wealth":.82,"enforcement":5},
}
CHANNEL_ORDER=("direct","dealer","wholesale")
CHANNELS={
 "direct":{"name":"فروش مستقیم","icon":"🤝","qty":1,"price":1.30,"chance":-5,"heat":7,"duration":900},
 "dealer":{"name":"توزیع‌کننده NPC","icon":"🧥","qty":2,"price":1.05,"chance":5,"heat":4,"duration":1500},
 "wholesale":{"name":"عمده‌فروش","icon":"📦","qty":4,"price":.82,"chance":12,"heat":2,"duration":2400},
}
SCREEN_ORDER=("fast","verify","reference")
SCREENS={
 "fast":{"name":"معامله سریع","icon":"⚡","chance":4,"price":1.06,"undercover":-18,"duration":.75},
 "verify":{"name":"بررسی هویت","icon":"🔎","chance":2,"price":.96,"undercover":8,"duration":1.2},
 "reference":{"name":"معرف معتبر","icon":"🛡️","chance":8,"price":.90,"undercover":18,"duration":1.5},
}
CUSTOMERS=("regular","vip","collector","undercover")
CUSTOMER_NAMES={"regular":"مشتری محلی","vip":"مشتری ویژه","collector":"کلکسیونر","undercover":"خریدار مشکوک"}
def undercover_pct(district,trace):return max(3,min(45,DISTRICTS[district]['enforcement']+max(0,int(trace)-30)//4))
def customer(district,trace,roll):
 u=undercover_pct(district,trace)
 if int(roll)<u:return "undercover"
 if int(roll)<u+15:return "collector"
 if int(roll)<u+35:return "vip"
 return "regular"
def plan(recipe,quality,power,stability,district,channel,screen,reputation,trace,team_effectiveness=0):
 d=DISTRICTS[district];c=CHANNELS[channel];s=SCREENS[screen];fit=14 if recipe.signature_key==d['signature'] else -3;base=58+c['chance']+s['chance']+fit+min(10,int(reputation)//10)+float(team_effectiveness)*4-max(0,int(trace)-40)*.15-d['enforcement']*.35
 chance=max(8,min(95,base));value=round(int(recipe.value)*int(c['qty'])*d['wealth']*c['price']*s['price']*(1+int(quality)/500+int(power)/700+int(stability)/900));duration=round(c['duration']*s['duration']);return {"chance":round(chance,2),"value":value,"qty":c['qty'],"duration":duration,"heat":c['heat']+d['enforcement']//6,"fit":fit>0}
def resolve(plan,customer_key,screen_key,roll):
 chance=float(plan['chance']);caught=False
 if customer_key=="undercover":chance+=SCREENS[screen_key]['undercover'];caught=float(roll)>=chance
 elif customer_key=="vip":chance+=5
 elif customer_key=="collector":chance+=8
 ok=float(roll)<max(5,min(97,chance));mult=1.25 if customer_key=='collector' else 1.15 if customer_key=='vip' else 1.0
 return {"success":ok,"payout":round(plan['value']*mult) if ok else 0,"caught":caught,"heat":plan['heat']+(14 if caught else 5 if not ok else 0),"rep":4 if ok else -6}
