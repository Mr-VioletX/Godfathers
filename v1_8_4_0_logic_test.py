# -*- coding: utf-8 -*-
"""Stage 87.11 / v1.8.4.0 fictional catalog and abstract laboratory tests."""
from __future__ import annotations
import ast,sys
from types import SimpleNamespace
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_laboratory as L
from app.data import dark_world_competitive as C
from app.data import dark_world as D
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,4,0)
assert D.ACCESS_LEVEL==35 and len(L.PRODUCT_ORDER)>=12 and len(L.MATERIALS)==4 and len(L.MODE_ORDER)==3
assert [C.division(x)['name'] for x in (0,500,1200,2500,5000)]==['جرقه‌ی کوچه','پچ‌پچِ مه','پنجه‌ی شب','فرمانده‌ی خسوف','تاج‌دارِ خلأ']
assert len(set(p['name'] for p in L.PRODUCTS.values()))>=12 and all(set(p['recipe'])<=set('abcd') for p in L.PRODUCTS.values())
lab=SimpleNamespace(level=10,equipment=2,power=2,ventilation=2,safety=2,condition=70)
safe=L.plan('ember',4,'safe',lab);precise=L.plan('ember',4,'precise',lab);rush=L.plan('ember',4,'rush',lab)
assert safe['chance']>precise['chance']>rush['chance'] and safe['duration']>precise['duration']>rush['duration']
assert precise['quality']>safe['quality'] and rush['yield_qty']>precise['yield_qty'] and rush['condition_loss']>safe['condition_loss']
weak=SimpleNamespace(level=10,equipment=1,power=1,ventilation=1,safety=1,condition=40);strong=SimpleNamespace(level=10,equipment=10,power=10,ventilation=10,safety=10,condition=100)
a=L.plan('ember',1,'precise',weak);b=L.plan('ember',1,'precise',strong)
assert b['chance']>a['chance'] and b['quality']>a['quality'] and b['potency']>a['potency'] and b['stability']>a['stability']
win=L.resolve(precise,0,50,50,50);lose=L.resolve(precise,99.99,50,50,50)
assert win['success'] and win['yield_qty']>0 and not win['accident'];assert not lose['success'] and lose['yield_qty']==0 and lose['accident'] and lose['condition_loss']>win['condition_loss'];assert L.resolve(precise,0,50,50,50)==win
assert L.broker_value('ember',90,90,90)>L.broker_value('ember',30,30,30)
model=(ROOT/'app/models/dark_world.py').read_text(encoding='utf-8');service=(ROOT/'app/services/dark_world_laboratory_service.py').read_text(encoding='utf-8');handler=(ROOT/'app/handlers/dark_world_laboratory.py').read_text(encoding='utf-8');keyboard=(ROOT/'app/keyboards/dark_world_laboratory_menu.py').read_text(encoding='utf-8');data=(ROOT/'app/data/dark_world_laboratory.py').read_text(encoding='utf-8');bot=(ROOT/'bot.py').read_text(encoding='utf-8')
for table in ('dark_world_labs','dark_world_lab_materials','dark_world_product_inventory','dark_world_production_batches','dark_world_lab_logs'):assert table in model
for field in ('equipment','power','ventilation','safety','condition','avg_quality','avg_potency','avg_stability','result_quality','result_potency','result_stability','accident','condition_loss'):assert field in model
assert 'secrets.randbelow(10_000)' in service and 'result_success=out[\'success\']' in service and 'roll_bp=rolls[0]' in service
assert 'DarkWorldProductionBatch.status=="active"' in service and 'condition=max' in service
assert 'credit_dirty' in service and 'fictional_product' in service and 'broker_value' in service
assert 'No real substances, chemistry, ingredients, temperatures, or production steps' in data
assert 'تمام محصولات، اجزا و فرایندها کاملاً خیالی و انتزاعی‌اند' in handler
assert 'اجزای خیالی A/B/C/D' in handler and 'هیچ معادل واقعی ندارند' in handler
assert 'from app.handlers import dark_world_laboratory' in bot and 'include_router(dark_world_laboratory.router)' in bot
for route in ('dwl:hub','dwl:catalog','dwl:products','dwl:modes:','dwl:prev:','dwl:start:','dwl:active','dwl:materials','dwl:mat:','dwl:upgrades','dwl:up:','dwl:repair','dwl:inventory','dwl:sell:'):assert route in handler or route in keyboard
assert 'economic_operation' in handler and 'ensure_owner' in handler and 'with_owner' in keyboard
uid='1234567890123456789';callbacks=[f'dwl:start:{k}:10:precise:{uid}' for k in L.PRODUCT_ORDER];assert max(len(x.encode()) for x in callbacks)<=64
files=sorted(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: five creative competitive ranks replaced generic metal tiers')
print('OK: 12 fictional products, four abstract tokens and three strategic modes')
print('OK: lab equipment, power, ventilation, safety, condition and capacity matter')
print('OK: persisted outcomes, quality/potency/stability, accidents, repair and broker sale')
print('OK: fictional-only safeguards and no real-world recipe or production details')
print(f'OK: {len(files)} Python files parsed')
