# XLSForm Translation Review Portal

Flask foundation for an XLSForm translation review portal.

This phase includes only the application factory, configuration, Flask extensions,
Bootstrap base template, home page, and health route. XLSForm import, reviewer
editing, user management, dashboards, and export are intentionally not implemented yet.

## Source XLSForm

The source workbook is kept unchanged at:

```text
source_files/va_who_2022_All_Language_Training-Module.xlsx
```

Observed workbook sheets:

- `survey`
- `choices`
- `settings`

## Windows Setup

From PowerShell in the project directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
flask run
```

Open:

```text
http://127.0.0.1:5000/
http://127.0.0.1:5000/health
```

## Configuration

Local development uses SQLite by default through `DATABASE_URL`:

```text
DATABASE_URL=sqlite:///instance/app.db
```

To use PostgreSQL later, change only `DATABASE_URL`, for example:

```text
DATABASE_URL=postgresql://username:password@localhost:5432/xlsform_review
```
