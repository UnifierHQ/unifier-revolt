async def check(bot):
    await bot.revolt_session.close()
    del bot.revolt_client
    del bot.revolt_session
