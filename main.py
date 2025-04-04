from flask import Flask, request
import discord
import asyncio
import threading

intents = discord.Intents.default()
intents.members = True

bot = discord.Client(intents=intents)
app = Flask(__name__)
TOKEN = 'TWOJ_TOKEN_BOTA'

def run_flask():
    app.run(host='0.0.0.0', port=5000)

@bot.event
async def on_ready():
    print(f'{bot.user} connected')

@app.route('/role', methods=['POST'])
def add_role():
    data = request.get_json()
    username = data['username']
    asyncio.run_coroutine_threadsafe(give_role(username), bot.loop)
    return 'ok'

async def give_role(username):
    for guild in bot.guilds:
        for member in guild.members:
            if member.name.lower() == username.lower() or member.display_name.lower() == username.lower():
                role = discord.utils.get(guild.roles, id=1357354439043973150)
                if role:
                    await member.add_roles(role)
                return

threading.Thread(target=run_flask).start()
bot.run(TOKEN)
