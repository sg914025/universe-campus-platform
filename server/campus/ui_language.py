import json
import re
from html import escape, unescape
from pathlib import Path

LANGUAGES = {'zh': '中文', 'en': 'English', 'ru': 'Русский', 'ja': '日本語'}

# Interface copy only: posts, patient records and AI output are never rewritten.
ROWS = [
('总管理员','Super administrator','Главный администратор'),('管理账号','Staff accounts','Учётные записи сотрудников'),('创建管理账号','Create a staff account','Создать учётную запись сотрудника'),('创建账号','Create account','Создать учётную запись'),('已有管理账号','Staff accounts','Учётные записи сотрудников'),('暂无管理账号','No staff accounts','Нет учётных записей сотрудников'),('姓名','Full name','Имя'),('确认密码','Confirm password','Подтвердите пароль'),('管理身份','Staff role','Роль сотрудника'),('医生','Doctor','Врач'),('所属科室','Department','Отделение'),('请选择科室','Select a department','Выберите отделение'),('创建医生时必须选择科室；其他管理员无需选择。','Required for doctors; not needed for other administrators.','Обязательно для врачей; другим администраторам не требуется.'),('创建医生账号必须选择科室。','Select a department for the doctor.','Выберите отделение врача.'),('该账号已存在，请更换账号。','This username already exists. Choose another.','Это имя пользователя уже занято. Выберите другое.'),('管理账号已创建，可从对应身份入口登录。','Staff account created. Use the matching role to sign in.','Учётная запись создана. Выберите соответствующую роль для входа.'),('这里只能创建三类业务账号，不会授予总管理员或系统配置权限。','Only the three service roles can be created here. Super administrator and system configuration access are not granted.','Здесь создаются только три служебные роли. Права главного администратора и настройки системы не предоставляются.'),('创建医生、论坛 / 跑腿管理员和预约管理员账号，分配对应权限。','Create doctor, forum / errands and booking accounts with their respective permissions.','Создавайте учётные записи врачей, администраторов форума и поручений, а также бронирований с соответствующими правами.'),('启用','Active','Активна'),('停用','Inactive','Неактивна'),

('校园生活站','Campus life hub','Центр жизни кампуса'),
('寰校通 UniVerse','寰校通 UniVerse','寰校通 UniVerse'),
('校园广场','Campus forum','Форум кампуса'),('校园跑腿','Campus errands','Поручения'),('AI 导诊','AI health guide','ИИ-помощник по здоровью'),('场地预约','Space booking','Бронирование'),
('管理员登录','Staff sign-in','Вход для сотрудников'),('管理入口','Staff portal','Портал сотрудников'),('选择管理身份','Choose your workspace','Выберите рабочий раздел'),
('请选择对应身份登录，账号权限由系统管理员分配。','Choose a role to sign in. Access is assigned by the system administrator.','Выберите роль для входа. Права назначает системный администратор.'),
('医生登录','Doctor sign-in','Вход для врача'),('论坛 / 跑腿管理员','Forum / errands administrator','Администратор форума и поручений'),('预约管理员','Booking administrator','Администратор бронирований'),
('查看本科室咨询、核实 AI 整理结果并参与会诊。','Review department cases, verify AI summaries and join consultations.','Просматривайте обращения своего отделения, проверяйте сводки ИИ и участвуйте в консилиумах.'),
('审核论坛内容、处理跑腿订单与用户咨询。','Moderate forum content, manage errands and respond to enquiries.','Модерируйте форум, управляйте поручениями и отвечайте на обращения.'),
('维护校园场地、开放状态并查看预约记录。','Maintain campus spaces, availability and booking records.','Управляйте площадками, их доступностью и записями бронирования.'),
('进入工作台','Open workspace','Открыть рабочий раздел'),('使用此身份登录','Sign in with this role','Войти с этой ролью'),('已有账号可继续使用，普通校园账号不能进入管理后台。','Existing staff accounts still work. Student accounts do not grant staff access.','Существующие учётные записи сотрудников продолжают действовать. Обычная учётная запись не даёт доступа к управлению.'),
('← 返回校园主页','← Campus home','← На главную кампуса'),('返回校园主页','Campus home','На главную кампуса'),('校园主页','Campus home','Главная кампуса'),
('← 选择其他管理身份','← Choose another role','← Выбрать другую роль'),('账号','Username','Имя пользователя'),('密码','Password','Пароль'),
('请输入账号','Enter username','Введите имя пользователя'),('请输入密码','Enter password','Введите пароль'),('显示','Show','Показать'),('隐藏','Hide','Скрыть'),
('登录工作台','Sign in to workspace','Войти в рабочий раздел'),('退出管理登录','Sign out of staff account','Выйти из учётной записи сотрудника'),
('当前已登录。可返回身份选择页进入已有权限的工作台，或使用其他管理账号登录。','You are signed in. Return to choose an available workspace, or sign in with another staff account.','Вы уже вошли. Выберите доступный рабочий раздел или войдите с другой учётной записью сотрудника.'),
('该账号没有所选后台的权限，请选择正确身份或联系系统管理员。','This account cannot access this workspace. Select the correct role or contact the administrator.','У этой учётной записи нет доступа к выбранному разделу. Выберите другую роль или обратитесь к администратору.'),
('学号或密码不正确。请确认学校已导入账号，并检查登录信息。','Incorrect student number or password. Confirm that the school imported your account.','Неверный номер студента или пароль. Уточните, импортирована ли ваша учётная запись.'),
('该账号暂不可用，请联系系统管理人员。','This account is unavailable. Contact the administrator.','Учётная запись недоступна. Обратитесь к администратору.'),
('此字段是必填项。','This field is required.','Обязательное поле.'),
('校园账号登录','Student sign-in','Вход для студентов'),('注册校园账号 ↗','Create an account ↗','Создать учётную запись ↗'),('退出','Sign out','Выйти'),
('CAMPUS LIFE / 你好，校园伙伴','CAMPUS LIFE / Hello, campus friend','ЖИЗНЬ КАМПУСА / Привет, друг!'),
('你的校园生活，','Your campus life,','Твоя жизнь в кампусе —'),('今天也有','a new day of ','сегодня тоже '),('新可能。','possibilities.','новые возможности.'),
('聊聊生活，找人帮忙，也照顾好自己。','Share your day, find a helping hand and look after yourself.','Общайтесь, находите помощь и заботьтесь о себе.'),
('从下面选一个入口，开始今天的校园日常。','Choose a space below to start your campus day.','Выберите раздел, чтобы начать день в кампусе.'),
('愿你今天也有好心情','Here’s to a lovely day','Хорошего настроения сегодня!'),
('01 / 分享与交流','01 / SHARE & CONNECT','01 / ОБЩЕНИЕ'),('02 / 互助与跑腿','02 / HELP & ERRANDS','02 / ВЗАИМОПОМОЩЬ'),('03 / 健康与陪伴','03 / HEALTH & CARE','03 / ЗДОРОВЬЕ'),('04 / 空间与安排','04 / SPACE & TIME','04 / МЕСТО И ВРЕМЯ'),
('今天有什么','What’s new','Что нового'),('新鲜事？','on campus?','в кампусе?'),('一起聊聊 ↗','Let’s chat ↗','Поговорим ↗'),
('分享日常，交流学习，','Share daily life and study tips.','Делитесь новостями и учитесь вместе.'),('遇见校园里有趣的同学。','Meet interesting people on campus.','Знакомьтесь с интересными студентами.'),('进入校园论坛','Explore the forum','Открыть форум'),
('下一站 · 你的身边','Next stop · nearby','Следующая остановка · рядом'),('取快递，代买东西，','Pickups, shopping and deliveries.','Посылки, покупки и доставка.'),('把小小的忙交给校园伙伴。','Let a campus friend lend a hand.','Попросите друзей в кампусе помочь.'),('发布需求 / 查看订单','Post a task / My orders','Создать поручение / Мои заказы'),
('关心，从倾听开始','Care begins with listening','Забота начинается с внимания'),('说说哪里不舒服，','Tell us what’s bothering you.','Расскажите, что вас беспокоит.'),('一步步梳理就医方向。','Find the next step toward care.','Сделайте первый шаг к решению проблемы.'),('简单导诊 / 高级导诊','Basic / Advanced guide','Базовый / Расширенный помощник'),
('我的校园时间','My campus time','Моё время в кампусе'),('学习 / 运动 / 好好生活','Study / Sport / Live well','Учёба / Спорт / Жизнь'),('自习室、球场，','Study rooms and sports courts.','Читальные залы и спортплощадки.'),('给学习和运动留一个位置。','Make room for study and sport.','Найдите место для учёбы и спорта.'),('选择场地 / 我的预约','Find a space / My bookings','Выбрать место / Мои бронирования'),
('还有这些小入口','Quick links','Быстрые ссылки'),('写一条校园动态 ↗','Share a campus moment ↗','Поделиться новостью ↗'),('我的跑腿订单 ↗','My errands ↗','Мои поручения ↗'),('我的导诊信箱 ↗','My health inbox ↗','Мои медицинские сообщения ↗'),
('分享与帮助，让校园生活轻松一点。','Share and help, for an easier campus day.','Общение и помощь делают жизнь в кампусе проще.'),('把生活连接起来','Bringing campus life together','Объединяем жизнь кампуса'),('校园广场 / 校园跑腿 / AI 导诊 / 场地预约','Forum / Errands / Health / Bookings','Форум / Поручения / Здоровье / Бронирования'),
('管理后台','Staff workspace','Панель управления'),('预约管理','Booking management','Управление бронированиями'),('校园场地预约','Campus space booking','Бронирование мест кампуса'),('选择场地','Find a space','Выбрать место'),('我的预约','My bookings','Мои бронирования'),
('论坛','Forum','Форум'),('接单广场','Task board','Доска поручений'),('我的订单','My orders','Мои заказы'),('疑惑解答','Enquiries','Вопросы'),('消息','Messages','Сообщения'),('个人信息','My profile','Мой профиль'),('广场','Forum','Форум'),('发帖','New post','Создать публикацию'),('登录','Sign in','Войти'),('注册','Register','Регистрация'),
('学号','Student number','Номер студента'),('请输入学号','Enter student number','Введите номер студента'),('学号登录','Student sign-in','Вход по номеру студента'),('账号说明','Account information','Информация об аккаунте'),('账号说明 ↗','Account information ↗','Информация об аккаунте ↗'),
('校园账号说明','Campus account information','Информация об аккаунте кампуса'),('校园账号采用学号制，由学校管理员统一导入。','Campus accounts use student numbers and are imported by school administrators.','Учётные записи создаются по номеру студента и импортируются администрацией.'),('校园账号由管理员根据新生名单统一导入，不对校外人员开放注册。初始账号和密码均为学号，首次登录后需要修改密码。','Campus accounts are imported from the enrolment list. The initial username and password are the student number; a password change is required at first sign-in.','Учётные записи импортируются из списка студентов. Начальный логин и пароль совпадают с номером студента; при первом входе пароль нужно изменить.'),('使用学号登录','Sign in with student number','Войти по номеру студента'),('已有学号账号，前往登录','Already have a student account? Sign in','Есть студенческий аккаунт? Войти'),('账号由学校统一导入，未找到账号请联系管理员。','Accounts are imported by the school. Contact an administrator if yours is missing.','Аккаунты импортирует учебное заведение. Если аккаунта нет, обратитесь к администратору.'),
('学校导入学号','School imports student number','Импорт номера студента'),('校外人员无法自行创建账号。','External users cannot create accounts.','Пользователи вне кампуса не могут создавать аккаунты.'),
('校园账号安全','Campus account security','Безопасность аккаунта'),('修改登录密码','Change sign-in password','Изменить пароль'),('首次登录请设置仅你本人知道的新密码。','Set a private password at first sign-in.','При первом входе задайте новый личный пароль.'),('当前密码','Current password','Текущий пароль'),('新密码','New password','Новый пароль'),('确认新密码','Confirm new password','Подтвердите новый пароль'),('初始密码为你的学号','The initial password is your student number','Начальный пароль — номер студента'),('至少 8 位，不能为纯数字','At least 8 characters; not numbers only','Не менее 8 символов, не только цифры'),('再次输入新密码','Enter the new password again','Введите новый пароль ещё раз'),('保存新密码','Save new password','Сохранить новый пароль'),('修改密码','Change password','Изменить пароль'),('返回个人资料','Back to profile','Вернуться к профилю'),
('统一导入学生学号账号，并创建医生、论坛 / 跑腿管理员和预约管理员账号。','Import student-number accounts and manage staff accounts.','Импортируйте студенческие аккаунты и создавайте служебные аккаунты.'),('导入新生账号','Import new students','Импорт новых студентов'),('上传 UTF-8 CSV 新生名单。学号是登录账号，初始密码与学号相同；学生首次登录后必须修改密码。','Upload a UTF-8 CSV enrolment list. The student number is the username and initial password; students must change it at first sign-in.','Загрузите список CSV в UTF-8. Номер студента служит логином и начальным паролем; при первом входе пароль нужно изменить.'),('新生名单 CSV','Student CSV','CSV со списком студентов'),('导入学生账号','Import student accounts','Импортировать аккаунты'),('下载 CSV 模板','Download CSV template','Скачать шаблон CSV'),('重复学号会跳过，不覆盖已有账号或密码。','Existing student numbers are skipped without overwriting accounts or passwords.','Существующие номера пропускаются без изменения аккаунтов и паролей.'),
('激活校园账号','Activate campus account','Активировать аккаунт кампуса'),('核对本人信息并设置新密码。完成后，此二维码立即失效。','Verify your details and set a new password. The QR code expires immediately after activation.','Подтвердите данные и задайте новый пароль. После активации QR-код сразу станет недействительным.'),('对应学号','Student number','Номер студента'),('确认信息并激活','Verify and activate','Подтвердить и активировать'),('激活二维码已失效','Activation QR code is no longer valid','QR-код активации недействителен'),('该账号可能已经激活、密码已经修改，或二维码已过期。请使用学号登录，或联系学校管理员重新处理。','The account may already be active, its password may have changed, or the QR code may have expired. Sign in with your student number or contact an administrator.','Аккаунт уже мог быть активирован, пароль изменён или срок QR-кода истёк. Войдите по номеру студента или обратитесь к администратору.'),('前往学号登录','Student sign-in','Вход по номеру студента'),('新生账号激活卡','Student activation cards','Карточки активации студентов'),('请将激活卡交给对应学生本人。二维码完成一次激活后自动失效。','Give each card to the named student. Its QR code expires after one activation.','Передайте карточку указанному студенту. QR-код станет недействительным после одной активации.'),('打印全部激活卡','Print all activation cards','Распечатать все карточки'),('返回账号管理','Back to account management','Вернуться к управлению аккаунтами'),('账号激活二维码','Account activation QR code','QR-код активации аккаунта'),('学号尾号','Student number ending','Последние цифры номера'),('扫码后输入完整学号和姓名，设置新密码。','Scan, enter your full student number and name, then set a new password.','Отсканируйте код, введите полный номер студента и имя, затем задайте новый пароль.'),('当前没有待打印的激活卡。请先导入新生 CSV。','No activation cards are ready. Import a student CSV first.','Нет карточек для печати. Сначала импортируйте CSV студентов.'),('学号与激活卡不匹配。','The student number does not match this card.','Номер студента не соответствует карточке.'),('姓名与学校导入的信息不匹配。','The name does not match the school record.','Имя не совпадает с данными учебного заведения.'),('两次输入的密码不一致。','The passwords do not match.','Пароли не совпадают.'),
('校园论坛','Campus forum','Форум кампуса'),('返回论坛','Back to forum','Вернуться на форум'),('管理员模式','Administrator mode','Режим администратора'),('工作台','Workspace','Рабочий раздел'),('数据总览','Overview','Обзор'),('AI 巡查中心','AI moderation','ИИ-модерация'),('公告置顶','Announcements','Объявления'),('审核与服务','Moderation & services','Модерация и услуги'),('风险复核','Risk review','Проверка рисков'),('举报审核','Reports','Жалобы'),('跑腿订单','Errand orders','Заказы поручений'),('用户咨询','User enquiries','Обращения пользователей'),('充值审核','Top-up review','Проверка пополнений'),
('医生工作台','Doctor workspace','Рабочий раздел врача'),('咨询工作台','Consultations','Обращения'),('常用药资料库','Medicine reference','Справочник лекарств'),('疾病与病因资料','Conditions & causes','Заболевания и причины'),
]
UI_KEYS = json.loads((Path(__file__).with_name('ui_keys.json')).read_text(encoding='utf-8'))
GENERATED = json.loads((Path(__file__).with_name('translations.json')).read_text(encoding='utf-8')) if Path(__file__).with_name('translations.json').exists() else {}
TRANSLATIONS = {**GENERATED, **{zh: {'en': en, 'ru': ru} for zh, en, ru in ROWS}}

