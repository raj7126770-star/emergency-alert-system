# Project Structure

```
emergency-alert-system/
├── run.py                  # Local Flask entry point
├── requirements.txt
├── .env                    # Local secrets; never commit this file
├── backend/
│   ├── __init__.py
│   └── app.py              # Routes, authentication, database and SMS logic
├── frontend/
│   └── templates/          # Jinja HTML pages
├── public/                 # CDN-served CSS and JavaScript on Vercel
│   ├── css/
│   └── js/
├── src/app.py              # Vercel's Flask function entry point
├── vercel.json             # Function configuration
├── .vercelignore           # Keeps local secrets/data out of deployments
└── database/
    ├── schema.sql          # SQLite schema
    └── emergency.db        # Local SQLite data
```

Run the application from the project root with `python run.py`. Flask is
configured to serve `frontend/templates` and `public` at the normal `/static`
URL. Vercel serves files in `public` through its CDN.
