# PlayPalace 主界面消息 (简体中文)

# 游戏分类
category-card-games = 纸牌游戏
category-dice-games = 骰子游戏
category-board-games = 棋盘游戏
category-rb-play-center = RB Play Center
category-poker = 扑克
category-uncategorized = 未分类

# 菜单标题
main-menu-title = 主菜单
play-menu-title = 开始游戏
categories-menu-title = 游戏分类
tables-menu-title = 可用桌台

# 菜单项目
play = 开始游戏
view-active-tables = 查看活跃桌台
options = 设置
logout = 退出登录
back = 返回
create-table = 创建新桌台
join-as-player = 作为玩家加入
join-as-spectator = 作为观众加入
leave-table = 离开桌台
start-game = 开始游戏
add-bot = 添加机器人
remove-bot = 移除机器人
actions-menu = 操作菜单
save-table = 保存桌台
whose-turn = 轮到谁
whos-at-table = 桌上都有谁
check-scores = 查看分数
check-scores-detailed = 详细分数
check-game-options = 查看游戏选项
no-game-options = 没有游戏选项。

# 桌台消息
table-created = { $host } 创建了一个新的 { $game } 桌台。
table-joined = { $player } 加入了桌台。
table-left = { $player } 离开了桌台。
new-host = { $player } 现在是主持人。
waiting-for-players = 等待玩家中。当前 { $current }/{ $min } 最少，{ $max } 最多。
game-starting = 游戏开始！
table-listing = { $host } 的桌台 ({ $count } 位用户)
table-listing-one = { $host } 的桌台 ({ $count } 位用户)
table-listing-with = { $host } 的桌台 ({ $count } 位用户) 与 { $members }
table-listing-game = { $game }: { $host } 的桌台 ({ $count } 位用户)
table-listing-game-one = { $game }: { $host } 的桌台 ({ $count } 位用户)
table-listing-game-with = { $game }: { $host } 的桌台 ({ $count } 位用户) 与 { $members }
table-not-exists = 桌台已不存在。
table-full = 桌台已满。
player-replaced-by-bot = { $player } 离开，已由机器人替代。
player-took-over = { $player } 接管了机器人。
spectator-joined = 已作为观众加入 { $host } 的桌台。
table-no-players = 没有玩家。
table-players-one = { $count } 位玩家：{ $players }。
table-players-many = { $count } 位玩家：{ $players }。
table-spectators = 观众：{ $spectators }。

# 观众模式
spectate = 观战
now-playing = { $player } 现在参与游戏。
now-spectating = { $player } 现在观战。
spectator-left = { $player } 停止观战。

# 通用
welcome = 欢迎来到 PlayPalace！
goodbye = 再见！

# 用户在线状态公告
user-online = { $player } 上线了。
user-offline = { $player } 下线了。
online-users-none = 没有用户在线。
online-users-one = 1 位用户: { $users }
online-users-many = { $count } 位用户: { $users }

# 设置
language = 语言
language-option = 语言：{ $language }
language-changed = 语言已设置为 { $language }。

# 布尔选项状态
option-on = 开启
option-off = 关闭

# 声音选项
turn-sound-option = 回合提示音：{ $status }

# 骰子选项
clear-kept-option = 掷骰时清除保留的骰子：{ $status }
dice-keeping-style-option = 骰子保留风格：{ $style }
dice-keeping-style-changed = 骰子保留风格已设置为 { $style }。
dice-keeping-style-indexes = 骰子索引
dice-keeping-style-values = 骰子点数

# 机器人名称
cancel = 取消
no-bot-names-available = 没有可用的机器人名称。
select-bot-name = 选择机器人名称
enter-bot-name = 输入机器人名称
no-options-available = 没有可用选项。
no-scores-available = 没有可用分数。

# 保存/恢复
saved-tables = 已保存的桌台
no-saved-tables = 您没有已保存的桌台。
no-active-tables = 没有活跃的桌台。
restore-table = 恢复
delete-saved-table = 删除
saved-table-deleted = 已删除保存的桌台。
missing-players = 无法恢复：以下玩家不在线：{ $players }
table-restored = 桌台已恢复！所有玩家已转移。
table-saved-destroying = 桌台已保存！返回主菜单。
game-type-not-found = 游戏类型不存在。

