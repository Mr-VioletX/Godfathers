# -*- coding: utf-8 -*-
"""Stage 87.6 — smuggling chain plus optional player supply/demand market."""
from __future__ import annotations
from datetime import date

WAREHOUSE_BASE_CAPACITY=30
WAREHOUSE_MAX_LEVEL=8
MARKET_FEE_PCT=2
OFFER_TTL_HOURS=48
SHIPMENT_MIN_QTY=1
SHIPMENT_MAX_QTY=20

GOOD_ORDER=("med","chip","art","docs","arms","lux")
GOODS={
 "med":{"name":"داروی کمیاب","icon":"💊","base":8_000_000,"category":"medical","heat":2},
 "chip":{"name":"تراشه رمزگذاری","icon":"💾","base":15_000_000,"category":"tech","heat":3},
 "art":{"name":"اثر هنری بی‌نام","icon":"🖼️","base":28_000_000,"category":"luxury","heat":4},
 "docs":{"name":"مدارک جعلی","icon":"📄","base":12_000_000,"category":"documents","heat":3},
 "arms":{"name":"تسلیحات سبک","icon":"🔫","base":22_000_000,"category":"arms","heat":6},
 "lux":{"name":"کالای لوکس ممنوعه","icon":"💎","base":35_000_000,"category":"luxury","heat":5},
}
PACK_ORDER=("cheap","secure","ghost")
PACKS={
 "cheap":{"name":"بسته‌بندی عادی","icon":"📦","cost_pct":3,"chance":0,"quality":0,"capacity_mult":1.0,"heat_mult":1.15},
 "secure":{"name":"پوشش تقویت‌شده","icon":"🧰","cost_pct":8,"chance":8,"quality":5,"capacity_mult":.9,"heat_mult":.85},
 "ghost":{"name":"محموله پوششی","icon":"🎭","cost_pct":15,"chance":15,"quality":10,"capacity_mult":.75,"heat_mult":.60},
}
ROUTE_ORDER=("safe","mixed","fast")
ROUTES={
 "safe":{"name":"مسیر کور","icon":"🥷","chance":12,"cash_mult":.88,"duration":3600,"heat_mult":.70},
 "mixed":{"name":"مسیر چندلایه","icon":"♟️","chance":2,"cash_mult":1.0,"duration":2400,"heat_mult":1.0},
 "fast":{"name":"شاهراه قرمز","icon":"💥","chance":-12,"cash_mult":1.35,"duration":1200,"heat_mult":1.45},
}
DEST_ORDER=("north","port","border","islands")
DESTINATIONS={
 "north":{"name":"حلقه شمال","icon":"🏙️","risk":0,"mult":1.05,"fav":"medical"},
 "port":{"name":"بندر سایه","icon":"⚓","risk":5,"mult":1.15,"fav":"tech"},
 "border":{"name":"مرز خاکستری","icon":"🛣️","risk":10,"mult":1.28,"fav":"arms"},
 "islands":{"name":"جزایر آزاد","icon":"🏝️","risk":14,"mult":1.42,"fav":"luxury"},
}

def good(k):return GOODS.get(str(k or ""))
def capacity(level):return WAREHOUSE_BASE_CAPACITY+(max(1,min(WAREHOUSE_MAX_LEVEL,int(level)))-1)*20
def upgrade_cost(level):return 180_000_000*max(1,int(level))**2
def demand_destination(day=None):
 day=day or date.today();return DEST_ORDER[day.toordinal()%len(DEST_ORDER)]
def demand_category(day=None):return DESTINATIONS[demand_destination(day)]["fav"]
def system_buy_price(key):return int(good(key)["base"])
def plan(good_key,qty,pack_key,route_key,dest_key,*,level=35,heat=0,team_effectiveness=0,team_tactic="balanced"):
 g=good(good_key);p=PACKS.get(pack_key);r=ROUTES.get(route_key);d=DESTINATIONS.get(dest_key);q=max(SHIPMENT_MIN_QTY,min(SHIPMENT_MAX_QTY,int(qty)))
 if not all((g,p,r,d)):return {}
 cap_need=q;effective_cap=max(1,int(capacity(1)*p["capacity_mult"]))
 team_bonus=min(9,max(0,float(team_effectiveness))*5);tactic=3 if team_tactic=="silent" else (-3 if team_tactic=="aggressive" else 0)
 chance=max(12,min(95,76+p["chance"]+r["chance"]-d["risk"]+max(0,min(10,int(level)-35))*.7+team_bonus+tactic-max(0,int(heat)-40)*.12-g["heat"]*.7))
 value=g["base"]*q;pack_cost=round(value*p["cost_pct"]/100);fav=1.18 if g["category"]==d["fav"] else 1.0;daily=1.12 if dest_key==demand_destination() else 1.0
 payout=round(value*d["mult"]*r["cash_mult"]*fav*daily*(1+p["quality"]/100))
 heat=max(1,round(g["heat"]*q**.55*r["heat_mult"]*p["heat_mult"]))
 return {"good_key":good_key,"qty":q,"pack_key":pack_key,"route_key":route_key,"dest_key":dest_key,"chance":round(chance,2),"pack_cost":pack_cost,"payout":payout,"duration":r["duration"],"heat":heat,"capacity_need":cap_need,"effective_pack_capacity":effective_cap}
def resolve(plan,roll):
 ok=float(roll)<float(plan["chance"])
 return {"success":ok,"cash":int(plan["payout"] if ok else round(plan["payout"]*.08)),"heat":int(plan["heat"] if ok else plan["heat"]+8),"lost_qty":0 if ok else int(plan["qty"])}
def market_reference(key,supply:int,demand:int):
 base=good(key)["base"];pressure=(int(demand)-int(supply))/max(10,int(demand)+int(supply));return round(base*max(.70,min(1.40,1+pressure*.45)))
def market_label(supply,demand):
 return "تقاضای سنگین" if demand>supply*1.5 else "عرضه سنگین" if supply>demand*1.5 else "متعادل"
def listing_price(reference,tier):return round(int(reference)*{"low":.90,"fair":1.0,"high":1.12}.get(tier,1.0))
