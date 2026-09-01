# رسائل الواجهة الرئيسية لـ PlayPalace

# فئات اللعبة
category-card-games = ألعاب الورق
category-dice-games = ألعاب النرد
category-rb-play-center = مركز RB للعب
category-poker = بوكر
category-uncategorized = غير مصنف

# عناوين القوائم
main-menu-title = القائمة الرئيسية
play-menu-title = العب
categories-menu-title = فئات الألعاب
tables-menu-title = الطاولات المتاحة

# عناصر القائمة
play = العب
view-active-tables = عرض الطاولات النشطة
options = الخيارات
logout = تسجيل الخروج
back = رجوع
go-back = ارجع
context-menu = قائمة السياق.
no-actions-available = لا توجد إجراءات متاحة.
create-table = إنشاء طاولة جديدة
join-as-player = انضم كلاعب
join-as-spectator = انضم كمتفرج
leave-table = غادر الطاولة
start-game = ابدأ اللعبة
add-bot = أضف بوت
remove-bot = احذف بوت
actions-menu = قائمة الإجراءات
save-table = احفظ الطاولة
whose-turn = دور من
whos-at-table = من على الطاولة
check-scores = تحقق من النتائج
check-scores-detailed = نتائج مفصلة
check-game-options = تحقق من خيارات اللعبة
no-game-options = لا توجد خيارات للعبة

# رسائل الدور
game-player-skipped = تم تخطي { $player }.

# رسائل الطاولة
table-created = { $host } أنشأ طاولة { $game } جديدة.
table-joined = { $player } انضم إلى الطاولة.
table-left = { $player } غادر الطاولة.
new-host = { $player } هو الآن المضيف.
waiting-for-players = في انتظار اللاعبين. {$min} كحد أدنى، { $max } كحد أقصى.
game-starting = اللعبة تبدأ!
table-listing = طاولة { $host } ({ $count } { $count ->
    [zero] مستخدمين
    [one] مستخدم واحد
    [two] مستخدمان
    [few] مستخدمين
    [many] مستخدماً
   *[other] مستخدم
})
table-listing-one = طاولة { $host } ({ $count } مستخدم)
table-listing-with = طاولة { $host } ({ $count } { $count ->
    [zero] مستخدمين
    [one] مستخدم
    [two] مستخدمان
    [few] مستخدمين
    [many] مستخدماً
   *[other] مستخدم
}) مع { $members }
table-listing-game = { $game }: طاولة { $host } ({ $count } { $count ->
    [zero] مستخدمين
    [one] مستخدم
    [two] مستخدمان
    [few] مستخدمين
    [many] مستخدماً
   *[other] مستخدم
})
table-listing-game-one = { $game }: طاولة { $host } ({ $count } مستخدم)
table-listing-game-with = { $game }: طاولة { $host } ({ $count } { $count ->
    [zero] مستخدمين
    [one] مستخدم
    [two] مستخدمان
    [few] مستخدمين
    [many] مستخدماً
   *[other] مستخدم
}) مع { $members }
table-not-exists = الطاولة لم تعد موجودة.
table-full = الطاولة ممتلئة.
player-replaced-by-bot = { $player } غادر وتم استبداله ببوت.
player-took-over = { $player } تولى من البوت.
spectator-joined = انضممت إلى طاولة { $host } كمتفرج.

# وضع المتفرج
spectate = تفرج
now-playing = { $player } يلعب الآن.
now-spectating = { $player } يتفرج الآن.
spectator-left = { $player } توقف عن المشاهدة.

# عام
welcome = مرحباً بك في PlayPalace!
goodbye = وداعاً!

# إعلانات حضور المستخدم
user-online = { $player } أصبح متصلاً.
user-offline = { $player } غير متصل.
user-is-admin = { $player } مسؤول في PlayPalace.
user-is-server-owner = { $player } هو مالك خادم PlayPalace.
online-users-none = لا يوجد مستخدمون متصلون.
online-users-one = مستخدم واحد: { $users }
online-users-many = { $count } { $count ->
    [zero] مستخدمين
    [one] مستخدم
    [two] مستخدمان
    [few] مستخدمين
    [many] مستخدماً
   *[other] مستخدم
}: { $users }
online-user-not-in-game = ليس في لعبة
online-user-waiting-approval = في انتظار الموافقة

