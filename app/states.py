from aiogram.fsm.state import State, StatesGroup

# ... کلاس‌های قبلی (ثبت‌نام/انتخاب جنسیت) را دست‌نخورده نگه دار ...

class ProfileStates(StatesGroup):
    editing_name = State()
    editing_title = State()
    editing_photo = State()

class Registration(StatesGroup):
    # منتظر انتخاب جنسیت کاربر
    choosing_gender = State()


class SpyStates(StatesGroup):
    # منتظر واردکردنِ آیدی/یوزرنیمِ هدف برای اعزامِ جاسوس
    entering_target = State()


class ChatStates(StatesGroup):
    # 🆕 مرحله ۱۳.۶ — چت‌مود
    choosing_target = State()   # منتظر انتخاب/ورودِ مخاطب
    offline_message = State()   # منتظر متنِ پیامِ آفلاین
    reporting = State()         # منتظر متنِ گزارش
    admin_password = State()    # منتظر رمزِ حالتِ ادمین


class ContactStates(StatesGroup):
    adding_manual = State()   # افزودن دستی مخاطب با آیدی یا یوزرنیم


class SportsStates(StatesGroup):
    # 🆕 مرحله ۱۴ — نام‌گذاری/برندسازیِ تیم و برند
    naming = State()   # منتظر متنِ نام/شعار/رنگ (نوعِ فیلد در FSM data ذخیره می‌شود)

class WarStates(StatesGroup):
    # 🆕 مرحله ۱۷ — جنگِ شخصی
    entering_target = State()   # منتظر واردکردنِ آیدی/یوزرنیمِ هدفِ حمله
    naming_country = State()    # منتظر نامِ کشور هنگامِ تأسیس
    renaming_country = State()  # 🆕 پچ: منتظر نامِ جدیدِ کشور هنگامِ تغییرِ نام


class AllianceStates(StatesGroup):
    # 🆕 مرحله ۱۸ — اتحادیه‌ها
    creating_tag = State()
    creating_name = State()
    renaming = State()   # 🆕 مرحله ۲۸ — تغییرِ نامِ برند/شرکت/هولدینگ
    setting_sub = State()
    setting_power = State()
    setting_name = State()
    setting_tag = State()
    depositing = State()        # 🆕 v1.7.9.1 — واریز به صندوقِ اتحادیه
    setting_auto_min = State()  # 🆕 v1.7.9.1 — حداقلِ تولیدِ خودکار
    buying_squads = State()     # 🆕 v1.8.2.0 — ورودِ دستیِ تعدادِ اسکادران در سربازخانه‌ی اتحادیه


class WorldAllianceStates(StatesGroup):
    # 🆕 مرحله ۱۹ — اتحادیه‌ی جهانی و جنگِ بین‌الملل
    creating_tag = State()
    creating_name = State()
    setting_power = State()   # حداقلِ قدرتِ کشور برای عضویت


class BrandStates(StatesGroup):
    # 🆕 مرحله ۱۹.۱ — برندسازی
    creating_name = State()
    renaming = State()  # 🐞 مرحله ۲۸: رفعِ AttributeError — تغییرِ نامِ کارخانه/هولدینگ/برند


class BankStates(StatesGroup):
    safebox_wait_amount = State()  # واریز/برداشت گاوصندوق
    # 🆕 مرحله ۱۹.۲ — بانکِ جهانی
    depositing = State()
    withdrawing = State()
    borrowing = State()


class TransferStates(StatesGroup):
    # 🆕 v11 — منوی انتخابیِ انتقال (منبع→مقدار→کاربر)، علاوه بر دستورِ متنی قدیمی
    cash_amount = State()       # منتظرِ مبلغِ انتقالی پول
    cash_target = State()       # منتظرِ آیدی/یوزرنیمِ گیرندهٔ پول
    resource_amount = State()   # منتظرِ مقدارِ کالا (پس از انتخابِ محصول)
    resource_target = State()   # منتظرِ آیدی/یوزرنیمِ گیرندهٔ کالا


