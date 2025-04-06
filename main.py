导入操作系统
从电报导入更新，ReplyKeyboardMarkup
从 telegram.ext 导入（
    应用程序构建器，
    命令处理程序，
    消息处理程序，
    过滤器，
    上下文类型，
    对话处理器，
    默认值
）
从 telegram.constants 导入 ParseMode

姓名、性别、年龄、爱好、个人简介 = 范围 (5)

异步 def start（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    print(f"✅ 收到 /start 来自用户：{update. effective_user.id}")
    wait update.message.reply_text("欢迎使用 MatchCouples Bot！输入 /profile 开始填写资料～")

异步 def start_profile（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    wait update.message.reply_text("让我们开始填写您的资料吧！\n请输入您的昵称：")
    返回名称

异步 def get_name（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    context.user_data['name'] = 更新消息.文本
    reply_keyboard = [['男', '女', '其他']]
    wait update.message.reply_text("你的性别是？",reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))
    返回性别

异步 def get_gender（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    context.user_data['性别'] = 更新消息.文本
    wait update.message.reply_text("你几岁啦？")
    返回 AGE

异步 def get_age（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    context.user_data['年龄'] = 更新消息.文本
    wait update.message.reply_text("有哪些兴趣爱好？（用分隔分隔）")
    返回 爱好

异步 def get_hobbies（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    context.user_data['爱好'] = 更新消息.文本
    wait update.message.reply_text("简单介绍一下你自己吧：")
    返回 BIO

异步 def get_bio（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    context.user_data['bio'] = 更新消息.文本
    个人资料=context.user_data
    等待更新.消息.回复文本（
        f"✅ 资料填写完成：\n\n"
        f" 昵称：{profile['name']}\n"
        f"性别：{个人资料['性别']}\n"
        f"年龄：{个人资料['年龄']}\n"
        f"兴趣：{个人资料['爱好']}\n"
        f"介绍：{profile['bio']}"
    ）
    返回 ConversationHandler.END

异步 def 取消（更新：更新，上下文：ContextTypes.DEFAULT_TYPE）：
    wait update.message.reply_text("❌ 已取消资料填写。")
    返回 ConversationHandler.END

定义主要（）：
    TOKEN = os.getenv(“TOKEN”)
    默认值 = 默认值（parse_mode=ParseMode.HTML）
    app = ApplicationBuilder().token(TOKEN).defaults(defaults).build()

    app.add_handler（CommandHandler（"开始", 开始））

    profile_conv = ConversationHandler（
        entry_points=[CommandHandler("profile", start_profile)],
        州={
            名称：[MessageHandler（filters.TEXT＆~filters.COMMAND，get_name）]，
            性别：[MessageHandler（filters.TEXT & ~filters.COMMAND，get_gender）]，
            年龄：[MessageHandler（filters.TEXT＆~filters.COMMAND，get_age）]，
            爱好：[MessageHandler（filters.TEXT＆~filters.COMMAND，get_hobbies）]，
            个人简介：[MessageHandler(filters.TEXT & ~filters.COMMAND, get_bio)]，
        }，
        fallbacks=[CommandHandler(“取消”, 取消)],
    ）
    应用程序.添加处理程序（profile_conv）

    print("🔁 使用轮询模式启动中...")
    应用程序.run_polling（）

如果 __name__ == "__main__"：
    主要的（）
