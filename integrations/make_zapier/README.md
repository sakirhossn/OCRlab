# Unlimited OCR Cloud — Make.com & Zapier Integration Guide

Connect **Unlimited OCR Cloud** to thousands of business applications (Slack, Google Drive, Salesforce, QuickBooks, HubSpot) via Make or Zapier without writing code.

---

## 1. Make.com (Integromat) Workflow

### Trigger: New Document in Cloud Storage (Google Drive / Dropbox)
1. Add module: **Google Drive > Watch Files in a Folder**.
2. Add module: **Google Drive > Download a File**.

### Action: Submit to Unlimited OCR
3. Add module: **HTTP > Make a request**:
   - **URL**: `https://api.ocrlab.cloud/v1/documents`
   - **Method**: `POST`
   - **Body type**: `Multipart/form-data`
   - **Fields**:
     - `file`: Map the binary data from Step 2 (Filename & Data).
     - `mode`: `auto`
   - **Headers**:
     - `Authorization`: `Bearer ocr_live_your_api_key_here`
4. Parse response: Extracts `job_id`.

### Webhook / Wait: Receive Notification
5. Add module: **Custom Webhook**:
   - Copy the webhook URL into your Unlimited OCR Dashboard under **Webhooks**.
   - Unlimited OCR Cloud delivers signed HMAC event `job.completed` with `job_id`.

### Action: Fetch Structured Results
6. Add module: **HTTP > Make a request**:
   - **URL**: `https://api.ocrlab.cloud/v1/jobs/{{job_id}}/result?format=json`
   - **Method**: `GET`
   - **Headers**: `Authorization: Bearer ocr_live_your_api_key_here`
7. Iterate through `pages[].blocks[]` and route extracted tables to Google Sheets or QuickBooks!

---

## 2. Zapier Integration

### Step 1: Trigger
- App: **Gmail** or **Email Parser by Zapier** -> "New Attachment".

### Step 2: Action (API Upload)
- App: **Webhooks by Zapier** -> "Custom Request":
  - **Method**: `POST`
  - **URL**: `https://api.ocrlab.cloud/v1/documents`
  - **Data**: Form data with attachment binary.
  - **Headers**:
    - `Authorization`: `Bearer ocr_live_xxxxxxxxxxxxxxxxxxxxxxxx`

### Step 3: Catch Webhook & Complete
- Use Zapier Webhooks "Catch Hook" to listen for `job.completed`, then invoke `GET /v1/jobs/{id}/result`.
