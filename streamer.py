import os

from dotenv import load_dotenv
from openai import OpenAI

from prompter import get_messages
from scraper import fetch_website_contents
from user_input import ask_choice

load_dotenv()

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
openrouter_base_url = os.getenv("OPENROUTER_BASE_URL")

openrouter_client = OpenAI(api_key=openrouter_api_key, base_url=openrouter_base_url)

MODEL = "openai/gpt-6-luna"


def stream_compelling_case():
    question = "What language would you like the professional career coach to speak?"
    options = ["English", "Spanish", "Italian", "German", "French"]
    language = ask_choice(question, options)

    profile_url = input("Enter your LinkedIn profile URL: ")
    experience_url = profile_url
    if not profile_url.endswith("/"):
        experience_url += "/"
    experience_url += "details/experience/"

    job_description_url = input("Enter the LinkedIn URL for the job description: ")

    try:
        profile_contents = fetch_website_contents(profile_url)
        experience_contents = fetch_website_contents(experience_url)
        job_contents = fetch_website_contents(job_description_url)
    except Exception as e:
        print(f"An error occurred while fetching website contents: {e}")

    messages = get_messages(
        language=language,
        profile_contents=profile_contents,
        experience_contents=experience_contents,
        job_contents=job_contents,
    )

    stream = openrouter_client.chat.completions.create(
        model=MODEL, messages=messages, stream=True
    )
    response = ""
    for chunk in stream:
        if not chunk.choices or not chunk.choices[0].delta:
            continue
        delta = chunk.choices[0].delta.content or ""
        response += delta
        print(delta, end="", flush=True)
    print()
    return response
