import os
import re
import smtplib
import requests
from email.message import EmailMessage
from io import BytesIO
from typing import List, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from PyPDF2 import PdfReader

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq

load_dotenv()
app = FastAPI()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
ATS_THRESHOLD = 79

with open("job_description.txt", "r") as jd_file:
    JOB_DESCRIPTION = jd_file.read()

class ResumeURLsRequest(BaseModel):
    resume_urls: List[str]

def extract_text_from_pdf_bytes(pdf_bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def extract_email(text: str) -> str | None:
    match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    return match.group(0) if match else None

def evaluate_ats_score(resume_text: str, job_description: str) -> int:
    system_prompt = f"""
        Rate the resume on how well it matches the job description. Only return a number between 0 to 100.

        Job Description:
        {job_description}

        Resume:
        {resume_text}

        Please give me score only nothing else.
    """
    chat_bot_prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", "")]
    )

    chat_bot = ChatGroq(
        temperature=0,
        groq_api_key=os.getenv("GROQ_API"),
        model_name="llama3-8b-8192"
    )

    chat_bot_chain = chat_bot_prompt | chat_bot | StrOutputParser()
    response = chat_bot_chain.invoke({"message": system_prompt})
    
    try:
        return int(response.strip())
    except ValueError:
        return 0

def send_email(to_email: str, score: int):
    msg = EmailMessage()
    msg["Subject"] = "Congratulations! Your resume passed the ATS screening"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(f"Hey there,\n\nYour resume passed the ATS screening with a score of {score}.\nWe'll be in touch soon!\n\nCheers!")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
    except Exception as e:
        print("Email send failed:", e)


def normalize_drive_link(url: str) -> str:
    """
    Convert a Google Drive share link to a direct download link.
    """
    drive_file_pattern = r"https?://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)/view\??.*"
    match = re.match(drive_file_pattern, url)
    if match:
        file_id = match.group(1)
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        print(f"🔁 Converted Google Drive link: {download_url}")
        return download_url
    return url  # If not a Google Drive link, return as-is

def is_valid_pdf_url(url: str) -> bool:
    """
    Check if the URL returns a valid PDF response.
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/pdf",
        }

        response = requests.get(url, stream=True, timeout=10,headers=headers)
        content_type = response.headers.get('Content-Type', '')
        return(response.status_code == 200 or response.status_code== 201) 
    except Exception as e:
        print(f"⚠️ Error while checking URL: {e}")
        return False
    

def convert_drive_link(link: str) -> str:
    """
    Convert Google Drive share/view link to direct download link.
    """
    drive_match = re.search(r"drive\.google\.com/file/d/([a-zA-Z0-9_-]+)", link)
    if drive_match:
        file_id = drive_match.group(1)
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return link  # If not a drive link, return as-is

def get_valid_pdf_url(original_url: str) -> tuple[str, bool]:
    """
    If the original URL is not valid, attempt to normalize and retry.
    Returns a tuple of (url, is_valid).
    """
    if is_valid_pdf_url(original_url):
        return original_url, True

    normalized_url = normalize_drive_link(original_url)
    print(normalized_url)
    if is_valid_pdf_url(normalized_url):
        return normalized_url, True

    print("❌ Unable to fetch a valid PDF from the provided URL.")
    return original_url, False


def download_pdf_from_drive(drive_url: str):
    try:
        # Convert Google Drive link to direct download link
        url = convert_drive_link(drive_url)
        print(f"🚀 Attempting to download: {url}")

        # Send GET request with proper headers to simulate browser download
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/pdf",
        }

        # Make request with allow_redirects set to True
        response = requests.get(url, headers=headers, allow_redirects=True)

        # Check if the response is successful
        if response.status_code == 200 or response.status_code==201:
            print("✅ Successfully retrieved the file!")
            return response  # You can now process the PDF
        else:
            print(f"❌ Failed to download file. Status code: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return None

@app.post("/evaluate-resumes/")
def evaluate_multiple_resumes(payload: ResumeURLsRequest):
    try:
        results: List[Dict] = []

        for url in payload.resume_urls:
            print(url)
            try:
                valid_url, is_valid = get_valid_pdf_url(url)
                result = {"url": valid_url}
                
                if not is_valid:
                    result.update({
                        "status": "Invalid PDF URL",
                        "score": None,
                        "email": None
                    })
                    results.append(result)
                    continue

                response = download_pdf_from_drive(url)
                print("pdf response",response)
                if response==None:
                    result.update({
                        "status": "Failed to download PDF",
                        "score": None,
                        "email": None
                    })
                    results.append(result)
                    continue

                resume_text = extract_text_from_pdf_bytes(response.content)
                email = extract_email(resume_text)

                if not email:
                    result.update({
                        "status": "No email found in resume",
                        "score": None,
                        "email": None
                    })
                    results.append(result)
                    continue

                score = evaluate_ats_score(resume_text, JOB_DESCRIPTION)
                result.update({
                    "score": score,
                    "email": email,
                    "status": "Passed" if score >= ATS_THRESHOLD else "Below threshold"
                })

                if score >= ATS_THRESHOLD:
                    send_email(email, score)

            except Exception as e:
                result.update({
                    "status": f"Error: {str(e)}",
                    "score": None,
                    "email": None
                })

            results.append(result)

        return {"results": results}
    except Exception as e:
        return {"error": f"Internal Server Error : {e}"}

@app.get("/")
def hello():
    return {"status": "ok"}


@app.get("/health")
def health_check():
    return {"status": "ok"}



# backup-code
# import os
# import re
# import requests
# from langchain_community.llms import HuggingFaceHub
# # from pdfminer.high_level import extract_text
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_groq import ChatGroq
# from langchain_core.output_parsers import StrOutputParser

# import smtplib
# import PyPDF2
# from email.message import EmailMessage
# from dotenv import load_dotenv

# load_dotenv()


# EMAIL_USER = os.getenv("EMAIL_USER")
# EMAIL_PASS = os.getenv("EMAIL_PASS")
# RESUME_FOLDER = "resumes"
# JOB_DESC_FILE = "job_description.txt"
# ATS_THRESHOLD = 79


# def extract_text_from_pdf(file_path):
#     with open(file_path, 'rb') as file:
#         reader = PyPDF2.PdfReader(file)
#         text = ""
#         for page in reader.pages:
#             text += page.extract_text()
#         return text

# def extract_email(text):
#     match = re.search(r'[\w\.-]+@[\w\.-]+', text)
#     return match.group(0) if match else None

# # def evaluate_ats_score(resume_text, job_description):
# #     prompt = f"""
# # You are an ATS system. Given the following resume and job description, score the resume out of 100 based on how well it matches.