# الخيارات
language = اللغة
language-option = اللغة: { $language }
language-changed = تم تعيين اللغة إلى { $language }.

# حالات الخيارات المنطقية
option-on = مفعّل
option-off = معطّل

# خيارات الصوت
turn-sound-option = صوت الدور: { $status }

# خيارات النرد
clear-kept-option = مسح النرد المحفوظ عند الرمي: { $status }
dice-keeping-style-option = أسلوب حفظ النرد: { $style }
dice-keeping-style-changed = تم تعيين أسلوب حفظ النرد إلى { $style }.
dice-keeping-style-indexes = فهارس النرد
dice-keeping-style-values = قيم النرد

# أسماء البوتات
cancel = إلغاء
no-bot-names-available = لا توجد أسماء بوتات متاحة.
select-bot-name = اختر اسماً للبوت
enter-bot-name = أدخل اسم البوت
no-options-available = لا توجد خيارات متاحة.
no-scores-available = لا توجد نتائج متاحة.

# تقدير المدة
estimate-duration = تقدير المدة
estimate-computing = جارٍ حساب مدة اللعبة المقدرة...
estimate-result = متوسط البوت: { $bot_time } (± { $std_dev }). { $outlier_info }الوقت المقدر للبشر: { $human_time }.
estimate-error = تعذر تقدير المدة.
estimate-already-running = تقدير المدة قيد التشغيل بالفعل.

# الحفظ/الاستعادة
saved-tables = الطاولات المحفوظة
no-saved-tables = ليس لديك طاولات محفوظة.
no-active-tables = لا توجد طاولات نشطة.
restore-table = استعادة
delete-saved-table = حذف
saved-table-deleted = تم حذف الطاولة المحفوظة.
missing-players = لا يمكن الاستعادة: هؤلاء اللاعبون غير متاحين: { $players }
table-restored = تم استعادة الطاولة! تم نقل جميع اللاعبين.
table-saved-destroying = تم حفظ الطاولة! العودة إلى القائمة الرئيسية.
game-type-not-found = نوع اللعبة لم يعد موجوداً.

# أسباب تعطيل الإجراءات
action-not-your-turn = ليس دورك.
action-not-playing = اللعبة لم تبدأ بعد.
action-spectator = المتفرجون لا يمكنهم فعل ذلك.
action-not-host = المضيف فقط يمكنه فعل ذلك.
action-game-in-progress = لا يمكن فعل ذلك أثناء تقدم اللعبة.
action-need-more-players = نحتاج المزيد من اللاعبين للبدء.
action-table-full = الطاولة ممتلئة.
action-no-bots = لا توجد بوتات لإزالتها.
action-bots-cannot = البوتات لا يمكنها فعل ذلك.
action-no-scores = لا توجد نتائج متاحة بعد.

# إجراءات النرد
dice-not-rolled = لم ترمِ بعد.
dice-locked = هذا النرد مقفل.
dice-no-dice = لا يوجد نرد متاح.

# إجراءات اللعبة
game-turn-start = دور { $player }.
game-no-turn = لا يوجد دور لأحد الآن.
table-no-players = لا يوجد لاعبون.
table-players-one = { $count } لاعب: { $players }.
table-players-many = { $count } { $count ->
    [zero] لاعبين
    [one] لاعب
    [two] لاعبان
    [few] لاعبين
    [many] لاعباً
   *[other] لاعب
}: { $players }.
table-spectators = المتفرجون: { $spectators }.
game-leave = غادر
game-over = انتهت اللعبة
game-final-scores = النتائج النهائية
game-points = { $count } { $count ->
    [zero] نقاط
    [one] نقطة واحدة
    [two] نقطتان
    [few] نقاط
    [many] نقطة
   *[other] نقطة
}
play = العب

# لوحات الصدارة
leaderboards = لوحات الصدارة
leaderboards-menu-title = لوحات الصدارة
leaderboards-select-game = اختر لعبة لعرض لوحة الصدارة الخاصة بها
leaderboard-no-data = لا توجد بيانات لوحة صدارة لهذه اللعبة بعد.

# أنواع لوحات الصدارة
leaderboard-type-wins = قادة الفوز
leaderboard-type-rating = تصنيف المهارة
leaderboard-type-total-score = النتيجة الإجمالية
leaderboard-type-high-score = أعلى نتيجة
leaderboard-type-games-played = الألعاب الملعوبة
leaderboard-type-avg-points-per-turn = متوسط النقاط لكل دور
leaderboard-type-best-single-turn = أفضل دور منفرد
leaderboard-type-score-per-round = النتيجة لكل جولة