REVIEWED = json.loads(Path(__file__).with_name('translations-reviewed.json').read_text(encoding='utf-8'))
TRANSLATIONS.update(REVIEWED)
for filename in ('translations-ja.json', 'translations-ja-reviewed.json'):
    path = Path(__file__).with_name(filename)
    if path.exists():
        for source, japanese in json.loads(path.read_text(encoding='utf-8')).items():
            TRANSLATIONS.setdefault(source, {})['ja'] = japanese


for extra_file in ('translations-payments.json','translations-moderation.json','translations-security.json','translations-external.json','translations-journey.json','translations-companion.json','translations-document-review.json'):
    extra_translations=Path(__file__).with_name(extra_file)
    if extra_translations.exists():
        for source, translations in json.loads(extra_translations.read_text(encoding='utf-8')).items():
            TRANSLATIONS.setdefault(source,{}).update(translations)

def translate(text, language):
    value = str(text) if text is not None else ''
    key = value.strip()
    result = TRANSLATIONS.get(key, {}).get(language)
    return value.replace(key, result) if result is not None and key else value


def translate_html(value, language):
    # This helper receives form help text, never posts or patient descriptions.
    return re.sub(r'(^|>)([^<]+)', lambda m: m[1] + escape(translate(unescape(m[2]), language)), value)


def context(request):
    code = request.session.get('campus_language', request.COOKIES.get('campus_language', 'zh'))
    if code not in LANGUAGES:
        code = 'zh'
    return {'ui_language': code, 'ui_languages': LANGUAGES, 'ui_browser_catalog': {key: item.get(code, key) for key,item in TRANSLATIONS.items()} if code != 'zh' else {}, 'ui_html_language': {'zh': 'zh-CN', 'en': 'en', 'ru': 'ru', 'ja': 'ja'}[code]}

# Russian Word review 20261030 verified rendering