# # Resume:
# # {resume_text}

# # Job Description:
# # {job_description}

# # Return only the score in this format: SCORE: 85
# # """
# #     response = openai.ChatCompletion.create(
# #         model="gpt-3.5-turbo",
# #         messages=[{"role": "user", "content": prompt}],
# #         temperature=0
# #     )
# #     text = response['choices'][0]['message']['content']
# #     match = re.search(r"SCORE:\s*(\d+)", text)
# #     return int(match.group(1)) if match else 0

# def evaluate_ats_score(resume_text,job_description):
#     # Provide only a **single numerical score from 0 to 100** as the final output. Do not include any additional explanation or text.
#     # Also please keep one thing your mid you're evaluating the resjume and the jd so may be there is a chance that you need to check the required experiecne and experience mentioned in resume , the core concepts mentioend in jd and mentioned in the resume and at the end you'll give e the score of the resume for that partifcularjd with reason what needs to improve
#     system_prompt = f"""
#         Rate the resume on how well it matches the job description. Only return a number between 0 to 100.

    
#             Job Description:
#             {job_description}
    
#             Resume:
#             {resume_text}
#         Please give me score only nothing else
#             """
#     # llm = HuggingFaceHub(
#     #     #  repo_id="mistralai/Mistral-7B-Instruct-v0.2", 
#     #     repo_id="igscience/bloomz-560m",
#     #     model_kwargs={"temperature": 0.5, "max_new_tokens": 64},
#     #         # model_kwargs={"temperature": 0.5, "max_new_tokens": 512},
#     #         huggingfacehub_api_token=HUGGINGFACE_API_TOKEN
#     # )
#     chat_bot_prompt = ChatPromptTemplate.from_messages(
#         [
#             ("system", system_prompt),
#             ("human", ""),
#         ]
#     )

#     chat_bot = ChatGroq(
#         temperature=0,
#         groq_api_key=os.environ.get("GROQ_API"),
#         model_name="llama3-8b-8192",
#     )

#     chat_bot_chain = chat_bot_prompt | chat_bot | StrOutputParser()

#     response= chat_bot_chain.invoke({"message": system_prompt})
#     print(response,"RESPONSE OF HUGGING")
#     # result = response.json()
#     # print(result,"Result of hugging face api")
#     # match = re.search(r'Score:\s*(\d+)', response)
#     # score = int(match.group(1)) if match else 0
#     # # output = result[0]["generated_text"]
#     # return 0
#     return int(response)

# def send_email(to_email, score):
#     msg = EmailMessage()
#     msg["Subject"] = "Congratulations! Your resume passed the ATS screening"
#     msg["From"] = EMAIL_USER
#     msg["To"] = to_email
#     msg.set_content(f"Hey there,\n\nYour resume has successfully passed our ATS screening with a score of {score}.\nWe'll be in touch with next steps!\n\nCheers!")
#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
#             print("Inside Send Email Function")
#             smtp.login(EMAIL_USER, EMAIL_PASS)
#             smtp.send_message(msg)
#             print(f"Sent an email to {to_email}")
#     except Exception as e:
#         print("Gettign an error",e)

# def main():
#     with open(JOB_DESC_FILE, "r") as jd_file:
#         job_description = jd_file.read()

#     for filename in os.listdir(RESUME_FOLDER):
#         if filename.endswith(".pdf"):
#             path = os.path.join(RESUME_FOLDER, filename)
#             resume_text = extract_text_from_pdf(path)
#             email = extract_email(resume_text)

#             if not email:
#                 print(f"❌ No email found in {filename}")
#                 continue

#             score = evaluate_ats_score(resume_text, job_description)
#             print(f"✅ {filename}: ATS Score = {score}, Email = {email}")

#             if score >= ATS_THRESHOLD:
#                 send_email(email, score)
#                 print(f"📩 Mail sent to {email} for {filename}")

# if __name__ == "__main__":
#     main()
#     # send_email("vinitchokshi1809@gmail.com",99)

