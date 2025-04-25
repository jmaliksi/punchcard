# Punchcard
A simple, self-hostable habit tracker inspired by [the Yetch Every Day Goal Calendar](https://yetch.studio/products/every-day-goal-calendar).

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
    image: ghcr.io/jmaliksi/punchcard
    container_name: punchcard
    volumes:
      - /apps/punchcard/data:/app/data
    environment:
      PUNCHCARD_USERNAME: "leave blank for no auth"
      PUNCHCARD_PASSWORD: "leave blank for no auth"
    ports:
      - 5001:5001
```