# رؤوس لوحات الصدارة
leaderboard-wins-header = { $game } - قادة الفوز
leaderboard-total-score-header = { $game } - النتيجة الإجمالية
leaderboard-high-score-header = { $game } - أعلى نتيجة
leaderboard-games-played-header = { $game } - الألعاب الملعوبة
leaderboard-rating-header = { $game } - تصنيفات المهارة
leaderboard-avg-points-header = { $game } - متوسط النقاط لكل دور
leaderboard-best-turn-header = { $game } - أفضل دور منفرد
leaderboard-score-per-round-header = { $game } - النتيجة لكل جولة

# إدخالات لوحة الصدارة
leaderboard-wins-entry = { $rank }: { $player }، { $wins } { $wins ->
    [zero] انتصارات
    [one] فوز واحد
    [two] فوزان
    [few] انتصارات
    [many] فوزاً
   *[other] فوز
} { $losses } { $losses ->
    [zero] خسارات
    [one] خسارة واحدة
    [two] خسارتان
    [few] خسارات
    [many] خسارة
   *[other] خسارة
}، { $percentage }% معدل الفوز
leaderboard-score-entry = { $rank }. { $player }: { $value }
leaderboard-avg-entry = { $rank }. { $player }: { $value } متوسط
leaderboard-games-entry = { $rank }. { $player }: { $value } { $value ->
    [zero] ألعاب
    [one] لعبة
    [two] لعبتان
    [few] ألعاب
    [many] لعبة
   *[other] لعبة
}

# إحصائيات اللاعب
leaderboard-player-stats = إحصائياتك: { $wins } انتصارات، { $losses } خسارات ({ $percentage }% معدل الفوز)
leaderboard-no-player-stats = لم تلعب هذه اللعبة بعد.

# لوحة صدارة تصنيف المهارة
leaderboard-no-ratings = لا توجد بيانات تصنيف لهذه اللعبة بعد.
leaderboard-rating-entry = { $rank }. { $player }: { $rating } تصنيف ({ $mu } ± { $sigma })
leaderboard-player-rating = تصنيفك: { $rating } ({ $mu } ± { $sigma })
leaderboard-no-player-rating = ليس لديك تصنيف لهذه اللعبة بعد.

# قائمة إحصائياتي
my-stats = إحصائياتي
my-stats-select-game = اختر لعبة لعرض إحصائياتك
my-stats-no-data = لم تلعب هذه اللعبة بعد.
my-stats-no-games = لم تلعب أي ألعاب بعد.
my-stats-header = { $game } - إحصائياتك
my-stats-wins = الانتصارات: { $value }
my-stats-losses = الخسارات: { $value }
my-stats-winrate = معدل الفوز: { $value }%
my-stats-games-played = الألعاب الملعوبة: { $value }
my-stats-total-score = النتيجة الإجمالية: { $value }
my-stats-high-score = أعلى نتيجة: { $value }
my-stats-rating = تصنيف المهارة: { $value } ({ $mu } ± { $sigma })
my-stats-no-rating = لا يوجد تصنيف مهارة بعد
my-stats-avg-per-turn = متوسط النقاط لكل دور: { $value }
my-stats-best-turn = أفضل دور منفرد: { $value }

# نظام التنبؤ
predict-outcomes = التنبؤ بالنتائج
predict-header = النتائج المتوقعة (حسب تصنيف المهارة)
predict-entry = { $rank }. { $player } (التصنيف: { $rating })
predict-entry-2p = { $rank }. { $player } (التصنيف: { $rating }، { $probability }% فرصة الفوز)
predict-unavailable = تنبؤات التصنيف غير متاحة.
predict-need-players = يلزم على الأقل لاعبان بشريان للتنبؤات.
action-need-more-humans = نحتاج المزيد من اللاعبين البشريين.
confirm-leave-game = هل أنت متأكد من أنك تريد مغادرة الطاولة؟
confirm-yes = نعم
confirm-no = لا

# الإدارة
administration = الإدارة
admin-menu-title = الإدارة

