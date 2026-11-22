# -*- coding: utf-8 -*-
"""Stage 87.6 — shipment chain and optional atomic player commodity market."""
from __future__ import annotations
import secrets
from datetime import datetime,timedelta
from sqlalchemy import select,update,func
from app.data import dark_world as D
from app.data import dark_world_smuggling as S
from app.models.dark_world import DarkWorldSmugglingProfile,DarkWorldSmugglingInventory,DarkWorldShipment,DarkWorldMarketOffer,DarkWorldMarketTrade
from app.services import dark_world_service as DS

def now():return datetime.utcnow()
async def profile(session,uid,create=True):
 row=await session.get(DarkWorldSmugglingProfile,int(uid))
 if row is None and create:row=DarkWorldSmugglingProfile(owner_id=int(uid),warehouse_level=1);session.add(row);await session.flush()
 return row
async def invrow(session,uid,key,create=False):
 row=(await session.execute(select(DarkWorldSmugglingInventory).where(DarkWorldSmugglingInventory.owner_id==int(uid),DarkWorldSmugglingInventory.good_key==key))).scalar_one_or_none()
 if row is None and create:row=DarkWorldSmugglingInventory(owner_id=int(uid),good_key=key,qty=0,cost_basis=0);session.add(row);await session.flush()
 return row
async def inventory(session,uid):return {r.good_key:int(r.qty or 0) for r in (await session.execute(select(DarkWorldSmugglingInventory).where(DarkWorldSmugglingInventory.owner_id==int(uid)))).scalars()}
async def total_inventory(session,uid):return sum((await inventory(session,uid)).values())
async def active(session,uid):return (await session.execute(select(DarkWorldShipment).where(DarkWorldShipment.owner_id==int(uid),DarkWorldShipment.status=="active").order_by(DarkWorldShipment.id.desc()))).scalar_one_or_none()
async def snapshot(session,uid):
 player=await DS.get_player(session,uid);blocked=DS.access_message(player)
 if blocked:return False,blocked,{}
 p=await profile(session,uid);i=await inventory(session,uid);a=await active(session,uid);dw=await DS.get_profile(session,uid,create=True);DS.apply_recovery(dw)
 return True,"ok",{"player":player,"profile":p,"inventory":i,"active":a,"dark":dw,"used":sum(i.values()),"capacity":S.capacity(p.warehouse_level)}
async def buy_system(session,uid,key,qty):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 g=S.good(key);q=max(1,min(20,int(qty)))
 if not g:return False,"کالای نامعتبر است."
 if s["used"]+q>s["capacity"]:return False,"ظرفیت انبار مخفی کافی نیست."
 market=await pulse(session)
 unit=max(S.system_buy_price(key),round(market[key]["reference"]*1.05))
 cost=unit*q
 if int(s["player"].cash or 0)<cost:return False,f"برای خرید {cost:,} پول لازم است."
 row=await invrow(session,uid,key,True);old=int(row.qty or 0);row.cost_basis=round((int(row.cost_basis or 0)*old+cost)/(old+q));row.qty=old+q;s["player"].cash=int(s["player"].cash or 0)-cost
 await session.commit();return True,f"✅ {q} واحد {g['name']} به قیمت {cost:,} وارد انبار شد."
async def preview(session,uid,g,q,p,r,d):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg,{}
 if s["active"]:return False,"یک محموله فعال داری.",{}
 if int(s["inventory"].get(g,0))<int(q):return False,"موجودی کالا کافی نیست.",{}
 if D.operation_locked(s["dark"].heat):return False,"Heat روی تعقیب سراسری است؛ ابتدا تهدید را خنثی کن.",{}
 from app.services import dark_world_npc_service as NS
 team=await NS.team_context(session,uid);plan=S.plan(g,q,p,r,d,level=int(s["player"].level or 1),heat=int(s["dark"].heat or 0),team_effectiveness=team["effectiveness"],team_tactic=team["tactic"])
 if not plan:return False,"طرح محموله نامعتبر است.",{}
 from app.services import dark_world_seasons_service as SES
 mods=await SES.modifiers(session,uid);plan["payout"]=round(int(plan["payout"])*(100+mods["market_pct"])/100);plan["season_market_pct"]=mods["market_pct"]
 plan.update({"cash":int(s["player"].cash or 0),"owned":int(s["inventory"].get(g,0)),"capacity":s["capacity"],"team":team});return int(s["player"].cash or 0)>=plan["pack_cost"],"ok" if int(s["player"].cash or 0)>=plan["pack_cost"] else "هزینه بسته‌بندی کافی نیست.",plan
