import discord
from discord.ext import commands
import datetime
from datetime import date, timezone, timedelta
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
import os
import dotenv
import logging
import json
import sentry_sdk
import subprocess
import shlex  # For safe command parsing

def configure_client():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    dotenv.load_dotenv()
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    client = commands.AutoShardedBot(
        intents=intents, command_prefix=os.environ.get("PREFIX"))
    transport = AIOHTTPTransport(
        url="https://leetcode.com/graphql",
        headers={"cookie": os.environ.get("LC_COOKIE")},
        ssl=True
    )
    gql_client = Client(transport=transport, fetch_schema_from_transport=False)
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),

        # Enable performance monitoring
        enable_tracing=True,
    )
    return client, gql_client


client, gql_client = configure_client()

# Define a function to log events


async def log_event(event):
    # Extract relevant information from the event
    # (e.g., event type, timestamp, user, message, etc.)
    message = f"Event: {event.__class__.__name__}"
    # Add further details based on the event type
    if isinstance(event, discord.Message):
        message += f"\nContent: {event.content}"
    elif isinstance(event, discord.MemberJoin):
        message += f"\nJoined: {event.member}"
    # ... Add logic for other event types
    logging.info(message)

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

def execute_command(command_tuple, check=True):
    try:
        result = subprocess.run(
            command_tuple,  # Directly pass the tuple as arguments
            check=check,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    except subprocess.CalledProcessError as e:
        stderr = e.stderr
        return None



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
                name=f"Category {category}", value=field_value, inline=False
            )
        return embed

    company_stats_result = await gql_client.execute_async(company_query, variable_values={"titleSlug": title_slug})
    company_data = await extract_company_data(company_stats_result)
    if not company_data:
        return discord.Embed(title="No Company Data Available")
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
    if not similar_questions:
        return discord.Embed(title="No Similar Questions Available")
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
                "topics": f"||{', '.join(item['name'] for item in data.get('topicTags', []))}||",
                "difficulty": f"||{data['question']['difficulty']}||"
            }
        elif "question" in query_type:
            return {
                "title": data["title"],
                "link": f"https://leetcode.com/{data['titleSlug']}",
                "paid_only": data["paidOnly"],
                "topics": f"||{', '.join(item['name'] for item in data.get('topicTags', []))}||",
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


async def find_message(target_channel: discord.TextChannel, ctx: discord.ext.commands.Context, search_string: str) -> None:
    if target_channel is None:
        await ctx.send("Target channel not found!")
        return

    # Fetch recent messages (adjust limit as needed)
    try:
        messages = target_channel.history(limit=100)
    except discord.HTTPException as e:
        await ctx.send(f"Failed to fetch messages: {e.__class__.__name__} - {e}")
        return

    # Search for matching message
    matching_messages = [message async for message in messages if search_string.lower() in message.content.lower()]

    if matching_messages:
        await ctx.send(f"Found message in {target_channel.mention}:\n{matching_messages[0].jump_url}")
        return
    else:
        await ctx.send(f"No message found containing {search_string} in the past 100 messages.")


async def get_thread_link(client: discord.Client, guild_id: int, thread_id: int) -> str:
    try:
        thread = client.get_guild(guild_id).get_thread(thread_id)
        if thread:
            return f"{thread.jump_url}"
        else:
            return None
    except discord.HTTPException as e:
        print(f"Error retrieving thread: {e}")
        return None


async def create_thread(target_channel, ctx, thread_name, embeds):
    if target_channel is None:
        await ctx.send("Target channel not found!")
        return

    # Check if user can create threads in target channel
    if not target_channel.permissions_for(ctx.author).create_public_threads:
        await ctx.send("You don't have permissions to create threads in this channel.")
        return

    # Check if thread already exists (using list threads method)
    for thread in target_channel.threads:
        if thread.name == thread_name:
            # Check thread creation time
            thread_creation_time = thread.created_at.astimezone(timezone.utc)
            utc_now = datetime.datetime.now(timezone.utc)

            # Calculate time difference in hours
            threshold_time = utc_now - timedelta(hours=24)

            if thread_creation_time >= threshold_time:
                await ctx.send(f"Thread {thread_name} already exists within the past 24 hours.")
                thread_link = await get_thread_link(client=client, guild_id=int(os.environ.get("GUILD_ID")), thread_id=thread.id)
                await ctx.send(thread_link)
                return

    try:
        thread = await target_channel.create_thread(name=thread_name, type=discord.ChannelType.public_thread)
        await thread.send(embeds=embeds)
        await ctx.send(f"Thread {thread_name} created in channel {target_channel.mention}")
    except discord.HTTPException as e:
        await ctx.send(f"Failed to create thread: {e}")


@client.event
async def on_ready():
    print(f"Logged in as {client.user} (ID: {client.user.id})")


@client.command(name="execute", description="Execute a console command")
@commands.is_owner()
async def execute(ctx, *command):
    try:
        response = execute_command(command)
        if response["err"]:
            print("Error:", response["stderr"])
        else:
            print("Standard output:", response["std"])
            await ctx.send(response["std"])
    except Exception as e:
        await ctx.send(f"Error: {e.args[0]}")
        return


@client.command(name="daily", description="Get Info about Daily LC Question")
async def daily(ctx):
    if isinstance(error, commands.CommandOnCooldown):
        # User is on cooldown, send informative message
        await ctx.send(f"Hey {ctx.author.mention}, this command is on cooldown. Please try again in {error.retry_after:.2f} seconds.")
    try:
        main_embed, title_slug = await get_question_embed(gql_client=gql_client, query_to_run=daily_query, result_key="activeDailyCodingChallengeQuestion", query_type="daily", description="This is the daily LeetCode question, Good Luck!", title="Daily LC")
        embeds = [
            main_embed,
            await get_company_stats_embed(gql_client=gql_client, company_query=company_query, title_slug=title_slug),
            await get_similar_questions_embed(gql_client=gql_client, similar_query=similar_query, title_slug=title_slug)]
        today = date.today().strftime("%Y-%m-%d")
        target_channel = client.get_channel(
            int(os.environ.get("LC_CHANNEL_ID")))
        thread = await create_thread(target_channel=target_channel, ctx=ctx, thread_name=f"Daily LC Thread For {today}", embeds=embeds)
    except Exception as e:
        print(f"Error: {e.args[0]}")
        return


@client.command(name="question", description="Get Info about a LC Question")
async def question(ctx, arg):
    try:
        main_embed = await get_question_embed(gql_client=gql_client, query_to_run=question_query, result_key="question", query_type="question", description="LC Question Details", title_slug=arg)
        embeds = [
            main_embed,
            await get_company_stats_embed(gql_client=gql_client, company_query=company_query, title_slug=arg),
            await get_similar_questions_embed(gql_client=gql_client, similar_query=similar_query, title_slug=arg)]
        target_channel = client.get_channel(
            int(os.environ.get("LC_CHANNEL_ID")))
        thread = await create_thread(target_channel=target_channel, ctx=ctx, thread_name=f"{arg} Thread", embeds=embeds)
    except Exception as e:
        print(f"Error: {e.args[0]}")
        return


@question.error
@daily.error
async def question_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        # User is on cooldown, send informative message
        await ctx.send(f"Hey {ctx.author.mention}, this command is on cooldown. Please try again in {error.retry_after:.2f} seconds.")
    if isinstance(error, commands.CommandInvokeError):
        # User is on cooldown, send informative message
        print(f"Error: {error.args[0]}")
        await ctx.send(f"Hey {ctx.author.mention}, this command is having some issues, please try again later.")

@client.command(name="ping", description="Ping Command")
async def ping(ctx):
    await ctx.send(f"Pong! In {round(client.latency * 1000)}ms")


@client.event
async def on_event(event):
    await log_event(event)


@client.event
async def on_ready():
    logging.log(logging.INFO, f"LC bot is ready.")

client.run(os.environ.get('DISCORD_BOT_TOKEN'))
