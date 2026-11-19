import json
import os
import re
import uuid
import html
import base64
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# These defaults match the addresses supplied for this project.
# You can instead set TABLE_NAME, RECIPIENT_EMAIL and SENDER_EMAIL
# as Lambda environment variables.
TABLE_NAME = os.environ.get("TABLE_NAME", "ContactFormSubmissions")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "jazzman22@gmail.com")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "anyanwuvalex@gmail.com")

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
ses = boto3.client("ses", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def build_response(status_code, body):
    """Return an API Gateway Lambda proxy response with CORS headers."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(body)
    }


def get_http_method(event):
    """Support both REST API (v1) and HTTP API (v2) event formats."""
    return (
        event.get("httpMethod")
        or event.get("requestContext", {}).get("http", {}).get("method")
        or ""
    ).upper()


def get_source_ip(event):
    request_context = event.get("requestContext", {})
    return (
        request_context.get("http", {}).get("sourceIp")
        or request_context.get("identity", {}).get("sourceIp")
        or "unknown"
    )


def parse_request_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        return {}

    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(raw_body).decode("utf-8")

    if isinstance(raw_body, dict):
        return raw_body

    return json.loads(raw_body)


def send_notification(name, visitor_email, subject, message, timestamp, submission_id):
    """Send the owner a notification using the verified SES sender identity."""
    safe_name = html.escape(name)
    safe_email = html.escape(visitor_email)
    safe_subject = html.escape(subject)
    safe_message = html.escape(message).replace("\n", "<br>")
    safe_timestamp = html.escape(timestamp)
    safe_submission_id = html.escape(submission_id)

    text_body = (
        "New Contact Form Submission\n"
        "============================\n\n"
        f"Name: {name}\n"
        f"Email: {visitor_email}\n"
        f"Subject: {subject}\n"
        f"Date: {timestamp}\n\n"
        f"Message:\n{message}\n\n"
        f"Submission ID: {submission_id}"
    )

    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#222">
      <h2 style="color:#f97316">New Contact Form Submission</h2>
      <table style="width:100%;border-collapse:collapse">
        <tr><td style="padding:8px;font-weight:bold">Name</td><td style="padding:8px">{safe_name}</td></tr>
        <tr style="background:#f7f7f7"><td style="padding:8px;font-weight:bold">Email</td><td style="padding:8px"><a href="mailto:{safe_email}">{safe_email}</a></td></tr>
        <tr><td style="padding:8px;font-weight:bold">Subject</td><td style="padding:8px">{safe_subject}</td></tr>
        <tr style="background:#f7f7f7"><td style="padding:8px;font-weight:bold">Date</td><td style="padding:8px">{safe_timestamp}</td></tr>
      </table>
      <h3>Message</h3>
      <div style="background:#f5f5f5;padding:16px;border-radius:8px">{safe_message}</div>
      <p style="font-size:12px;color:#777">Submission ID: {safe_submission_id}</p>
    </div>
    """

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        ReplyToAddresses=[visitor_email],
        Message={
            "Subject": {
                "Data": f"Contact Form: {subject}",
                "Charset": "UTF-8"
            },
            "Body": {
                "Text": {"Data": text_body, "Charset": "UTF-8"},
                "Html": {"Data": html_body, "Charset": "UTF-8"}
            }
        }
    )


def lambda_handler(event, context):
    """Receive a contact form submission, store it, then email a notification."""
    logger.info("Received contact form request")

    method = get_http_method(event)

    if method == "OPTIONS":
        return build_response(200, {"message": "CORS preflight successful"})

    if method != "POST":
        return build_response(405, {"error": "Method not allowed"})

    try:
        body = parse_request_body(event)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as error:
        logger.warning("Could not parse request body: %s", str(error))
        return build_response(400, {"error": "Request body must contain valid JSON."})

    if not isinstance(body, dict):
        return build_response(400, {"error": "Request body must be a JSON object."})

    name = str(body.get("name", "")).strip()
    visitor_email = str(body.get("email", "")).strip()
    subject = str(body.get("subject", "")).strip() or "No Subject"
    message = str(body.get("message", "")).strip()

    errors = []
    if not name:
        errors.append("Name is required.")
    elif len(name) > 100:
        errors.append("Name must be 100 characters or fewer.")

    if not visitor_email:
        errors.append("Email is required.")
    elif len(visitor_email) > 254 or not EMAIL_PATTERN.match(visitor_email):
        errors.append("Enter a valid email address.")

    if not message:
        errors.append("Message is required.")
    elif len(message) > 5000:
        errors.append("Message must be 5,000 characters or fewer.")

    if len(subject) > 200:
        errors.append("Subject must be 200 characters or fewer.")

    if errors:
        return build_response(400, {
            "error": "Please correct the form errors.",
            "details": errors
        })

    submission_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    item = {
        "submission_id": submission_id,
        "name": name,
        "email": visitor_email,
        "subject": subject,
        "message": message,
        "submitted_at": timestamp,
        "source_ip": get_source_ip(event)
    }

    # Save first. If this fails, return an error and do not claim the message was received.
    try:
        table.put_item(Item=item)
        logger.info("Submission stored in DynamoDB: %s", submission_id)
    except ClientError:
        logger.exception("DynamoDB PutItem failed")
        return build_response(500, {
            "error": "We could not save your message. Please try again later."
        })

    # Email failure does not delete the saved message. The response tells the frontend
    # that the message was saved but that the notification email did not go out.
    try:
        send_notification(
            name,
            visitor_email,
            subject,
            message,
            timestamp,
            submission_id
        )
        logger.info("SES notification sent for submission: %s", submission_id)
        email_sent = True
    except ClientError:
        logger.exception("SES notification failed for submission: %s", submission_id)
        email_sent = False

    return build_response(200, {
        "message": "Your message has been received.",
        "submission_id": submission_id,
        "email_sent": email_sent
    })
