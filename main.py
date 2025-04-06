import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    Defaults
)
from telegram.constants import ParseMode

NAME, GENDER, AGE, HOBBIES, BIO = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"✅ 收到 /start 来自用户：{update.effective_user.id}")
    await update.message.reply_text("欢迎使用 MatchCouples Bot！输入 /profile 开始填写资料～")

async def start_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 进入资料收集流程")
    await update.message.reply_text("让我们开始填写你的资料吧！\n请输入你的昵称：")
    return NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"👤 用户昵称：{update.message.text}")
    context.user_data['name'] = update.message.text
    reply_keyboard = [['男', '女', '其他']]
    await update.message.reply_text("你的性别是？", reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    return GENDER

async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"👤 性别：{update.message.text}")
    context.user_data['gender'] = update.message.text
    await update.message.reply_text("你几岁啦？")
    return AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"👤 年龄：{update.message.text}")
    context.user_data['age'] = update.message.text
    await update.message.reply_text("有哪些兴趣爱好？（用逗号分隔）")
    return HOBBIES

async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"👤 兴趣：{update.message.text}")
    context.user_data['hobbies'] = update.message.text
    await update.message.reply_text("简单介绍一下你自己吧：")
    return BIO

async def get_bio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"👤 简介：{update.message.text}")
    context.user_data['bio'] = update.message.text
    profile = context.user_data
    await update.message.reply_text(
        f"✅ 资料填写完成：\n\n"
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

def main():
    TOKEN = os.getenv("TOKEN")
    defaults = Defaults(parse_mode=ParseMode.HTML)
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    app.add_handler(CommandHandler("start", start))

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