class AdminStates(StatesGroup):
    # 🆕 مرحله ۲۱ — سیستمِ ادمین/ادمین‌مود
    waiting_login_password = State()   # منتظر رمزِ ورود به حالتِ ادمین
    waiting_new_password = State()     # منتظر رمزِ جدید (اولین ورود یا تغییرِ رمز)
    # مدیریتِ کاربران
    users_wait_uid = State()           # منتظر یوزرآیدیِ کاربرِ هدف
    users_wait_cash = State()          # منتظر مقدارِ پولِ جدید/تغییر
    users_wait_level = State()         # منتظر لولِ جدید
    users_wait_xp = State()            # منتظر XP جدید
    # اشتراک
    sub_wait_uid = State()             # منتظر یوزرآیدی برای فعال/غیرفعالِ اشتراک
    # القاب
    title_wait_uid = State()           # منتظر یوزرآیدی برای اعطا/حذفِ لقب
    title_wait_custom = State()        # منتظر متنِ لقبِ دلخواه برای کاربر
    title_wait_inspect_uid = State()   # منتظر یوزرآیدی برای بررسیِ القاب
    # اخبار و همگانی
    news_wait_text = State()           # منتظر متنِ خبر
    broadcast_wait_text = State()
    # ابرکارخانهٔ دون
    giga_wait_uid = State()           # منتظر یوزرآیدی برای دسترسی ابرکارخانه
    cityprod_wait_uid = State()      # منتظر یوزرآیدی برای تکمیل فوری ساخت شهر      # منتظر متنِ پیامِ همگانی
    broadcast_confirm = State()        # 🆕 پیش‌نمایشِ پیامِ همگانی قبل از ارسالِ نهایی (امکانِ ویرایش)
    # مدیریتِ ادمین‌ها
    admins_wait_uid = State()          # منتظر یوزرآیدیِ ادمینِ جدید
    admins_wait_initpw = State()       # منتظر رمزِ اولیه برای ادمینِ جدید
    admins_wait_revoke = State()       # منتظر یوزرآیدیِ ادمین برای عزل
    coach_price_wait = State()         # 🆕 v1.7.9.5 — منتظر قیمت جدید سرمربی (ادمین)
    control_wait_testers = State()     # 🆕 v1.7.9.6 — منتظر آیدی تست‌کننده‌ها
    market_price_wait = State()        # 🆕 v1.7.9.7 — منتظر قیمت جدید بازیکن (ادمین)
    pmarket_wait_search = State()      # 🆕 v1.8.2.1 — منتظر اسم بازیکن برای جستجوی قیمت
    fball_pm_wait_uid = State()        # 🆕 v1.8.2.1 — منتظر یوزرآیدی برای مدیریت بازیکن
    fball_give_wait_name = State()     # 🆕 v1.8.2.1 — منتظر اسم بازیکن برای اهدا
    fball_transfer_wait_uid = State()  # 🆕 v1.8.2.1 — منتظر یوزرآیدی مقصد برای انتقال بازیکن
    market_give_uid = State()          # 🆕 v1.7.9.7 — منتظر یوزرآیدی دادن/گرفتن بازیکن (ادمین)
    admins_wait_editperms = State()
    users_list_search = State()
    users_list_goto = State()    # منتظر یوزرآیدیِ ادمین برای ویرایشِ دسترسی
    # کانالِ گزارش
    channel_wait_ref = State()         # منتظر لینک/آیدی/فورواردِ کانالِ گزارش
    force_join_wait_ref = State()      # منتظر معرفی کانال عضویت اجباری
    force_join_wait_link = State()     # منتظر لینک دعوت عمومی/خصوصی کانال
    news_channel_wait_ref = State()     # منتظر لینک/آیدی/فورواردِ کانالِ اخبار
    self_change_password = State()      # 🆕 تغییرِ خودخواسته‌یِ رمز (هر زمان، از داخلِ پنل)
    # 🆕 مرحله ۲۱.۱ — پنلِ گسترده‌یِ اشتراک (قیمت‌گذاری/ادمینِ فروش/درخواست‌ها/پیگیری)
    sub_wait_priceval = State()         # منتظر قیمتِ جدیدِ یک سطح (فقط ادمینِ اصلی)
    sub_wait_salesadmin_uid = State()   # منتظر یوزرآیدیِ ادمینِ فروش (یا 0 برایِ حذف)
    sub_wait_trackcode = State()        # منتظر کدِ پیگیری برایِ دریافتِ مستنداتِ خرید
    # 🆕 مرحله ۲۷ — رویدادهایِ بونس (XP/پول) + ابزارهایِ ویژه‌یِ ادمینِ اصلی
    event_wait_mult = State()           # منتظر ضریبِ رویداد (مثلاً 2 یا 1.5)
    event_wait_hours = State()          # منتظر مدتِ رویداد به ساعت (یا «نامحدود»)
    event_wait_title = State()          # منتظر نامِ اونت
    tools_wait_gift_amount = State()    # منتظر مقدارِ هدیهِ همگانی
    # 🆕 مرحله ۳۰ — هدیه به یک کاربرِ خاص و هدیهِ لقب
    tools_wait_gift_uid = State()       # منتظر یوزرآیدیِ گیرندهٔ هدیه
    tools_wait_gift_one = State()       # منتظر مقدارِ هدیهِ تک‌نفره
    tools_wait_title_uid = State()      # منتظر یوزرآیدی برایِ هدیهِ لقب
    tools_wait_title_key = State()      # منتظر کلید/نامِ لقب
    tools_wait_reset_uid = State()      # منتظر یوزرآیدیِ کاربر برایِ ریست
    tools_confirm_reset = State()       # منتظر تأییدِ نهاییِ ریستِ کاربر
    tools_wait_delete_uid = State()     # 🆕 v1.7.2 — حذف کامل کاربر
    tools_confirm_delete = State()     # 🆕 v1.7.2 — تأیید حذف کامل
    backup_wait_channel = State()      # 🆕 v1.7.2 — کانال بکاپ
    backup_wait_hours = State()        # 🆕 v1.7.2 — فاصله بکاپ
    tools_wait_military_reset_uid = State()   # 🆕 مرحله ۴۶ — ریستِ نظامیِ یک کاربر
    tools_wait_military_uid = State()  # گزارش نظامی کاربر برای ادمین
    tools_wait_qflush_uid = State()     # 🆕 مرحله ۷۱ — تکمیلِ فوریِ صف‌های یک کاربر
    control_wait_section = State()
    control_wait_user = State()
    control_wait_reason = State()
    # پنل مستقیم فعال/غیرفعال‌سازی دستیار برای یک کاربر
    assistant_user_wait = State()
    numbers_wait_key = State()
    numbers_wait_value = State()
    titled_wait_page = State()
    referral_wait_cash = State()
    referral_wait_bonus = State()
    bulk_level_value = State()
    level_batch_ids = State()
    level_batch_amount = State()
    level_batch_confirm = State()
    level_all_delta_amount = State()
    level_all_delta_confirm = State()
    wealth_batch_ids = State()
    wealth_batch_amount = State()
    wealth_batch_confirm = State()
    wealth_all_amount = State()
    wealth_all_confirm = State()
    loan_reset_targets = State()
    loan_reset_confirm = State()
    tools_wait_military_level_uid = State()
    tools_wait_military_level_value = State()
    activity_wait_uid = State()
    wb_wait_value = State()            # v1.7.8.2 bank panel numeric input


class SubStates(StatesGroup):
    # 🆕 مرحله ۲۱.۱ — پس از ثبتِ درخواستِ خرید، دریافتِ رسیدِ پرداخت (اختیاری)
    awaiting_receipt = State()


class MilitaryStates(StatesGroup):
    # 🆕 مرحله ۴۶ — واردکردنِ عددیِ تعدادِ نیرو
    entering_qty = State()


class CityStates(StatesGroup):
    naming_city = State()
    renaming_city = State()
    buying_resource_amount = State()
    building_amount = State()

class FootballStates(StatesGroup):
    # 🆕 v1.7.9.2 — فوتبال منیجر
    creating_name = State()
    social_wait_photo = State()   # 🆕 v1.7.9.4 — منتظر عکس پست سوشال
    coach_receipt_wait = State()  # 🆕 v1.7.9.5 — منتظر رسید خرید سرمربی
    market_bid = State()          # 🆕 v1.7.9.7 — منتظر مبلغ پیشنهاد مزایده
    market_transfer = State()     # 🆕 v1.7.9.7 — منتظر یوزرآیدی هدف انتقال بازیکن
