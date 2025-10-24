# Blind Tech Visionary Feedback Bot

A FastAPI-based Telegram bot to collect feedback from users and send it to the admin.

---

## Requirements

- Python 3.10+  
- Telegram Bot Token  
- Vercel account for deployment

---

## Project Structure```
.
├── main.py             # FastAPI bot code
├── requirements.txt    # Dependencies
├── vercel.json         # Vercel deployment config
└── README.md
```

---
## requirements.txt

```
fastapi
uvicorn
python-telegram-bot
```

*(No pinned versions required)*

---
## vercel.json

```json
{
  "version": 3,
  "builds": [
    { "src": "main.py", "use": "@vercel/python" }
  ],
  "routes": [
    { "src": "/(.*)", "dest": "/main.py" }
  ]
}
```

---
## Environment Variables

Set the following in Vercel:

| Name         | Value                                    | Environment         |
| ------------ | ---------------------------------------- | ------------------ |
| WEBHOOK_URL  | https://feedbackbotsdf.vercel.app       | All Environments   |

*Use the “FastAPI” preset when adding the project.*

---
## Deploying to Vercel (First Time)

1. Push your code to GitHub (main branch).
2. Go to [Vercel Dashboard → New Project → Import Git Repository].
3. Select your repo and set **Preset** to `FastAPI`.
4. Add the environment variable `WEBHOOK_URL`.
5. Click **Deploy**.
6. After deployment, open:  
   ```
   https://feedbackbotsdf.vercel.app/set_webhook
   ```  
   This registers your Telegram webhook.

---
## Commands

- `/start` – Start the bot  
- `/reply` – Reply to a message  
- `/sendnewmessage` – Send new message to admin  
- `/sendmessagetoall` – Send message to all users (admin only)

---
## Notes

- Ensure main branch is deployed to activate production domain.
- Preview deploys work automatically but production URL needs a commit to main.
- Test with `/start` to confirm the bot is live.