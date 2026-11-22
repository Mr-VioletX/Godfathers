# -*- coding: utf-8 -*-
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.utils.ui import with_owner
def hub(owner,season_done=False,claimable=False,boss_alive=True):
 b=InlineKeyboardBuilder();b.button(text="🏆 جدول چندمحوره",callback_data=with_owner("dwk:board",owner));b.button(text="📊 امتیاز من",callback_data=with_owner("dwk:me",owner))
 if boss_alive:b.button(text="👁️ حمله به نگهبان شب",callback_data=with_owner("dwk:boss",owner))
 b.button(text="📈 تله‌متری اقتصاد",callback_data=with_owner("dwk:economy",owner))
 if season_done and claimable:b.button(text="🎁 جایزه رقابتی",callback_data=with_owner("dwk:claim",owner))
 b.button(text="🏛️ تالار افتخار",callback_data=with_owner("dwk:hall",owner));b.button(text="↩️ دنیای سیاه",callback_data=with_owner("dw:sec:competition",owner));b.adjust(2,2,2,1);return b.as_markup()
