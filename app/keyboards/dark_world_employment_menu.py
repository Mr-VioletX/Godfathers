# -*- coding: utf-8 -*-
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.data import dark_world_employment as E
from app.utils.ui import with_owner

def hub(owner):
 b=InlineKeyboardBuilder();b.button(text="➕ ثبت قرارداد",callback_data=with_owner("dwe:new",owner));b.button(text="🛒 بازار کار",callback_data=with_owner("dwe:market",owner));b.button(text="📂 قراردادهای من",callback_data=with_owner("dwe:mine",owner));b.button(text="⭐ اعتبار کاری",callback_data=with_owner("dwe:rep",owner));b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:crew",owner));b.adjust(2,2,1);return b.as_markup()
def jobs(owner):
 b=InlineKeyboardBuilder()
 for k in E.JOB_ORDER:
  j=E.JOBS[k];b.button(text=f"{j['icon']} {j['name']}",callback_data=with_owner(f"dwe:job:{k}",owner))
 b.button(text="↩️ بازار کار",callback_data=with_owner("dwe:hub",owner));b.adjust(1);return b.as_markup()
def payments(job,owner):
 b=InlineKeyboardBuilder()
 for k in E.PAYMENT_ORDER:b.button(text=f"💰 {E.PAYMENTS[k]['name']}",callback_data=with_owner(f"dwe:preview:{job}:{k}",owner))
 b.button(text="↩️ نوع کار",callback_data=with_owner("dwe:new",owner));b.adjust(1);return b.as_markup()
def publish(job,pay,owner):
 b=InlineKeyboardBuilder();b.button(text="✅ قفل escrow و انتشار",callback_data=with_owner(f"dwe:publish:{job}:{pay}",owner));b.button(text="↩️ مدل پرداخت",callback_data=with_owner(f"dwe:job:{job}",owner));b.adjust(1);return b.as_markup()
def list_contracts(rows,owner,market=False):
 b=InlineKeyboardBuilder()
 for c in rows:b.button(text=f"#{c.id} · {E.JOBS[c.job_key]['name']} · {c.fixed_wage:,}",callback_data=with_owner(f"dwe:view:{c.id}",owner))
 b.button(text="↩️ بازار کار",callback_data=with_owner("dwe:hub",owner));b.adjust(1);return b.as_markup()
def detail(c,viewer,owner):
 b=InlineKeyboardBuilder()
 if c.status=="open" and viewer!=c.employer_id:b.button(text="🤝 پذیرش قرارداد",callback_data=with_owner(f"dwe:accept:{c.id}",owner))
 if c.status=="open" and viewer==c.employer_id:b.button(text="✖️ لغو و بازپرداخت",callback_data=with_owner(f"dwe:cancel:{c.id}",owner))
 if c.status=="accepted" and viewer==c.worker_id:b.button(text="▶️ شروع کار",callback_data=with_owner(f"dwe:start:{c.id}",owner))
 if c.status=="in_progress" and viewer==c.worker_id:b.button(text="♟️ اجرای مأموریت",callback_data=with_owner(f"dwe:plans:{c.id}",owner))
 if c.status=="submitted" and viewer in (c.employer_id,c.worker_id):b.button(text="💳 تسویه اتمیک",callback_data=with_owner(f"dwe:settle:{c.id}",owner));b.button(text="⚖️ ثبت اختلاف",callback_data=with_owner(f"dwe:dispute:{c.id}",owner))
 b.button(text="↩️ قراردادهای من",callback_data=with_owner("dwe:mine",owner));b.adjust(1);return b.as_markup()
def plans(c,chances,owner):
 b=InlineKeyboardBuilder()
 for k in E.APPROACH_ORDER:
  a=E.APPROACHES[k];b.button(text=f"{a['icon']} {a['name']} · {chances[k]['chance']:.0f}٪",callback_data=with_owner(f"dwe:do:{c.id}:{k}",owner))
 b.button(text="↩️ قرارداد",callback_data=with_owner(f"dwe:view:{c.id}",owner));b.adjust(1);return b.as_markup()
