import discord
import dotenv
import requests
import os
import threading
import time

dotenv.load_dotenv()
prefix = "!"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

daily_query = """
query questionOfToday {
	activeDailyCodingChallengeQuestion {
		date
		link
		question {
			acRate
			difficulty
			freqBar
			frontendQuestionId: questionFrontendId
			isFavor
			paidOnly: isPaidOnly
			status
			title
			hasVideoSolution
			hasSolution
		}
	}
}
"""

intents = discord.Intents.default()
intents.message_content = True

def send_heartbeat():
    while True:
        # Send your heartbeat message (e.g., log it, send to server)
        print("Sending heartbeat...")
        time.sleep(60)  # Send heartbeat every minute

thread = threading.Thread(target=send_heartbeat)
thread.start()

def get_multifield_embed(*args, title="Daily LC", description="This is the Daily LC Question"):
    embed = discord.Embed(title=title, description=description)
    for embedArg in args:
        embed.add_field(name=embedArg["title"], value=embedArg["value"], inline=True)
    return embed


def getDailyLC(query):
    # Send the POST request with the query
    response = requests.post(os.environ.get('LC_ENDPOINT'), json={"query": query})

    # Check for successful response
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()["data"]["activeDailyCodingChallengeQuestion"]
        response_dict = {
            "title": data["question"]["title"],
            "date": data["date"],
            "link": 
        }
        return get_multifield_embed(data["question"]["title"], data["date"], "https://leetcode.com" + data["link"])
        
    else:
        print(f"Error: {response.status_code}")

@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(prefix + "daily"):
        await message.channel.send(embed=getDailyLC(daily_query))

client.run(os.environ.get('BOT_TOKEN'))
