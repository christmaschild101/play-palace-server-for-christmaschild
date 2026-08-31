# PlayPalace için ana UI mesajları

# Oyun kategorileri
category-card-games = Kart Oyunları
category-dice-games = Zar Oyunları
category-rb-play-center = RB Oyun Merkezi
category-poker = Poker
category-uncategorized = Kategorisiz

# Menü başlıkları
main-menu-title = Ana Menü
play-menu-title = Oyna
categories-menu-title = Oyun Kategorileri
tables-menu-title = Mevcut Masalar

# Menü öğeleri
play = Oyna
view-active-tables = Aktif masaları görüntüle
options = Seçenekler
logout = Çıkış yap
back = Geri
go-back = Geri dön
context-menu = Bağlam menüsü.
no-actions-available = Mevcut eylem yok.
create-table = Yeni masa oluştur
join-as-player = Oyuncu olarak katıl
join-as-spectator = İzleyici olarak katıl
leave-table = Masadan ayrıl
start-game = Oyunu başlat
add-bot = Bot ekle
remove-bot = Bot kaldır
actions-menu = Eylemler menüsü
save-table = Masayı kaydet
whose-turn = Kimin turu
whos-at-table = Masada kim var
check-scores = Skorları kontrol et
check-scores-detailed = Detaylı skorlar
check-game-options = Oyun seçeneklerini kontrol et
no-game-options = Oyun seçeneği yok.

# Tur mesajları
game-player-skipped = { $player } atlanıyor.

# Masa mesajları
table-created = { $host } yeni bir { $game } masası oluşturdu.
table-joined = { $player } masaya katıldı.
table-left = { $player } masadan ayrıldı.
new-host = { $player } artık ev sahibi.
waiting-for-players = Oyuncular bekleniyor. { $min } min, { $max } maks.
game-starting = Oyun başlıyor!
table-listing = { $host }'ın masası ({ $count } kullanıcı)
table-listing-one = { $host }'ın masası ({ $count } kullanıcı)
table-listing-with = { $host }'ın masası ({ $count } kullanıcı) { $members } ile
table-listing-game = { $game }: { $host }'ın masası ({ $count } kullanıcı)
table-listing-game-one = { $game }: { $host }'ın masası ({ $count } kullanıcı)
table-listing-game-with = { $game }: { $host }'ın masası ({ $count } kullanıcı) { $members } ile
table-not-exists = Masa artık mevcut değil.
table-full = Masa dolu.
player-replaced-by-bot = { $player } ayrıldı ve yerine bot geldi.
player-took-over = { $player } botun yerini aldı.
spectator-joined = İzleyici olarak { $host }'ın masasına katıldı.

# İzleyici modu
spectate = İzle
now-playing = { $player } şimdi oynuyor.
now-spectating = { $player } şimdi izliyor.
spectator-left = { $player } izlemeyi bıraktı.

# Genel
welcome = PlayPalace'a hoş geldiniz!
goodbye = Hoşçakalın!

# Kullanıcı varlığı duyuruları
user-online = { $player } çevrimiçi oldu.
user-offline = { $player } çevrimdışı oldu.
user-is-admin = { $player } PlayPalace yöneticisidir.
user-is-server-owner = { $player } PlayPalace sunucu sahibidir.
online-users-none = Çevrimiçi kullanıcı yok.
online-users-one = 1 kullanıcı: { $users }
online-users-many = { $count } kullanıcı: { $users }
online-user-not-in-game = Oyunda değil
online-user-waiting-approval = Onay bekliyor

# Seçenekler
language = Dil
language-option = Dil: { $language }
language-changed = Dil { $language } olarak ayarlandı.

# Boolean seçenek durumları
option-on = Açık
option-off = Kapalı

# Ses seçenekleri
turn-sound-option = Tur sesi: { $status }

# Zar seçenekleri
clear-kept-option = Atarken tutulan zarları temizle: { $status }
dice-keeping-style-option = Zar tutma stili: { $style }
dice-keeping-style-changed = Zar tutma stili { $style } olarak ayarlandı.
dice-keeping-style-indexes = Zar indeksleri
dice-keeping-style-values = Zar değerleri

