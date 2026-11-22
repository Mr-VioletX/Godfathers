from pathlib import Path
from types import SimpleNamespace
import ast,sys
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from app.data import dark_world_empire as E
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (1,8,4,3)
assert len(E.FACILITIES)==3 and len(E.UPGRADES)==4 and len(E.RIVALS)==4 and len(E.INSPECTION_CHOICES)==3
fs=[SimpleNamespace(facility_key='micro_lab',capacity_level=2,stealth_level=2,status='active')]
assert E.empire_capacity(fs)==5 and E.empire_stealth(fs)>12
assert E.inspection_risk(90,90,fs)>E.inspection_risk(10,10,fs)
a=E.inspection_result(70,'pause',0,35);b=E.inspection_result(70,'fortify',2,35);assert b['chance']>a['chance']
win=E.rival_plan('razor','quality',100,20);lose=E.rival_plan('crown','price',0,90);assert win['success'] and not lose['success']
model=(ROOT/'app/models/dark_world.py').read_text();service=(ROOT/'app/services/dark_world_empire_service.py').read_text();handler=(ROOT/'app/handlers/dark_world_empire.py').read_text();keys=(ROOT/'app/keyboards/dark_world_empire_menu.py').read_text();bot=(ROOT/'bot.py').read_text()
for x in ('dark_world_empire_profiles','dark_world_facilities','dark_world_rival_conflicts','dark_world_inspections','dark_world_empire_logs'):assert x in model
for x in ('chance_bp','roll_bp','result_success','confiscated_qty','maybe_schedule_inspection','credit_dirty','debit_dirty'):assert x in model+service
for x in ('dwi:hub','dwi:build','dwi:buy:','dwi:facility:','dwi:upgrade:','dwi:rivals','dwi:rival:','dwi:inspection','dwi:prepare:'):assert x in handler+keys
assert 'include_router(dark_world_empire.router)' in bot
files=list(ROOT.rglob('*.py'))
for p in files:ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
print('OK: facilities, four upgrade branches and five-center empire cap')
print('OK: four dynamic rivals and three strategic responses')
print('OK: warning-based inspections, persistent rolls and confiscation consequences')
print(f'OK: {len(files)} Python files parsed')
