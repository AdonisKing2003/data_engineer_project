# Image chung cho cả nhóm: Python 3.11 + Java 17 + Spark (qua pyspark) + DuckDB + Streamlit
# Ghim bookworm vì Debian bản mới hơn không còn gói openjdk-17.
FROM python:3.11-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless procps make curl \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Java nằm ở thư mục khác nhau giữa máy Intel/AMD và Mac chip M: dò rồi trỏ /opt/java tới đó
RUN ln -sfn "$(dirname "$(dirname "$(readlink -f "$(which java)")")")" /opt/java \
 && echo "JAVA_HOME thật: $(readlink -f /opt/java)"
ENV JAVA_HOME=/opt/java

WORKDIR /work
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

EXPOSE 8501 4040
CMD ["sleep", "infinity"]
