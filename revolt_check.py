async def check(bot):
    await bot.revolt_session.close()
    if hasattr(bot, 'platforms'):
        try:
            bot.platforms.pop('revolt')
        except:
            pass
    del bot.revolt_client
    del bot.revolt_session
