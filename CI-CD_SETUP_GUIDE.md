# CI/CD Setup Guide - Data Watchdog

## What is CI/CD?

CI/CD stands for **Continuous Integration / Continuous Deployment**. It automatically runs tests, checks code quality, builds Docker images, and sends notifications every time you push code to GitHub.

**Without CI/CD:** You push code, manually test, hope nothing breaks.
**With CI/CD:** You push code, everything is tested automatically, you get notified of results.

---

## Step 1: Push Files to GitHub

```bash
git add .github/ requirements-dev.txt tests/ Dockerfile.prod docker-compose.test.yml
git add QUICK_IMPLEMENTATION_STEPS.md CI-CD_SETUP_GUIDE.md NOTIFICATIONS_PREVIEW.md CI-CD_SUMMARY.md CI-CD_README_FOR_TEAM.md
git commit -m "Add CI/CD pipeline with automated testing, Slack & Gmail notifications"
git push origin main
```

---

## Step 2: Get Slack Webhook URL

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** > **"From scratch"**
3. App name: `Data Watchdog`
4. Select your workspace
5. Click **"Incoming Webhooks"** in the left sidebar
6. Toggle **Active** to ON
7. Click **"Add New Webhook to Workspace"**
8. Select a channel (e.g., `#deployments` or `#general`)
9. Click **"Allow"**
10. Copy the webhook URL (looks like `https://hooks.slack.com/services/T.../B.../xxx`)

---

## Step 3: Get Gmail App Password

1. Go to https://myaccount.google.com/security
2. Enable **2-Step Verification** (required)
3. After enabling, go back to Security page
4. Find **"App passwords"** (search in Google Account settings)
5. Select: App = **Mail**, Device = **Windows Computer**
6. Click **Generate**
7. Google shows a 16-character password (e.g., `abcd efgh ijkl mnop`)
8. Copy it **without spaces**: `abcdefghijklmnop`

---

## Step 4: Add GitHub Secrets

Go to your GitHub repo > **Settings** > **Secrets and variables** > **Actions**

Click **"New repository secret"** and add each:

### Secret 1: Slack Webhook
- Name: `SLACK_WEBHOOK_URL`
- Value: `https://hooks.slack.com/services/T.../B.../xxx`

### Secret 2: Gmail Username
- Name: `SMTP_USER`
- Value: `yourname@gmail.com`

### Secret 3: Gmail App Password
- Name: `SMTP_PASS`
- Value: `abcdefghijklmnop` (16 chars, no spaces)

### Secret 4: Gmail From Address
- Name: `SMTP_FROM`
- Value: `yourname@gmail.com`

### Secret 5: Notification Recipient
- Name: `ALERT_EMAIL`
- Value: `yourname@gmail.com` (or any email you want to notify)

---

## Step 5: Test the Pipeline

```bash
echo "# CI/CD verification" >> README.md
git add README.md
git commit -m "Test CI/CD pipeline"
git push origin main
```

Go to **GitHub** > **Actions** tab to watch the pipeline run.

---

## Understanding the Output

### GitHub Actions Tab
- **Green checkmark** = Build passed
- **Red X** = Build failed
- Click on any run to see detailed logs

### Each Run Shows:
1. **Checkout** - Downloads your code
2. **Python Setup** - Installs Python 3.11
3. **Install Dependencies** - Installs requirements
4. **PostgreSQL** - Starts test database
5. **Linting** - Checks code style
6. **Tests** - Runs pytest
7. **Docker Build** - Builds production image
8. **Notifications** - Sends Slack + Gmail alerts

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Slack not notifying | Check webhook URL has no extra spaces |
| Gmail not sending | Ensure app password is 16 chars without spaces |
| Tests failing | Click Actions > click run > see error details |
| Secrets not working | Verify names are EXACTLY as listed (case-sensitive) |
| Docker build failing | Check Dockerfile.prod syntax |

---

## Adding More Tests

Add new test functions to `tests/test_basic.py`:

```python
def test_my_new_feature():
    """Test description."""
    result = my_function()
    assert result == expected_value
```

Push to GitHub and the CI/CD pipeline will automatically run your new tests.
