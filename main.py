import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# 定义状态常量
NAME, GENDER, AGE, HOBBIES, BIO = range(5)

TOKEN = os.getenv("TOKEN")

# --- 处理指令和对话流程 ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("欢迎使用 MatchCouples Bot! 输入 /profile 开始填写资料～")

async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    await update.message.reply_text(
        "你的性别是？",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("你几岁啦？")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['age'] = update.message.text
    await update.message.reply_text("有哪些兴趣爱好？（用逗号分隔）")
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['hobbies'] = update.message.text
    await update.message.reply_text("简单介绍一下你自己吧：")
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bio'] = update.message.text
    profile = context.user_data

    await update.message.reply_text(
        f"✅ 你的资料填写完毕！\n\n"
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

# --- 主程序入口 ---
if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()

    # 加入命令
    app.add_handler(CommandHandler("start", start))

    # 加入 profile 对话流程
    profile_conv_handler = ConversationHandler(
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
    app.add_handler(profile_conv_handler)

    # 🔐 加锁逻辑：仅在主进程或本地开发时运行 Polling
    is_railway = os.getenv("RAILWAY_ENVIRONMENT") == "production"

    if not is_railway:
        print("🔁 本地运行中，启动 polling")
        app.run_polling()
    else:
        print("🚀 Railway 部署，不启动 polling（由远程处理）")
