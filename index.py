import discord
import dotenv
import requests
import os


dotenv.load_dotenv()
prefix = "!"

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


def get_multifield_embed(
    questionTitle,
    questionDate,
    questionLink,
    title="Daily LC",
    description="This is the Daily LC Question",
):
    embed = discord.Embed(title=title, description=description)
    embed.add_field(name="Title", value=questionTitle, inline=False)
    embed.add_field(name="Date", value=questionDate, inline=True)
    embed.add_field(name="Link", value=questionLink, inline=False)

    return embed


def getDailyLC():
    # Send the POST request with the query
    response = requests.post(os.environ.get("LC_ENDPOINT"), json={"query": query})

    # Check for successful response
    if response.status_code == 200:
        # Parse the JSON response
        data = response.json()

        # Access the data
        for value in data["activeDailyCodingChallengeQuestion"]:
            return get_multifield_embed(
                value["question"]["title"],
                value["date"],
                "https://leetcode.com" + value["link"],
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
        await message.channel.send(embed=getDailyLC())


client.run(os.environ.get("BOT_TOKEN"))