# 排行榜
leaderboards = 排行榜
leaderboards-menu-title = 排行榜
leaderboards-select-game = 选择游戏查看排行榜
leaderboard-no-data = 此游戏暂无排行榜数据。

# 排行榜类型
leaderboard-type-wins = 胜利排行
leaderboard-type-rating = 技能评分
leaderboard-type-total-score = 总分排行
leaderboard-type-high-score = 最高分排行
leaderboard-type-games-played = 游戏场次排行
leaderboard-type-avg-points-per-turn = 平均每回合得分
leaderboard-type-best-single-turn = 单回合最高分
leaderboard-type-score-per-round = 每轮得分

# 排行榜标题
leaderboard-wins-header = { $game } - 胜利排行
leaderboard-total-score-header = { $game } - 总分排行
leaderboard-high-score-header = { $game } - 最高分排行
leaderboard-games-played-header = { $game } - 游戏场次排行
leaderboard-rating-header = { $game } - 技能评分
leaderboard-avg-points-header = { $game } - 平均每回合得分
leaderboard-best-turn-header = { $game } - 单回合最高分
leaderboard-score-per-round-header = { $game } - 每轮得分

# 排行榜条目
leaderboard-wins-entry = { $rank }：{ $player }，{ $wins }胜 { $losses }负，{ $percentage }%胜率
leaderboard-score-entry = { $rank }. { $player }：{ $value }
leaderboard-avg-entry = { $rank }. { $player }：{ $value } 平均
leaderboard-games-entry = { $rank }. { $player }：{ $value } 场

# 玩家统计
leaderboard-player-stats = 您的统计：{ $wins } 胜，{ $losses } 负（{ $percentage }% 胜率）
leaderboard-no-player-stats = 您还没有玩过这个游戏。

# 技能评分排行榜
leaderboard-no-ratings = 此游戏暂无评分数据。
leaderboard-rating-entry = { $rank }. { $player }：{ $rating } 评分（{ $mu } ± { $sigma }）
leaderboard-player-rating = 您的评分：{ $rating }（{ $mu } ± { $sigma }）
leaderboard-no-player-rating = 您还没有这个游戏的评分。

# 我的统计菜单
my-stats = 我的统计
my-stats-select-game = 选择游戏查看您的统计
my-stats-no-data = 您还没有玩过这个游戏。
my-stats-no-games = 您还没有玩过任何游戏。
my-stats-header = { $game } - 您的统计
my-stats-wins = 胜利：{ $value }
my-stats-losses = 失败：{ $value }
my-stats-winrate = 胜率：{ $value }%
my-stats-games-played = 游戏场次：{ $value }
my-stats-total-score = 总分：{ $value }
my-stats-high-score = 最高分：{ $value }
my-stats-rating = 技能评分：{ $value }（{ $mu } ± { $sigma }）
my-stats-no-rating = 暂无技能评分
my-stats-avg-per-turn = 平均每回合得分：{ $value }
my-stats-best-turn = 单回合最高分：{ $value }

# 预测系统
predict-outcomes = 预测结果
predict-header = 预测结果（按技能评分）
predict-entry = { $rank }. { $player }（评分：{ $rating }）
predict-entry-2p = { $rank }. { $player }（评分：{ $rating }，{ $probability }% 获胜概率）
predict-unavailable = 评分预测不可用。
predict-need-players = 需要至少2名人类玩家才能进行预测。
action-need-more-humans = 需要更多人类玩家。
confirm-leave-game = 确定要离开桌子吗？
confirm-yes = 是
confirm-no = 否

# 管理
administration = 管理
admin-menu-title = 管理

# 账户审批
account-approval = 账户审批
account-approval-menu-title = 账户审批
no-pending-accounts = 没有待审批的账户。
approve-account = 批准
decline-account = 拒绝
account-approved = { $player } 的账户已被批准。
account-declined = { $player } 的账户已被拒绝并删除。

# 等待审批（显示给未审批用户）
waiting-for-approval = 您的账户正在等待管理员审批。
account-approved-welcome = 您的账户已获批准！欢迎来到 PlayPalace！
account-declined-goodbye = 您的账户申请已被拒绝。
    原因：
account-banned = 您的账户已被封禁，无法访问。

# 登录错误
incorrect-username = 您输入的用户名不存在。
incorrect-password = 您输入的密码不正确。
already-logged-in = 此账户已登录。