# الموافقة على الحساب
account-approval = الموافقة على الحساب
account-approval-menu-title = الموافقة على الحساب
no-pending-accounts = لا توجد حسابات معلقة.
approve-account = الموافقة
decline-account = الرفض
account-approved = تمت الموافقة على حساب { $player }.
account-declined = تم رفض وحذف حساب { $player }.

# في انتظار الموافقة (يظهر للمستخدمين غير المعتمدين)
waiting-for-approval = حسابك في انتظار الموافقة من قبل مسؤول.
account-approved-welcome = تمت الموافقة على حسابك! مرحباً بك في PlayPalace!
account-declined-goodbye = تم رفض طلب حسابك.
    السبب:
account-banned = حسابك محظور ولا يمكن الوصول إليه.

# أخطاء تسجيل الدخول
incorrect-username = اسم المستخدم الذي أدخلته غير موجود.
incorrect-password = كلمة المرور التي أدخلتها غير صحيحة.
already-logged-in = هذا الحساب مسجل دخول بالفعل.

# التحقق من صحة بيانات الاعتماد
credential-username-length = يجب أن يتراوح اسم المستخدم بين { $min } و{ $max } حرفاً.
credential-password-length = يجب أن تتراوح كلمة المرور بين { $min } و{ $max } حرفاً.

# تقييد معدل الطلبات
rate-limit-login-ip = محاولات تسجيل دخول كثيرة جداً من هذا العنوان. يرجى الانتظار والمحاولة مرة أخرى.
rate-limit-login-user = محاولات تسجيل دخول فاشلة كثيرة جداً لاسم المستخدم هذا. يرجى الانتظار والمحاولة مرة أخرى.
rate-limit-registration = محاولات تسجيل كثيرة جداً من هذا العنوان. يرجى الانتظار والمحاولة مرة أخرى.
rate-limit-refresh = محاولات تحديث كثيرة جداً من هذا العنوان. يرجى الانتظار والمحاولة مرة أخرى.

# أخطاء الجلسة والمصادقة
account-not-found = الحساب غير موجود.
session-expired = انتهت صلاحية الجلسة. يرجى تسجيل الدخول مرة أخرى.
session-token-mismatch = رمز الجلسة لا يطابق اسم المستخدم.
refresh-token-expired = انتهت صلاحية رمز التحديث. يرجى تسجيل الدخول مرة أخرى.
refresh-token-mismatch = رمز التحديث لا يطابق اسم المستخدم.

# التسجيل
registration-success = تم التسجيل بنجاح! حسابك في انتظار الموافقة.
registration-username-taken = اسم المستخدم مأخوذ بالفعل. يرجى اختيار اسم مستخدم مختلف.

# الرجوع إلى الإعداد الافتراضي للتفضيلات
pref-invalid-value = اختيار غير صالح، سيتم استخدام الإعداد الافتراضي.

# سبب الرفض
decline-reason-prompt = أدخل سبب الرفض (أو اضغط Escape للإلغاء):
account-action-empty-reason = لم يتم تقديم سبب.

# إشعارات المشرف لطلبات الحساب
account-request = طلب حساب
account-action = تم اتخاذ إجراء على الحساب

# ترقية/تخفيض رتبة المشرف
promote-admin = ترقية مشرف
demote-admin = تخفيض رتبة مشرف
promote-admin-menu-title = ترقية مشرف
demote-admin-menu-title = تخفيض رتبة مشرف
no-users-to-promote = لا يوجد مستخدمون متاحون للترقية.
no-admins-to-demote = لا يوجد مشرفون متاحون لتخفيض رتبتهم.
confirm-promote = هل أنت متأكد من أنك تريد ترقية { $player } إلى مشرف؟
confirm-demote = هل أنت متأكد من أنك تريد تخفيض رتبة { $player } من مشرف؟
broadcast-to-all = الإعلان لجميع المستخدمين
broadcast-to-admins = الإعلان للمشرفين فقط
broadcast-to-nobody = صامت (لا إعلان)
promote-announcement = تمت ترقية { $player } إلى مشرف!
promote-announcement-you = تمت ترقيتك إلى مشرف!
demote-announcement = تم تخفيض رتبة { $player } من مشرف.
demote-announcement-you = تم تخفيض رتبتك من مشرف.
not-admin-anymore = لم تعد مشرفاً ولا يمكنك تنفيذ هذا الإجراء.
not-server-owner = مالك الخادم فقط يمكنه تنفيذ هذا الإجراء.

