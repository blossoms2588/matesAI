import os
import random
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
    ConversationHandler, Defaults
)
from telegram.constants import ParseMode
from pymongo import MongoClient

async def safe_reply(update, text, **kwargs):
    if update.message:
        await update.message.reply_text(text, **kwargs)
    elif update.callback_query and update.callback_query.message:
        await update.callback_query.message.reply_text(text, **kwargs)
    else:
        print("⚠️ 无法回复：未找到合适的消息对象")

# Conversation states
NAME, GENDER, AGE, HOBBIES, BIO = range(5)

# MongoDB 连接
MONGO_URI = os.getenv("MONGO_URI")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["matchmates"]
users_collection = db["users"]
# likes_collection = db["likes"]  # 暂时用不到可先注释

# /start：判断是否新用户，显示不同按钮
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = users_collection.find_one({'telegram_id': user_id})

    if profile:
        # 老用户
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 开始匹配", callback_data="trigger_match")],
            [InlineKeyboardButton("📄 我的资料", callback_data="my_profile")]
        ])
        await safe_reply(update, "欢迎回来！你已填写过资料，可直接开始匹配或查看资料～", reply_markup=keyboard)
    else:
        # 新用户
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🆕 添加资料", callback_data="trigger_profile")]
        ])
        await safe_reply(update, "你好！看来你是新用户，点击下方按钮快速添加你的资料吧～", reply_markup=keyboard)

# 查看资料
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    profile = users_collection.find_one({'telegram_id': user_id})
    if not profile:
        await safe_reply(update, "⚠️ 你还没有填写资料哦，输入 /profile 开始吧～")
        return

    text = (
        f"📄 你的资料：\n\n"
        f"昵称：{profile.get('name', '未填写')}\n"
        f"性别：{profile.get('gender', '未填写')}\n"
        f"年龄：{profile.get('age', '未填写')}\n"
        f"兴趣：{profile.get('hobbies', '未填写')}\n"
        f"简介：{profile.get('bio', '未填写')}"
    )

    buttons = [
        [InlineKeyboardButton("✏️ 修改资料", callback_data="trigger_edit")],
        [InlineKeyboardButton("🔙 返回匹配", callback_data="trigger_match")]
    ]
    await safe_reply(update, text, reply_markup=InlineKeyboardMarkup(buttons))

# 进入资料填写(或修改资料)
async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        # 按钮触发
        await update.callback_query.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")
    else:
        # 命令触发
        await update.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")

    return NAME

# ---- 各步骤 ----
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await safe_reply(update, "你的性别是？", reply_markup=ReplyKeyboardMarkup([['男', '女', '其他']], one_time_keyboard=True))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await safe_reply(update, "你几岁啦？")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    await safe_reply(update, "有哪些兴趣爱好？（用逗号分隔）", reply_markup=ReplyKeyboardMarkup([["跳过兴趣"]], one_time_keyboard=True))
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "跳过兴趣":
        context.user_data['hobbies'] = "未填写"
    else:
        context.user_data['hobbies'] = update.message.text

    await safe_reply(update, "简单介绍一下你自己吧：", reply_markup=ReplyKeyboardMarkup([["跳过简介"]], one_time_keyboard=True))
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

    await safe_reply(update, "✅ 资料填写完成，已保存！")
    return ConversationHandler.END

# /cancel
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_reply(update, "❌ 已取消资料填写。")
    return ConversationHandler.END

# 简化的匹配逻辑
async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 这里做一个示例
    await safe_reply(update, "[匹配逻辑示例] 你可以拓展兴趣、性别等筛选")
    return

# 处理按钮回调
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "trigger_match":
        await match(update, context)
    elif query.data == "my_profile":
        await me(update, context)
    elif query.data == "trigger_edit":
        return await start_profile(update, context)
    elif query.data == "trigger_profile":
        return await start_profile(update, context)
    else:
        await query.message.reply_text("[未知按钮]")
        return

def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    # 命令
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("me", me))

    # 按钮回调
    app.add_handler(CallbackQueryHandler(handle_button))

    # 会话流程
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("profile", start_profile),
            CommandHandler("edit", start_profile),
            CallbackQueryHandler(start_profile, pattern="^trigger_edit$"),
            CallbackQueryHandler(start_profile, pattern="^trigger_profile$"),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hobbies)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv_handler)

    print("🔁 使用 polling 模式启动中...")
    app.run_polling()

if __name__ == "__main__":
    main()
