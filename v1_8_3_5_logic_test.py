# -*- coding: utf-8 -*-
"""Stage 87.6 / v1.8.3.5 smuggling and optional P2P market tests."""
from __future__ import annotations
import ast,sys
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_smuggling as S
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,3,5)
assert D.ACCESS_LEVEL==35 and len(S.GOOD_ORDER)==6 and len(S.PACK_ORDER)==3 and len(S.ROUTE_ORDER)==3 and len(S.DEST_ORDER)==4
assert S.capacity(1)==30<S.capacity(8) and S.WAREHOUSE_MAX_LEVEL==8
# Packaging and route create meaningful trade-offs.
base=S.plan('chip',5,'cheap','mixed','port',level=40,heat=20,team_effectiveness=1)
secure=S.plan('chip',5,'secure','mixed','port',level=40,heat=20,team_effectiveness=1)
ghost=S.plan('chip',5,'ghost','mixed','port',level=40,heat=20,team_effectiveness=1)
assert ghost['chance']>secure['chance']>base['chance'] and ghost['pack_cost']>secure['pack_cost']>base['pack_cost'] and ghost['heat']<=secure['heat']<=base['heat']
safe=S.plan('arms',5,'secure','safe','border',level=40,heat=20,team_effectiveness=1)
fast=S.plan('arms',5,'secure','fast','border',level=40,heat=20,team_effectiveness=1)
assert safe['chance']>fast['chance'] and safe['payout']<fast['payout'] and safe['duration']>fast['duration'] and safe['heat']<fast['heat']
# Destination/category matching and rotating daily demand reward informed routing.
d0=date(2026,9,3);d1=d0+timedelta(days=1)
assert S.demand_destination(d0)!=S.demand_destination(d1)
fav=S.DESTINATIONS['port']['fav'];fav_good=next(k for k,v in S.GOODS.items() if v['category']==fav);other=next(k for k,v in S.GOODS.items() if v['category']!=fav)
assert S.plan(fav_good,2,'secure','mixed','port')['payout']/S.GOODS[fav_good]['base'] > S.plan(other,2,'secure','mixed','port')['payout']/S.GOODS[other]['base']
# Hidden roll is deterministic once stored.
win=S.resolve(base,0);lose=S.resolve(base,99.99)
assert win['success'] and win['cash']>lose['cash'] and not lose['success'] and lose['lost_qty']==5
assert S.resolve(base,0)==win
# Supply/demand reference and seller tiers respond in the right direction.
scarce=S.market_reference('chip',supply=5,demand=50);balanced=S.market_reference('chip',20,20);glut=S.market_reference('chip',50,5)
assert scarce>balanced>glut and S.market_label(5,50)=='تقاضای سنگین' and S.market_label(50,5)=='عرضه سنگین'
assert S.listing_price(balanced,'low')<S.listing_price(balanced,'fair')<S.listing_price(balanced,'high')
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_smuggling_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_smuggling.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_smuggling_menu.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_smuggling_profiles','dark_world_smuggling_inventory','dark_world_shipments','dark_world_market_offers','dark_world_market_trades'):assert table in model
for field in ('warehouse_level','chance_bp','roll_bp','result_success','remaining_qty','price_per_unit','seller_id','buyer_id'):assert field in model
# Direct supplier proves market is auxiliary, while player trades are atomic and escrow goods in listings.
assert 'buy_system' in service and 'خرید مستقیم از تأمین‌کننده سیستم' in handler
assert 'row.qty=int(row.qty or 0)-q' in service
assert 'DarkWorldMarketOffer.remaining_qty>=q' in service and 'result.rowcount!=1' in service
assert 'int(o.seller_id)==int(uid)' in service and 'MARKET_FEE_PCT' in service
assert 'market_reference' in service and 'func.sum(DarkWorldMarketTrade.qty)' in service
# Shipment result, amount and route are fixed at start; active NPC team participates.
assert 'secrets.randbelow(10_000)' in service and 'result_success=out["success"]' in service and 'roll_bp=roll' in service
assert 'team_context' in service and 'apply_mission_wear' in service and 'D.operation_locked' in service
assert 'from app.handlers import dark_world_smuggling' in bot and 'include_router(dark_world_smuggling.router)' in bot
for route in ('smg:hub','smg:stock','smg:buy:','smg:goods','smg:qty:','smg:pack:','smg:route:','smg:dest:','smg:prev:','smg:start:','smg:active','smg:upgrade','smg:market','smg:pulse','smg:offers','smg:sellgoods','smg:list:','smg:take:'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[]
for g in S.GOOD_ORDER:
 for p in S.PACK_ORDER:
  for r in S.ROUTE_ORDER:
   for d in S.DEST_ORDER:callbacks.append(f'smg:start:{g}:20:{p}:{r}:{d}:{uid}')
assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: six goods, three packages, three routes and four destinations')
print('OK: route/category/daily-demand strategy and persisted hidden outcomes')
print('OK: optional P2P market with dynamic supply/demand reference')
print('OK: atomic purchases, seller escrow, capacity, fee and self-trade guard')
print('OK: direct system supplier keeps player market auxiliary, not mandatory')
print(f'OK: {len(files)} Python files parsed')
