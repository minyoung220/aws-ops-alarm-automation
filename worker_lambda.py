# [WHY] SQSからトリガーされる非同期ワーカー用Lambdaです。
# S3からマニュアルを取得し、Bedrock(Claude 3 Haiku)で分析後、Slack(テキスト)とTwilio(音声)へマルチチャネル通知を行います。
# 障害レベル(CRITICAL/WARNING/SEIKAN)に応じたルーティングでAIコストを制御します。

import json
import boto3
import urllib.request
import urllib.parse
import base64
import os

s3 = boto3.client('s3', region_name='ap-northeast-1')
bedrock = boto3.client('bedrock-runtime', region_name='ap-northeast-1')

def lambda_handler(event, context):
    print("=== [Sherpa V2 Worker: 日本語マルチエージェント稼働開始] ===")

    # 環境変数の取得 (ハードコーディング排除)
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
    TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
    TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
    TWILIO_FROM_NUMBER = os.environ.get('TWILIO_FROM_NUMBER', '')
    OPERATOR_PHONE_NUMBER = os.environ.get('OPERATOR_PHONE_NUMBER', '')
    DISPATCHER_API_URL = os.environ.get('DISPATCHER_API_URL', '')
    S3_BUCKET_NAME = os.environ.get('S3_BUCKET_NAME', '')

    for record in event['Records']:
        body = json.loads(record['body'])
        
        # =================================================================
        # [ パターン分岐A ] Slackインタラクティブボタンクリック処理 (Dry-Run Stub)
        # =================================================================
        if "payload" in body:
            print("★ [Slackインタラクティブ信号検知] 復旧自動化インターフェースを稼働します。")
            slack_payload = json.loads(body["payload"])
            response_url = slack_payload.get("response_url")
            click_user = slack_payload.get("user", {}).get("name", "Operator")
            
            action_value = json.loads(slack_payload["actions"][0]["value"])
            target_id = action_value.get("alarm_id", "UNKNOWN")
            
            print(f"▶ [DRY-RUN START] Target: {target_id} / Executor: {click_user}")
            print(f"▶ [DRY-RUN PROGRESS] Running script: /opt/automation/force_release_{target_id}.sh")
            print("▶ [DRY-RUN END] Automation script exit code: 0 (SUCCESS)")
            
            mutated_text = f"✅ *【自動対応完了】 障害ID: {target_id}* \n\nSCSKインフラ監視センターの報告書が更新されました。\n*対応オペレーター:* {click_user} 様\n*結果:* 仮想復旧インターフェース(Dry-Run Stub)が正常に作動し、セッションが安全に解放されました。"
            
            try:
                req_mutation = urllib.request.Request(
                    response_url,
                    data=json.dumps({"replace_original": True, "text": mutated_text}).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                urllib.request.urlopen(req_mutation)
                print("★ Slackメッセージを完了状態へ置換成功!")
            except Exception as e:
                print(f"🚨 Slackメッセージ置換失敗: {e}")
            continue

        # =================================================================
        # [ パターン分岐B ] 初回障害受付処理 (S3 + Bedrock AI分析)
        # =================================================================
        alarm_id = body.get('alarm_id', 'UNKNOWN')
        alarm_type = body.get('alarm_type', 'WARNING')
        
        # コスト最適化: SEIKAN(静観)レベルはAI呼び出しをスキップ
        if alarm_type == "SEIKAN":
            print(f"ℹ️ [静観スキップ] 障害等級がSEIKANのため、処理を終了します。 ID: {alarm_id}")
            continue
            
        target_manual = {}
        try:
            resp = s3.get_object(Bucket=S3_BUCKET_NAME, Key="manual.json")
            manual_db = json.loads(resp['Body'].read().decode('utf-8'))
            target_manual = manual_db.get(alarm_id, {})
        except Exception as e:
            print(f"🚨 S3マニュアルロード失敗: {e}")

        job_name = target_manual.get('job_name', '未登録ホスト')
        error_msg = target_manual.get('error_msg', 'エラーログなし')
        solution = target_manual.get('past_solution', '担当者手動確認必要')
        jira_link = target_manual.get('jira_ticket', 'N/A')
        ai_persona = target_manual.get('ai_persona', "あなたは優秀なインフラエンジニアです。冷静かつ客観的に分析してください。")

        has_past_history = "あり (過去に同一の対応実績が100%存在します)" if solution != "担当者手動確認必要" else "なし (新規障害タイプ)"

        ai_analysis_text = "AI推論エラー: 担当者の手動確認が必要です。"
        try:
            prompt_payload = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 400,
                "system": f"{ai_persona} 管理者が確認してすぐに理解できるよう、必ず以下の3つの見出しに分けて、日本語のビジネス敬体（丁寧語）で明確に作成してください。\n1. 【発生原因の分析】\n2. 【二次波及の可能性】\n3. 【オペレーターが直ちに遂行すべき作業】",
                "messages": [{"role": "user", "content": f"障害内容: {error_msg}\n対応マニュアル: {solution}"}]
            })
            res = bedrock.invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0", contentType="application/json", accept="application/json", body=prompt_payload)
            res_json = json.loads(res.get('body').read())
            ai_analysis_text = res_json['content'][0]['text'].strip()
        except Exception as e:
            print(f"🚨 Bedrock API呼び出し失敗: {e}")

        perfect_slack_report = f"""🚨 【緊急障害通知】 障害ID: {alarm_id} / 等級: {alarm_type} 🚨

お疲れ様です。SCSKクラウドインフラ監視センターより緊急のご連絡です。

■ 障害概要
・障害ID : {alarm_id}
・障害等級 : {alarm_type}
・対象JOB/サーバー : {job_name}
・過去対応実績 : {has_past_history}

■ 障害内容
{error_msg}

■ 対応手順（マニュアル準拠）
{solution}

💡 【AIエージェント精密分析レポート】
{ai_analysis_text}

■ JIRAチケット
{jira_link}"""

        slack_block_payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": perfect_slack_report}
                },
                {
                    "type": "actions",
                    "block_id": f"action_block_{alarm_id}",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "🚀 自動復旧スクリプト稼働 (ACK)"},
                            "style": "primary",
                            "value": json.dumps({"alarm_id": alarm_id, "action": "ACK"}),
                            "action_id": "action_ack"
                        }
                    ]
                }
            ]
        }

        try:
            req_s = urllib.request.Request(SLACK_WEBHOOK_URL, data=json.dumps(slack_block_payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req_s)
            print("★ Slackへのレポート送信成功!")
        except Exception as e:
            print(f"🚨 Slack送信失敗: {e}")

        # =================================================================
        # [ パターン分岐C ] CRITICALレベル時のみTwilio音声電話発信
        # =================================================================
        if alarm_type == "CRITICAL":
            ultra_short_err = error_msg[:35].replace('\n', ' ')
            short_history = "過去の実績あり" if "あり" in has_past_history else "実績なし"
            short_tts = f"SCSK監視センターです。緊急度、{alarm_type}。ホスト、{job_name}。エラーは、{ultra_short_err}。{short_history}。原因とAIアクションプランはSlackを確認ください。承認は1、静観は2を押してください。"

            twiml = f"""<Response>
    <Gather numDigits="1" action="{DISPATCHER_API_URL}" method="POST" timeout="7">
        <Say language="ja-JP" voice="alice">{short_tts}</Say>
    </Gather>
    <Say language="ja-JP" voice="alice">確認不能。切断します。</Say>
</Response>"""

            payload_t = urllib.parse.urlencode({
                "To": OPERATOR_PHONE_NUMBER, 
                "From": TWILIO_FROM_NUMBER, 
                "Twiml": twiml
            })
            
            auth_t = base64.b64encode(f"{TWILIO_ACCOUNT_SID}:{TWILIO_AUTH_TOKEN}".encode('utf-8')).decode('utf-8')
            
            try:
                req_t = urllib.request.Request(
                    f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Calls.json",
                    data=payload_t.encode('utf-8'),
                    headers={"Authorization": f"Basic {auth_t}"},
                    method="POST"
                )
                urllib.request.urlopen(req_t)
                print("📞 [Twilio] 自動音声電話の発信リクエスト成功!")
            except Exception as e:
                print(f"🚨 Twilio発信失敗: {e}")

    return {"statusCode": 200, "body": "Success"}