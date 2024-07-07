async def check(bot):
    await bot.revolt_session.close()
    if hasattr(bot, 'platforms'):
        bot['platforms'].pop('revolt')
    del bot.revolt_client
    del bot.revolt_session
