# [WHY] API Gatewayのハードタイムアウト(29秒)を回避するため、
# AI処理を待たずにSQSへメッセージを投げ(非同期処理)、クライアントへ即時200 OKを返却する受付用Lambdaです。

import json
import boto3
import urllib.parse
import os

# SQS クライアントの初期化
sqs = boto3.client('sqs', region_name='ap-northeast-1')

def lambda_handler(event, context):
    print("=== [Sherpa V2 Dispatcher 稼働開始] ===")
    
    # 環境変数の取得
    QUEUE_URL = os.environ.get('SQS_QUEUE_URL', '')
    SECRET_LOCK = os.environ.get('API_SECRET_KEY', '')

    body_str = event.get('body') or ''
    is_twilio_dtmf = isinstance(body_str, str) and 'Digits=' in body_str

    # =================================================================
    # [ Slackインタラクティブボタンクリック条件付きフリーパス処理 ]
    # =================================================================
    if isinstance(body_str, str) and "payload=" in body_str:
        print("★ [SlackボタンクリックPOST検知] トークン検証をスキップし、SQSへ直接送信します。")
        parsed_body = urllib.parse.parse_qs(body_str)
        payload_json = json.loads(parsed_body['payload'][0])
        
        try:
            # 後続のWorkerが処理できるよう、SQSへペイロードの原本を送信
            sqs.send_message(
                QueueUrl=QUEUE_URL,
                MessageBody=json.dumps({"payload": json.dumps(payload_json)})
            )
            print("★ Slackボタンデータ SQS転送成功!")
        except Exception as e:
            print(f"🚨 SQS転送失敗: {e}")
            
        # Slackサーバー専用の応答フォーマット返却 (3秒タイムアウト回避)
        return {"statusCode": 200, "headers": {"Content-Type": "text/plain"}, "body": "OK"}

    # =================================================================
    # [ 1. DevSecOps API Gatewayセキュリティトークン検証 ]
    # =================================================================
    raw_headers = event.get('headers') or {}
    headers = {k.lower(): v for k, v in raw_headers.items()}
    
    received_token = headers.get('x-api-key', '')
    
    if not is_twilio_dtmf and received_token != SECRET_LOCK:
        print(f"🚨 [遮断] 不正な外部アクセスの試みを検知しました。(入力トークン: {received_token})")
        return {
            'statusCode': 403,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({"error": "Access Denied: Invalid Header Security Token"})
        }

    # =================================================================
    # [ 2. Twilio電話着信時「キーパッド1番」押下時のARS承認Webhook処理 ]
    # =================================================================
    if is_twilio_dtmf:
        parsed_body = dict(urllib.parse.parse_qsl(body_str))
        digits = parsed_body.get('Digits', '')
        
        if digits == '1':
            print("★ [承認完了] オペレーターが1番を押下しました。自動復旧を稼働します。")
            twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response><Say language="ja-JP" voice="alice">確認いたしました。自動停止プロセスを実行します。</Say></Response>"""
        else:
            print("★ [静観/無視] オペレーターが対応をキャンセルしました。")
            twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response><Say language="ja-JP" voice="alice">処理をキャンセルしました。</Say></Response>"""
            
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/xml'},
            'body': twiml_response
        }

    # =================================================================
    # [ 3. スマートフォンリモコン等からのトリガー -> SQS送信後即時終了 ]
    # =================================================================
    params = event.get('queryStringParameters') or {}
    alarm_id = params.get('alarm_id', 'DB_UNKNOWN')
    alarm_type = params.get('alarm_type', 'WARNING')
    
    payload = {
        "alarm_id": alarm_id,
        "alarm_type": alarm_type,
        "source": "Sherpa_V2_Secure_Header"
    }
    
    try:
        response = sqs.send_message(
            QueueUrl=QUEUE_URL,
            MessageBody=json.dumps(payload)
        )
        print(f"★ SQSキューへの格納成功! MessageId: {response.get('MessageId')}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                "status": "Queued",
                "message": "バックグラウンドジョブキューへの登録に成功しました。",
                "architecture": "AWS_Event_Driven_V2"
            })
        }
    except Exception as e:
        print(f"🚨 SQS送信エラー: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({"error": f"SQS Dispatch Failed: {str(e)}"})
        }