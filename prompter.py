def get_system_prompt(language):
    return f"""You are a {language} speaking professional career coach who helps a candidate market themselves for a job.
To do this, you analyze the candidate’s LinkedIn profile and their “Experience” section, on the one hand, and the LinkedIn job posting, on the other.
Then, you provide a compelling case in {language}, written in the first person as if you were the candidate addressing the company, that demonstrates, with airtight logic, why the candidate is the perfect fit for the position.
Respond in markdown. Do not wrap the summary in a code block - respond just with the markdown.
"""


def get_user_prompt(language, profile_contents, experience_contents, job_contents):
    return f"""The candidate's LinkedIn profile is as follows:
{profile_contents}
The candidate's LinkedIn "Experience" section is as follows:
{experience_contents}
The LinkedIn job posting is as follows:
{job_contents}
Please provide a compelling case in {language}, written in the first person as if you were the candidate addressing the company, that demonstrates, with airtight logic, why the candidate is the perfect fit for the position.
"""


def get_messages(language, profile_contents, experience_contents, job_contents):
    system_prompt = get_system_prompt(language)
    user_prompt = get_user_prompt(
        language, profile_contents, experience_contents, job_contents
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
