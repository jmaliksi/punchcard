# Punchcard
A simple, self-hostable habit tracker inspired by [Simone Giertz' Every Day Goal Calendar](https://yetch.studio/products/every-day-goal-calendar).

![Screen Shot 2025-04-25 at 14 09 22](https://github.com/user-attachments/assets/519ba0f2-b0e6-410f-bfa6-6a7a6d368841)


# Development
```
pip install -r requirements.txt
cd punchcard
fastapi dev main.py
```

# Deployment
compose.yml
```
version: "3.8"
services:
  punchcard:
    restart: unless-stopped
    image: ghcr.io/jmaliksi/punchcard:main
    container_name: punchcard
    volumes:
      - /apps/punchcard/data:/app/data
    environment:
      PUNCHCARD_USERNAME: "leave blank for no auth"
      PUNCHCARD_PASSWORD: "leave blank for no auth"
    ports:
      - 5001:5001
```

# Troubleshooting
If you get a `sqlite3.OperationalError: no such table: punchcards` on service start, this may mean that the database on disc was not created with the correct user permissions. SQLite needs read/write on both the db file **and** its parent folder on the **host machine**. Running `chmod -R u+w` on the db parent folder, as well as making sure chown all matches up should resolve the permissions error, and the service will attempt to create the table after a restart.
