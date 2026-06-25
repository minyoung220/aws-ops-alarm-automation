import json
import boto3
import urllib.request
import urllib.parse
import base64

s3 = boto3.client('s3', region_name='ap-northeast-1')
bedrock = boto3.client('bedrock-runtime', region_name='ap-northeast-1')

def lambda_handler(event, context):
    # [★修正されたコア解析部★: POSTリクエストだけでなく、GETリクエスト(クエリパラメータ)も同時にキャッチします！]
    body = {}
    if event.get('queryStringParameters'):
        body = event['queryStringParameters']
    elif event.get('body'):
        try:
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        except Exception:
            body = event
    else:
        body = event
        
    alarm_id = body.get('alarm_id', 'BJK220')
    # [セキュリティー保護] ご自身のS3バケット名に変更してください
    bucket_name = "YOUR_S3_BUCKET_NAME"
    file_key = "manual.json"
    
    try:
        response = s3.get_object(Bucket=bucket_name, Key=file_key)
        manual_db = json.loads(response['Body'].read().decode('utf-8'))
    except Exception as e:
        return {"statusCode": 500, "body": f"S3マニュアルのロードに失敗しました: {str(e)}"}
        
    if alarm_id not in manual_db:
        return {"statusCode": 404, "body": f"マニュアルに登録されていないアラームIDです: {alarm_id}"}
        
    target_manual = manual_db[alarm_id]
    
    # リクエストボディやクエリパラメータで強制指定されたタイプがあれば、それを最優先で適用します！
    alarm_type = body.get('alarm_type', target_manual['alarm_type'])
    
    if alarm_type == "SEIKAN":
        slack_text = f"【静観自動処理】 障害ID: {alarm_id} | JOB名: {target_manual['job_name']} - マニュアルに従い、自動停止およびモニタリング除外処理を実施しました。"
        return {
            "statusCode": 200,
            "result": {
                "alarm_id": alarm_id,
                "alarm_type": "SEIKAN",
                "action_target": "SILENT_CLOSE",
                "assignee": "System",
                "generated_slack_text": slack_text,
                "generated_voice_script": ""
            }
        }
        
    prompt = f"""
    あなたは日本の大手IT企業SCSKのトップクラスのクラウドインフラ障害対応AIオペレーターです。
    以下の[障害情報]と[対応マニュアル]をもとに、担当者へ送信するSlackメッセージと電話音声案内の台本を作成してください。

    [障害ID]: {alarm_id}
    [障害等級]: {alarm_type}
    [JOB/サーバー名]: {target_manual.get('job_name', '')}
    [マニュアル指示事項]: {target_manual.get('past_solution', '')}
    [JIRAリンク]: {target_manual.get('jira_url', '')}

    出力制約条件:
    1. 挨拶、余計な言葉、バッククォート(```)は使用せず、純粋なJSON Objectのみを出力してください。
    2. JSON Value内で実際の改行(Enter)をしないでください。必要な場合は '\\n' と表記してください。
    3. ダブルクォーテーション(")を使用しないでください。
    4. generated_voice_scriptは、約20秒分量のスマートな監視ブリーフィングスタイルで作成し、以下の4つを順番に含めてください:
       ① 「こちらはSCSKクラウドインフラ監視センターです。」
       ② 「障害ID {alarm_id}、{alarm_type} 等級にて、{target_manual.get('job_name', '')} にエラーが発生しました。」
       ③ 「マニュアルに従い、プロセスの強制終了後、再実行をお願いいたします。」
       ④ 「詳細なエラーログおよびJIRAチケットのリンクは、Slackチャンネルをご確認ください。」

    出力フォーマット:
    {{
        "alarm_id": "{alarm_id}",
        "alarm_type": "{alarm_type}",
        "action_target": "{target_manual.get('action_target', '')}",
        "assignee": "{target_manual.get('assignee', '')}",
        "generated_slack_text": "[丁寧な日本語のSlack本文]",
        "generated_voice_script": "[20秒分量の電話台本]"
    }}
    """
    
    try:
        bedrock_req = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000, 
            "messages": [{"role": "user", "content": prompt}]
        }
        
        bedrock_resp = bedrock.invoke_model(
            modelId='arn:aws:bedrock:ap-northeast-1:532287338885:inference-profile/jp.anthropic.claude-sonnet-4-6',
            body=json.dumps(bedrock_req)
        )
        
        raw_response_body = bedrock_resp['body'].read().decode('utf-8')
        parsed_response = json.loads(raw_response_body)
        ai_result_text = parsed_response['content'][0]['text'].strip()
        
        if ai_result_text.startswith("```json"):
            ai_result_text = ai_result_text[7:]
        if ai_result_text.startswith("```"):
            ai_result_text