# 凭据验证
credential-username-length = 用户名长度必须在 { $min } 到 { $max } 个字符之间。
credential-password-length = 密码长度必须在 { $min } 到 { $max } 个字符之间。

# 速率限制
rate-limit-login-ip = 此地址的登录尝试次数过多，请稍后再试。
rate-limit-login-user = 此用户名的登录失败次数过多，请稍后再试。
rate-limit-registration = 此地址的注册尝试次数过多，请稍后再试。
rate-limit-refresh = 此地址的刷新尝试次数过多，请稍后再试。

# 会话/认证错误
account-not-found = 未找到该账户。
session-expired = 会话已过期，请重新登录。
session-token-mismatch = 会话令牌与用户名不匹配。
refresh-token-expired = 刷新令牌已过期，请重新登录。
refresh-token-mismatch = 刷新令牌与用户名不匹配。

# 注册
registration-success = 注册成功！您的账户正在等待审批。
registration-username-taken = 该用户名已被占用，请选择其他用户名。

# 偏好设置回退
pref-invalid-value = 选择无效，已使用默认值。

# 拒绝原因
decline-reason-prompt = 请输入拒绝原因（或按Escape键取消）：
account-action-empty-reason = 未提供原因。

# 账户请求的管理员通知
account-request = 账户请求
account-action = 账户操作已完成

# 管理员升级/降级
promote-admin = 升级为管理员
demote-admin = 降级管理员
promote-admin-menu-title = 升级为管理员
demote-admin-menu-title = 降级管理员
no-users-to-promote = 没有可升级的用户。
no-admins-to-demote = 没有可降级的管理员。
confirm-promote = 确定要将 { $player } 升级为管理员吗？
confirm-demote = 确定要将 { $player } 从管理员降级吗？
broadcast-to-all = 向所有用户宣布
broadcast-to-admins = 仅向管理员宣布
broadcast-to-nobody = 静默（不宣布）
promote-announcement = { $player } 已被升级为管理员！
promote-announcement-you = 您已被升级为管理员！
demote-announcement = { $player } 已被降级。
demote-announcement-you = 您已被降级。
not-admin-anymore = 您已不再是管理员，无法执行此操作。
not-server-owner = 只有服务器所有者才能执行此操作。

# 服务器所有权转移
transfer-ownership = 转移所有权
transfer-ownership-menu-title = 转移所有权
no-admins-for-transfer = 没有可转移所有权的管理员。
confirm-transfer-ownership = 确定要将服务器所有权转移给 { $player } 吗？您将被降级为管理员。
transfer-ownership-announcement = { $player } 现在是 Play Palace 服务器的所有者！
transfer-ownership-announcement-you = 您现在是 Play Palace 服务器的所有者！

# 用户封禁
ban-user = 封禁用户
unban-user = 解封用户
no-users-to-ban = 没有可封禁的用户。
no-users-to-unban = 没有被封禁的用户可解封。
confirm-ban = 确定要封禁 { $player } 吗？
confirm-unban = 确定要解封 { $player } 吗？
ban-reason-prompt = 输入封禁原因（可选）：
unban-reason-prompt = 输入解封原因（可选）：
user-banned = { $player } 已被封禁。
user-unbanned = { $player } 已被解封。
you-have-been-banned = 您已被此服务器封禁。
    原因：
you-have-been-unbanned = 您已被此服务器解封。
    原因：
