import subprocess

app_labels = ["accounting", "admin", "auth", "companies", "content_types", "hr", "inventory", "project_costing", "purchase", "registration", "sales", "users"]

# Get a list of all migrations
migrations = {}

for app_label in app_labels:
    result = subprocess.run(
        ["python", "manage.py", "showmigrations", app_label],
        capture_output=True, text=True
    )

    # Parse the output to get the list of migrations that have not been applied
    migrations[app_label] = [
        line.strip().split(" ")[-1]
        for line in result.stdout.splitlines()
        if line.strip() and not line.startswith("[X]")
    ]

# Run sqlmigrate for each migration in each app
for app_label, app_migrations in migrations.items():
    for migration in app_migrations:
        print(f"\n--- SQL for migration {migration} in app {app_label} ---")
        subprocess.run(["python", "manage.py", "sqlmigrate", app_label, migration])
