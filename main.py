import os
import random
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    Defaults,
)

from telegram.constants import ParseMode
from pymongo import MongoClient

# 通用安全回复函数（防止消息不存在时报错）
async def safe_reply(update, text, **kwargs):
    if update.message:
        await update.message.reply_text(text, **kwargs)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, **kwargs)
    else:
        print("⚠️ 无法 reply：message 不存在")

# 对话状态定义（用于用户资料填写流程）
NAME, GENDER, AGE, HOBBIES, BIO = range(5)

# MongoDB 初始化
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["matchmates"]
users_collection = db["users"]    # 用户资料集合
likes_collection = db["likes"]    # 用户喜欢关系集合

########################################
# 核心功能：机器人命令处理
########################################

# /start 命令：显示主菜单按钮
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 开始匹配", callback_data="trigger_match")], 
        [InlineKeyboardButton("📄 我的资料", callback_data="my_profile")]
    ])
    await update.message.reply_text(
        "欢迎来到 MatchCouples Bot！点击下方按钮开始～",
        reply_markup=keyboard
    )

# /me 命令：显示当前用户资料
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = users_collection.find_one({'telegram_id': user_id})
    if not profile:
        await safe_reply(update, "⚠️ 你还没有填写资料哦，输入 /profile 开始吧～")
        return

    # 显示资料并添加操作按钮
    buttons = [
        [InlineKeyboardButton("✏️ 修改资料", callback_data="trigger_edit")],
        [InlineKeyboardButton("🔙 返回匹配", callback_data="trigger_match")]
    ]
    await safe_reply(
        update,
        f"📄 你的资料：\n\n"
        f"昵称：{profile.get('name', '未填写')}\n"
        f"性别：{profile.get('gender', '未填写')}\n"
        f"年龄：{profile.get('age', '未填写')}\n"
        f"兴趣：{profile.get('hobbies', '未填写')}\n"
        f"简介：{profile.get('bio', '未填写')}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

########################################
# 用户资料填写流程（ConversationHandler）
########################################

# 启动资料填写/修改流程
async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = users_collection.find_one({'telegram_id': user_id})

    # 已存在资料时的处理
    if update.message.text == "/profile" and existing:
        await safe_reply(update, "你已经填写过资料了，输入 /edit 可以修改哦～")
        return ConversationHandler.END

    await safe_reply(update, "让我们开始填写你的资料吧！\n请输入你的昵称：")
    return NAME  # 进入昵称输入状态

# 昵称 → 性别
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    await safe_reply(update, "请选择性别：", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GENDER

# 性别 → 年龄
async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await safe_reply(update, "请输入年龄：")
    return AGE

# 年龄 → 兴趣
async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过兴趣"]], one_time_keyboard=True)
    await safe_reply(update, "请输入兴趣（用逗号分隔）：", reply_markup=reply_markup)
    return HOBBIES

# 兴趣 → 简介
async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过兴趣":
        context.user_data['hobbies'] = "未填写"
    else:
        context.user_data['hobbies'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过简介"]], one_time_keyboard=True)
    await safe_reply(update, "请输入个人简介：", reply_markup=reply_markup)
    return BIO

# 保存资料 → 结束流程
async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过简介":
        context.user_data['bio'] = "未填写"
    else:
        context.user_data['bio'] = update.message.text

    # 保存到 MongoDB
    profile = context.user_data
    profile['telegram_id'] = update.effective_user.id
    users_collection.update_one(
        {'telegram_id': profile['telegram_id']},
        {'$set': profile},
        upsert=True
    )

    await safe_reply(update, f"✅ 资料填写完成，已保存：\n\n昵称：{profile['name']}\n性别：{profile['gender']}\n年龄：{profile['age']}\n兴趣：{profile['hobbies']}\n介绍：{profile['bio']}")
    return ConversationHandler.END

########################################
# 匹配系统核心逻辑
########################################

async def match(update, context):
    # 获取当前用户信息
    me_id = update.effective_user.id
    me = users_collection.find_one({'telegram_id': me_id})
    if not me:
        await safe_reply(update, "你还没有填写资料，请先输入 /profile")
        return

    # 匹配条件计算
    my_age = int(me.get("age", 0))
    my_gender = me.get("gender")
    my_hobbies = set(me.get("hobbies", "").split(","))

    # 筛选潜在匹配对象（异性、年龄差5岁以内、有共同兴趣）
    potentials = users_collection.find({'telegram_id': {'$ne': me_id}, 'gender': {'$ne': my_gender}})
    candidates = []
    for p in potentials:
        try:
            age_diff = abs(int(p.get("age", 0)) - my_age)
            other_hobbies = set(p.get("hobbies", "").split(","))
            if age_diff <= 5 and my_hobbies & other_hobbies:
                candidates.append(p)
        except:
            continue

    # 随机选取并展示
    if not candidates:
        await safe_reply(update, "😢 暂时没有找到匹配对象，请稍后再试")
        return

    match = random.choice(candidates)
    context.user_data['last_match'] = match['telegram_id']  # 记录最后匹配的用户
    text = f"🎯 为你找到一个匹配对象：\n\n昵称：{match['name']}\n性别：{match['gender']}\n年龄：{match['age']}\n兴趣：{match['hobbies']}\n介绍：{match['bio']}"
    buttons = [[
        InlineKeyboardButton("❤️ 喜欢", callback_data="like"),
        InlineKeyboardButton("🙅 跳过", callback_data="skip")
    ]]
    await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

########################################
# 按钮回调处理
########################################

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # 主菜单按钮处理
    if query.data == "my_profile":
        await me(update, context)
    elif query.data == "trigger_match":
        await match(update, context)
    elif query.data == "trigger_edit":
        await start_profile(update, context)

    # 匹配操作处理
    user_id = query.from_user.id
    target_id = context.user_data.get("last_match")
    if query.data == "like" and target_id:
        # 记录喜欢关系并检查是否双向匹配
        likes_collection.update_one(
            {'from': user_id, 'to': target_id},
            {'$set': {'from': user_id, 'to': target_id}},
            upsert=True
        )
        mutual = likes_collection.find_one({'from': target_id, 'to': user_id})
        if mutual:
            await query.edit_message_text("🎉 配对成功！你们可以开始聊天啦！")
        else:
            await query.edit_message_text("❤️ 已发送喜欢，等待对方回应！")
    elif query.data == "skip":
        await query.edit_message_text("已跳过该用户。")

########################################
# 机器人启动配置
########################################

def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    # 添加命令处理器
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(CallbackQueryHandler(handle_button))

    # 配置对话处理器（用于资料填写）
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("profile", start_profile),
            CommandHandler("edit", start_profile),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hobbies)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    print("🔁 使用 polling 模式启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