# نقل ملكية الخادم
transfer-ownership = نقل الملكية
transfer-ownership-menu-title = نقل الملكية
no-admins-for-transfer = لا يوجد مشرفون متاحون لنقل الملكية إليهم.
confirm-transfer-ownership = هل أنت متأكد من أنك تريد نقل ملكية الخادم إلى { $player }؟ سيتم تخفيض رتبتك إلى مشرف.
transfer-ownership-announcement = { $player } هو الآن مالك خادم Play Palace!
transfer-ownership-announcement-you = أنت الآن مالك خادم Play Palace!

# حظر المستخدم
ban-user = حظر المستخدم
unban-user = إلغاء حظر المستخدم
no-users-to-ban = لا يوجد مستخدمون متاحون للحظر.
no-users-to-unban = لا يوجد مستخدمون محظورون لإلغاء حظرهم.
confirm-ban = هل أنت متأكد من أنك تريد حظر { $player }؟
confirm-unban = هل أنت متأكد من أنك تريد إلغاء حظر { $player }؟
ban-reason-prompt = أدخل سبب الحظر (اختياري):
unban-reason-prompt = أدخل سبب إلغاء الحظر (اختياري):
user-banned = تم حظر { $player }.
user-unbanned = تم إلغاء حظر { $player }.
you-have-been-banned = تم حظرك من هذا الخادم.
    السبب:
you-have-been-unbanned = تم إلغاء حظرك من هذا الخادم.
    السبب:
ban-no-reason = لم يتم تقديم سبب.