# Bot isimleri
cancel = İptal
no-bot-names-available = Mevcut bot ismi yok.
select-bot-name = Bot için bir isim seç
enter-bot-name = Bot ismini girin
no-options-available = Mevcut seçenek yok.
no-scores-available = Mevcut skor yok.

# Süre tahmini
estimate-duration = Süreyi tahmin et
estimate-computing = Tahmini oyun süresi hesaplanıyor...
estimate-result = Bot ortalaması: { $bot_time } (± { $std_dev }). { $outlier_info }Tahmini insan süresi: { $human_time }.
estimate-error = Süre tahmin edilemedi.
estimate-already-running = Süre tahmini zaten devam ediyor.

# Kaydet/Geri Yükle
saved-tables = Kaydedilen Masalar
no-saved-tables = Kaydedilmiş masan yok.
no-active-tables = Aktif masa yok.
restore-table = Geri yükle
delete-saved-table = Sil
saved-table-deleted = Kaydedilmiş masa silindi.
missing-players = Geri yüklenemiyor: bu oyuncular mevcut değil: { $players }
table-restored = Masa geri yüklendi! Tüm oyuncular aktarıldı.
table-saved-destroying = Masa kaydedildi! Ana menüye dönülüyor.
game-type-not-found = Oyun türü artık mevcut değil.

# Eylem devre dışı nedenleri
action-not-your-turn = Senin turun değil.
action-not-playing = Oyun henüz başlamadı.
action-spectator = İzleyiciler bunu yapamaz.
action-not-host = Bunu sadece ev sahibi yapabilir.
action-game-in-progress = Oyun devam ederken bunu yapamazsın.
action-need-more-players = Başlamak için daha fazla oyuncu gerekli.
action-table-full = Masa dolu.
action-no-bots = Kaldırılacak bot yok.
action-bots-cannot = Botlar bunu yapamaz.
action-no-scores = Henüz mevcut skor yok.

# Zar eylemleri
dice-not-rolled = Henüz atmadın.
dice-locked = Bu zar kilitli.
dice-no-dice = Mevcut zar yok.

# Oyun eylemleri
game-turn-start = { $player }'ın turu.
game-no-turn = Şu anda kimsenin turu değil.
table-no-players = Oyuncu yok.
table-players-one = { $count } oyuncu: { $players }.
table-players-many = { $count } oyuncu: { $players }.
table-spectators = İzleyiciler: { $spectators }.
game-leave = Ayrıl
game-over = Oyun Bitti
game-final-scores = Final Skorları
game-points = { $count } { $count ->
    [one] puan
   *[other] puan
}
play = Oyna

# Lider tabloları
leaderboards = Lider Tabloları
leaderboards-menu-title = Lider Tabloları
leaderboards-select-game = Lider tablosunu görüntülemek için bir oyun seç
leaderboard-no-data = Bu oyun için henüz lider tablosu verisi yok.

# Lider tablosu türleri
leaderboard-type-wins = Galibiyet Liderleri
leaderboard-type-rating = Yetenek Puanı
leaderboard-type-total-score = Toplam Skor
leaderboard-type-high-score = Yüksek Skor
leaderboard-type-games-played = Oynanan Oyunlar
leaderboard-type-avg-points-per-turn = Tur Başına Ort. Puan
leaderboard-type-best-single-turn = En İyi Tek Tur
leaderboard-type-score-per-round = Raund Başına Skor

# Lider tablosu başlıkları
leaderboard-wins-header = { $game } - Galibiyet Liderleri
leaderboard-total-score-header = { $game } - Toplam Skor
leaderboard-high-score-header = { $game } - Yüksek Skor
leaderboard-games-played-header = { $game } - Oynanan Oyunlar
leaderboard-rating-header = { $game } - Yetenek Puanları
leaderboard-avg-points-header = { $game } - Tur Başına Ort. Puan
leaderboard-best-turn-header = { $game } - En İyi Tek Tur
leaderboard-score-per-round-header = { $game } - Raund Başına Skor

