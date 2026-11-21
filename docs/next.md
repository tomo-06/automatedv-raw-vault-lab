# 引き継ぎ（S01 終了時点）

## 現在地
- マイルストーン: M0 環境の再構築（残りはデータの利用規約確認のみ）
- 前回: S01 環境の再構築（完了、2026-11-18）

## S01 でやったこと
- リポジトリ automatedv-raw-vault-lab を作成（public、Apache-2.0）
- PostgreSQL 16-alpine（Docker、ポート 5433、named volume）
- uv + Python 3.12 + dbt-core / dbt-postgres 1.10.x
- dbt プロジェクトを dbt/ に作成（AutomateDV 0.11.5、dbt_utils 1.4.1、hash: SHA）
- Makefile（up / down / ps / psql / db-reset / deps / debug / run / test / build / clean）
- main に Ruleset（PR 必須・承認数 0・force push と削除の禁止）、squash merge のみ許可
- 確認: make debug 成功、make deps でパッケージ導入、make run 正常終了（モデルなし）

## 決めたこと
- リポジトリ名: automatedv-raw-vault-lab
- AutomateDV は 0.11.5 に上げる（最新に合わせる）
- 旧プロジェクトの既定値はすべて引き継ぐ（承認数のみ 0 に変更）
- PR のタイトル・本文はチャットで生成してコピペする
- データ本体の扱い | リポジトリに置かない（取得スクリプトのみ）。利用規約の確認は継続 | 2026/11/21 |

## 次回の着手点
- 平日: 法人番号公表サイト・gBizINFO の利用規約と再配布可否を確認し、docs/decisions.md に記録する
- S02（M1 データの準備）: 法人番号データの取得スクリプトと範囲の絞り込み、raw_stage への投入
- 決めること: 範囲の絞り込み条件（都道府県・件数の目安）

## メモ
- AutomateDV のグローバル変数は hash 以外は既定値のまま。必要になったら判断する
- DB のタイムゾーンは UTC のまま（M3 の LOAD_DATETIME 検証で扱う）
- docs/next.md と docs/decisions.md は S02 のブランチでコミットする