# البوتات الافتراضية (مالك الخادم فقط)
virtual-bots = البوتات الافتراضية
virtual-bots-fill = ملء الخادم
virtual-bots-clear = مسح جميع البوتات
virtual-bots-status = الحالة
virtual-bots-clear-confirm = هل أنت متأكد من أنك تريد مسح جميع البوتات الافتراضية؟ سيؤدي هذا أيضاً إلى تدمير أي طاولات موجودة فيها.
virtual-bots-not-available = البوتات الافتراضية غير متاحة.
virtual-bots-filled = تمت إضافة { $added } بوتات افتراضية. { $online } متصلون الآن.
virtual-bots-already-filled = جميع البوتات الافتراضية من الإعدادات نشطة بالفعل.
virtual-bots-cleared = تم مسح { $bots } بوتات افتراضية وتدمير { $tables } { $tables ->
    [zero] طاولات
    [one] طاولة
    [two] طاولتان
    [few] طاولات
    [many] طاولة
   *[other] طاولة
}.
virtual-bot-table-closed = تم إغلاق الطاولة بواسطة المسؤول.
virtual-bots-none-to-clear = لا توجد بوتات افتراضية لمسحها.
virtual-bots-status-report = البوتات الافتراضية: { $total } إجمالي، { $online } متصل، { $offline } غير متصل، { $in_game } في لعبة.
virtual-bots-guided-overview = الطاولات الموجهة
virtual-bots-groups-overview = مجموعات البوتات
virtual-bots-profiles-overview = الملفات الشخصية
virtual-bots-guided-header = الطاولات الموجهة: { $count } { $count ->
    [zero] قواعد
    [one] قاعدة
    [two] قاعدتان
    [few] قواعد
    [many] قاعدة
   *[other] قاعدة
}. التخصيص: { $allocation }، الاحتياطي: { $fallback }، الملف الافتراضي: { $default_profile }.
virtual-bots-guided-empty = لم يتم تكوين قواعد طاولة موجهة.
virtual-bots-guided-status-active = نشط
virtual-bots-guided-status-inactive = غير نشط
virtual-bots-guided-table-linked = مرتبط بالطاولة { $table_id } (المضيف { $host }، اللاعبون { $players }، البشر { $humans })
virtual-bots-guided-table-stale = الطاولة { $table_id } مفقودة على الخادم
virtual-bots-guided-table-unassigned = لم يتم تتبع أي طاولة حالياً
virtual-bots-guided-next-change = التغيير التالي في { $ticks } دورات
virtual-bots-guided-no-schedule = لا توجد نافذة جدولة
virtual-bots-guided-warning = ⚠ غير مكتملة
virtual-bots-guided-line = { $table }: اللعبة { $game }، الأولوية { $priority }، البوتات { $assigned } (الحد الأدنى { $min_bots }، الحد الأقصى { $max_bots })، في الانتظار { $waiting }، غير متاح { $unavailable }، الحالة { $status }، الملف الشخصي { $profile }، المجموعات { $groups }. { $table_state }. { $next_change } { $warning_text }
virtual-bots-groups-header = مجموعات البوتات: { $count } { $count ->
    [zero] علامات
    [one] علامة
    [two] علامتان
    [few] علامات
    [many] علامة
   *[other] علامة
}، { $bots } بوتات مكونة.
virtual-bots-groups-empty = لم يتم تعريف مجموعات بوتات.
virtual-bots-groups-line = { $group }: الملف الشخصي { $profile }، البوتات { $total } (متصل { $online }، في الانتظار { $waiting }، في اللعبة { $in_game }، غير متصل { $offline })، القواعد { $rules }.
virtual-bots-groups-no-rules = لا شيء
virtual-bots-no-profile = افتراضي
virtual-bots-profile-inherit-default = يرث الملف الافتراضي
virtual-bots-profiles-header = الملفات الشخصية: { $count } محدد (الافتراضي: { $default_profile }).
virtual-bots-profiles-empty = لم يتم تعريف ملفات شخصية.
virtual-bots-profiles-line = { $profile } ({ $bot_count } { $bot_count ->
    [zero] بوتات
    [one] بوت
    [two] بوتان
    [few] بوتات
    [many] بوتاً
   *[other] بوت
}) التجاوزات: { $overrides }.
virtual-bots-profiles-no-overrides = يرث الإعدادات الأساسية
virtual-bots-add = إضافة بوت افتراضي
virtual-bots-edit = تعديل بوت افتراضي
virtual-bots-delete = حذف بوت افتراضي
virtual-bots-add-prompt = أدخل اسماً للبوت الافتراضي الجديد:
virtual-bots-rename-prompt = أدخل اسماً جديداً لـ { $name }:
virtual-bots-rename = إعادة تسمية
virtual-bots-change-profile = تغيير الملف الشخصي
virtual-bots-added = تمت إضافة البوت الافتراضي { $name } وإحضاره عبر الإنترنت.
virtual-bots-renamed = تمت إعادة تسمية البوت الافتراضي من { $old_name } إلى { $new_name }.
virtual-bots-profile-changed = تم تغيير ملف البوت الافتراضي { $name } إلى { $profile }.
virtual-bots-deleted = تم حذف البوت الافتراضي { $name }. تم إغلاق { $tables } جدول(جداول).
virtual-bots-name-taken = يوجد بالفعل بوت افتراضي بهذا الاسم.
virtual-bots-name-invalid = هذا الاسم غير صالح.
virtual-bots-no-bots = لا توجد بوتات افتراضية لإدارتها.
virtual-bots-delete-confirm = حذف البوت الافتراضي { $name }؟ سيؤدي ذلك إلى إغلاق أي جدول فيه.
virtual-bots-no-profiles = لا توجد ملفات شخصية متاحة.

localization-in-progress-try-again = جارٍ إعداد الترجمة. يُرجى المحاولة مرة أخرى بعد دقيقة.

# Server reboot
admin-reboot-server = إعادة تشغيل الخادم
confirm-reboot-server = هل أنت متأكد من رغبتك في إعادة تشغيل الخادم؟ سيتم فصل جميع اللاعبين وإعادة توصيلهم.
server-reboot-warning = سيتم إعادة تشغيل الخادم خلال { $seconds } ثانية.
server-restarting = الخادم قيد إعادة التشغيل. سوف يتم إعادة توصيلك تلقائياً.
server-reboot-failed = تعذر إعادة تشغيل الخادم. يرجى المحاولة مرة أخرى.
# Admin: server status
server-status = Server Status
server-status-title = -- Server Status --
server-status-uptime = Uptime: { $minutes } min
server-status-tick = Tick: { $tick }
server-status-online-users = Online users: { $count }
server-status-approved = Approved online: { $count }
server-status-tables = Open tables: { $count }
server-status-db-users = Registered users: { $count }
server-status-virtual-bots = Virtual bots: { $total } total ({ $online } online, { $in_game } in game)

