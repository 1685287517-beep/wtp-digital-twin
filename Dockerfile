# One image, shared by the sim / historian / agent services.
# Each service overrides the command in docker-compose.yml.
FROM python:3.12-slim

WORKDIR /opt/wtp
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# default: run the simulator
CMD ["python", "-m", "app.sim_main"]
