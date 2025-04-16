# ATS (Applicant Tracking System)

A FastAPI-based Applicant Tracking System that automatically evaluates resumes against job descriptions, providing ATS compatibility scores and automated email notifications for qualified candidates.

## Features

- **PDF Resume Processing**: Supports both direct PDF URLs and Google Drive links
- **Automated Resume Evaluation**: Uses AI to score resumes against job descriptions
- **Email Notifications**: Automatically notifies candidates who pass the ATS threshold
- **Batch Processing**: Process multiple resumes simultaneously
- **Smart URL Handling**: Supports and converts various URL formats (especially Google Drive links)

## Prerequisites

- Python 3.8+
- A valid email account for sending notifications
- Groq API key for AI-powered resume evaluation

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Vinit-180/ats-agent
cd ats-agent
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```env
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_email_app_password
GROQ_API=your_groq_api_key
```

5. Create a `job_description.txt` file with your job requirements.

## Usage

1. Start the FastAPI server:
```bash
uvicorn main:app --reload
```

2. Send a POST request to `/evaluate-resumes/` with a JSON payload:
```json
{
    "resume_urls": [
        "https://example.com/resume1.pdf",
        "https://drive.google.com/file/d/your-file-id/view"
    ]
}
```

### API Endpoints

- `POST /evaluate-resumes/`: Submit resumes for evaluation
- `GET /health`: Health check endpoint
- `GET /`: Root endpoint

### Response Format

```json
{
    "results": [
        {
            "url": "https://example.com/resume1.pdf",
            "status": "Passed",
            "score": 85,
            "email": "candidate@example.com"
        }
    ]
}
```

## Status Codes

- **Passed**: Resume score meets or exceeds the ATS threshold (currently set to 79)
- **Below threshold**: Resume score is below the ATS threshold
- **Invalid PDF URL**: The provided URL is not accessible or is not a valid PDF
- **Failed to download PDF**: The system couldn't download the PDF from the provided URL
- **No email found in resume**: No valid email address was found in the resume

## Error Handling

The system handles various error cases:
- Invalid URLs
- Inaccessible PDFs
- Missing email addresses
- PDF parsing errors
- Network connectivity issues

## Security Notes

- Use environment variables for sensitive data
- The email password should be an app-specific password for Gmail
- Keep your Groq API key secure

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 