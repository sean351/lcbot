import discord
import dotenv
import os
import logging
import json
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

# Setup and Config clients
logging.basicConfig(level=logging.DEBUG)
dotenv.load_dotenv()
prefix = "?"
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents, prefix='?')
transport = AIOHTTPTransport(url=os.environ.get("LC_ENDPOINT"), headers={
    "cookie": os.environ.get("LC_COOKIE")
})
gql_client = Client(transport=transport, fetch_schema_from_transport=False)
intents = discord.Intents.default()
intents.message_content = True

company_query = gql(
    """
query questionCompanyStats($titleSlug: String!) {
	question(titleSlug: $titleSlug) {
		companyTagStats
	}
}
"""
)

daily_query = gql(
    """
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
            titleSlug
			hasVideoSolution
			hasSolution
            topicTags {
                name
            }
		}
	}
}
"""
)

similar_query = gql(
    """
query SimilarQuestions($titleSlug: String!) {
    question(titleSlug: $titleSlug) {
        similarQuestionList {
            difficulty
            titleSlug
            title
            isPaidOnly
        }
    }
}
"""
)


def create_similar_embed(question_list):
    embed = discord.Embed(title="Similar Questions")

    for question in question_list:
        # Extract relevant information
        difficulty = question["difficulty"]
        title = question["title"]
        link = "https://leetcode.com/problems/" + question["titleSlug"]
        is_paid_only = question["isPaidOnly"]

        # Create embed field with proper formatting
        field_text = f"{link}"
        title_text = f"{title}"
        if is_paid_only:
            title_text += " (Paid Only)"

        embed.add_field(name=title_text, value=field_text, inline=False)

    return embed


def create_company_embed(company_data):
    # Remove unnecessary quotes
    data = json.loads(company_data)

    embed = discord.Embed(title="Company Encounter Summary")

    # Loop through each category in the data
    for category, companies in data.items():
        # Create a field for each category
        field_name = f"Category {category}"
        field_value = ""

    # Loop through each company in the category
    for company in companies:
        # Add company information to the field value
        field_value += f"✅ **{company['name']}** ({company['timesEncountered']})\n"

    # Add the field to the embed
    embed.add_field(name=field_name, value=field_value, inline=False)

    return embed

# Generate the Embed


def get_multifield_embed(embedDict, title="Daily LC", description="This is the Daily LC Question"):
    embed = discord.Embed(title=title, description=description)
    for key, value in embedDict.items():
        embed.add_field(name=key, value=value, inline=True)

    return embed

# Get the Data


async def getDailyLC(dailyQuery, companyQuery, similarQuery):

    # Send the requests to get data
    daily_result = await gql_client.execute_async(dailyQuery)
    data = daily_result["activeDailyCodingChallengeQuestion"]
    company_stats_result = await gql_client.execute_async(companyQuery, variable_values={"titleSlug": data["question"]["titleSlug"]})
    company_data = company_stats_result["question"]["companyTagStats"]
    similar_result = await gql_client.execute_async(similarQuery, variable_values={"titleSlug": data["question"]["titleSlug"]})
    similar_data = similar_result["question"]["similarQuestionList"]

    diff = data["question"]["difficulty"]
    mainEmbed = get_multifield_embed(embedDict={
        "title": data["question"]["title"],
        "date": data["date"],
        "link": "https://leetcode.com" + data["link"],
        "paidOnly": data["question"]["paidOnly"],
        "topics": ",".join([item["name"] for item in data["question"]["topicTags"]]),
        "difficulty": f"||{diff}||"
    },
        title="Daily LC",
        description="This is the daily leetcode question, Good Luck!"
    )
    similarEmbed = create_similar_embed(similar_data)
    companyEmbed = create_company_embed(company_data)
    return [mainEmbed, companyEmbed, similarEmbed]


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(prefix + "daily"):
        await message.channel.send(embeds=await getDailyLC(dailyQuery=daily_query, companyQuery=company_query, similarQuery=similar_query))

    if message.content.startswith(prefix + "ping"):
        await message.send(f'Pong! In {round(client.latency * 1000)}ms')

client.run(os.environ.get('DISCORD_BOT_TOKEN'))