# Lider tablosu girdileri
leaderboard-wins-entry = { $rank }: { $player }, { $wins } { $wins ->
    [one] galibiyet
   *[other] galibiyet
} { $losses } { $losses ->
    [one] mağlubiyet
   *[other] mağlubiyet
}, %{ $percentage } kazanma oranı
leaderboard-score-entry = { $rank }. { $player }: { $value }
leaderboard-avg-entry = { $rank }. { $player }: { $value } ort
leaderboard-games-entry = { $rank }. { $player }: { $value } oyun

# Oyuncu istatistikleri
leaderboard-player-stats = Senin istatistiğin: { $wins } galibiyet, { $losses } mağlubiyet (%{ $percentage } kazanma oranı)
leaderboard-no-player-stats = Bu oyunu henüz oynamadın.

# Yetenek puanı lider tablosu
leaderboard-no-ratings = Bu oyun için henüz puan verisi yok.
leaderboard-rating-entry = { $rank }. { $player }: { $rating } puan ({ $mu } ± { $sigma })
leaderboard-player-rating = Senin puanın: { $rating } ({ $mu } ± { $sigma })
leaderboard-no-player-rating = Bu oyun için henüz bir puanın yok.

# İstatistiklerim menüsü
my-stats = İstatistiklerim
my-stats-select-game = İstatistiklerini görüntülemek için bir oyun seç
my-stats-no-data = Bu oyunu henüz oynamadın.
my-stats-no-games = Henüz hiç oyun oynamadın.
my-stats-header = { $game } - Senin İstatistiklerin
my-stats-wins = Galibiyetler: { $value }
my-stats-losses = Mağlubiyetler: { $value }
my-stats-winrate = Kazanma oranı: %{ $value }
my-stats-games-played = Oynanan oyunlar: { $value }
my-stats-total-score = Toplam skor: { $value }
my-stats-high-score = Yüksek skor: { $value }
my-stats-rating = Yetenek puanı: { $value } ({ $mu } ± { $sigma })
my-stats-no-rating = Henüz yetenek puanı yok
my-stats-avg-per-turn = Tur başına ort. puan: { $value }
my-stats-best-turn = En iyi tek tur: { $value }

# Tahmin sistemi
predict-outcomes = Sonuçları tahmin et
predict-header = Tahmin Edilen Sonuçlar (yetenek puanına göre)
predict-entry = { $rank }. { $player } (puan: { $rating })
predict-entry-2p = { $rank }. { $player } (puan: { $rating }, %{ $probability } kazanma şansı)
predict-unavailable = Puan tahminleri mevcut değil.
predict-need-players = Tahminler için en az 2 insan oyuncu gerekli.
action-need-more-humans = Daha fazla insan oyuncu gerekli.
confirm-leave-game = Masadan ayrılmak istediğinden emin misin?
confirm-yes = Evet
confirm-no = Hayır

# Yönetim
administration = Yönetim
admin-menu-title = Yönetim

# Hesap onayı
account-approval = Hesap Onayı
account-approval-menu-title = Hesap Onayı
no-pending-accounts = Bekleyen hesap yok.
approve-account = Onayla
decline-account = Reddet
account-approved = { $player }'ın hesabı onaylandı.
account-declined = { $player }'ın hesabı reddedildi ve silindi.

# Onay bekleniyor (onaylanmamış kullanıcılara gösterilen)
waiting-for-approval = Hesabınız bir yönetici tarafından onaylanmayı bekliyor.
account-approved-welcome = Hesabınız onaylandı! PlayPalace'a hoş geldiniz!
account-declined-goodbye = Hesap isteğiniz reddedildi.
    Sebep:
account-banned = Hesabınız yasaklandı ve erişilemez.

# Giriş hataları
incorrect-username = Girdiğiniz kullanıcı adı mevcut değil.
incorrect-password = Girdiğiniz şifre yanlış.
already-logged-in = Bu hesap zaten giriş yapmış.