# Admin: kick user
kick-user = Kick User
no-users-to-kick = No online users to kick.
confirm-kick-user = Are you sure you want to kick { $player }? They will be disconnected but not banned.
user-kicked = { $player } has been kicked.
user-not-online = { $player } is not currently online.
cannot-kick-higher-rank = You cannot kick { $player }.

# Admin: broadcast announcement
broadcast-announcement = Broadcast Announcement
broadcast-announcement-prompt = Enter a message to broadcast to all users (or press Escape to cancel):
broadcast-sent = Announcement sent to { $count } users.
broadcast-empty-message = The announcement was empty. Nothing was sent.

# Admin: user lookup
lookup-user = Look Up User
lookup-user-prompt = Enter a username to look up (or press Escape to cancel):
lookup-user-title = -- { $player } --
lookup-user-trust = Role: { $role }
lookup-user-approved = Approved: { $state }
lookup-user-online = Online: { $state }
lookup-user-banned = Banned: { $state }
user-not-found = User "{ $player }" was not found.

# Trust level names
trust-banned = Banned
trust-user = User
trust-admin = Admin
trust-developer = Developer
trust-server-owner = Server Owner

# Server reboot with virtual bots
confirm-reboot-server-bots-connected = Virtual bots are currently connected ({ $bots }). If you continue, they will be disconnected.


# Developer role
user-is-developer = { $player } مطور في PlayPalace.
promote-developer = ترقية إلى مطور
demote-developer = خفض من مطور
confirm-promote-developer = هل أنت متأكد من ترقية { $player } إلى مطور؟
confirm-demote-developer = هل أنت متأكد من خفض { $player } من مطور؟
promote-developer-announcement = تمت ترقية { $player } إلى مطور!
promote-developer-announcement-you = لقد تمت ترقيتك إلى مطور!
demote-developer-announcement = تم خفض { $player } من مطور.
demote-developer-announcement-you = لقد تم خفضك من مطور.
no-admins-to-promote-developer = لا يوجد مدراء متاحون للترقية إلى مطور.
no-developers-to-demote = لا يوجد مطورون متاحون للخفض.
promote-developer-unavailable = لا يمكن ترقية { $player } إلى مطور.
demote-developer-unavailable = لا يمكن خفض { $player } من مطور.

# Virtual bots (bring specific bots online)
virtual-bots-fill-localization-in-progress = أثناء عملية الترجمة، لا يمكنك جلب البوتات إلى الاتصال.
virtual-bots-bring-online = جلب بوت إلى الاتصال
virtual-bots-brought-online = تم جلب البوت الافتراضي { $name } إلى الاتصال.
virtual-bots-already-online = البوت الافتراضي { $name } متصل بالفعل.
virtual-bots-all-online = جميع البوتات الافتراضية متصلة بالفعل.
virtual-bots-take-offline = إخراج البوت من الاتصال
virtual-bots-taken-offline = تم إخراج البوت الافتراضي { $name } من الاتصال.
virtual-bots-already-offline = البوت الافتراضي { $name } غير متصل بالفعل.
virtual-bots-all-offline = جميع البوتات الافتراضية غير متصلة بالفعل.
# Virtual bot presence (server-side chat + session cadence)
virtual-bots-presence = Presence & Chat
virtual-bots-presence-status = Status
virtual-bots-presence-report = Presence: enabled { $enabled }, kill switch { $kill_switch }, quiet hours now { $in_quiet_hours }, chats sent { $chats_sent }, blocked { $chats_blocked }.
virtual-bots-presence-enable = Enable Presence
virtual-bots-presence-disable = Disable Presence
virtual-bots-presence-pause = Pause All Chatter
virtual-bots-presence-resume = Resume All Chatter
virtual-bots-presence-profiles = Profile Presence
virtual-bots-presence-enabled = Presence enabled.
virtual-bots-presence-disabled = Presence disabled.
virtual-bots-presence-paused = All bot chatter paused.
virtual-bots-presence-resumed = Bot chatter resumed.
virtual-bots-presence-profile-enabled = Presence enabled for profile { $profile }.
virtual-bots-presence-profile-disabled = Presence disabled for profile { $profile }.

# Cards Against Humanity mature-content notice
cah-content-notice = تحتوي هذه اللعبة على محتوى غير ناضج للغاية. لا يُنصح بها للاعبين دون سن 16 عامًا أو الحساسين لبعض المواضيع.
cah-keep-playing = متابعة اللعب
cah-go-back = عودة


