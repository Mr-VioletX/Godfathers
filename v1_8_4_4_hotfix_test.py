from pathlib import Path
import ast
R=Path(__file__).parent
h=(R/"app/handlers/dark_world_finance.py").read_text();f=(R/"app/services/dark_world_finance_service.py").read_text()
assert "from aiogram import F,Router" in h
assert "dark_world_finance as DF" in h
assert "dark_world_finance as F" not in h
assert "@router.callback_query(F.data.startswith" in h
for x in ("DF.climate()","DF.METHODS","DF.rare_today()","DF.RARE"):assert x in h
assert "async def debit_dirty" in f and "debit:" in f
files=list(R.rglob("*.py"))
for p in files:ast.parse(p.read_text(encoding="utf-8"),filename=str(p))
print("OK: aiogram F filter is no longer shadowed by finance data")
print("OK: empire dirty-balance debit dependency exists")
print(f"OK: {len(files)} Python files parsed")
