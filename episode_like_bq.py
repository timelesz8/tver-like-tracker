# --- 修正後の upload_to_bigquery 関数 ---
def upload_to_bigquery(data_list):
    """取得したデータをBigQueryに一括保存"""
    table_ref = bq_client.dataset(DATASET_ID).table(TABLE_ID)
    json_data = "\n".join([json.dumps(d) for d in data_list])
    file_obj = io.StringIO(json_data)
    
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        # autodetectを一旦Falseにし、既存テーブルのスキーマを尊重するようにします
        autodetect=False, 
        write_disposition="WRITE_APPEND",
        # 【重要】スキーマ更新を許可しない設定にすることで、REQUIRED設定を維持します
        schema_update_options=[] 
    )
    try:
        load_job = bq_client.load_table_from_file(file_obj, table_ref, job_config=job_config)
        load_job.result()
        logger.info(f"BigQueryへのアップロード成功: {len(data_list)}件")
    except Exception as e:
        logger.error(f"BigQueryアップロードエラー: {e}")