# Credential validation
credential-username-length = Kullanıcı adı { $min } ile { $max } karakter arasında olmalıdır.
credential-password-length = Şifre { $min } ile { $max } karakter arasında olmalıdır.

# Rate limiting
rate-limit-login-ip = Bu adresten çok fazla giriş denemesi yapıldı. Lütfen bekleyip tekrar deneyin.
rate-limit-login-user = Bu kullanıcı adı için çok fazla başarısız giriş denemesi yapıldı. Lütfen bekleyip tekrar deneyin.
rate-limit-registration = Bu adresten çok fazla kayıt denemesi yapıldı. Lütfen bekleyip tekrar deneyin.
rate-limit-refresh = Bu adresten çok fazla yenileme denemesi yapıldı. Lütfen bekleyip tekrar deneyin.

# Session/auth errors
account-not-found = Hesap bulunamadı.
session-expired = Oturum süresi doldu. Lütfen tekrar giriş yapın.
session-token-mismatch = Oturum tokeni kullanıcı adıyla eşleşmiyor.
refresh-token-expired = Yenileme tokeni süresi doldu. Lütfen tekrar giriş yapın.
refresh-token-mismatch = Yenileme tokeni kullanıcı adıyla eşleşmiyor.

# Registration
registration-success = Kayıt başarılı! Hesabınız onay bekliyor.
registration-username-taken = Bu kullanıcı adı zaten alınmış. Lütfen farklı bir kullanıcı adı seçin.

# Preference fallback
pref-invalid-value = Geçersiz seçim, varsayılan kullanılıyor.

