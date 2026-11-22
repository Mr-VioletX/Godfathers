# -*- coding: utf-8 -*-
"""Stage 87.12 — combinatorial fictional recipes; no real materials or processes."""
from __future__ import annotations
import hashlib
from datetime import date
PLOT_LIMIT=3
INGREDIENT_PACK=5
BASE_ORDER=("moonleaf","prismoss","emberreed","whisperfern","starbloom")
BASES={
 "moonleaf":{"name":"برگ ماه خیالی","icon":"🌙","fragment":"ماه","grow":1800,"yield":5,"seed":28_000_000,"market":55_000_000,"power":8,"stability":12,"risk":2},
 "prismoss":{"name":"خزه منشوری خیالی","icon":"🌈","fragment":"منشور","grow":2400,"yield":6,"seed":35_000_000,"market":70_000_000,"power":5,"stability":16,"risk":1},
 "emberreed":{"name":"نی آتشین خیالی","icon":"🔥","fragment":"اخگر","grow":1500,"yield":4,"seed":32_000_000,"market":64_000_000,"power":16,"stability":4,"risk":5},
 "whisperfern":{"name":"سرخس نجوا خیالی","icon":"🌿","fragment":"نجوا","grow":3000,"yield":7,"seed":44_000_000,"market":88_000_000,"power":7,"stability":18,"risk":3},
 "starbloom":{"name":"شکوفه ستاره خیالی","icon":"✨","fragment":"ستاره","grow":3600,"yield":8,"seed":60_000_000,"market":120_000_000,"power":18,"stability":10,"risk":7},
}
CATALYST_ORDER=("echo","velvet","static","obsidian","mirage")
CATALYSTS={
 "echo":{"name":"طنین E خیالی","icon":"🔊","fragment":"پژواک","market":75_000_000,"power":8,"quality":8,"risk":2},
 "velvet":{"name":"هسته V خیالی","icon":"🪻","fragment":"مخمل","market":95_000_000,"power":4,"quality":15,"risk":1},
 "static":{"name":"جوهر S خیالی","icon":"⚡","fragment":"صاعقه","market":125_000_000,"power":17,"quality":3,"risk":8},
 "obsidian":{"name":"دانه O خیالی","icon":"🖤","fragment":"ابسیدین","market":155_000_000,"power":12,"quality":11,"risk":6},
 "mirage":{"name":"آینه M خیالی","icon":"🏜️","fragment":"سراب","market":190_000_000,"power":20,"quality":6,"risk":10},
}
SIGNATURE_ORDER=("frost","solar","dream","pulse","void")
SIGNATURES={
 "frost":{"name":"امضای یخ F خیالی","icon":"❄️","fragment":"یخی","market":85_000_000,"stability":18,"quality":5,"risk":-2},
 "solar":{"name":"امضای خورشید H خیالی","icon":"☀️","fragment":"خورشیدی","market":110_000_000,"stability":5,"quality":10,"risk":4},
 "dream":{"name":"امضای رویا R خیالی","icon":"💭","fragment":"رویایی","market":140_000_000,"stability":14,"quality":13,"risk":2},
 "pulse":{"name":"امضای ضربان P خیالی","icon":"💓","fragment":"تپنده","market":175_000_000,"stability":3,"quality":8,"risk":9},
 "void":{"name":"امضای خلأ X خیالی","icon":"🕳️","fragment":"خلأ","market":230_000_000,"stability":9,"quality":17,"risk":12},
}
BRANDS={"street":{"name":"برند کوچه","prefix":"سایه"},"neon":{"name":"برند نئون","prefix":"نئون"},"royal":{"name":"برند سلطنتی","prefix":"تاج"}}
def ingredient(key):return BASES.get(key) or CATALYSTS.get(key) or SIGNATURES.get(key)
def market_price(key):return int(ingredient(key)['market'])
def fingerprint(base,catalyst,signature):return hashlib.sha256(f"fictional:{base}:{catalyst}:{signature}".encode()).hexdigest()[:16]
def formula(base,catalyst,signature,brand="street"):
 b=BASES[base];c=CATALYSTS[catalyst];s=SIGNATURES[signature];seed=int(fingerprint(base,catalyst,signature),16);quality=max(20,min(95,42+c['quality']+s['quality']+seed%13));power=max(15,min(100,35+b['power']+c['power']+(seed//13)%12));stability=max(15,min(100,40+b['stability']+s['stability']+(seed//29)%10));risk=max(3,min(45,8+b['risk']+c['risk']+s['risk']));value=round((b['market']+c['market']+s['market'])*1.45*(.7+quality/200+power/300));name=f"{BRANDS[brand]['prefix']} {b['fragment']}-{c['fragment']} {s['fragment']}"
 return {"fingerprint":fingerprint(base,catalyst,signature),"base_key":base,"catalyst_key":catalyst,"signature_key":signature,"brand_key":brand,"name":name,"quality":quality,"power":power,"stability":stability,"risk":risk,"value":value,"required_level":max(2,round((risk+power)/18))}
def production(recipe,mode,lab):
 from app.data import dark_world_laboratory as L
 m=L.MODES[mode];chance=max(15,min(97,88-int(recipe.risk)+int(lab.safety)*2+int(lab.ventilation)+(int(lab.condition)-50)*.1-m['risk']));duration=round((1200+int(recipe.risk)*55)*m['duration']);qty=max(1,round(2*m['yield']));return {"chance":round(chance,2),"duration":duration,"qty":qty,"quality":max(1,min(100,int(recipe.quality)+int(lab.equipment)*2+m['quality'])),"power":max(1,min(100,int(recipe.power)+int(lab.power)*2)),"stability":max(1,min(100,int(recipe.stability)+int(lab.ventilation))),"condition_loss":m['condition']+int(recipe.risk)//6}
def resolve(plan,roll,qroll,proll,sroll):
 ok=float(roll)<float(plan['chance']);adj=lambda x,r:max(1,min(100,round(x+(float(r)-50)/12)));return {"success":ok,"qty":plan['qty'] if ok else 0,"quality":adj(plan['quality'],qroll),"power":adj(plan['power'],proll),"stability":adj(plan['stability'],sroll),"condition_loss":plan['condition_loss']+(10 if not ok else 0)}
def demand_signature(day=None):return SIGNATURE_ORDER[(day or date.today()).toordinal()%len(SIGNATURE_ORDER)]
def sale_value(recipe,quality,power,stability,day=None):return round(int(recipe.value)*(.72+int(quality)/350+int(power)/500+int(stability)/700)*(1.22 if recipe.signature_key==demand_signature(day) else 1.0))
