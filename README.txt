# PixelCraft Studio Contact Form

## Project files
- `index.html`
- `css/style.css`
- `js/app.js`
- `index.py` (AWS Lambda backend)

## 1. Frontend API URL
Open `js/app.js` and replace:
`PASTE_YOUR_API_GATEWAY_INVOKE_URL_HERE`
with your API Gateway invoke URL.

Example REST API URL:
`https://abc123.execute-api.us-east-1.amazonaws.com/prod`

Do not add `/contact` at the end. The JavaScript adds `/contact`.

If your HTTP API uses the `$default` stage, use its invoke URL without a stage suffix. If it uses a named stage such as `prod`, include `/prod`.

## 2. Lambda setup
- Runtime: a supported Python runtime (for example Python 3.12 or 3.13 if available in your account).
- Handler: `index.lambda_handler`
- Upload `index.py` as the Lambda code file.
- Region: use the same region as your DynamoDB table and SES identities. This project currently assumes `us-east-1`.
- Suggested timeout: 15 seconds.

## 3. DynamoDB
Create/confirm table:
- Table name: `ContactFormSubmissions`
- Partition key: `submission_id`
- Type: String
- No sort key required.

## 4. Lambda execution role permissions
Attach `AWSLambdaBasicExecutionRole` for CloudWatch logs.
Also grant:
- `dynamodb:PutItem` on the `ContactFormSubmissions` table ARN.
- `ses:SendEmail` for the SES identity/region used by this function.

## 5. SES
The sender identity `anyanwuvalex@gmail.com` must be verified in SES in `us-east-1`.
If the SES account is still in Sandbox, the recipient `jazzman22@gmail.com` must also be verified in that same region. Request production access to send to unverified recipients.

## 6. API Gateway
Create a `POST /contact` route integrated with this Lambda using Lambda proxy integration.
Deploy the API to a stage. The API URL configured in `js/app.js` must include that stage if it is a named stage.
Enable CORS for your S3 website origin, allowing POST and OPTIONS and the Content-Type header. For learning/testing, the Lambda response includes `Access-Control-Allow-Origin: *`; configure API Gateway CORS consistently and avoid conflicting CORS settings.

## 7. S3 upload
Upload the files preserving this exact structure:
- `index.html` at the bucket root
- `css/style.css`
- `js/app.js`

Then open the S3 website or CloudFront URL and test the form.

## 8. Test Lambda directly
Use this test event in the Lambda console:
```json
{
  "httpMethod": "POST",
  "body": "{\"name\":\"Test User\",\"email\":\"test@example.com\",\"subject\":\"Test message\",\"message\":\"Testing the PixelCraft contact form.\"}",
  "requestContext": {
    "identity": {
      "sourceIp": "127.0.0.1"
    }
  }
}
```
Expected result: HTTP statusCode 200 and `email_sent` true or false. The DynamoDB item should be saved either way, as long as the Lambda role has PutItem permission and the table exists in the same region.

If the result has `email_sent: false`, open the Lambda CloudWatch log stream to see the SES error. If DynamoDB save fails, Lambda returns HTTP 500 and logs the DynamoDB exception.