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

async def safe_reply(update, text, **kwargs):
    if update.message:
        await update.message.reply_text(text, **kwargs)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, **kwargs)
    else:
        print("⚠️ 无法 reply：message 不存在")


NAME, GENDER, AGE, HOBBIES, BIO = range(5)

# MongoDB 初始化
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["matchmates"]
users_collection = db["users"]
likes_collection = db["likes"]

# /start，带按钮
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 开始匹配", callback_data="trigger_match")]
    ])
    await safe_reply(update, "欢迎来到 MatchCouples Bot！点击下方按钮开始匹配～", reply_markup=keyboard)

    
# /me 查看资料
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = users_collection.find_one({'telegram_id': user_id})
    if not profile:
        await safe_reply(update, "⚠️ 你还没有填写资料哦，输入 /profile 开始吧～")
        return

    await safe_reply(
        update,
        f"📄 你的资料：\n\n"
        f"昵称：{profile.get('name', '未填写')}\n"
        f"性别：{profile.get('gender', '未填写')}\n"
        f"年龄：{profile.get('age', '未填写')}\n"
        f"兴趣：{profile.get('hobbies', '未填写')}\n"
        f"简介：{profile.get('bio', '未填写')}"
    )



# profile/edit 流程共用函数
async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    existing = users_collection.find_one({'telegram_id': user_id})
    if update.message.text == "/profile" and existing:
        return ConversationHandler.END

    return NAME


async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过兴趣"]], one_time_keyboard=True)
    
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过兴趣":
        context.user_data['hobbies'] = "未填写"
    else:
        context.user_data['hobbies'] = update.message.text
    reply_markup = ReplyKeyboardMarkup([["跳过简介"]], one_time_keyboard=True)
    
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

    await safe_reply(
        update,
        f"✅ 资料填写完成，已保存：\n\n"
        f"昵称：{profile['name']}\n"
        f"性别：{profile['gender']}\n"
        f"年龄：{profile['age']}\n"
        f"兴趣：{profile['hobbies']}\n"
        f"介绍：{profile['bio']}"
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, "❌ 已取消资料填写。")
    return ConversationHandler.END


# 匹配逻辑
async def match(update, context):
    me_id = update.effective_user.id
    me = users_collection.find_one({'telegram_id': me_id})
    if not me:
        await safe_reply(update, "你还没有填写资料，请先输入 /profile")
        return

    my_age = int(me.get("age", 0))
    my_gender = me.get("gender")
    my_hobbies = set(me.get("hobbies", "").split(","))

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

    if not candidates:
        await safe_reply(update, "😢 暂时没有找到匹配对象，请稍后再试")
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
    buttons = [[
        InlineKeyboardButton("❤️ 喜欢", callback_data="like"),
        InlineKeyboardButton("🙅 跳过", callback_data="skip")
    ]]
    await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# 按钮响应
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "trigger_edit":
        await start_profile(update, context)
        return

    if query.data == "trigger_match":
        await match(update, context)
        return

    user_id = query.from_user.id
    target_id = context.user_data.get("last_match")

    if query.data == "like" and target_id:
        likes_collection.update_one({'from': user_id, 'to': target_id}, {'$set': {'from': user_id, 'to': target_id}}, upsert=True)
        mutual = likes_collection.find_one({'from': target_id, 'to': user_id})
        if mutual:
            await query.edit_message_text("🎉 配对成功！你们可以开始聊天啦！")
        else:
            await query.edit_message_text("❤️ 已发送喜欢，等待对方回应！")
    elif query.data == "skip":
        await query.edit_message_text("已跳过该用户。")

def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(CallbackQueryHandler(handle_button))

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
