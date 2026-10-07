# Chạy TRONG container:  docker compose exec app make <lệnh>
# (Máy Windows không có make thì gõ thẳng lệnh ở dòng bên dưới mỗi mục)

.PHONY: check bq-test staging test app

check:        ## 1.1b kiểm tra Spark, DuckDB, Streamlit, PostgreSQL, BigQuery
	python scripts/check_env.py

bq-test:      ## 1.2 nạp thử courses lên BigQuery
	python scripts/bq_smoke_test.py

staging:      ## 1.3 đọc 7 CSV vào data/staging
	cd etl && spark-submit --driver-memory $${SPARK_DRIVER_MEMORY:-3g} 01_staging.py

test:
	pytest -q

app:
	streamlit run app/Home.py --server.address 0.0.0.0 --server.port 8501
