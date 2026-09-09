# Notifications Preview - CI/CD Pipeline

## Success Notifications

### Slack Message (Build Passed)

```
:white_check_mark: *Data Watchdog CI/CD - Build Successful*

*Branch:* main
*Author:* Maiyarasu
*Commit:* Add new feature
*Status:* All tests passed :tada:
*Link:* View Run
```

### Gmail Message (Build Passed)

```
Subject: Data Watchdog Build Passed - main

Hello,

The CI/CD pipeline for Data Watchdog has completed successfully.

Branch: main
Commit: Add new feature
Author: Maiyarasu
Status: All tests passed

View the full run here:
https://github.com/Maiii66/data-watchdog/actions/runs/123456

This message was sent automatically by Data Watchdog CI/CD.
```

---

## Failure Notifications

### Slack Message (Build Failed)

```
:x: *Data Watchdog CI/CD - Build Failed*

*Branch:* main
*Author:* Maiyarasu
*Commit:* Breaking change
*Status:* Build failed - please investigate :warning:
*Link:* View Run
```

### Gmail Message (Build Failed)

```
Subject: Data Watchdog Build FAILED - main

Hello,

The CI/CD pipeline for Data Watchdog has FAILED.

Branch: main
Commit: Breaking change
Author: Maiyarasu
Status: Build failed - please investigate

View the full run here:
https://github.com/Maiii66/data-watchdog/actions/runs/123457

This message was sent automatically by Data Watchdog CI/CD.
```

---

## Timeline of Notifications

```
Push code to GitHub
        |
        v
GitHub Actions starts (0:00)
        |
        v
Tests run (0:30 - 1:30)
        |
        v
Docker builds (1:30 - 2:30)
        |
        v
Slack notification sent (2:30)
        |
        v
Gmail notification sent (2:30)
        |
        v
Pipeline complete (2:30)
```

---

## Where Notifications Appear

- **Slack**: Channel you selected during webhook setup
- **Gmail**: Inbox of the email in `ALERT_EMAIL` secret
- **GitHub**: Actions tab shows green/red status
