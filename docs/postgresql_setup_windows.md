# PostgreSQL Setup Guide for Windows

This guide explains how to set up and verify PostgreSQL for the **Airline Price Index (APIx)** project on Windows.

---

## 1. Quick Verification (Check if PostgreSQL is Installed)

Open PowerShell and check if the PostgreSQL service is running:

```powershell
Get-Service *postgres*
```

If you see:
```text
Status   Name               DisplayName
------   ----               -----------
Running  postgresql-x64-18  postgresql-x64-18 - PostgreSQL Server...
```
PostgreSQL is already installed and running on your system!

---

## 2. Create the Database (`apix_db`)

### Option A: Using `psql` from the PostgreSQL Bin Directory

On Windows, PostgreSQL is installed at:
`C:\Program Files\PostgreSQL\<version>\bin\psql.exe` (e.g. version 18).

Run this command in PowerShell to create the `apix_db` database:

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "CREATE DATABASE apix_db;"
```
*(Enter your postgres superuser password when prompted).*

If the database already exists, you can verify it by listing databases:
```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -c "\l"
```

### Option B: Using pgAdmin GUI
1. Open **pgAdmin 4** from your Windows Start Menu.
2. Enter your master password to unlock the server.
3. Right-click on **Databases** -> **Create** -> **Database...**
4. Name the database `apix_db` and click **Save**.

### Option C: Using Docker (Alternative)
If you prefer running PostgreSQL in a clean Docker container:
```powershell
docker run --name apix-postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=apix_db -p 5432:5432 -d postgres:16
```

---

## 3. Update Your `.env` Configuration

In `flight-price-index/.env`, set your connection string:

```env
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/apix_db
```
Replace `YOUR_PASSWORD` with the password you set during PostgreSQL installation (often `postgres`, `admin`, or your custom password).

---

## 4. Automatic SQLite Fallback for Instant Testing

The application includes an automatic fallback:
If PostgreSQL is temporarily down or credentials are still being configured, setting:
```env
ALLOW_SQLITE_FALLBACK=true
```
allows the application to seamlessly create and query a local `apix_local.db` SQLite database so development, testing, and dashboard views never break.