# ===== Reload caches =====
reload-caches = Reload Caches
confirm-reload-caches = Force-reload localization and documents from disk? This rebuilds locale bundles from source.
reload-caches-done = Caches reloaded ({ $locales } locales, { $documents } documents).

# ===== Scheduled actions =====
scheduled-actions = Scheduled Actions
scheduled-actions-none = (no scheduled actions)
scheduled-actions-add = Add Action
scheduled-action-reboot = Reboot Server
scheduled-action-broadcast = Broadcast Announcement
scheduled-action-run-at = runs { $time }
scheduled-action-enabled = enabled
scheduled-action-disabled = disabled
repeating-every-minutes = repeating every { $minutes } minute(s)
one-shot = one-shot
scheduled-action-toggle = Toggle Enabled
scheduled-action-delete = Delete
scheduled-action-delete-confirm = Delete scheduled action #{ $id }? This cannot be undone.
scheduled-actions-message-prompt = Announcement message (sent to everyone online):
scheduled-actions-when-prompt = Run in how many minutes from now?
scheduled-actions-repeat-prompt = Repeat every how many minutes? (0 = once)
scheduled-actions-empty-message = The message cannot be empty.
scheduled-actions-invalid-number = Please enter a valid whole number.
scheduled-actions-summary-type = Type: { $type }. 
scheduled-actions-summary-when = Run in { $minutes } minute(s). 
scheduled-actions-summary-repeat = Repeat every { $minutes } minute(s).
scheduled-actions-created = Scheduled action created.
scheduled-actions-deleted = Scheduled action deleted.

pref-category-display = Display
pref-category-sounds = Sounds
pref-category-dice = Dice Behaviour
pref-category-gameplay = Gameplay
pref-set-play-turn-sound = Turn sound: { $status }
pref-desc-play-turn-sound = Play a sound when it becomes your turn
pref-changed-play-turn-sound = Turn sound { $status }.
pref-set-brief-announcements = Brief announcements: { $status }
pref-desc-brief-announcements = Use shorter announcements during gameplay instead of detailed commentary
pref-changed-brief-announcements = Brief announcements { $status }.
pref-set-clear-kept-on-roll = Clear kept dice when rolling: { $status }
pref-desc-clear-kept-on-roll = Automatically unkeep all dice after each roll
pref-changed-clear-kept-on-roll = Clear kept dice when rolling { $status }.
pref-set-dice-keeping-style = Dice keeping style: { $choice }
pref-desc-dice-keeping-style = How dice are selected for keeping
pref-select-dice-keeping-style = Select dice keeping style:
pref-changed-dice-keeping-style = Dice keeping style set to { $choice }.
pref-dice-keeping-style-playpalace = Dice indexes
pref-set-confirm-destructive-actions = Confirm destructive actions: { $status }
pref-desc-confirm-destructive-actions = Request confirmation when performing destructive actions like passing your turn
pref-changed-confirm-destructive-actions = Confirm destructive actions { $status }.
pref-back = Back
pref-reset-all = Reset all preferences to defaults
pref-reset-category = Reset { $category } to defaults
pref-reset-done = Preferences reset to defaults.
pref-per-game-for = { $game }: { $value }
pref-default = Default

pref-set-online-sound = Online sound: { $choice }
pref-changed-online-sound = Online sound set to { $choice }.
pref-set-offline-sound = Offline sound: { $choice }
pref-changed-offline-sound = Offline sound set to { $choice }.
pref-online-sound-default = Default
pref-online-sound-chime = Chime
pref-online-sound-alert = Alert
pref-offline-sound-default = Default
pref-offline-sound-chime = Chime
pref-offline-sound-alert = Alert

# Server freeze
freeze-server = تجميد الخادم
unfreeze-server = إلغاء تجميد الخادم
confirm-freeze-server = هل أنت متأكد من رغبتك في تجميد الخادم؟ لن يتمكن اللاعبون من فعل أي شيء حتى يقوم المشرف بإلغاء التجميد.
server-frozen = تم تجميد الخادم بواسطة مشرف. لا يمكن تنفيذ أي إجراءات حتى يتم إلغاء تجميد الخادم.
server-unfrozen = تم إلغاء تجميد الخادم. يمكن استئناف النشاط الطبيعي.
server-frozen-notice = الخادم مجمد حاليًا بواسطة مشرف. يرجى الانتظار.