async def start_shipment(session,uid,g,q,p,r,d):
 ready,msg,plan=await preview(session,uid,g,q,p,r,d)
 if not ready:return False,msg
 player=await DS.get_player(session,uid);dw=await DS.get_profile(session,uid,True);row=await invrow(session,uid,g);row.qty=int(row.qty or 0)-int(plan["qty"]);player.cash=int(player.cash or 0)-int(plan["pack_cost"])
 roll=secrets.randbelow(10_000);out=S.resolve(plan,roll/100);t=now();ship=DarkWorldShipment(owner_id=int(uid),good_key=g,qty=int(plan["qty"]),pack_key=p,route_key=r,dest_key=d,status="active",chance_bp=int(round(plan["chance"]*100)),roll_bp=roll,result_success=out["success"],result_cash=out["cash"],result_heat=out["heat"],started_at=t,ready_at=t+timedelta(seconds=int(plan["duration"])))
 session.add(ship);await session.commit();return True,"محموله حرکت کرد؛ نتیجه همین حالا مخفی و پایدار ثبت شد."
async def collect(session,uid):
 ship=await active(session,uid)
 if not ship:return False,"محموله فعالی نداری."
 remain=max(0,int((ship.ready_at-now()).total_seconds()))
 if remain:return False,f"هنوز {remain//60+1} دقیقه مانده."
 player=await DS.get_player(session,uid);dw=await DS.get_profile(session,uid,True);from app.services import dark_world_finance_service as FS
 await FS.credit_dirty(session,uid,int(ship.result_cash or 0),"shipment");dw.heat=min(100,int(dw.heat or 0)+int(ship.result_heat or 0));ship.status="completed" if ship.result_success else "failed";ship.completed_at=now()
 p=await profile(session,uid);p.shipments=int(p.shipments or 0)+1;p.cash_earned=int(p.cash_earned or 0)+int(ship.result_cash or 0);p.successes=int(p.successes or 0)+(1 if ship.result_success else 0)
 from app.services import dark_world_npc_service as NS
 note=await NS.apply_mission_wear(session,uid,3 if ship.route_key!="fast" else 4,bool(ship.result_success));await session.commit();return True,("✅ محموله رسید." if ship.result_success else "❌ محموله از دست رفت.")+f"\n🌑 پول کثیف دریافتی: {int(ship.result_cash):,}\n🚨 Heat: +{int(ship.result_heat)}"+note
async def upgrade(session,uid):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg
 level=int(s["profile"].warehouse_level or 1)
 if level>=S.WAREHOUSE_MAX_LEVEL:return False,"انبار در بالاترین سطح است."
 cost=S.upgrade_cost(level)
 if int(s["player"].cash or 0)<cost:return False,f"هزینه ارتقا {cost:,} است."
 s["player"].cash=int(s["player"].cash or 0)-cost;s["profile"].warehouse_level=level+1;await session.commit();return True,f"انبار به سطح {level+1} و ظرفیت {S.capacity(level+1)} رسید."
async def cleanup_offers(session):
 rows=list((await session.execute(select(DarkWorldMarketOffer).where(DarkWorldMarketOffer.status=="open",DarkWorldMarketOffer.expires_at<=now()))).scalars())
 for o in rows:
  inv=await invrow(session,o.seller_id,o.good_key,True);inv.qty=int(inv.qty or 0)+int(o.remaining_qty or 0);o.remaining_qty=0;o.status="expired"
 return len(rows)
