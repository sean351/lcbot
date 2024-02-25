import discord
from discord.ext import commands
from datetime import date
import os
import dotenv
import logging
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
import json


def configure_client():
    logging.basicConfig(level=logging.DEBUG)
    dotenv.load_dotenv()
    prefix = "?"
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(intents=intents, command_prefix=prefix)
    transport = AIOHTTPTransport(
        url=os.environ.get("LC_ENDPOINT"),
        headers={"cookie": os.environ.get("LC_COOKIE")}
    )
    gql_client = Client(transport=transport, fetch_schema_from_transport=False)
    return client, gql_client


client, gql_client = configure_client()

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
			difficulty
			paidOnly: isPaidOnly
			title
            titleSlug
            topicTags {
                name
            }
		}
	}
}
"""
)

question_query = gql(
    """
query questionTitle($titleSlug: String!) {
	question(titleSlug: $titleSlug) {
		title
		titleSlug
		paidOnly: isPaidOnly
		difficulty
		categoryTitle
		topicTags {
			name
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


async def get_company_stats_embed(gql_client, company_query, title_slug):
    """Fetches company stats and creates an embed with company encounter summaries."""

    async def extract_company_data(result):
        """Extracts company data from the GraphQL result."""
        return result["question"]["companyTagStats"]

    async def create_embed(company_data):
        """Creates an embed with fields for each company category."""
        embed = discord.Embed(title="Company Encounter Summary")
        for category, companies in company_data.items():
            field_value = "\n".join(
                f"✅ **{company['name']}** ({company['timesEncountered']})"
                for company in companies
            )
            embed.add_field(
                name=f"Category {category}", value=field_value, inline=False)
        return embed

    company_stats_result = await gql_client.execute_async(company_query, variable_values={"titleSlug": title_slug})
    company_data = await extract_company_data(company_stats_result)
    return await create_embed(json.loads(company_data))


async def get_similar_questions_embed(gql_client, similar_query, title_slug):
    """Fetches similar questions and creates an embed with their details."""

    async def extract_similar_questions(result):
        """Extracts similar question data from the GraphQL result."""
        return result["question"]["similarQuestionList"]

    async def create_embed(questions):
        """Creates an embed with fields for each question."""
        embed = discord.Embed(title="Similar Questions")
        for question in questions:
            title = question["title"]
            link = f"https://leetcode.com/problems/{question['titleSlug']}"
            is_paid_only = question["isPaidOnly"]
            title_text = title + (" (Paid Only)" if is_paid_only else "")
            embed.add_field(name=title_text, value=link, inline=False)
        return embed

    similar_result = await gql_client.execute_async(similar_query, variable_values={"titleSlug": title_slug})
    similar_questions = await extract_similar_questions(similar_result)
    return await create_embed(similar_questions)


async def get_question_embed(gql_client, query_to_run, result_key, query_type, description, title_slug="", title=""):
    variables = {}
    """Fetches LeetCode question data and creates a Discord embed."""
    async def create_embed(question_data, embed_description, title):
        """Creates a Discord embed with fields from question data."""
        question_title = question_data["title"]
        if "Daily" in title:
            embed_title = f"{title} - {question_title}"
        else:
            embed_title = f"{question_title}"
        embed = discord.Embed(
            title=embed_title,
            description=description
        )
        for field_name, value in question_data.items():
            embed.add_field(name=field_name.title(), value=value, inline=True)
        return embed

    async def extract_question_data(result, result_key, query_type, title_slug):
        """Extracts relevant question data from the GraphQL result."""
        if "daily" in query_type:
            return {
                "title": data["question"]["title"],
                "date": data["date"],
                "link": f"https://leetcode.com{data['link']}",
                "paid_only": data["question"]["paidOnly"],
                "topics": ",".join(item["name"] for item in data["question"]["topicTags"]),
                "difficulty": f"||{data['question']['difficulty']}||"
            }
        elif "question" in query_type:
            return {
                "title": data["title"],
                "link": f"https://leetcode.com/{data['titleSlug']}",
                "paid_only": data["paidOnly"],
                "topics": ",".join(item["name"] for item in data["topicTags"]),
                "difficulty": f"||{data['difficulty']}||"
            }

    if "question" in query_type:
        variables = {
            "titleSlug": title_slug
        }
    result = await gql_client.execute_async(query_to_run, variable_values=variables)
    data = result[result_key]
    question_data = await extract_question_data(result=data, result_key=result_key, query_type=query_type, title_slug=title_slug)
    if "daily" in query_type:
        return await create_embed(question_data, embed_description=description, title=title),  data["question"]["titleSlug"]
    return await create_embed(question_data, embed_description=description, title=title)


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")


@client.command(name="daily")
async def daily(ctx):
    main_embed, title_slug = await get_question_embed(gql_client=gql_client, query_to_run=daily_query, result_key="activeDailyCodingChallengeQuestion", query_type="daily", description="This is the daily LeetCode question, Good Luck!", title="Daily LC")
    embeds = [
        main_embed,
        await get_company_stats_embed(gql_client=gql_client, company_query=company_query, title_slug=title_slug),
        await get_similar_questions_embed(gql_client=gql_client, similar_query=similar_query, title_slug=title_slug)]

    await ctx.send(embeds=embeds)


@client.command(name="question")
async def question(ctx, arg):
    main_embed = await get_question_embed(gql_client=gql_client, query_to_run=question_query, result_key="question", query_type="question", description="LC Question Details", title_slug=arg)
    embeds = [
        main_embed,
        await get_company_stats_embed(gql_client=gql_client, company_query=company_query, title_slug=arg),
        await get_similar_questions_embed(gql_client=gql_client, similar_query=similar_query, title_slug=arg)]

    await ctx.send(embeds=embeds)


@client.command(name="ping")
async def ping(ctx):
    await ctx.send(f'Pong! In {round(client.latency * 1000)}ms')


client.run(os.environ.get('DISCORD_BOT_TOKEN'))
