import subprocess

app_labels = ["accounting", "admin", "auth", "companies", "content_types", "hr", "inventory", "project_costing", "purchase", "registration", "sales", "users"]
# app_label = 'your_app_name'  # Replace with your app name

# Get a list of all migrations
# Run a for loop to go through all the apps
results = []
for app_label in app_labels:
	result_migrations = []
	result = subprocess.run(
    		["python", "manage.py", "showmigrations", app_label],
    		capture_output=True, text=True
	)
	result_migrations.append(result)
	results.append(result_migrations)
migrations = []
for result in results:
	migrations.append([
    		line.strip().split(" ")[-1]
   		for line in result.stdout.splitlines()
    		if line.strip() and not line.startswith(" [X]")
	])

# Run sqlmigrate for each migration
for migration in migrations:
    print(f"\n--- SQL for migration {migration} ---")
    subprocess.run(["python", "manage.py", "sqlmigrate", app_label, migration])
