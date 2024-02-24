import discord
import dotenv
import requests
import os

dotenv.load_dotenv()
prefix = "?"

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents, prefix='?')

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

def get_multifield_embed(embedDict, difficuly, title="Daily LC", description="This is the Daily LC Question"):
    embed = discord.Embed(title=title, description=description)
    for key, value in embedDict.items():
        embed.add_field(name=key, value=value, inline=True)
    embed.add_field(name="difficulty", value=f"||{difficuly}||", inline=True)
    return embed

def getDailyLC(query):
    # Send the POST request with the query
    response = requests.post(os.environ.get('LC_ENDPOINT'), json={"query": query})

    # Check for successful response
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()["data"]["activeDailyCodingChallengeQuestion"]
        return get_multifield_embed({
            "title": data["question"]["title"],
            "date": data["date"],
            "link": "https://leetcode.com" + data["link"],
            "paidOnly": data["question"]["paidOnly"]
        },
        data["question"]["difficulty"],
        "Daily LC",
        "This is the daily leetcode question, Good Luck!"
        )
        
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
    
    if message.content.startswith(prefix + "ping"):
        await message.send(f'Pong! In {round(client.latency * 1000)}ms')

client.run(os.environ.get('DISCORD_BOT_TOKEN'))