# Reddetme nedeni
decline-reason-prompt = Reddetme sebebini girin (veya iptal etmek için Escape'e basın):
account-action-empty-reason = Sebep verilmedi.

# Hesap istekleri için yönetici bildirimleri
account-request = hesap isteği
account-action = hesap eylemi alındı

# Yönetici terfi/düşürme
promote-admin = Yönetici Yükselt
demote-admin = Yöneticiliği Düşür
promote-admin-menu-title = Yönetici Yükselt
demote-admin-menu-title = Yöneticiliği Düşür
no-users-to-promote = Yükseltilecek kullanıcı yok.
no-admins-to-demote = Düşürülecek yönetici yok.
confirm-promote = { $player }'ı yöneticiliğe yükseltmek istediğinden emin misin?
confirm-demote = { $player }'ı yöneticiden düşürmek istediğinden emin misin?
broadcast-to-all = Tüm kullanıcılara duyur
broadcast-to-admins = Sadece yöneticilere duyur
broadcast-to-nobody = Sessiz (duyuru yok)
promote-announcement = { $player } yöneticiliğe yükseltildi!
promote-announcement-you = Yöneticiliğe yükseltildin!
demote-announcement = { $player } yöneticiden düşürüldü.
demote-announcement-you = Yöneticiden düşürüldün.
not-admin-anymore = Artık yönetici değilsin ve bu eylemi gerçekleştiremezsin.
not-server-owner = Bu eylemi sadece sunucu sahibi gerçekleştirebilir.

# Sunucu sahipliği transferi
transfer-ownership = Sahipliği Aktar
transfer-ownership-menu-title = Sahipliği Aktar
no-admins-for-transfer = Sahipliği aktarılacak yönetici yok.
confirm-transfer-ownership = Sunucu sahipliğini { $player }'a aktarmak istediğinden emin misin? Yöneticiliğe düşürüleceksin.
transfer-ownership-announcement = { $player } artık Play Palace sunucu sahibi!
transfer-ownership-announcement-you = Artık Play Palace sunucu sahibisin!

# Kullanıcı yasaklama
ban-user = Kullanıcıyı Yasakla
unban-user = Yasağı Kaldır
no-users-to-ban = Yasaklanacak kullanıcı yok.
no-users-to-unban = Yasağı kaldırılacak kullanıcı yok.
confirm-ban = { $player }'ı yasaklamak istediğinden emin misin?
confirm-unban = { $player }'ın yasağını kaldırmak istediğinden emin misin?
ban-reason-prompt = Yasaklama sebebini girin (isteğe bağlı):
unban-reason-prompt = Yasak kaldırma sebebini girin (isteğe bağlı):
user-banned = { $player } yasaklandı.
user-unbanned = { $player }'ın yasağı kaldırıldı.
you-have-been-banned = Bu sunucudan yasaklandın.
    Sebep:
you-have-been-unbanned = Bu sunucudan yasağın kaldırıldı.
    Sebep:
ban-no-reason = Sebep verilmedi.

# Sanal botlar (sadece sunucu sahibi)
virtual-bots = Sanal Botlar
virtual-bots-fill = Sunucuyu Doldur
virtual-bots-clear = Tüm Botları Temizle
virtual-bots-status = Durum
virtual-bots-clear-confirm = Tüm sanal botları temizlemek istediğinden emin misin? Bu aynı zamanda içinde bulundukları masaları da yok edecek.
virtual-bots-not-available = Sanal botlar mevcut değil.
virtual-bots-filled = { $added } sanal bot eklendi. { $online } şimdi çevrimiçi.
virtual-bots-already-filled = Yapılandırmadaki tüm sanal botlar zaten aktif.
virtual-bots-cleared = { $bots } sanal bot temizlendi ve { $tables } { $tables ->
    [one] masa
   *[other] masa
} yok edildi.
virtual-bot-table-closed = Masa yönetici tarafından kapatıldı.
virtual-bots-none-to-clear = Temizlenecek sanal bot yok.
virtual-bots-status-report = Sanal Botlar: { $total } toplam, { $online } çevrimiçi, { $offline } çevrimdışı, { $in_game } oyunda.
virtual-bots-guided-overview = Yönlendirilmiş Masalar
virtual-bots-groups-overview = Bot Grupları
virtual-bots-profiles-overview = Profiller
virtual-bots-guided-header = Yönlendirilmiş masalar: { $count } kural. Tahsis: { $allocation }, yedek: { $fallback }, varsayılan profil: { $default_profile }.
virtual-bots-guided-empty = Yönlendirilmiş masa kuralı yapılandırılmamış.
virtual-bots-guided-status-active = aktif
virtual-bots-guided-status-inactive = pasif
virtual-bots-guided-table-linked = masa { $table_id }'e bağlı (ev sahibi { $host }, oyuncular { $players }, insanlar { $humans })
virtual-bots-guided-table-stale = masa { $table_id } sunucuda eksik
virtual-bots-guided-table-unassigned = şu anda izlenen masa yok
virtual-bots-guided-next-change = { $ticks } tik sonra sonraki değişiklik
virtual-bots-guided-no-schedule = zamanlama penceresi yok
virtual-bots-guided-warning = ⚠ yetersiz doldurulmuş
virtual-bots-guided-line = { $table }: oyun { $game }, öncelik { $priority }, botlar { $assigned } (min { $min_bots }, maks { $max_bots }), bekliyor { $waiting }, mevcut değil { $unavailable }, durum { $status }, profil { $profile }, gruplar { $groups }. { $table_state }. { $next_change } { $warning_text }
virtual-bots-groups-header = Bot grupları: { $count } etiket, { $bots } yapılandırılmış bot.
virtual-bots-groups-empty = Bot grubu tanımlanmamış.
virtual-bots-groups-line = { $group }: profil { $profile }, botlar { $total } (çevrimiçi { $online }, bekliyor { $waiting }, oyunda { $in_game }, çevrimdışı { $offline }), kurallar { $rules }.
virtual-bots-groups-no-rules = yok
virtual-bots-no-profile = varsayılan
virtual-bots-profile-inherit-default = varsayılan profili miras alır
virtual-bots-profiles-header = Profiller: { $count } tanımlı (varsayılan: { $default_profile }).
virtual-bots-profiles-empty = Profil tanımlanmamış.
virtual-bots-profiles-line = { $profile } ({ $bot_count } bot) geçersiz kılmalar: { $overrides }.
virtual-bots-profiles-no-overrides = temel yapılandırmayı miras alır
virtual-bots-add = Sanal Bot Ekle
virtual-bots-edit = Sanal Botu Düzenle
virtual-bots-delete = Sanal Botu Sil
virtual-bots-add-prompt = Yeni sanal bot için bir ad girin:
virtual-bots-rename-prompt = { $name } için yeni bir ad girin:
virtual-bots-rename = Yeniden Adlandır
virtual-bots-change-profile = Profili Değiştir
virtual-bots-added = Sanal bot { $name } eklendi ve çevrimiçi yapıldı.
virtual-bots-renamed = Sanal bot { $old_name } adından { $new_name } adına yeniden adlandırıldı.
virtual-bots-profile-changed = Sanal bot { $name } profili { $profile } olarak değiştirildi.
virtual-bots-deleted = Sanal bot { $name } silindi. { $tables } masa kapatıldı.
virtual-bots-name-taken = Bu ada sahip bir sanal bot zaten var.
virtual-bots-name-invalid = Bu ad geçerli değil.
virtual-bots-no-bots = Yönetilecek sanal bot yok.
virtual-bots-delete-confirm = Sanal bot { $name } silinsin mi? Bu, bulunduğu masayı kapatır.
virtual-bots-no-profiles = Kullanılabilir profil yok.

localization-in-progress-try-again = Yerelleştirme sürüyor. Lütfen bir dakika sonra tekrar deneyin.

# Server reboot
admin-reboot-server = Sunucuyu yeniden başlat
confirm-reboot-server = Sunucuyu yeniden başlatmak istediğinizden emin misiniz? Tüm oyuncular bağlantısı kesilip yeniden bağlanacaktır.
server-reboot-warning = Sunucu { $seconds } saniye içinde yeniden başlatılacak.
server-restarting = Sunucu yeniden başlatılıyor. Otomatik olarak yeniden bağlanacaksınız.
server-reboot-failed = Sunucu yeniden başlatılamadı. Lütfen tekrar deneyin.
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
user-is-developer = { $player }, PlayPalace'ın bir geliştiricisidir.
promote-developer = Geliştiriciye Terfi Et
demote-developer = Geliştiriciden Düşür
confirm-promote-developer = { $player } kullanıcısını geliştiriciye terfi ettirmek istediğinize emin misiniz?
confirm-demote-developer = { $player } kullanıcısını geliştiriciden düşürmek istediğinize emin misiniz?
promote-developer-announcement = { $player } geliştiriciye terfi ettirildi!
promote-developer-announcement-you = Geliştiriciye terfi ettirildiniz!
demote-developer-announcement = { $player } geliştiriciden düşürüldü.
demote-developer-announcement-you = Geliştiriciden düşürüldünüz.
no-admins-to-promote-developer = Geliştiriciye terfi ettirilecek yönetici yok.
no-developers-to-demote = Düşürülecek geliştirici yok.
promote-developer-unavailable = { $player } geliştiriciye terfi ettirilemez.
demote-developer-unavailable = { $player } geliştiriciden düşürülemez.

# Virtual bots (bring specific bots online)
virtual-bots-fill-localization-in-progress = Yerelleştirme sürerken botları çevrimiçi duruma getiremezsiniz.
virtual-bots-bring-online = Botu çevrimiçi yap
virtual-bots-brought-online = Sanal bot { $name } çevrimiçi duruma getirildi.
virtual-bots-already-online = Sanal bot { $name } zaten çevrimiçi.
virtual-bots-all-online = Tüm sanal botlar zaten çevrimiçi.
virtual-bots-take-offline = Botu çevrimdışı yap
virtual-bots-taken-offline = Sanal bot { $name } çevrimdışı yapıldı.
virtual-bots-already-offline = Sanal bot { $name } zaten çevrimdışı.
virtual-bots-all-offline = Tüm sanal botlar zaten çevrimdışı.
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
cah-content-notice = Bu oyun çok olgunlaşmamış içerik içerir. 16 yaşın altındaki oyunculara veya belirli konulara duyarlı kişilere önerilmez.
cah-keep-playing = Oynamaya devam et
cah-go-back = Geri


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