async def pulse(session):
 await cleanup_offers(session);since=now()-timedelta(hours=24);out={}
 for k in S.GOOD_ORDER:
  supply=(await session.execute(select(func.coalesce(func.sum(DarkWorldMarketOffer.remaining_qty),0)).where(DarkWorldMarketOffer.good_key==k,DarkWorldMarketOffer.status=="open"))).scalar() or 0
  demand=(await session.execute(select(func.coalesce(func.sum(DarkWorldMarketTrade.qty),0)).where(DarkWorldMarketTrade.good_key==k,DarkWorldMarketTrade.created_at>=since))).scalar() or 0
  ref=S.market_reference(k,int(supply),int(demand));out[k]={"supply":int(supply),"demand":int(demand),"reference":ref,"label":S.market_label(int(supply),int(demand))}
 return out
async def offers(session,uid):
 await cleanup_offers(session);return list((await session.execute(select(DarkWorldMarketOffer).where(DarkWorldMarketOffer.status=="open",DarkWorldMarketOffer.remaining_qty>0,DarkWorldMarketOffer.seller_id!=int(uid)).order_by(DarkWorldMarketOffer.price_per_unit,DarkWorldMarketOffer.created_at).limit(15))).scalars())
async def list_offer(session,uid,key,qty,tier):
 ok,msg,s=await snapshot(session,uid)
 if not ok:return False,msg,None
 q=max(1,min(20,int(qty)));row=await invrow(session,uid,key)
 if not row or int(row.qty or 0)<q:return False,"موجودی کافی برای عرضه نداری.",None
 data=await pulse(session);price=S.listing_price(data[key]["reference"],tier);row.qty=int(row.qty or 0)-q;o=DarkWorldMarketOffer(seller_id=int(uid),good_key=key,total_qty=q,remaining_qty=q,price_per_unit=price,status="open",expires_at=now()+timedelta(hours=S.OFFER_TTL_HOURS));session.add(o);await session.flush();await session.commit();return True,f"عرضه #{o.id} ثبت شد: {q} واحد، هر واحد {price:,}.",o
async def buy_offer(session,uid,offer_id,qty=1):
 buyer=await DS.get_player(session,uid);blocked=DS.access_message(buyer)
 if blocked:return False,blocked
 o=await session.get(DarkWorldMarketOffer,int(offer_id));q=max(1,int(qty))
 if not o or o.status!="open" or int(o.remaining_qty or 0)<q:return False,"این عرضه دیگر موجود نیست."
 if int(o.seller_id)==int(uid):return False,"خرید عرضه خودت ممنوع است."
 p=await profile(session,uid);used=await total_inventory(session,uid)
 if used+q>S.capacity(p.warehouse_level):return False,"ظرفیت انبار کافی نیست."
 total=int(o.price_per_unit)*q
 if int(buyer.cash or 0)<total:return False,"پول کافی نداری."
 result=await session.execute(update(DarkWorldMarketOffer).where(DarkWorldMarketOffer.id==int(offer_id),DarkWorldMarketOffer.status=="open",DarkWorldMarketOffer.remaining_qty>=q).values(remaining_qty=DarkWorldMarketOffer.remaining_qty-q))
 if result.rowcount!=1:await session.rollback();return False,"خریدار دیگری زودتر این مقدار را خرید."
 seller=await DS.get_player(session,o.seller_id);fee=round(total*S.MARKET_FEE_PCT/100);buyer.cash=int(buyer.cash or 0)-total;seller.cash=int(seller.cash or 0)+total-fee;inv=await invrow(session,uid,o.good_key,True);inv.qty=int(inv.qty or 0)+q
 await session.flush();fresh=await session.get(DarkWorldMarketOffer,int(offer_id));
 if int(fresh.remaining_qty or 0)<=0:fresh.status="filled"
 session.add(DarkWorldMarketTrade(offer_id=int(offer_id),seller_id=int(o.seller_id),buyer_id=int(uid),good_key=o.good_key,qty=q,price_per_unit=int(o.price_per_unit),fee=fee));await session.commit();return True,f"معامله انجام شد؛ {q} واحد به مبلغ {total:,} خریدی."
