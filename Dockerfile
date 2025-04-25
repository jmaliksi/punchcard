FROM python:3.12-slim
EXPOSE 5001

WORKDIR /app
RUN mkdir /app/data
VOLUME /app/data

COPY ./punchcard requirements.txt ./
RUN pip install -r requirements.txt
RUN pip install "uvicorn[standard]"

RUN python -m main
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001", "--proxy-headers", "--forwarded-allow-ips", "*"]
