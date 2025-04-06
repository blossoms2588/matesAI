import os
import random
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    Defaults
)
from telegram.constants import ParseMode
from pymongo import MongoClient

NAME, GENDER, AGE, HOBBIES, BIO = range(5)

# MongoDB 初始化
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["matchmates"]
users_collection = db["users"]
likes_collection = db["likes"]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("欢迎使用 MatchCouples Bot！输入 /profile 开始填写资料，或输入 /match 查看推荐匹配！")

# /profile 开始流程
async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    await update.message.reply_text("你的性别是？", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("你几岁啦？")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过兴趣"]], one_time_keyboard=True)
    await update.message.reply_text("有哪些兴趣爱好？（用逗号分隔）", reply_markup=reply_markup)
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过兴趣":
        context.user_data['hobbies'] = "未填写"
    else:
        context.user_data['hobbies'] = update.message.text

    reply_markup = ReplyKeyboardMarkup([["跳过简介"]], one_time_keyboard=True)
    await update.message.reply_text("简单介绍一下你自己吧：", reply_markup=reply_markup)
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过简介":
        context.user_data['bio'] = "未填写"
    else:
        context.user_data['bio'] = update.message.text

    profile = context.user_data
    profile['telegram_id'] = update.effective_user.id

    users_collection.update_one(
        {'telegram_id': profile['telegram_id']},
        {'$set': profile},
        upsert=True
    )
    await update.message.reply_text(
        f"✅ 资料填写完成，已保存：\n\n"
        f"昵称：{profile['name']}\n"
        f"性别：{profile['gender']}\n"
        f"年龄：{profile['age']}\n"
        f"兴趣：{profile['hobbies']}\n"
        f"介绍：{profile['bio']}"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 已取消资料填写。")
    return ConversationHandler.END

# /match 匹配逻辑
async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me_id = update.effective_user.id
    me = users_collection.find_one({'telegram_id': me_id})
    if not me:
        await update.message.reply_text("你还没有填写资料，请先输入 /profile")
        return

    my_age = int(me.get("age", 0))
    my_gender = me.get("gender")
    my_hobbies = set(me.get("hobbies", "").split(","))

    potentials = users_collection.find({
        'telegram_id': {'$ne': me_id},
        'gender': {'$ne': my_gender}
    })

    candidates = []
    for p in potentials:
        try:
            age_diff = abs(int(p.get("age", 0)) - my_age)
            other_hobbies = set(p.get("hobbies", "").split(","))
            if age_diff <= 5 and my_hobbies & other_hobbies:
                candidates.append(p)
        except:
            continue

    if not candidates:
        await update.message.reply_text("😢 暂时没有找到匹配对象，请稍后再试")
        return

    match = random.choice(candidates)
    context.user_data['last_match'] = match['telegram_id']

    text = (
        f"🎯 为你找到一个匹配对象：\n\n"
        f"昵称：{match['name']}\n"
        f"性别：{match['gender']}\n"
        f"年龄：{match['age']}\n"
        f"兴趣：{match['hobbies']}\n"
        f"介绍：{match['bio']}"
    )
    buttons = [
        [InlineKeyboardButton("❤️ 喜欢", callback_data="like"),
         InlineKeyboardButton("🙅 跳过", callback_data="skip")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 回调按钮处理
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    target_id = context.user_data.get("last_match")

    if query.data == "like" and target_id:
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

# 主程序入口
def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CallbackQueryHandler(handle_button))

    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", start_profile)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hobbies)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(profile_conv)

    print("🔁 使用 polling 模式启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
import os
import random
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    Defaults
)
from telegram.constants import ParseMode
from pymongo import MongoClient

NAME, GENDER, AGE, HOBBIES, BIO = range(5)

# MongoDB 初始化
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["matchmates"]
users_collection = db["users"]
likes_collection = db["likes"]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("欢迎使用 MatchCouples Bot！输入 /profile 开始填写资料，或输入 /match 查看推荐匹配！")

# /profile 开始流程
async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    await update.message.reply_text("你的性别是？", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("你几岁啦？")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过兴趣"]], one_time_keyboard=True)
    await update.message.reply_text("有哪些兴趣爱好？（用逗号分隔）", reply_markup=reply_markup)
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过兴趣":
        context.user_data['hobbies'] = "未填写"
    else:
        context.user_data['hobbies'] = update.message.text

    reply_markup = ReplyKeyboardMarkup([["跳过简介"]], one_time_keyboard=True)
    await update.message.reply_text("简单介绍一下你自己吧：", reply_markup=reply_markup)
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过简介":
        context.user_data['bio'] = "未填写"
    else:
        context.user_data['bio'] = update.message.text

    profile = context.user_data
    profile['telegram_id'] = update.effective_user.id

    users_collection.update_one(
        {'telegram_id': profile['telegram_id']},
        {'$set': profile},
        upsert=True
    )
    await update.message.reply_text(
        f"✅ 资料填写完成，已保存：\n\n"
        f"昵称：{profile['name']}\n"
        f"性别：{profile['gender']}\n"
        f"年龄：{profile['age']}\n"
        f"兴趣：{profile['hobbies']}\n"
        f"介绍：{profile['bio']}"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ 已取消资料填写。")
    return ConversationHandler.END

# /match 匹配逻辑
async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    me_id = update.effective_user.id
    me = users_collection.find_one({'telegram_id': me_id})
    if not me:
        await update.message.reply_text("你还没有填写资料，请先输入 /profile")
        return

    my_age = int(me.get("age", 0))
    my_gender = me.get("gender")
    my_hobbies = set(me.get("hobbies", "").split(","))

    potentials = users_collection.find({
        'telegram_id': {'$ne': me_id},
        'gender': {'$ne': my_gender}
    })

    candidates = []
    for p in potentials:
        try:
            age_diff = abs(int(p.get("age", 0)) - my_age)
            other_hobbies = set(p.get("hobbies", "").split(","))
            if age_diff <= 5 and my_hobbies & other_hobbies:
                candidates.append(p)
        except:
            continue

    if not candidates:
        await update.message.reply_text("😢 暂时没有找到匹配对象，请稍后再试")
        return

    match = random.choice(candidates)
    context.user_data['last_match'] = match['telegram_id']

    text = (
        f"🎯 为你找到一个匹配对象：\n\n"
        f"昵称：{match['name']}\n"
        f"性别：{match['gender']}\n"
        f"年龄：{match['age']}\n"
        f"兴趣：{match['hobbies']}\n"
        f"介绍：{match['bio']}"
    )
    buttons = [
        [InlineKeyboardButton("❤️ 喜欢", callback_data="like"),
         InlineKeyboardButton("🙅 跳过", callback_data="skip")]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 回调按钮处理
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    target_id = context.user_data.get("last_match")

    if query.data == "like" and target_id:
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

# 主程序入口
def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CallbackQueryHandler(handle_button))

    profile_conv = ConversationHandler(
        entry_points=[CommandHandler("profile", start_profile)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hobbies)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(profile_conv)

    print("🔁 使用 polling 模式启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
