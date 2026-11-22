ifneq (,$(wildcard .env))
include .env
export
endif

DBT_DIR   := dbt
DBT       := uv run dbt
DBT_FLAGS := --project-dir $(DBT_DIR) --profiles-dir $(DBT_DIR)

.DEFAULT_GOAL := help
.PHONY: help up down ps psql db-reset deps debug run test build clean load-houjin

load-houjin: ## 法人番号 zip を raw_stage に投入（例: make load-houjin ZIP=data/raw/xxx.zip ARGS="--city-code 201"）
	uv run python scripts/load_houjin.py $(ZIP) $(ARGS)

help: ## ターゲット一覧を表示
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

## --- Docker ---
up: ## Postgres を起動（healthy になるまで待つ）
	docker compose up -d --wait

down: ## Postgres を停止（データは残る）
	docker compose down

ps: ## コンテナの状態
	docker compose ps

psql: ## psql で接続
	docker compose exec postgres psql -U dbt -d avlab

db-reset: ## データを消して作り直す（volume 削除）
	docker compose down -v
	docker compose up -d --wait

## --- dbt ---
deps: ## dbt パッケージをインストール
	$(DBT) deps $(DBT_FLAGS)

debug: ## 接続確認
	$(DBT) debug $(DBT_FLAGS)

run: ## dbt run（例: make run ARGS="-s hub_corp"）
	$(DBT) run $(DBT_FLAGS) $(ARGS)

test: ## dbt test
	$(DBT) test $(DBT_FLAGS) $(ARGS)

build: ## dbt build
	$(DBT) build $(DBT_FLAGS) $(ARGS)

clean: ## target / dbt_packages を削除
	$(DBT) clean $(DBT_FLAGS)