virtual-bots-guided-overview = Guided Tables
virtual-bots-groups-overview = Bot Groups
virtual-bots-profiles-overview = Profiles
virtual-bots-guided-header = Guided tables: { $count } rule(s). Allocation: { $allocation }, fallback: { $fallback }, default profile: { $default_profile }.
virtual-bots-guided-empty = No guided table rules are configured.
virtual-bots-guided-status-active = active
virtual-bots-guided-status-inactive = inactive
virtual-bots-guided-table-linked = linked to table { $table_id } (host { $host }, players { $players }, humans { $humans })
virtual-bots-guided-table-stale = table { $table_id } missing on server
virtual-bots-guided-table-unassigned = no table is currently tracked
virtual-bots-guided-next-change = next change in { $ticks } ticks
virtual-bots-guided-no-schedule = no scheduling window
virtual-bots-guided-warning = ⚠ underfilled
virtual-bots-guided-line = { $table }: game { $game }, priority { $priority }, bots { $assigned } (min { $min_bots }, max { $max_bots }), waiting { $waiting }, unavailable { $unavailable }, status { $status }, profile { $profile }, groups { $groups }. { $table_state }. { $next_change } { $warning_text }
virtual-bots-groups-header = Bot groups: { $count } tag(s), { $bots } configured bots.
virtual-bots-groups-empty = No bot groups are defined.
virtual-bots-groups-line = { $group }: profile { $profile }, bots { $total } (online { $online }, waiting { $waiting }, in-game { $in_game }, offline { $offline }), rules { $rules }.
virtual-bots-groups-no-rules = none
virtual-bots-no-profile = default
virtual-bots-profile-inherit-default = inherits default profile
virtual-bots-profiles-header = Profiles: { $count } defined (default: { $default_profile }).
virtual-bots-profiles-empty = No profiles are defined.
virtual-bots-profiles-line = { $profile } ({ $bot_count } bots) overrides: { $overrides }.
virtual-bots-profiles-no-overrides = inherits base configuration
virtual-bots-add = Add Virtual Bot
virtual-bots-edit = Edit Virtual Bot
virtual-bots-delete = Delete Virtual Bot
virtual-bots-add-prompt = Enter a name for the new virtual bot:
virtual-bots-rename-prompt = Enter a new name for { $name }:
virtual-bots-rename = Rename
virtual-bots-change-profile = Change Profile
virtual-bots-added = Virtual bot { $name } added and brought online.
virtual-bots-renamed = Virtual bot renamed from { $old_name } to { $new_name }.
virtual-bots-profile-changed = Virtual bot { $name } profile changed to { $profile }.
virtual-bots-deleted = Virtual bot { $name } deleted. { $tables } table(s) closed.
virtual-bots-name-taken = A virtual bot with that name already exists.
virtual-bots-name-invalid = That name is not valid.
virtual-bots-no-bots = There are no virtual bots to manage.
virtual-bots-delete-confirm = Delete virtual bot { $name }? This will close any table it is in.
virtual-bots-no-profiles = No profiles are available.

localization-in-progress-try-again = 本地化正在进行中。请在一分钟后重试。

# Server reboot
admin-reboot-server = 重新启动服务器
confirm-reboot-server = 您确定要重新启动服务器吗？ 所有玩家将被断开并重新连接。
server-reboot-warning = 服务器将在 { $seconds } 秒后重新启动。
server-restarting = 服务器正在重新启动。 您将自动重新连接。
server-reboot-failed = 无法重新启动服务器。 请重试。
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
user-is-developer = { $player } 是 PlayPalace 的开发者。
promote-developer = 升级为开发者
demote-developer = 降级开发者
confirm-promote-developer = 确定要将 { $player } 升级为开发者吗？
confirm-demote-developer = 确定要将 { $player } 从开发者降级吗？
promote-developer-announcement = { $player } 已被升级为开发者！
promote-developer-announcement-you = 您已被升级为开发者！
demote-developer-announcement = { $player } 已从开发者降级。
demote-developer-announcement-you = 您已从开发者降级。
no-admins-to-promote-developer = 没有可升级为开发者的管理员。
no-developers-to-demote = 没有可降级的开发者。
promote-developer-unavailable = 无法将 { $player } 升级为开发者。
demote-developer-unavailable = 无法将 { $player } 从开发者降级。

# Virtual bots (bring specific bots online)
virtual-bots-fill-localization-in-progress = 在本地化进行中时，您无法让机器人上线。
virtual-bots-bring-online = 让机器人上线
virtual-bots-brought-online = 虚拟机器人 { $name } 已上线。
virtual-bots-already-online = 虚拟机器人 { $name } 已经在线。
virtual-bots-all-online = 所有虚拟机器人均已在线。
virtual-bots-take-offline = 让机器人下线
virtual-bots-taken-offline = 虚拟机器人 { $name } 已下线。
virtual-bots-already-offline = 虚拟机器人 { $name } 已离线。
virtual-bots-all-offline = 所有虚拟机器人均已离线。
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
cah-content-notice = 此游戏包含非常不成熟的内容。不建议未满 16 岁的玩家或对某些话题敏感的人游玩。
cah-keep-playing = 继续游玩
cah-go-back = 返回


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

