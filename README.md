# Sherpa-V2 (AWS サーバーレス無人障害検知・対応自動化システム)

AWS Lambda + SQS + Bedrock + Slack + Twilioで構築したイベント駆動型のインシデント対応パイプラインです。
障害発生 -> AI分析 -> Slack通知 -> Twilio音声通報までを「3〜5秒以内」に完了します。

---

## アーキテクチャ
<img width="978" height="564" alt="architecture" src="https://github.com/user-attachments/assets/1ac00b8a-85ad-46c9-a147-323ab9508a3b" />


---

## プロジェクト状況および中核成果
- 開発期間: 2026.06.28 ~ 2026.07.01
- ステータス: AWS本番環境へ100%デプロイ完了 (PoC)
- 参加度: 100% 個人プロジェクト
- テスト: 仮想アラートの発報から、Slackへの通知およびTwilio音声通話の着信までのE2E動作検証を完了
  

### 主要パフォーマンス指標 (Metrics)
- Dispatcher 応答速度: 20〜50ms (即時200 OK返却によるAPI Gatewayタイムアウト防止)
- Worker 処理時間: 3〜5秒 (AI分析 + Slack/Twilio送信)
- コスト最適化: 障害1件あたり1セント未満 (月300件発生時、月額維持費1〜2ドル水準)

---

## 技術スタック (Tech Stack)
- AWS Lambda: Dispatcher (128MB/3s), Worker (256MB/30s)
- Amazon SQS: Visibility Timeout 30〜60s, Max Receive Count 3 (DLQ連携)
- Amazon Bedrock: Claude 3 Haiku (速度およびコスト最適化)
- Amazon API Gateway: REST API (x-api-key)
- Slack & Twilio API
- IaC: Terraform

---

## トラブルシューティング (問題解決)
1. API Gatewayのタイムアウト問題: SQSを導入し「非同期」処理とすることで100%解決。
2. メッセージの消失防止: DLQ (Dead Letter Queue)の連携により、データ損失率0%を達成。
3. コスト爆発の防止: CRITICAL / WARNING / SEIKAN の3段階ルーティングにより、不要なAI API呼び出しを根本から遮断。
